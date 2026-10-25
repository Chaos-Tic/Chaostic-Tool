"""Small Win32 ownership layer for the Windows runner (Windows 10 or newer).

The job is assigned by CreateProcess itself, before any child code can execute.
No fallback to an unowned process is allowed. All handles are private except the
explicit stdin/stdout handle list inherited by the child. Import is safe on POSIX;
the Windows DLL is loaded only when a process is requested.
"""
from __future__ import annotations

import ctypes as c
import os
import subprocess
import uuid
from ctypes import wintypes as w

from core.runner import RunRequest

_INVALID_HANDLE = c.c_void_p(-1).value
_BROKEN_PIPE = {109, 232, 233}


class _BasicLimits(c.Structure):
    _fields_ = [("ProcessTime", c.c_int64), ("JobTime", c.c_int64),
                ("Flags", w.DWORD), ("MinWorkingSet", c.c_size_t),
                ("MaxWorkingSet", c.c_size_t), ("ActiveProcesses", w.DWORD),
                ("Affinity", c.c_size_t), ("Priority", w.DWORD), ("Scheduling", w.DWORD)]


class _ExtendedLimits(c.Structure):
    _fields_ = [("Basic", _BasicLimits), ("IoCounters", c.c_uint64 * 6),
                ("ProcessMemory", c.c_size_t), ("JobMemory", c.c_size_t),
                ("PeakProcessMemory", c.c_size_t), ("PeakJobMemory", c.c_size_t)]


class _Accounting(c.Structure):
    _fields_ = [("TotalUserTime", c.c_int64), ("TotalKernelTime", c.c_int64),
                ("PeriodUserTime", c.c_int64), ("PeriodKernelTime", c.c_int64),
                ("PageFaults", w.DWORD), ("TotalProcesses", w.DWORD),
                ("ActiveProcesses", w.DWORD), ("TerminatedProcesses", w.DWORD)]


class _StartupInfo(c.Structure):
    _fields_ = [("cb", w.DWORD), ("reserved", w.LPWSTR), ("desktop", w.LPWSTR),
                ("title", w.LPWSTR), ("x", w.DWORD), ("y", w.DWORD),
                ("xsize", w.DWORD), ("ysize", w.DWORD), ("xchars", w.DWORD),
                ("ychars", w.DWORD), ("fill", w.DWORD), ("flags", w.DWORD),
                ("show", w.WORD), ("reserved_size", w.WORD), ("reserved_data", c.c_void_p),
                ("stdin", w.HANDLE), ("stdout", w.HANDLE), ("stderr", w.HANDLE)]


class _StartupInfoEx(c.Structure):
    _fields_ = [("info", _StartupInfo), ("attributes", c.c_void_p)]


class _ProcessInfo(c.Structure):
    _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE),
                ("pid", w.DWORD), ("tid", w.DWORD)]


class _Overlapped(c.Structure):
    _fields_ = [("internal", c.c_size_t), ("internal_high", c.c_size_t),
                ("offset", w.DWORD), ("offset_high", w.DWORD), ("event", w.HANDLE)]


def _kernel():
    if os.name != "nt":
        raise OSError("Windows process supervision requires Windows 10 or newer")
    kernel = c.WinDLL("kernel32", use_last_error=True)
    # Explicit pointer-width signatures are essential on 64-bit Windows.
    signatures = {
        "CreateJobObjectW": (w.HANDLE, [c.c_void_p, w.LPCWSTR]),
        "SetInformationJobObject": (w.BOOL, [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]),
        "TerminateJobObject": (w.BOOL, [w.HANDLE, w.UINT]),
        "QueryInformationJobObject": (w.BOOL, [w.HANDLE, c.c_int, c.c_void_p,
                                               w.DWORD, c.c_void_p]),
        "CloseHandle": (w.BOOL, [w.HANDLE]),
        "CreatePipe": (w.BOOL, [c.POINTER(w.HANDLE), c.POINTER(w.HANDLE), c.c_void_p, w.DWORD]),
        "SetHandleInformation": (w.BOOL, [w.HANDLE, w.DWORD, w.DWORD]),
        "GetStdHandle": (w.HANDLE, [w.DWORD]),
        "GetCurrentProcess": (w.HANDLE, []),
        "DuplicateHandle": (w.BOOL, [w.HANDLE, w.HANDLE, w.HANDLE, c.POINTER(w.HANDLE),
                                    w.DWORD, w.BOOL, w.DWORD]),
        "CreateNamedPipeW": (w.HANDLE, [w.LPCWSTR, w.DWORD, w.DWORD, w.DWORD,
                                        w.DWORD, w.DWORD, w.DWORD, c.c_void_p]),
        "CreateFileW": (w.HANDLE, [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p,
                                   w.DWORD, w.DWORD, w.HANDLE]),
        "CreateEventW": (w.HANDLE, [c.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR]),
        "InitializeProcThreadAttributeList": (w.BOOL, [c.c_void_p, w.DWORD, w.DWORD,
                                                       c.POINTER(c.c_size_t)]),
        "UpdateProcThreadAttribute": (w.BOOL, [c.c_void_p, w.DWORD, c.c_size_t,
                                               c.c_void_p, c.c_size_t, c.c_void_p, c.c_void_p]),
        "DeleteProcThreadAttributeList": (None, [c.c_void_p]),
        "CreateProcessW": (w.BOOL, [w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p,
                                    w.BOOL, w.DWORD, c.c_void_p, w.LPCWSTR,
                                    c.c_void_p, c.POINTER(_ProcessInfo)]),
        "PeekNamedPipe": (w.BOOL, [w.HANDLE, c.c_void_p, w.DWORD, c.c_void_p,
                                   c.POINTER(w.DWORD), c.c_void_p]),
        "ReadFile": (w.BOOL, [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]),
        "WriteFile": (w.BOOL, [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD),
                               c.POINTER(_Overlapped)]),
        "GetOverlappedResult": (w.BOOL, [w.HANDLE, c.POINTER(_Overlapped),
                                         c.POINTER(w.DWORD), w.BOOL]),
        "CancelIoEx": (w.BOOL, [w.HANDLE, c.POINTER(_Overlapped)]),
        "WaitForSingleObject": (w.DWORD, [w.HANDLE, w.DWORD]),
        "GetExitCodeProcess": (w.BOOL, [w.HANDLE, c.POINTER(w.DWORD)]),
        "GenerateConsoleCtrlEvent": (w.BOOL, [w.DWORD, w.DWORD]),
    }
    for name, (restype, argtypes) in signatures.items():
        function = getattr(kernel, name)
        function.restype, function.argtypes = restype, argtypes
    return kernel


