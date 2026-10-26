"""UI-independent, single-use process runner.

Output callbacks receive merged stdout/stderr text (including partial lines), or
unchanged bytes when raw_output is requested. They run on the backend worker
thread and must return promptly. No output is retained by the runner; callers
own logging, redaction and presentation.
"""
from __future__ import annotations

import math
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol


@dataclass(frozen=True)
class RunRequest:
    argv: Sequence[str]
    cwd: str | os.PathLike[str] | None = None
    # None inherits the environment; a mapping replaces it, as with Popen.
    env: Mapping[str, str] | None = None
    timeout: float | None = None
    stop_grace: float = 0.5
    # CLI capture keeps the invoking terminal or redirected stdin unchanged.
    # send_input is unavailable; close_input leaves the inherited descriptor alone.
    inherit_stdin: bool = False
    # Binary journals must not lose invalid UTF-8 through text decoding.
    raw_output: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.argv, (str, bytes)) or not self.argv:
            raise ValueError("argv must be a non-empty sequence of arguments")
        if any(not isinstance(arg, str) or "\0" in arg for arg in self.argv):
            raise ValueError("arguments must be strings without NUL bytes")
        if not self.argv[0]:
            raise ValueError("the executable must not be empty")
        if self.stop_grace is None:
            raise ValueError("stop_grace must be finite and positive")
        for name, value in (("timeout", self.timeout), ("stop_grace", self.stop_grace)):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive")
        object.__setattr__(self, "argv", tuple(self.argv))
        if self.env is not None:
            object.__setattr__(self, "env", MappingProxyType(dict(self.env)))


@dataclass(frozen=True)
class RunResult:
    # Raw subprocess status, including negative POSIX signal numbers.
    returncode: int
    cancelled: bool = False
    timed_out: bool = False
    error: str | None = None


OutputCallback = Callable[[str | bytes], None]
CompletionCallback = Callable[[RunResult], None]


class ProcessBackend(Protocol):
    def start(self, request: RunRequest, on_output: OutputCallback | None = None,
              on_complete: CompletionCallback | None = None) -> None: ...
    def send_input(self, text: str) -> bool: ...
    def close_input(self) -> None: ...
    def interrupt(self) -> None: ...
    def stop(self) -> None: ...
    def wait(self, timeout: float | None = None) -> RunResult | None: ...


class Runner:
    """One run, optionally using an injected platform backend.

    ``stop`` is an asynchronous, idempotent cancellation request. ``wait`` returns
    None on expiry, otherwise the result after all callbacks and worker cleanup.
    Waiting from a callback is unsupported. ``interrupt`` sends SIGINT on POSIX
    or best-effort CTRL_BREAK on Windows (requires a shared console), without
    classifying the run as cancelled. Input is UTF-8, queued with a bounded buffer.
    """

    def __init__(self, backend: ProcessBackend | None = None) -> None:
        if backend is None:
            if os.name == "nt":
                from core.backends.windows import WindowsBackend
                backend = WindowsBackend()
            elif os.name == "posix":
                from core.backends.posix import PosixBackend
                backend = PosixBackend()
            else:
                raise NotImplementedError("a process backend is required on this platform")
        self._backend = backend

    def start(self, request: RunRequest, on_output: OutputCallback | None = None,
              on_complete: CompletionCallback | None = None) -> None:
        self._backend.start(request, on_output, on_complete)

    def send_input(self, text: str) -> bool:
        return self._backend.send_input(text)

    def close_input(self) -> None:
        self._backend.close_input()

    def interrupt(self) -> None:
        self._backend.interrupt()

    def stop(self) -> None:
        self._backend.stop()

    def wait(self, timeout: float | None = None) -> RunResult | None:
        return self._backend.wait(timeout)
