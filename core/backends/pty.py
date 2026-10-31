"""POSIX pseudo-terminal backend: a real controlling TTY with bounded shutdown.

Interactive tools (msfconsole, the Metasploit/Impacket consoles, bettercap and
the wireless suite) refuse a pipe. They need ``isatty()``, a line discipline that
turns a typed Ctrl-C into SIGINT for the foreground group, a negotiable window
size and raw/cbreak input. This backend gives the child its own pseudo-terminal
while still handing the merged byte stream to ``on_output`` and accepting
keystrokes through ``send_input``/``write_bytes``, so the neutral ``Runner`` owns
the interactive lifecycle exactly as it owns captures.

Process-group ownership, the signal escalation and the drain/reap discipline are
the ``PosixBackend``'s, reused verbatim; only the pipe launch is replaced by a
master/slave pair, the child acquires the slave as its controlling terminal, and
EOF on the master surfaces as ``OSError(EIO)`` rather than an empty read.

``winsize`` and ``resize`` are PTY-specific extensions, outside the
``ProcessBackend`` Protocol, which has no window-size surface; the interactive
consumer tracks SIGWINCH through ``resize``.
"""
from __future__ import annotations

import codecs
import errno
import fcntl
import logging
import os
import pty
import select
import signal
import struct
import subprocess
import termios
import threading
import time

from core.runner import CompletionCallback, OutputCallback, RunRequest, RunResult

LOG = logging.getLogger(__name__)
_POLL = 0.02
_INPUT_LIMIT = 1024 * 1024
_DEFAULT_WINSIZE = (24, 80)


def _acquire_controlling_tty() -> None:
    # Runs in the child after fork, before exec: fd 0 is already the pty slave
    # and start_new_session has run setsid, so the session leader has no
    # controlling terminal yet. Claim the slave as it, so the line discipline
    # delivers SIGINT/SIGTSTP from a typed Ctrl-C/Ctrl-Z to this foreground
    # group. Only async-signal-safe syscalls are allowed here.
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


