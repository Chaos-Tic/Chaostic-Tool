import contextlib
import http.server
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import psutil

from desktop.catalog import availability, build_arguments, catalog
from desktop.process import Runner
from desktop.storage import Store, parse_target, write_json
from desktop.theme import apply_theme
from desktop.window import Window

APP = QApplication.instance() or QApplication([])
apply_theme(APP)


def wait_run(runner, start, stop_after=None):
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


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="chaostic-test-")
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "données avec espaces")

    def tearDown(self):
        APP.processEvents()
        self.temp.cleanup()

    def test_target_parsing(self):
        self.assertEqual(parse_target("https://example.com:8443/path?q=1")["port"], 8443)
        self.assertEqual(parse_target("::1")["url"], "https://[::1]/")
        self.assertEqual(parse_target("https://[::1]:443/a")["host"], "::1")
        self.assertEqual(parse_target("éxemple.fr")["host"], "xn--xemple-9ua.fr")
        for invalid in ("-oN", "example.com -p 22", "../..", "http://", "ftp://host", "https://user:pass@host", "example.com:0", "https://host:99999", "host\nInjected", "*.example.com"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_target(invalid)

    def test_target_persistence_and_dedup(self):
        target = self.store.add_target("localhost", "Banc local")
        self.store.add_target("localhost", "Second nom")
        self.assertEqual(len(self.store.targets), 1)
        self.assertEqual(Store(self.store.root).active_target, target)
        self.store.remove_target(target["id"])
        self.assertIsNone(self.store.active_target)

    def test_corrupt_settings_are_preserved(self):
        self.store.path.write_text("{broken", encoding="utf-8")
        store = Store(self.store.root)
        self.assertTrue(store.warning)
        self.assertEqual(next(store.root.glob("settings-unreadable-*.json")).read_text(), "{broken")

    def test_abandoned_run_is_marked_interrupted(self):
        directory, record = self.store.new_run("test", "test", None, ["test"])
        restored = Store(self.store.root)
        self.assertEqual(restored.history()[0]["status"], "interrupted")
        self.assertTrue(directory.exists())

    def test_catalog_and_argument_boundaries(self):
        tools = {t["key"]: t for t in catalog()}
        self.assertEqual(availability(tools["desktop-dns"], {}), ("Inclus", True))
        self.assertFalse(availability(tools["airmon-ng"], {}, self.store.root)[1])
        target = parse_target("https://[::1]:8443/")
        args = build_arguments(tools["nmap"], 1, target)
        self.assertEqual(args, ["-6", "-sT", "-Pn", "-n", "-p", "8443", "::1"])
        with self.assertRaises(ValueError):
            build_arguments(tools["subfinder"], 0, target)
        words = self.root / "liste avec espaces.txt"
        words.write_text("test")
        args = build_arguments(tools["ffuf"], 0, parse_target("https://localhost/a?q=2"), str(words))
        self.assertIn(str(words.resolve()), args)
        self.assertIn("https://localhost/a/FUZZ", args)

    def test_builtin_worker_persists_output(self):
        runner = Runner(self.store)
        result = wait_run(runner, lambda: runner.start("Diagnostic", "Local", None, worker="diagnostic"))
        self.assertEqual(result["status"], "success", result)
        self.assertIn("opérationnel", (Path(result["directory"]) / "output.txt").read_text(encoding="utf-8"))

    def test_dns_localhost(self):
        runner = Runner(self.store)
        result = wait_run(runner, lambda: runner.start("DNS", "Adresses", parse_target("localhost"), worker="dns"))
        self.assertEqual(result["status"], "success", result)
        self.assertIn("127.0.0.1", (Path(result["directory"]) / "output.txt").read_text(encoding="utf-8"))

    def test_http_local_fixture(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_HEAD(self):
                self.send_response(200)
                self.send_header("X-Chaostic-Test", "passed")
                self.end_headers()
            def log_message(self, *args):
                pass
        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            runner = Runner(self.store)
            target = parse_target(f"http://127.0.0.1:{server.server_port}/")
            result = wait_run(runner, lambda: runner.start("HTTP", "HEAD", target, worker="http"))
            self.assertEqual(result["status"], "success", result)
            text = (Path(result["directory"]) / "output.txt").read_text(encoding="utf-8")
            self.assertIn("X-Chaostic-Test: passed", text)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_missing_executable_is_saved_as_failure(self):
        runner = Runner(self.store)
        result = wait_run(runner, lambda: runner.start("Missing", "Local", None, command=[str(self.root / "absent.exe")]))
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["detail"])
        self.assertFalse(runner.active)

    def test_cancellation_kills_descendants_and_keeps_partial_log(self):
        helper = self.root / "child tree.py"
        pid_file = self.root / "pid.txt"
        helper.write_text("import subprocess, sys, time\nfrom pathlib import Path\np = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\nPath(sys.argv[1]).write_text(str(p.pid))\nprint('partial result', flush=True)\ntime.sleep(60)\n", encoding="utf-8")
        runner = Runner(self.store)
        result = wait_run(runner, lambda: runner.start("Tree", "Cancel", None, command=[sys.executable, str(helper), str(pid_file)]), stop_after=1300)
        self.assertEqual(result["status"], "cancelled", result)
        self.assertIn("partial result", (Path(result["directory"]) / "output.txt").read_text(encoding="utf-8"))
        self.assertTrue(pid_file.exists())
        pid = int(pid_file.read_text())
        deadline = time.monotonic() + 3
        while psutil.pid_exists(pid) and time.monotonic() < deadline:
            QTest.qWait(50)
        self.assertFalse(psutil.pid_exists(pid), "Le descendant doit être arrêté")

    def test_timeout_is_failure_not_success(self):
        runner = Runner(self.store)
        result = wait_run(runner, lambda: runner.start("Timeout", "Local", None, command=[sys.executable, "-c", "import time; time.sleep(30)"], timeout_ms=400))
        self.assertEqual(result["status"], "failed")
        self.assertIn("maximale", result["detail"])

    def test_graphical_navigation_filter_and_run(self):
        window = Window(self.store)
        window.show()
        for index, nav in enumerate(window.nav):
            QTest.mouseClick(nav, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.MouseButton.LeftButton)
            self.assertEqual(window.stack.currentIndex(), index)
        window.navigate(2)
        # System tools vary between Linux desktops; test the bundled filter alone.
        with patch("desktop.catalog.native_command", return_value=None):
            window.only_ready.setChecked(True)
            window.search.setText("certificat")
        self.assertEqual([t["key"] for t in window.filtered_tools], ["desktop-tls"])
        result = wait_run(window.runner, lambda: window.launch("desktop-diagnostic", show_dialog=False))
        self.assertEqual(result["status"], "success")
        self.assertIn("opérationnel", window.console.toPlainText())
        self.assertEqual(window.history_table.rowCount(), 1)
        window.close()
        window.deleteLater()


if __name__ == "__main__":
    unittest.main()
