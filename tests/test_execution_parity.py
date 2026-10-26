"""Contract scenarios run through both real CLI and Desktop execution adapters.

Children are disposable local Python programs; no security tools or network are
used. The CLI presentation is replaced only to drive its existing abort callback.
These contracts cover execution and saved output, not installation, routing,
flows, Windows/WSL or UI rendering.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unicodedata
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from core import executor
from desktop.process import Runner as DesktopRunner
from desktop.storage import Store

APP = QApplication.instance() or QApplication([])


@unittest.skipUnless(os.name == "posix", "the CLI adapter requires POSIX")
class ExecutionParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="chaostic-parity-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "desktop data")

    def run_cli(self, command: list[str], ready: Path | None = None, *,
                timeout: float | None = None, redactions: tuple[str, ...] = ()) -> dict:
        output = self.root / "cli output.txt"

        def cancel_when_ready(state, start, abort, context, cmd, output_path):
            start()
            deadline = time.monotonic() + 8
            while not ready.exists() and not state.done.is_set():
                if time.monotonic() >= deadline:
                    abort()
                    self.fail("CLI fixture did not become ready")
                time.sleep(0.01)
            self.assertTrue(ready.exists(), "CLI fixture exited before readiness")
            abort()
            self.assertTrue(state.done.wait(8), "CLI cancellation did not finish")

        with patch.object(executor.console, "print"), \
                patch("core.scan_view.available", return_value=ready is not None), \
                patch("core.scan_view.run_scan", side_effect=cancel_when_ready):
            code = executor.run_tool(command, output, context={"wait": False},
                                     timeout=timeout, redactions=redactions)
        self.assertEqual(executor.ACTIVE_PROCS, [], "CLI retained an active process")
        if ready is not None:
            self.assertEqual(code, 130, "CLI must expose its cancellation exit code")
        return {
            "code": code,
            "status": "cancelled" if ready is not None else "success" if code == 0 else "failed",
            "output": output.read_text(encoding="utf-8") if output.exists() else "",
        }

    def run_desktop(self, command: list[str], ready: Path | None = None, *,
                    timeout: float | None = None,
                    redactions: tuple[str, ...] = ()) -> dict:
        runner = DesktopRunner(self.store)
        self.addCleanup(runner.shutdown)
        completed, activity = [], []
        loop = QEventLoop()

        def finish(record):
            completed.append(record)
            loop.quit()

        runner.completed.connect(finish)
        runner.activeChanged.connect(activity.append)
        watchdog = QTimer()
        watchdog.setSingleShot(True)
        watchdog.timeout.connect(loop.quit)
        watcher = QTimer()
        watcher.setInterval(10)

        def cancel_when_ready():
            if ready.exists():
                watcher.stop()
                runner.stop()

        if ready is not None:
            watcher.timeout.connect(cancel_when_ready)
        try:
            runner.start("Parity", "Local fixture", None, command=command,
                         timeout_ms=int(timeout * 1000) if timeout is not None else 10_000,
                         redactions=redactions)
            watchdog.start(10_000)
            if ready is not None:
                watcher.start()
            if not completed:
                loop.exec()
        finally:
            watchdog.stop()
            watcher.stop()
            runner.shutdown()
        self.assertEqual(len(completed), 1, "Desktop must finish exactly once")
        self.assertEqual(activity, [True, False])
        self.assertFalse(runner.active)
        record = completed[0]
        directory = Path(record["directory"])
        persisted = json.loads((directory / "run.json").read_text(encoding="utf-8"))
        for key in ("status", "exit_code", "finished", "detail"):
            self.assertEqual(persisted[key], record[key])
        return {
            "code": record["exit_code"],
            "status": record["status"],
            "output": (directory / "output.txt").read_text(encoding="utf-8"),
        }

    def assert_fixture(self, source: str, expected: str, code: int = 0,
                       arguments: tuple[str, ...] = ()) -> None:
        command = [sys.executable, "-u", "-c", source, *arguments]
        cli = self.canonical(self.run_cli(command))
        desktop = self.canonical(self.run_desktop(command))
        self.assertEqual(cli, desktop)
        self.assertEqual(cli, self.canonical({
            "code": code,
            "status": "success" if code == 0 else "failed",
            "output": expected,
        }))

    @staticmethod
    def canonical(result: dict) -> dict:
        # On macOS, QProcess routes the child's argv through Core Foundation,
        # which normalizes it to NFD, while the CLI adapter (subprocess) keeps
        # the NFC the user typed. That boundary is outside the project's control,
        # so compare canonical NFC forms there; Linux and Windows stay byte-exact.
        if sys.platform != "darwin":
            return result
        return {**result, "output": unicodedata.normalize("NFC", result["output"])}

    def test_success_merges_streams_and_preserves_utf8_and_final_fragment(self):
        self.assert_fixture(
            "import os; os.write(1, 'résultat €\\n'.encode()); "
            "os.write(2, b'error stream\\n'); os.write(1, b'last')",
            "résultat €\nerror stream\nlast",
        )

    def test_failure_preserves_nonzero_status_and_partial_output(self):
        self.assert_fixture(
            "import os,sys; os.write(1,b'partial failure'); sys.exit(7)",
            "partial failure", code=7,
        )

    def test_redaction_masks_secrets_split_across_output_chunks(self):
        secret = "adapter-private-secret"
        command = [sys.executable, "-u", "-c",
                   "import os,sys,time; value=sys.argv[1].encode(); "
                   "os.write(1,value[:7]); time.sleep(.05); "
                   "os.write(1,value[7:]+b'\\n')", secret]
        cli = self.canonical(self.run_cli(command, redactions=(secret,)))
        desktop = self.canonical(self.run_desktop(command, redactions=(secret,)))
        self.assertEqual(cli, desktop)
        self.assertEqual(cli["output"], "[masque]\n")
        self.assertNotIn(secret, cli["output"])

    def test_timeout_preserves_matching_partial_output_and_failure(self):
        command = [sys.executable, "-u", "-c",
                   "import os,time; os.write(1,b'partial\\n'); time.sleep(30)"]
        cli = self.canonical(self.run_cli(command, timeout=0.2))
        desktop = self.canonical(self.run_desktop(command, timeout=0.2))
        self.assertEqual(cli, desktop)
        self.assertEqual(cli["status"], "failed")
        self.assertNotEqual(cli["code"], 0)
        self.assertTrue(cli["output"].startswith("partial\n"), cli["output"])

    def test_empty_success_has_an_empty_journal(self):
        self.assert_fixture("pass", "")

    def test_large_output_is_saved_completely_by_both_adapters(self):
        # Larger than the CLI display tail and Desktop final-rendering limit.
        expected = "x" * (2 * 1024 * 1024) + "\nEND"
        self.assert_fixture(
            "import sys; sys.stdout.write('x' * (2 * 1024 * 1024) + '\\nEND')",
            expected,
        )

    def test_argument_boundaries_keep_shell_metacharacters_literal(self):
        unwanted = self.root / "must not exist"
        argument = f"literal; $(touch '{unwanted}') * ' spaces €"
        self.assert_fixture(
            "import sys; sys.stdout.write(sys.argv[1])", argument,
            arguments=(argument,),
        )
        self.assertFalse(unwanted.exists(), "an adapter interpreted argv as shell code")

    def test_cancellation_keeps_partial_output_and_reports_non_success(self):
        # Wait for a child-written marker instead of a timing-dependent delay.
        # SIGINT exits cleanly in the CLI; Desktop may use a platform kill code.
        source = (
            "import pathlib,signal,sys,time; "
            "signal.signal(signal.SIGINT,lambda *args:sys.exit(130)); "
            "print('partial result',flush=True); "
            "pathlib.Path(sys.argv[1]).write_text('ready'); time.sleep(30)"
        )
        results = []
        for name, run in (("cli", self.run_cli), ("desktop", self.run_desktop)):
            with self.subTest(adapter=name):
                ready = self.root / f"{name}.ready"
                command = [sys.executable, "-u", "-c", source, str(ready)]
                result = run(command, ready)
                self.assertEqual(result["status"], "cancelled")
                self.assertNotEqual(result["code"], 0)
                self.assertEqual(result["output"], "partial result\n")
                results.append((result["status"], result["output"]))
        self.assertEqual(results[0], results[1])


if __name__ == "__main__":
    unittest.main()