class PtyBackend:
    def __init__(self, winsize: tuple[int, int] | None = None) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._interrupt = threading.Event()
        self._result: RunResult | None = None
        self._input = bytearray()
        self._input_closed = False
        # close_input must push the line-discipline EOF char once; inherit_stdin
        # only disables queuing and must never inject a spurious Ctrl-D.
        self._eof_requested = False
        self._eof_sent = False
        rows, cols = winsize or _DEFAULT_WINSIZE
        self._winsize = (rows or _DEFAULT_WINSIZE[0], cols or _DEFAULT_WINSIZE[1])
        self._master = -1

    def start(self, request: RunRequest, on_output: OutputCallback | None = None,
              on_complete: CompletionCallback | None = None) -> None:
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("a backend can only be started once")
            self._input_closed = self._input_closed or request.inherit_stdin
            self._thread = threading.Thread(
                target=self._run, args=(request, on_output, on_complete),
                name="chaostic-runner", daemon=False,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            if self._thread is not None and self._result is None:
                self._stop.set()

    def interrupt(self) -> None:
        with self._lock:
            if self._thread is not None and self._result is None:
                self._interrupt.set()

    def send_input(self, text: str) -> bool:
        return self._enqueue(text.encode("utf-8"))

    def write_bytes(self, data: bytes) -> bool:
        """Queue raw terminal bytes for the master, losslessly.

        The Protocol only offers UTF-8 ``send_input``; a terminal bridge forwards
        arbitrary input bytes (arrow keys, non-UTF-8 locales), so this extension
        takes bytes directly through the same bounded, locked buffer."""
        return self._enqueue(bytes(data))

    def _enqueue(self, data: bytes) -> bool:
        with self._lock:
            if (self._thread is None or self._result is not None
                    or self._input_closed or self._stop.is_set()):
                return False
            if len(self._input) + len(data) > _INPUT_LIMIT:
                raise BufferError("pending process input exceeds 1 MiB")
            self._input.extend(data)
            return True

    def close_input(self) -> None:
        with self._lock:
            self._input_closed = True
            self._eof_requested = True

    def resize(self, rows: int, cols: int) -> None:
        """Apply a new window size to the master; the kernel signals SIGWINCH."""
        if not rows or not cols:
            return
        with self._lock:
            self._winsize = (rows, cols)
            if self._master >= 0:
                try:
                    fcntl.ioctl(self._master, termios.TIOCSWINSZ,
                                struct.pack("HHHH", rows, cols, 0, 0))
                except OSError:
                    pass

    def wait(self, timeout: float | None = None) -> RunResult | None:
        with self._lock:
            worker = self._thread
        if worker is None:
            raise RuntimeError("the backend has not been started")
        if worker is threading.current_thread():
            raise RuntimeError("cannot wait from a runner callback")
        worker.join(timeout)
        return None if worker.is_alive() else self._result

    @staticmethod
    def _signal_group(proc: subprocess.Popen[bytes], sig: int) -> None:
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass

    @staticmethod
    def _group_exists(proc: subprocess.Popen[bytes]) -> bool:
        try:
            os.killpg(proc.pid, 0)
        except ProcessLookupError:
            return False
        return True

    @staticmethod
    def _eof_byte(master: int) -> bytes:
        try:
            control = termios.tcgetattr(master)[6][termios.VEOF]
        except (OSError, IndexError, ValueError):
            return b"\x04"
        if isinstance(control, bytes) and control:
            return control
        if isinstance(control, int):
            return bytes([control])
        return b"\x04"

    def _write_input(self, master: int) -> None:
        with self._lock:
            if self._input:
                try:
                    written = os.write(master, self._input[:65536])
                    del self._input[:written]
                except BlockingIOError:
                    pass
                except OSError:
                    self._input.clear()
                    self._input_closed = True
            if (self._eof_requested and not self._input and not self._eof_sent):
                self._eof_sent = True
                try:
                    os.write(master, self._eof_byte(master))
                except OSError:
                    pass

    def _run(self, request: RunRequest, on_output: OutputCallback | None,
             on_complete: CompletionCallback | None) -> None:
        proc = None
        master = -1
        error = None
        timed_out = False
        returncode = 1
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        started = time.monotonic()
        try:
            master, slave = pty.openpty()
            rows, cols = self._winsize
            try:
                fcntl.ioctl(slave, termios.TIOCSWINSZ,
                            struct.pack("HHHH", rows, cols, 0, 0))
            except OSError:
                pass
            with self._lock:
                self._master = master
            try:
                proc = subprocess.Popen(
                    request.argv, cwd=request.cwd, env=request.env, shell=False,
                    stdin=slave, stdout=slave, stderr=slave,
                    start_new_session=True, preexec_fn=_acquire_controlling_tty,
                    close_fds=True,
                )
            finally:
                os.close(slave)
            os.set_blocking(master, False)
            stopping = None
            phase = 0
            eof = False
            while True:
                now = time.monotonic()
                code = proc.poll()
                exited = code is not None
                if code is not None:
                    returncode = code
                if (stopping is None and request.timeout is not None
                        and now - started >= request.timeout and not exited):
                    timed_out = True
                if stopping is None and (self._stop.is_set() or timed_out or exited):
                    stopping = now
                    self._signal_group(proc, signal.SIGINT)
                if self._interrupt.is_set():
                    self._interrupt.clear()
                    self._signal_group(proc, signal.SIGINT)
                if stopping is not None:
                    elapsed = now - stopping
                    if phase == 0 and elapsed >= request.stop_grace:
                        self._signal_group(proc, signal.SIGTERM)
                        phase = 1
                    if phase == 1 and elapsed >= 2 * request.stop_grace:
                        self._signal_group(proc, signal.SIGKILL)
                        phase = 2
                    if exited and eof and not self._group_exists(proc):
                        break
                    # Includes a descendant still holding the slave open.
                    if elapsed >= 3 * request.stop_grace:
                        break
                if not eof:
                    self._write_input(master)
                ready, _, _ = select.select([] if eof else [master], [], [], _POLL)
                if ready:
                    try:
                        data = os.read(master, 65536)
                    except BlockingIOError:
                        continue
                    except OSError as exc:
                        # The slave is fully closed: a PTY reports EOF this way.
                        if exc.errno != errno.EIO:
                            raise
                        data = b""
                    eof = not data
                    output = data if request.raw_output else decoder.decode(data, final=eof)
                    if output and on_output:
                        on_output(output)
            if not eof and not request.raw_output:
                tail = decoder.decode(b"", final=True)
                if tail and on_output:
                    on_output(tail)
        except FileNotFoundError as exc:
            returncode, error = 127, str(exc)
        except Exception as exc:
            # Callback failures also require group cleanup and a final result.
            error = f"{type(exc).__name__}: {exc}"
            LOG.exception("Process execution failed")
        finally:
            if proc is not None:
                try:
                    if proc.poll() is None:
                        # SIGKILL cannot be caught or ignored, so once signalled
                        # the group leader is guaranteed to terminate. Block until
                        # it is reaped to read its real status instead of leaving
                        # the fabricated default: a bounded wait could expire on a
                        # starved runner and report that default (e.g. 1) as if the
                        # child had exited cleanly. Only the leader is awaited, so a
                        # descendant that escaped the group (and may still hold the
                        # slave open) cannot delay this. The master stays open until
                        # the leader is reaped; closing it first would only hang up
                        # the slave, which changes nothing for a SIGKILLed child.
                        self._signal_group(proc, signal.SIGKILL)
                        returncode = proc.wait()
                    else:
                        returncode = proc.returncode
                except OSError as exc:
                    error = error or f"Process cleanup failed: {exc}"
            with self._lock:
                if master >= 0:
                    try:
                        os.close(master)
                    except OSError:
                        pass
                self._master = -1
                self._input.clear()
                self._result = RunResult(returncode, self._stop.is_set(), timed_out, error)
            if on_complete:
                try:
                    on_complete(self._result)
                except Exception:
                    LOG.exception("Process completion callback failed")
