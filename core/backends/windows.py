"""Windows Job Object supervision without Qt or third-party dependencies.

Windows 10+ is required. Console interruption is best effort (CTRL_BREAK for a
shared console); stop/timeout always terminate the entire job after the grace
period, including descendants whose leader has already exited. This is process
ownership, not an isolation boundary for untrusted programs or remote WSL jobs.
"""
from __future__ import annotations

import codecs
import logging
import threading
import time

from core.backends.windows_api import WindowsProcess
from core.runner import CompletionCallback, OutputCallback, RunRequest, RunResult

LOG = logging.getLogger(__name__)
_POLL = 0.02
_INPUT_LIMIT = 1024 * 1024


class WindowsBackend:
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

    def _write_input(self, proc: WindowsProcess) -> None:
        with self._lock:
            if self._input:
                try:
                    written = proc.write(bytes(self._input[:65536]))
                    del self._input[:written]
                except BrokenPipeError:
                    self._input.clear()
                    self._input_closed = True
            if self._input_closed and not self._input:
                proc.close_input()

    def _run(self, request: RunRequest, on_output: OutputCallback | None,
             on_complete: CompletionCallback | None) -> None:
        proc = None
        error = None
        timed_out = False
        returncode = 1
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        started = time.monotonic()
        try:
            proc = WindowsProcess(request)
            stopping = None
            terminated = False
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
                    if not exited:
                        proc.interrupt()
                if self._interrupt.is_set():
                    self._interrupt.clear()
                    if not exited and not proc.interrupt():
                        LOG.warning("Windows process has no shared console for interruption")
                if stopping is not None:
                    elapsed = now - stopping
                    if not terminated and (exited or elapsed >= request.stop_grace):
                        proc.terminate()
                        terminated = True
                        proc.close_input()
                    if exited and eof:
                        break
                    if elapsed >= 3 * request.stop_grace:
                        break
                if stopping is None:
                    self._write_input(proc)
                data = None if eof else proc.read()
                if data is not None:
                    eof = not data
                    output = data if request.raw_output else decoder.decode(data, final=eof)
                    if output and on_output:
                        on_output(output)
                else:
                    time.sleep(_POLL)
            if not eof and not request.raw_output:
                tail = decoder.decode(b"", final=True)
                if tail and on_output:
                    on_output(tail)
        except FileNotFoundError as exc:
            returncode, error = 127, str(exc)
        except Exception as exc:
            # A failing consumer must still release the job and complete once.
            error = f"{type(exc).__name__}: {exc}"
            LOG.exception("Process execution failed")
        finally:
            if proc is not None:
                try:
                    proc.terminate()
                    deadline = time.monotonic() + request.stop_grace
                    while time.monotonic() < deadline:
                        code = proc.poll()
                        if code is not None and proc.tree_exited():
                            break
                        time.sleep(_POLL)
                    code = proc.poll()
                    if code is not None and proc.tree_exited():
                        returncode = code
                    else:
                        error = error or "Process tree did not exit after job termination"
                except OSError as exc:
                    error = error or f"Process cleanup failed: {exc}"
                finally:
                    proc.close()
            with self._lock:
                self._input.clear()
                self._result = RunResult(returncode, self._stop.is_set(), timed_out, error)
            if on_complete:
                try:
                    on_complete(self._result)
                except Exception:
                    LOG.exception("Process completion callback failed")
