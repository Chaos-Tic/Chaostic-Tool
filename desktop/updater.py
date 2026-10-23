"""Anonymous, daily GitHub checks and verified installer downloads."""
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QThread

from core import update_service
from desktop import VERSION
from desktop.storage import data_root


class _Worker(QObject):
    done = Signal(dict)

    def __init__(self, cache, manual):
        super().__init__()
        self.cache = cache
        self.manual = manual

    def run(self):
        self.done.emit(update_service.check("desktop", VERSION, self.cache, force=self.manual))


class UpdateChecker(QObject):
    result = Signal(bool, str, str, bool)

    def __init__(self, parent=None, root=None):
        super().__init__(parent)
        self.root = root or data_root()
        self._thread = None
        self._worker = None

    def check(self, manual=False):
        if self._thread is not None:
            return
        self._manual = manual
        self._thread = QThread(self)
        self._worker = _Worker(self.root / "update-check.json", manual)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_done)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    def _on_done(self, result):
        thread = self._thread
        worker = self._worker
        self._thread = self._worker = None
        thread.quit()
        thread.wait(3000)
        thread.deleteLater()
        self.result.emit(result["available"], result["version"], result["url"], self._manual)

    def shutdown(self):
        if self._thread is not None:
            self._thread.requestInterruption()
            self._thread.quit()
            self._thread.wait(10000)


class _DownloadWorker(QObject):
    done = Signal(str, str)

    def __init__(self, tag, filename, destination):
        super().__init__()
        self.tag, self.filename, self.destination = tag, filename, destination

    def run(self):
        try:
            path = update_service.download_verified(self.tag, self.filename, self.destination,
                cancelled=QThread.currentThread().isInterruptionRequested)
            self.done.emit(str(path), "")
        except (OSError, ValueError) as exc:
            self.done.emit("", str(exc))


class InstallerDownload(QObject):
    result = Signal(str, str)

    def __init__(self, destination: Path, parent=None):
        super().__init__(parent)
        self.destination = destination
        self._thread = self._worker = None

    def start(self, tag, filename):
        if self._thread is not None:
            return
        self._thread = QThread(self)
        self._worker = _DownloadWorker(tag, filename, self.destination)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_done)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    def _on_done(self, path, error):
        thread = self._thread
        worker = self._worker
        self._thread = self._worker = None
        thread.quit()
        thread.wait(3000)
        thread.deleteLater()
        self.result.emit(path, error)

    def shutdown(self):
        if self._thread is not None:
            self._thread.requestInterruption()
            self._thread.quit()
            self._thread.wait(10000)
