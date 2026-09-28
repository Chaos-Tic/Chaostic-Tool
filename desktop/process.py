"""Asynchronous process execution with bounded UI output and persistent full logs."""
from __future__ import annotations

import codecs
import ctypes
import os
import json
import sys
from pathlib import Path

import psutil
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from desktop.storage import now, write_json
from desktop.profiles import StreamRedactor,redact


class WindowsJob:
    """Kill the entire owned process tree when the job closes (also on app crash)."""
    def __init__(self, pid):
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", w.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]
        class Io(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", Io),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        kernel.CreateJobObjectW.restype = w.HANDLE
        kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        kernel.SetInformationJobObject.restype = w.BOOL
        kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        kernel.OpenProcess.restype = w.HANDLE
        kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        kernel.AssignProcessToJobObject.restype = w.BOOL
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.CloseHandle.restype = w.BOOL
        self.kernel = kernel
        self.handle = kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        process = kernel.OpenProcess(0x0100 | 0x0001, False, pid)
        try:
            if not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not process or not kernel.AssignProcessToJobObject(self.handle, process):
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception:
            self.close()
            raise
        finally:
            if process:
                kernel.CloseHandle(process)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def worker_command(worker, request, log):
    if getattr(sys, "frozen", False):
        return [sys.executable, "--worker", worker, str(request), str(log)]
    return [sys.executable, str(Path(__file__).resolve().parent.parent / "chaostic_desktop.py"),
            "--worker", worker, str(request), str(log)]


class Runner(QObject):
    output = Signal(str)
    completed = Signal(dict)
    activeChanged = Signal(bool)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.proc = None
        self.job = None
        self.record = None
        self.directory = None
        self.cancelled = False
        self.failure = ""
        self.builtin = False
        self.offset = 0
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.poll = QTimer(self)
        self.poll.setInterval(100)
        self.poll.timeout.connect(self._tail)
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self._timeout)

    @property
    def active(self):
        return self.proc is not None

    def start(self, tool, preset, target, command=None, worker=None, timeout_ms=1_200_000, bridge=False, fields=None, redactions=(), elevate=False, metadata=None, environment_extra=None):
        if self.active:
            raise RuntimeError("Une opération est déjà en cours.")
        display=[redact(arg,redactions) for arg in (command or ['builtin',worker])]
        directory, record = self.store.new_run(tool, preset, target, display)
        if metadata:
            record.update({k:metadata[k] for k in ('flow_id','flow_name','flow_step') if k in metadata})
            write_json(directory/'run.json',record)
        self.directory, self.record = directory, record
        self.cancelled, self.failure, self.builtin, self.offset = False, "", worker is not None, 0
        self.decoder.reset()
        self.redactor=StreamRedactor(redactions)
        self.bridge=bridge
        self.initial_input=None
        self.log = directory / "output.txt"
        self.log.touch()
        if worker:
            command = worker_command(worker, directory / "run.json", self.log)
        elif bridge:
            try:
                from desktop.backends import execution_plan
                command,request=execution_plan(command,{'requires_root':elevate},self.store.root,directory,fields)
                request['timeout']=max(1,timeout_ms//1000)
                self.initial_input=(json.dumps(request)+'\n').encode('utf-8')
            except Exception as exc:
                record.update(status='failed',detail=str(exc),finished=now(),exit_code=-1)
                write_json(directory/'run.json',record)
                raise
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.setWorkingDirectory(str(directory))
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUTF8", "1")
        environment.insert("PYTHONUNBUFFERED", "1")
        environment.insert("NO_COLOR", "1")
        for key,value in (environment_extra or {}).items(): environment.insert(key,value)
        self.proc.setProcessEnvironment(environment)
        self.proc.started.connect(self._started)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.errorOccurred.connect(self._error)
        self.proc.finished.connect(self._finished)
        self.activeChanged.emit(True)
        self.poll.start()
        self.deadline.start(timeout_ms)
        self.proc.start(command[0], command[1:])

    def _started(self):
        if os.name == "nt":
            try:
                self.job = WindowsJob(int(self.proc.processId()))
            except OSError as exc:
                self.failure = f"Impossible d’encadrer le processus Windows : {exc}"
                self.stop(cancelled=False)
                return
        if self.initial_input:
            self.proc.write(self.initial_input)
            self.initial_input=None

    def send_input(self,text,secret=False):
        if not self.active: return
        if secret:
            # No user input is recorded separately. Mask it if the tool echoes it.
            self.redactor.secrets.append(text.rstrip('\r\n').encode('utf-8'))
            self.redactor.keep=max(self.redactor.keep,len(text.encode('utf-8')))
        data=(json.dumps({'op':'input','text':text})+'\n').encode('utf-8') if self.bridge else text.encode('utf-8')
        self.proc.write(data)

    def interrupt(self):
        if self.active:
            self.proc.write((json.dumps({'op':'interrupt'})+'\n').encode() if self.bridge else b'\x03')

    def _read(self):
        if self.proc is None:
            return
        data = bytes(self.proc.readAllStandardOutput())
        if data and not self.builtin:
            with self.log.open("ab") as stream:
                stream.write(self.redactor.feed(data))

    def _tail(self):
        if self.directory is None:
            return
        try:
            with self.log.open("rb") as stream:
                stream.seek(self.offset)
                data = stream.read(256 * 1024)
                self.offset = stream.tell()
            if data:
                self.output.emit(self.decoder.decode(data))
        except OSError:
            pass

    def _error(self, error):
        if self.proc is not None and error == QProcess.ProcessError.FailedToStart:
            self.failure = self.proc.errorString()
            self._finished(-1, QProcess.ExitStatus.CrashExit)

    def _timeout(self):
        self.failure = "Durée maximale atteinte. Les résultats partiels sont conservés."
        self.stop(cancelled=False)

    def stop(self, cancelled=True):
        if not self.active:
            return
        self.cancelled = cancelled
        if self.bridge:
            self.proc.write((json.dumps({'op':'stop'})+'\n').encode())
            self.proc.closeWriteChannel()
            current=self.proc
            QTimer.singleShot(3000,lambda: self._force_stop() if self.proc is current else None)
            return
        self._force_stop()

    def _force_stop(self):
        if not self.active: return
        if self.job:
            self.job.close()
            self.job = None
        else:
            pid = int(self.proc.processId())
            if pid:
                try:
                    children = psutil.Process(pid).children(recursive=True)
                    for child in reversed(children):
                        try:
                            child.kill()
                        except psutil.Error:
                            pass
                except psutil.Error:
                    pass
            self.proc.kill()

    def _finished(self, code, exit_status):
        if not self.active:
            return
        self._read()
        if not self.builtin:
            with self.log.open('ab') as stream: stream.write(self.redactor.feed(b'',final=True))
        self.poll.stop()
        self.deadline.stop()
        # Keep final rendering bounded even when an external tool floods stdout.
        if self.log.stat().st_size - self.offset > 1_000_000:
            self.offset = max(0, self.log.stat().st_size - 500_000)
            self.decoder.reset()
            self.output.emit("\n[Affichage abrégé : le journal complet reste enregistré.]\n")
        while self.log.stat().st_size > self.offset:
            previous = self.offset
            self._tail()
            if self.offset == previous:
                break
        remaining = self.decoder.decode(b"", final=True)
        if remaining:
            self.output.emit(remaining)
        if self.job:
            self.job.close()
            self.job = None
        status = "cancelled" if self.cancelled else ("success" if code == 0 and not self.failure else "failed")
        self.record.update(status=status, exit_code=code, finished=now(), detail=self.failure)
        write_json(self.directory / "run.json", self.record)
        result = dict(self.record, directory=str(self.directory))
        self.proc.deleteLater()
        self.proc = None
        self.activeChanged.emit(False)
        self.completed.emit(result)

    def shutdown(self):
        if self.active:
            self.stop()
            if self.proc:
                if not self.proc.waitForFinished(5000):
                    self._force_stop()
                    if self.proc: self.proc.waitForFinished(3000)
