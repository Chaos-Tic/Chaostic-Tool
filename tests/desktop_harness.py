"""Shared Qt harness for the desktop tests.

One offscreen ``QApplication`` for the whole suite, themed like the real
application, plus ``wait_run`` to drive a ``Runner`` to completion from a test.

Import it by its bare name (``from desktop_harness import APP, wait_run``):
``python -m unittest discover -s tests`` puts ``tests/`` on ``sys.path`` on its
own, and ``tests/conftest.py`` does the same for pytest, so the module is
loaded exactly once under either runner.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from desktop.theme import apply_theme

APP = QApplication.instance() or QApplication([])
apply_theme(APP)


def wait_run(runner, start, stop_after=None):
    """Start a run through ``start()`` and block until ``runner.completed`` fires.

    ``stop_after`` (milliseconds) requests ``runner.stop()`` once the run is
    under way. Fails the test if nothing completes within 15 seconds.
    """
    result = []
    loop = QEventLoop()
    def finish(record):
        result.append(record)
        loop.quit()
    runner.completed.connect(finish)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    timeout.start(15000)
    start()
    if stop_after is not None:
        QTimer.singleShot(stop_after, lambda: runner.stop())
    if not result:
        loop.exec()
    timeout.stop()
    runner.completed.disconnect(finish)
    if not result:
        runner.shutdown()
        raise AssertionError("Processus non terminé dans le délai du test")
    return result[0]
