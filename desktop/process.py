"""Qt adapter for shared execution, bounded UI output and persistent full logs."""
from __future__ import annotations

import codecs
import json
import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from core.runner import Runner as ProcessRunner
from core.runner import RunRequest, RunResult
from desktop.profiles import StreamRedactor, redact
from desktop.storage import now, write_json


def worker_command(worker, request, log):
    if getattr(sys, "frozen", False):
        return [sys.executable, "--worker", worker, str(request), str(log)]
    return [sys.executable, str(Path(__file__).resolve().parent.parent / "chaostic_desktop.py"),
            "--worker", worker, str(request), str(log)]


class Runner(QObject):
    output = Signal(str)
    completed = Signal(dict)
    activeChanged = Signal(bool)
    _executionFinished = Signal(object, object)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.proc: ProcessRunner | None = None
        self.record = None
        self.directory = None
        self.cancelled = False
        self.failure = ""
        self.builtin = False
        self.offset = 0
        self._log_lock = threading.Lock()
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.poll = QTimer(self)
        self.poll.setInterval(100)
        self.poll.timeout.connect(self._tail)
        # Remote/PTY jobs must receive their JSON stop request before the local
        # transport is cancelled. Native process deadlines belong to the core.
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self._timeout)
        self._executionFinished.connect(self._finished, Qt.ConnectionType.QueuedConnection)

    @property
    def active(self):
        return self.proc is not None

    def start(self, tool, preset, target, command=None, worker=None, timeout_ms=1_200_000, bridge=False, fields=None, redactions=(), elevate=False, metadata=None, environment_extra=None, local_bridge=False, linux_install_keys=None):
        if self.active:
            raise RuntimeError("Une opération est déjà en cours.")
        display = [redact(arg, redactions) for arg in (command or ['builtin', worker])]
        directory, record = self.store.new_run(tool, preset, target, display)
        if metadata:
            record.update({k: metadata[k] for k in ('flow_id', 'flow_name', 'flow_step', 'flow_target') if k in metadata})
            write_json(directory / 'run.json', record)
        self.directory, self.record = directory, record
        self.cancelled, self.failure, self.builtin, self.offset = False, "", worker is not None, 0
        self.decoder.reset()
        self.redactor = StreamRedactor(redactions)
        self.bridge = bridge
        self.log = directory / "output.txt"
        self.log.touch()
        initial_input = None
        try:
            if worker:
                command = worker_command(worker, directory / "run.json", self.log)
            elif bridge:
                from desktop.backends import execution_plan
                command, request = execution_plan(command, {'requires_root': elevate}, self.store.root, directory, fields, local=local_bridge)
                if linux_install_keys:
                    from desktop.backends import install_choices
                    request['skip_installed'] = install_choices(linux_install_keys)
                request['timeout'] = max(1, timeout_ms // 1000)
                initial_input = json.dumps(request) + '\n'
            from desktop.tool_paths import tool_search_path
            environment = dict(os.environ, PATH=tool_search_path(), PYTHONUTF8="1",
                               PYTHONUNBUFFERED="1", NO_COLOR="1")
            environment.update(environment_extra or {})
            request = RunRequest(command, cwd=directory, env=environment,
                                 timeout=None if bridge else timeout_ms / 1000,
                                 raw_output=True)
            current = ProcessRunner()
        except Exception as exc:
            record.update(status='failed', detail=str(exc), finished=now(), exit_code=-1)
            write_json(directory / 'run.json', record)
            raise
        self.proc = current
        self.activeChanged.emit(True)
        self.poll.start()
        if bridge:
            self.deadline.start(timeout_ms)
        current.start(request, self._read,
                      lambda result: self._executionFinished.emit(current, result))
        if initial_input:
            current.send_input(initial_input)

    def send_input(self, text, secret=False):
        if not self.active:
            return
        if secret:
            # The backend can emit concurrently with user input. Register the
            # secret before queuing input so even an immediate echo is masked.
            with self._log_lock:
                self.redactor.add(text.rstrip('\r\n'))
        data = json.dumps({'op': 'input', 'text': text}) + '\n' if self.bridge else text
        self.proc.send_input(data)

    def interrupt(self):
        if self.active:
            self.proc.send_input(json.dumps({'op': 'interrupt'}) + '\n' if self.bridge else '\x03')

    def _read(self, data: bytes):
        # This callback runs on the core worker thread. Persist here instead of
        # enqueuing unbounded output events; only the Qt timer renders the tail.
        if data and not self.builtin:
            with self._log_lock, self.log.open("ab") as stream:
                stream.write(self.redactor.feed(data))

    def _tail(self):
        if self.directory is None:
            return
        try:
            with self._log_lock, self.log.open("rb") as stream:
                stream.seek(self.offset)
                data = stream.read(256 * 1024)
                self.offset = stream.tell()
            if data:
                self.output.emit(self.decoder.decode(data))
        except OSError:
            pass

    def _timeout(self):
        self.failure = "Durée maximale atteinte. Les résultats partiels sont conservés."
        self.stop(cancelled=False)

    def stop(self, cancelled=True):
        if not self.active:
            return
        self.cancelled = cancelled
        if self.bridge:
            self.proc.send_input(json.dumps({'op': 'stop'}) + '\n')
            self.proc.close_input()
            current = self.proc
            QTimer.singleShot(3000, lambda: current.stop() if self.proc is current else None)
        else:
            self.proc.stop()

    def _finished(self, current: ProcessRunner, result: RunResult):
        # shutdown may consume the result while its queued notification is still
        # pending. Never let an old completion finish a subsequent run.
        if self.proc is not current:
            return
        if not self.builtin:
            with self._log_lock, self.log.open('ab') as stream:
                stream.write(self.redactor.feed(b'', final=True))
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
        if result.timed_out:
            self.failure = "Durée maximale atteinte. Les résultats partiels sont conservés."
        elif result.error:
            self.failure = result.error
        code = result.returncode
        status = "cancelled" if self.cancelled else ("success" if code == 0 and not self.failure else "failed")
        self.record.update(status=status, exit_code=code, finished=now(), detail=self.failure)
        write_json(self.directory / "run.json", self.record)
        record = dict(self.record, directory=str(self.directory))
        self.proc = None
        self.activeChanged.emit(False)
        self.completed.emit(record)

    def shutdown(self):
        if self.active:
            current = self.proc
            self.stop()
            result = current.wait(5)
            if result is None:
                current.stop()
                result = current.wait(3)
            if result is not None:
                self._finished(current, result)