def _check(value):
    if not value:
        raise c.WinError(c.get_last_error())
    return value


def _environment(request: RunRequest):
    if request.env is None:
        return None
    entries = []
    for key, value in sorted(request.env.items(), key=lambda item: item[0].upper()):
        if not key or "=" in key or "\0" in key or "\0" in value:
            raise ValueError("invalid environment variable")
        entries.append(f"{key}={value}")
    return c.create_unicode_buffer("\0".join(entries) + "\0\0")


class WindowsProcess:
    """Own one process, its job, and nonblocking parent-side pipes.

    Only the backend worker calls this class. The overlapped write buffer stays
    alive until Windows acknowledges completion or cancellation.
    """

    def __init__(self, request: RunRequest) -> None:
        self.kernel = _kernel()
        self.job = self.process = self.output = self.input = self.event = None
        self._pending: c.Array[c.c_char] | None = None
        self._overlapped: _Overlapped | None = None
        self.pid = 0
        self._returncode: int | None = None
        child_input = child_output = None
        try:
            self.job = _check(self.kernel.CreateJobObjectW(None, None))
            limits = _ExtendedLimits()
            limits.Basic.Flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, no breakaway
            _check(self.kernel.SetInformationJobObject(self.job, 9, c.byref(limits), c.sizeof(limits)))
            read, write = w.HANDLE(), w.HANDLE()
            _check(self.kernel.CreatePipe(c.byref(read), c.byref(write), None, 65536))
            self.output, child_output = read.value, write.value
            if request.inherit_stdin:
                source = self.kernel.GetStdHandle(-10)  # STD_INPUT_HANDLE
                if source and source != _INVALID_HANDLE:
                    duplicate = w.HANDLE()
                    current = self.kernel.GetCurrentProcess()
                    _check(self.kernel.DuplicateHandle(current, source, current,
                                                       c.byref(duplicate), 0, True, 2))
                    child_input = duplicate.value
                else:
                    child_input = self._open_input("NUL")
            else:
                name = rf"\\.\pipe\chaostic-runner-{uuid.uuid4().hex}"
                # OUTBOUND | OVERLAPPED | FIRST_PIPE_INSTANCE; reject remote clients.
                self.input = self.kernel.CreateNamedPipeW(
                    name, 0x40080002, 0x8, 1, 65536, 65536, 0, None)
                if self.input == _INVALID_HANDLE:
                    self.input = None
                    raise c.WinError(c.get_last_error())
                child_input = self._open_input(name)
                self.event = _check(self.kernel.CreateEventW(None, True, False, None))
            assert child_input is not None and child_output is not None
            self._launch(request, child_input, child_output)
        except BaseException:
            self.close()
            raise
        finally:
            for handle in (child_input, child_output):
                if handle:
                    self.kernel.CloseHandle(handle)

    def _open_input(self, path: str) -> int:
        handle = self.kernel.CreateFileW(path, 0x80000000, 0, None, 3, 0, None)
        if handle == _INVALID_HANDLE:
            raise c.WinError(c.get_last_error())
        return handle

    def _launch(self, request: RunRequest, stdin: int, stdout: int) -> None:
        size = c.c_size_t()
        self.kernel.InitializeProcThreadAttributeList(None, 2, 0, c.byref(size))
        attributes = c.create_string_buffer(size.value)
        _check(self.kernel.InitializeProcThreadAttributeList(attributes, 2, 0, c.byref(size)))
        try:
            handles = (w.HANDLE * 2)(stdin, stdout)
            for handle in handles:
                _check(self.kernel.SetHandleInformation(handle, 1, 1))
            jobs = (w.HANDLE * 1)(self.job)
            # HANDLE_LIST and JOB_LIST: association is atomic with process creation.
            for attribute, values in ((0x20002, handles), (0x2000D, jobs)):
                _check(self.kernel.UpdateProcThreadAttribute(
                    attributes, 0, attribute, values, c.sizeof(values), None, None))
            startup = _StartupInfoEx()
            startup.info.cb = c.sizeof(startup)
            startup.info.flags = 0x101  # USESTDHANDLES | USESHOWWINDOW (hidden)
            startup.info.stdin, startup.info.stdout, startup.info.stderr = stdin, stdout, stdout
            startup.attributes = c.cast(attributes, c.c_void_p)
            info = _ProcessInfo()
            command = c.create_unicode_buffer(subprocess.list2cmdline(request.argv))
            environment = _environment(request)
            # NEW_PROCESS_GROUP | UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT
            _check(self.kernel.CreateProcessW(
                None, command, None, None, True, 0x80600, environment,
                os.fspath(request.cwd) if request.cwd is not None else None,
                c.byref(startup), c.byref(info)))
            self.process, self.pid = info.process, info.pid
            self.kernel.CloseHandle(info.thread)
        finally:
            self.kernel.DeleteProcThreadAttributeList(attributes)

    def poll(self) -> int | None:
        if self._returncode is not None:
            return self._returncode
        status = self.kernel.WaitForSingleObject(self.process, 0)
        if status == 258:  # WAIT_TIMEOUT
            return None
        if status != 0:
            raise c.WinError(c.get_last_error())
        code = w.DWORD()
        _check(self.kernel.GetExitCodeProcess(self.process, c.byref(code)))
        self._returncode = code.value
        return self._returncode

    def read(self) -> bytes | None:
        """None means not ready; empty bytes means EOF."""
        available = w.DWORD()
        if not self.kernel.PeekNamedPipe(self.output, None, 0, None, c.byref(available), None):
            if c.get_last_error() in _BROKEN_PIPE:
                return b""
            raise c.WinError(c.get_last_error())
        if not available.value:
            return None
        buffer = c.create_string_buffer(min(available.value, 65536))
        read = w.DWORD()
        _check(self.kernel.ReadFile(self.output, buffer, len(buffer), c.byref(read), None))
        return buffer.raw[:read.value]

    def write(self, data: bytes) -> int:
        """Start/poll one overlapped write; acknowledge bytes only on completion."""
        if self.input is None:
            raise BrokenPipeError("process stdin is closed")
        written = w.DWORD()
        if self._pending is None:
            self._pending = c.create_string_buffer(data)
            self._overlapped = _Overlapped(event=self.event)
            if not self.kernel.WriteFile(self.input, self._pending, len(data),
                                         c.byref(written), c.byref(self._overlapped)):
                error = c.get_last_error()
                if error == 997:  # IO_PENDING
                    return 0
                self._pending = self._overlapped = None
                if error in _BROKEN_PIPE:
                    raise BrokenPipeError("process stdin is closed")
                raise c.WinError(error)
        else:
            assert self._overlapped is not None
            if not self.kernel.GetOverlappedResult(
                    self.input, c.byref(self._overlapped), c.byref(written), False):
                error = c.get_last_error()
                if error == 996:  # IO_INCOMPLETE
                    return 0
                self._pending = self._overlapped = None
                if error in _BROKEN_PIPE:
                    raise BrokenPipeError("process stdin is closed")
                raise c.WinError(error)
        self._pending = self._overlapped = None
        return written.value

    def interrupt(self) -> bool:
        # CTRL_BREAK targets our group only. GUI applications without a shared
        # console cannot receive console events; job termination still works.
        return bool(self.kernel.GenerateConsoleCtrlEvent(1, self.pid))

    def terminate(self) -> None:
        if self.job:
            _check(self.kernel.TerminateJobObject(self.job, 1))

    def tree_exited(self) -> bool:
        info = _Accounting()
        _check(self.kernel.QueryInformationJobObject(self.job, 1, c.byref(info), c.sizeof(info), None))
        return info.ActiveProcesses == 0

    def close_input(self) -> None:
        if self._pending is not None:
            assert self._overlapped is not None
            self.kernel.CancelIoEx(self.input, c.byref(self._overlapped))
            # Kernel pipe cancellation must be acknowledged before freeing its
            # OVERLAPPED/buffer. Unlike a writer thread, it never waits for a reader.
            written = w.DWORD()
            self.kernel.GetOverlappedResult(self.input, c.byref(self._overlapped),
                                            c.byref(written), True)
            self._pending = self._overlapped = None
        if self.input:
            self.kernel.CloseHandle(self.input)
            self.input = None

    def close(self) -> None:
        # Closing the last job handle also covers abrupt interpreter termination.
        if self.job:
            self.kernel.CloseHandle(self.job)
            self.job = None
        self.close_input()
        for name in ("output", "event", "process"):
            handle = getattr(self, name)
            if handle:
                self.kernel.CloseHandle(handle)
                setattr(self, name, None)
