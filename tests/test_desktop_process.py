"""Qt adapter contracts using disposable children and a controlled core backend."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_desktop import APP, wait_run

from core.runner import Runner as ProcessRunner
from core.runner import RunResult
from desktop.process import Runner
from desktop.storage import Store


class ControlledBackend:
    def __init__(self):
        self.inputs = []
        self.closed = False
        self.stopped = False
        self.result = None

    def start(self, request, on_output=None, on_complete=None):
        self.request, self.output, self.completed = request, on_output, on_complete

    def send_input(self, text):
        self.inputs.append(text)
        return True

    def close_input(self):
        self.closed = True

    def interrupt(self):
        raise AssertionError("Desktop interruption must preserve its stdin protocol")

    def stop(self):
        self.stopped = True

    def wait(self, timeout=None):
        return self.result

    def finish(self, result=None):
        self.result = result if result is not None else RunResult(0)
        self.completed(self.result)


class DesktopProcessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="chaostic-qt-runner-")
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "data with spaces")
        self.runner = Runner(self.store)
        self.addCleanup(self.runner.shutdown)

    def controlled(self, backend=None):
        backend = backend or ControlledBackend()
        factory = patch("desktop.process.ProcessRunner", return_value=ProcessRunner(backend))
        factory.start()
        self.addCleanup(factory.stop)
        return backend

    def test_native_request_preserves_argv_environment_metadata_and_input(self):
        backend = self.controlled()
        argv = ["literal program", "a; $(anything)", "€ spaces"]
        self.runner.start("Fixture", "Native", None, command=argv, timeout_ms=1234,
                          environment_extra={"ADAPTER_TEST": "present", "NO_COLOR": "custom"},
                          metadata={"flow_id": "flow", "flow_step": 2, "unrelated": "drop"})
        request = backend.request
        self.assertEqual(request.argv, tuple(argv))
        self.assertEqual(request.cwd, self.runner.directory)
        self.assertEqual(request.timeout, 1.234)
        self.assertTrue(request.raw_output)
        self.assertFalse(request.inherit_stdin)
        self.assertEqual(request.env["ADAPTER_TEST"], "present")
        self.assertEqual(request.env["NO_COLOR"], "custom")
        self.assertEqual(request.env["PYTHONUTF8"], "1")
        self.assertEqual(request.env["PYTHONUNBUFFERED"], "1")
        self.runner.send_input("héllo\n")
        self.runner.interrupt()
        self.assertEqual(backend.inputs, ["héllo\n", "\x03"])
        with self.assertRaises(RuntimeError):
            self.runner.start("Second", "Native", None, command=["unused"])
        result = wait_run(self.runner, backend.finish)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["flow_id"], "flow")
        self.assertEqual(result["flow_step"], 2)
        self.assertNotIn("unrelated", result)

    def test_bridge_keeps_transport_argv_and_json_control_protocol(self):
        backend = self.controlled()
        argv = ["tool", "literal; argument", "private"]
        transport = ["transport", "--", "literal bridge source"]
        request = {"op": "run", "argv": argv, "cwd": "/remote/run"}
        with patch("desktop.backends.execution_plan", return_value=(transport, request)) as plan, \
                patch("desktop.backends.install_choices", return_value={"tool": {"candidates": ["tool"]}}), \
                patch("desktop.process.QTimer.singleShot") as later:
            self.runner.start("Fixture", "Bridge", None, command=argv, bridge=True,
                              fields={"wordlist": "/tmp/words"}, elevate=True,
                              local_bridge=True, linux_install_keys=["tool"], timeout_ms=2500,
                              redactions=["private"])
            plan.assert_called_once_with(argv, {"requires_root": True}, self.store.root,
                                         self.runner.directory, {"wordlist": "/tmp/words"}, local=True)
            self.assertEqual(backend.request.argv, tuple(transport))
            self.assertIsNone(backend.request.timeout)
            initial = json.loads(backend.inputs[0])
            self.assertEqual(initial["argv"], argv)
            self.assertEqual(initial["timeout"], 2)
            self.assertEqual(initial["skip_installed"], {"tool": {"candidates": ["tool"]}})
            self.runner.send_input("answer\n")
            self.runner.interrupt()
            self.runner.stop()
            self.assertEqual([json.loads(value) for value in backend.inputs[1:]], [
                {"op": "input", "text": "answer\n"}, {"op": "interrupt"}, {"op": "stop"}])
            self.assertTrue(backend.closed)
            self.assertFalse(backend.stopped)
            later.assert_called_once()
            self.assertEqual(later.call_args.args[0], 3000)
            result = wait_run(self.runner, lambda: backend.finish(RunResult(130)))
            self.assertEqual(result["status"], "cancelled")
            later.call_args.args[1]()
            self.assertFalse(backend.stopped, "stale bridge timer must not stop a completed run")
        self.assertNotIn("private", (Path(result["directory"]) / "run.json").read_text())

    def test_bridge_timeout_sends_stop_and_remains_failed_on_clean_transport_exit(self):
        backend = self.controlled()
        with patch("desktop.backends.execution_plan", return_value=(["transport"], {"op": "run"})), \
                patch("desktop.process.QTimer.singleShot") as later:
            self.runner.start("Fixture", "Bridge", None, command=["tool"], bridge=True)
            self.runner._timeout()
            self.assertEqual(json.loads(backend.inputs[-1]), {"op": "stop"})
            later.call_args.args[1]()
            self.assertTrue(backend.stopped)
            result = wait_run(self.runner, lambda: backend.finish(RunResult(0, cancelled=True)))
        self.assertEqual(result["status"], "failed")
        self.assertIn("maximale", result["detail"])

    def test_bridge_preparation_failure_is_persisted_without_activity(self):
        activity = []
        self.runner.activeChanged.connect(activity.append)
        with patch("desktop.backends.execution_plan", side_effect=ValueError("invalid backend")), \
                self.assertRaisesRegex(ValueError, "invalid backend"):
            self.runner.start("Fixture", "Bridge", None, command=["tool"], bridge=True)
        self.assertEqual(activity, [])
        self.assertFalse(self.runner.active)
        record = json.loads((self.runner.directory / "run.json").read_text())
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["exit_code"], -1)
        self.assertEqual(record["detail"], "invalid backend")

    def test_raw_journal_and_signals_are_completed_on_qt_thread(self):
        emitted, activity, completed, threads = [], [], [], []
        qt_thread = threading.get_ident()
        self.runner.output.connect(lambda value: (emitted.append(value), threads.append(threading.get_ident())))
        self.runner.activeChanged.connect(lambda value: (activity.append(value), threads.append(threading.get_ident())))
        self.runner.completed.connect(lambda value: (completed.append(value), threads.append(threading.get_ident())))
        self.runner.start("Fixture", "Bytes", None, command=[sys.executable, "-c",
            "import os; os.write(1,b'prefix\\xff\\xe2'); os.write(2,b'\\x82\\xac\\xe2')"])
        self.assertIsInstance(self.runner.proc, ProcessRunner)
        self.assertEqual(self.runner.proc.wait(5).returncode, 0)
        self.assertEqual(completed, [], "completion must be queued until Qt handles events")
        APP.processEvents()
        self.assertEqual(len(completed), 1)
        self.assertEqual(activity, [True, False])
        self.assertTrue(all(value == qt_thread for value in threads))
        self.assertEqual("".join(emitted), "prefix\ufffd\u20ac\ufffd")
        directory = Path(completed[0]["directory"])
        self.assertEqual((directory / "output.txt").read_bytes(), b"prefix\xff\xe2\x82\xac\xe2")
        persisted = json.loads((directory / "run.json").read_text())
        for key in ("status", "exit_code", "finished", "detail"):
            self.assertEqual(persisted[key], completed[0][key])

    def test_secret_stdin_echo_is_masked_before_persistence_and_rendering(self):
        emitted = []
        self.runner.output.connect(emitted.append)
        command = [sys.executable, "-u", "-c",
                   ("import os,sys,time; text=sys.stdin.readline().encode(); "
                    "os.write(1,text[:7]); time.sleep(.05); os.write(1,text[7:]); os.write(1,b'final')")]
        def start():
            self.runner.start("Fixture", "Secret input", None, command=command)
            self.runner.send_input("unique-private-input\n", secret=True)
        result = wait_run(self.runner, start)
        self.assertEqual(result["status"], "success")
        saved = (Path(result["directory"]) / "output.txt").read_text()
        self.assertEqual(saved.replace("\r\n", "\n"), "[redacted]\nfinal")
        self.assertNotIn("unique-private-input", "".join(emitted))

    def test_missing_executable_keeps_core_code_and_persisted_failure(self):
        completed = []
        self.runner.completed.connect(completed.append)
        self.runner.start("Missing", "Native", None,
                          command=[str(self.store.root / "missing executable")])
        result = self.runner.proc.wait(5)
        self.assertEqual(result.returncode, 127)
        APP.processEvents()
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["status"], "failed")
        self.assertEqual(completed[0]["exit_code"], 127)
        self.assertTrue(completed[0]["detail"])
        self.assertFalse(self.runner.active)
        persisted = json.loads((self.runner.directory / "run.json").read_text())
        self.assertEqual(persisted["detail"], completed[0]["detail"])

    def test_native_timeout_runs_in_core_without_qt_event_processing(self):
        completed = []
        self.runner.completed.connect(completed.append)
        self.runner.start("Timeout", "Native", None, command=[sys.executable, "-u", "-c",
            "import time; print('partial'); time.sleep(30)"], timeout_ms=200)
        self.assertFalse(self.runner.deadline.isActive())
        self.assertTrue(self.runner.proc.wait(5).timed_out)
        self.assertEqual(completed, [])
        APP.processEvents()
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["status"], "failed")
        self.assertIn("maximale", completed[0]["detail"])
        self.assertIn("partial", (self.runner.directory / "output.txt").read_text())

    def test_shutdown_consumes_result_once_and_stale_callback_cannot_finish_next_run(self):
        first, second = ControlledBackend(), ControlledBackend()
        with patch("desktop.process.ProcessRunner", side_effect=[ProcessRunner(first), ProcessRunner(second)]):
            completed, activity = [], []
            self.runner.completed.connect(completed.append)
            self.runner.activeChanged.connect(activity.append)
            self.runner.start("First", "Native", None, command=["fixture"])
            first.output(b"first")
            first.finish()
            self.runner.shutdown()
            self.assertFalse(self.runner.active)
            self.assertEqual(len(completed), 1)
            self.runner.start("Second", "Native", None, command=["fixture"])
            APP.processEvents()
            self.assertTrue(self.runner.active)
            self.assertEqual(len(completed), 1)
            second.output(b"second")
            result = wait_run(self.runner, second.finish)
        self.assertEqual(result["tool"], "Second")
        self.assertEqual(result["status"], "success")
        self.assertEqual((Path(result["directory"]) / "output.txt").read_bytes(), b"second")
        self.assertEqual(len(completed), 2)
        self.assertEqual(activity, [True, False, True, False])

    def test_large_output_bounds_display_while_journal_remains_complete(self):
        backend = self.controlled()
        emitted = []
        self.runner.output.connect(emitted.append)
        self.runner.start("Fixture", "Flood", None, command=["fixture"])
        data = b"x" * (2 * 1024 * 1024) + b"END"
        backend.output(data)
        result = wait_run(self.runner, backend.finish)
        self.assertEqual((Path(result["directory"]) / "output.txt").read_bytes(), data)
        self.assertIn("Affichage abrégé", "".join(emitted))
        self.assertLess(len("".join(emitted)), 501_000)
        self.assertTrue("".join(emitted).endswith("END"))


if __name__ == "__main__":
    unittest.main()
