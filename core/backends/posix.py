"""POSIX process-group ownership with nonblocking pipes and bounded shutdown.

Descendants remaining in the launched group are stopped even after the leader
exits. A descendant deliberately escaping with setsid/setpgid is outside this
backend's ownership; this is process supervision, not a security sandbox.
"""
from __future__ import annotations

import codecs
import logging
import os
import select
import signal
import subprocess
import threading
import time

from core.runner import CompletionCallback, OutputCallback, RunRequest, RunResult

LOG = logging.getLogger(__name__)
_POLL = 0.02
_INPUT_LIMIT = 1024 * 1024


class PosixBackend:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._interrupt = threading.Event()
        self._result: RunResult | None = None
        self._input = bytearray()
        self._input_closed = False

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
        data = text.encode("utf-8")
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

    def _write_input(self, proc: subprocess.Popen[bytes]) -> None:
        if proc.stdin is None:
            return
        with self._lock:
            if proc.stdin.closed:
                return
            if self._input:
                try:
                    written = os.write(proc.stdin.fileno(), self._input[:65536])
                    del self._input[:written]
                except BlockingIOError:
                    pass
                except BrokenPipeError:
                    self._input.clear()
                    self._input_closed = True
            if self._input_closed and not self._input:
                proc.stdin.close()

    def _run(self, request: RunRequest, on_output: OutputCallback | None,
             on_complete: CompletionCallback | None) -> None:
        proc = None
        error = None
        timed_out = False
        returncode = 1
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        started = time.monotonic()
        try:
            proc = subprocess.Popen(
                request.argv, cwd=request.cwd, env=request.env, shell=False,
                stdin=None if request.inherit_stdin else subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                start_new_session=True, bufsize=0,
            )
            assert proc.stdout is not None
            os.set_blocking(proc.stdout.fileno(), False)
            if proc.stdin is not None:
                os.set_blocking(proc.stdin.fileno(), False)
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
                    # Includes inherited pipes held by an escaped descendant.
                    if elapsed >= 3 * request.stop_grace:
                        break
                self._write_input(proc)
                ready, _, _ = select.select([] if eof else [proc.stdout], [], [], _POLL)
                if ready:
                    try:
                        data = os.read(proc.stdout.fileno(), 65536)
                    except BlockingIOError:
                        continue
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
                        # stdout pipe) cannot delay this.
                        self._signal_group(proc, signal.SIGKILL)
                        returncode = proc.wait()
                    else:
                        returncode = proc.returncode
                except OSError as exc:
                    error = error or f"Process cleanup failed: {exc}"
                finally:
                    for stream in (proc.stdin, proc.stdout):
                        if stream is not None:
                            stream.close()
            with self._lock:
                self._input.clear()
                self._result = RunResult(returncode, self._stop.is_set(), timed_out, error)
            if on_complete:
                try:
                    on_complete(self._result)
                except Exception:
                    LOG.exception("Process completion callback failed")
