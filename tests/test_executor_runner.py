"""CLI adapter contracts, using disposable children and output directories."""
import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from core import executor
from core.runner import RunRequest, Runner

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "CLI execution requires POSIX")
class ExecutorRunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / "output.txt"
        self.addCleanup(executor.cleanup_processes)

    def run_capture(self, code):
        with patch("core.scan_view.available", return_value=False), patch.object(executor.console, "print"):
            return executor.run_tool([sys.executable, "-u", "-c", code], self.output)

    def test_capture_uses_runner_and_invoking_user_environment(self):
        requests = []

        class ObservedRunner(Runner):
            def start(self, request, on_output=None, on_complete=None):
                requests.append(request)
                super().start(request, on_output, on_complete)

        env = dict(os.environ, CLI_RUNNER_TEST="present")
        with patch.object(executor, "Runner", ObservedRunner), patch.object(executor, "_build_env", return_value=env):
            rc = self.run_capture("import os; print(os.getenv('CLI_RUNNER_TEST'))")
        self.assertEqual(rc, 0)
        self.assertEqual(self.output.read_text(), "present\n")
        self.assertTrue(requests[0].inherit_stdin)
        self.assertEqual(executor.ACTIVE_PROCS, [])

    def test_stderr_unicode_partial_lines_and_raw_signal_status(self):
        rc = self.run_capture("import os,signal; os.write(1,b'first\\n'); "
                              "os.write(2,b'\\xe2\\x82\\xac\\xfflast'); "
                              "os.kill(os.getpid(),signal.SIGTERM)")
        self.assertEqual(rc, -signal.SIGTERM)
        self.assertEqual(self.output.read_text(), "first\n€\ufffdlast")

    def test_missing_binary_and_unwritable_log_are_reported(self):
        with patch("core.scan_view.available", return_value=False), patch.object(executor.console, "print"):
            rc = executor.run_tool(["/nonexistent/chaostic-cli-test"], self.output)
        self.assertEqual(rc, 127)
        self.assertEqual(self.output.read_text(), "Binary not found: /nonexistent/chaostic-cli-test\n")
        self.output = Path(self.directory.name)  # opening a directory as a log fails
        with patch("core.scan_view.available", return_value=False), patch.object(executor.console, "print") as display:
            rc = executor.run_tool([sys.executable, "-c", "print('saved elsewhere')"], self.output)
        self.assertEqual(rc, 0)
        self.assertTrue(any("Could not save output:" in str(call) for call in display.call_args_list))
        self.assertEqual(executor.ACTIVE_PROCS, [])

    def test_spawn_permission_error_returns_failure_and_records_diagnostic(self):
        binary = Path(self.directory.name) / "not-executable"
        binary.write_text("no executable permission")
        binary.chmod(0o600)
        with patch("core.scan_view.available", return_value=False), \
                patch.object(executor.console, "print"), \
                self.assertLogs("core.backends.posix", level="ERROR"):
            rc = executor.run_tool([str(binary)], self.output)
        self.assertEqual(rc, 1)
        self.assertIn("Execution failed:", self.output.read_text())
        self.assertEqual(executor.ACTIVE_PROCS, [])

    def test_cancel_preserves_partial_log_and_returns_130(self):
        def scan(state, start, abort, *args):
            start()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with state.lock:
                    ready = "ready" in "".join(state.visible)
                if ready:
                    break
                time.sleep(0.01)
            self.assertTrue(ready, "child did not emit its readiness marker")
            abort()
            self.assertTrue(state.done.wait(8))

        with patch("core.scan_view.available", return_value=True), patch("core.scan_view.run_scan", side_effect=scan):
            rc = executor.run_tool([sys.executable, "-u", "-c",
                                    "import time; print('ready'); time.sleep(30)"], self.output)
        self.assertEqual(rc, 130)
        self.assertIn("ready\n", self.output.read_text())
        self.assertEqual(executor.ACTIVE_PROCS, [])

    def test_redirected_stdin_is_inherited_without_text_reencoding(self):
        code = """
import sys
from core.executor import run_tool
rc = run_tool([sys.executable, '-c',
    'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())'], sys.argv[1])
assert rc == 0, rc
"""
        subprocess.run([sys.executable, "-c", code, str(self.output)], cwd=ROOT,
                       input=b"input\n\xff", stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, check=True, timeout=8)
        self.assertEqual(self.output.read_text(), "input\n\ufffd")

    def test_inherited_input_refuses_queued_input_and_keeps_parent_input_open(self):
        runner = Runner()
        self.addCleanup(runner.stop)
        runner.start(RunRequest([sys.executable, "-c", "pass"], inherit_stdin=True))
        self.assertFalse(runner.send_input("do not queue"))
        runner.close_input()
        self.assertEqual(runner.wait(5).returncode, 0)
        self.assertFalse(sys.stdin.closed)

    def test_real_ctrl_c_in_plain_capture_saves_output_and_reaps_child(self):
        ready = Path(self.directory.name) / "ready.pid"
        code = """
import sys
from core.executor import run_tool
child = "import os,time,pathlib; print('ready',flush=True); pathlib.Path(%r).write_text(str(os.getpid())); time.sleep(30)" % sys.argv[2]
rc = run_tool([sys.executable, '-u', '-c', child], sys.argv[1])
assert rc == 130, rc
"""
        proc = subprocess.Popen([sys.executable, "-c", code, str(self.output), str(ready)],
                                cwd=ROOT, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            child_pid = None
            while proc.poll() is None and time.monotonic() < deadline:
                try:
                    child_pid = int(ready.read_text())
                    break
                except (FileNotFoundError, ValueError):
                    pass
                time.sleep(0.01)
            self.assertIsNotNone(child_pid, "child did not become ready")
            os.kill(proc.pid, signal.SIGINT)
            _, errors = proc.communicate(timeout=8)
            self.assertEqual(proc.returncode, 0, errors.decode(errors="replace"))
            self.assertIn("ready\n", self.output.read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)

    def test_interactive_execution_keeps_the_inherited_terminal_path(self):
        with patch.object(executor, "Runner", side_effect=AssertionError("captured runner used")), \
                patch.object(sys, "stdin", io.StringIO()), patch.object(executor.console, "print"):
            rc = executor.run_tool([sys.executable, "-c", "raise SystemExit(9)"], interactive=True)
        self.assertEqual(rc, 9)
        self.assertEqual(executor.ACTIVE_PROCS, [])


if __name__ == "__main__":
    unittest.main()
