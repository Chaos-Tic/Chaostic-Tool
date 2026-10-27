"""UI-free process tests using only disposable local Python children."""
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from core.runner import Runner, RunRequest

ROOT = Path(__file__).resolve().parents[1]


class RequestTests(unittest.TestCase):
    def test_import_does_not_load_rich_or_qt(self):
        code = """
import sys
class NoUI:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'rich', 'PySide6', 'PyQt6', 'desktop'}:
            raise AssertionError(fullname)
sys.meta_path.insert(0, NoUI())
from core.runner import RunRequest, RunResult, Runner
"""
        subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True, timeout=5)

    def test_invalid_requests_and_snapshot(self):
        for argv in ([], "echo hello", [""], ["x\0"], [1]):
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                RunRequest(argv)
        for value in (0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=value), self.assertRaises(ValueError):
                RunRequest(["x"], timeout=value)
        with self.assertRaises(ValueError):
            RunRequest(["x"], stop_grace=None)
        argv, env = ["x"], {"RUNNER_TEST": "original"}
        request = RunRequest(argv, env=env)
        argv[0], env["RUNNER_TEST"] = "changed", "changed"
        self.assertEqual(request.argv, ("x",))
        self.assertEqual(request.env["RUNNER_TEST"], "original")


@unittest.skipUnless(os.name == "posix", "POSIX backend")
class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.runners = []

    def tearDown(self):
        for runner in self.runners:
            runner.stop()
            self.assertIsNotNone(runner.wait(5), "runner leaked a worker")

    def start(self, code, output=None, complete=None, **kwargs):
        runner = Runner()
        runner.start(RunRequest([sys.executable, "-u", "-c", code],
                                stop_grace=0.1, **kwargs), output, complete)
        self.runners.append(runner)
        return runner

    def test_nonzero_and_merged_output(self):
        output, completed = [], []
        runner = self.start("import sys; print('out'); print('err', file=sys.stderr); sys.exit(7)",
                            output.append, completed.append)
        result = runner.wait(5)
        self.assertEqual(result.returncode, 7)
        self.assertEqual("".join(output), "out\nerr\n")
        self.assertEqual(completed, [result])
        self.assertFalse(result.cancelled or result.timed_out)
        self.assertIsNone(result.error)

    def test_fragments_arrive_before_exit_and_utf8_is_incremental(self):
        output = []
        ready = threading.Event()

        def receive(text):
            output.append(text)
            ready.set()

        runner = self.start("import os,sys; os.write(1,b'prompt:'); sys.stdin.readline(); "
                            "os.write(1,b'\\xe2'); sys.stdin.readline(); "
                            "os.write(1,b'\\x82\\xac\\xff\\xe2')", receive)
        self.assertTrue(ready.wait(3))
        self.assertIsNone(runner.wait(0))
        self.assertEqual("".join(output), "prompt:")
        self.assertTrue(runner.send_input("continue\n"))
        # A delayed last byte makes separate reads likely; correctness must not
        # depend on packet boundaries either way.
        time.sleep(0.05)
        self.assertTrue(runner.send_input("finish\n"))
        self.assertEqual(runner.wait(5).returncode, 0)
        self.assertEqual("".join(output), "prompt:€\ufffd\ufffd")

    def test_cwd_environment_and_no_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            output = []
            literal = "$(touch unwanted); * ' spaces"
            runner = Runner()
            runner.start(RunRequest([sys.executable, "-c",
                "import json,os,sys; print(json.dumps([os.getcwd(),os.getenv('RUNNER_TEST'),sys.argv[1]]))",
                literal], cwd=directory, env={"RUNNER_TEST": "present"}), output.append)
            self.runners.append(runner)
            self.assertEqual(runner.wait(5).returncode, 0)
            # The child reports its resolved working directory; on macOS the temp
            # dir sits under the /var -> /private/var symlink, so compare realpaths.
            self.assertEqual(json.loads("".join(output)),
                             [os.path.realpath(directory), "present", literal])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_raw_output_preserves_invalid_utf8_and_unfinished_fragment(self):
        output = []
        runner = self.start("import os; os.write(1,b'prefix\\xff\\xe2'); "
                            "os.write(2,b'\\x82\\xac\\xfe\\xe2')", output.append,
                            raw_output=True)
        self.assertEqual(runner.wait(5).returncode, 0)
        self.assertTrue(all(isinstance(chunk, bytes) for chunk in output))
        self.assertEqual(b"".join(output), b"prefix\xff\xe2\x82\xac\xfe\xe2")

    def test_raw_timeout_does_not_decode_or_duplicate_final_bytes(self):
        output = []
        runner = self.start("import os,signal,time; "
                            "signal.signal(signal.SIGINT,signal.SIG_IGN); "
                            "os.write(1,b'partial\\xff\\xe2'); time.sleep(30)",
                            output.append, raw_output=True, timeout=0.2)
        self.assertTrue(runner.wait(5).timed_out)
        self.assertEqual(b"".join(output), b"partial\xff\xe2")

    def test_missing_executable_completes_once(self):
        completed = []
        runner = Runner()
        runner.start(RunRequest(["/nonexistent/chaostic-runner-test"]), on_complete=completed.append)
        self.runners.append(runner)
        result = runner.wait(5)
        self.assertEqual(result.returncode, 127)
        self.assertIsNotNone(result.error)
        self.assertEqual(completed, [result])
        runner.stop()
        self.assertIs(runner.wait(0), result)

    def test_timeout_retains_partial_output(self):
        output = []
        runner = self.start("import time; print('partial'); time.sleep(30)", output.append, timeout=0.2)
        result = runner.wait(5)
        self.assertTrue(result.timed_out)
        self.assertFalse(result.cancelled)
        self.assertIn("partial", "".join(output))
        self.assertNotEqual(result.returncode, 0)

    def test_large_output_is_drained_without_capture_limits(self):
        output = []
        runner = self.start("import os; os.write(1,b'x' * (2 * 1024 * 1024))", output.append)
        self.assertEqual(runner.wait(5).returncode, 0)
        self.assertEqual("".join(output), "x" * (2 * 1024 * 1024))

    def test_repeated_cancel_escalates_and_finishes_once(self):
        ready, completed = threading.Event(), []
        runner = self.start("import signal,time; signal.signal(signal.SIGINT,signal.SIG_IGN); "
                            "signal.signal(signal.SIGTERM,signal.SIG_IGN); print('ready'); time.sleep(30)",
                            lambda text: ready.set(), completed.append)
        self.assertTrue(ready.wait(3))
        callers = [threading.Thread(target=runner.stop) for _ in range(8)]
        started = time.monotonic()
        for caller in callers:
            caller.start()
        for caller in callers:
            caller.join()
        result = runner.wait(5)
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(result.returncode, -signal.SIGKILL)
        self.assertTrue(result.cancelled)
        self.assertEqual(completed, [result])
        self.assertFalse(runner.send_input("late"))
        self.assertFalse(runner._backend._thread.is_alive())

    def test_immediate_cancel_and_single_use(self):
        runner = self.start("import time; time.sleep(30)")
        runner.stop()
        self.assertTrue(runner.wait(5).cancelled)
        with self.assertRaises(RuntimeError):
            runner.start(RunRequest([sys.executable, "-c", "pass"]))

    def test_input_eof_and_interrupt(self):
        output = []
        runner = self.start("import sys; print(sys.stdin.read(),end='')", output.append)
        self.assertTrue(runner.send_input("héllo\n"))
        runner.close_input()
        self.assertFalse(runner.send_input("late"))
        self.assertEqual(runner.wait(5).returncode, 0)
        self.assertEqual("".join(output), "héllo\n")
        ready = threading.Event()
        runner = self.start("import signal,time,sys; signal.signal(signal.SIGINT,lambda *args:sys.exit(12)); "
                            "print('ready'); time.sleep(30)", lambda text: ready.set())
        self.assertTrue(ready.wait(3))
        runner.interrupt()
        result = runner.wait(5)
        self.assertEqual(result.returncode, 12)
        self.assertFalse(result.cancelled)

    def test_full_input_pipe_does_not_block_cancellation(self):
        runner = self.start("import time; time.sleep(30)")
        runner.send_input("x" * (1024 * 1024))
        with self.assertRaises(BufferError):
            runner.send_input("x" * (1024 * 1024))
        runner.stop()
        self.assertTrue(runner.wait(5).cancelled)

    @unittest.skipUnless(sys.platform.startswith("linux"), "uses /proc to distinguish zombies")
    def test_resistant_descendant_stopped_after_parent_exit(self):
        for close_output, cancel in ((False, False), (True, False), (False, True)):
            with self.subTest(close_output=close_output, cancel=cancel), tempfile.TemporaryDirectory() as directory:
                child_file = Path(directory) / "child.pid"
                child = ("import os,signal,time; signal.signal(signal.SIGINT,signal.SIG_IGN); "
                         "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                         f"open({str(child_file)!r},'w').write(str(os.getpid())); "
                         + ("os.close(1); os.close(2); " if close_output else "")
                         + "time.sleep(30)")
                parent = ("import subprocess,sys,time,pathlib; "
                          f"subprocess.Popen([sys.executable,'-c',{child!r}]); "
                          f"p=pathlib.Path({str(child_file)!r}); "
                          "\nwhile not p.exists(): time.sleep(0.01)\n")
                if cancel:
                    parent += "print('ready',flush=True)\ntime.sleep(30)\n"
                ready = threading.Event()
                runner = self.start(parent, lambda text, ready=ready: ready.set())
                if cancel:
                    self.assertTrue(ready.wait(3))
                    runner.stop()
                result = runner.wait(5)
                self.assertIsNotNone(result)
                if not cancel:
                    self.assertEqual(result.returncode, 0)
                self.assertEqual(result.cancelled, cancel)
                pid = int(child_file.read_text())
                state = Path(f"/proc/{pid}/stat")
                if state.exists():
                    self.assertEqual(state.read_text().split(") ")[1].split()[0], "Z")

    def test_output_callback_failure_still_cleans_up(self):
        completed = []

        def broken(text):
            raise RuntimeError("consumer failed")

        with self.assertLogs("core.backends.posix", level="ERROR"):
            runner = self.start("import time; print('ready'); time.sleep(30)", broken, completed.append)
            result = runner.wait(5)
        self.assertIn("consumer failed", result.error)
        self.assertEqual(completed, [result])
        self.assertFalse(runner._backend._thread.is_alive())

    def test_completion_callback_failure_does_not_leak_worker(self):
        calls = []

        def broken(result):
            calls.append(result)
            raise RuntimeError("completion failed")

        with self.assertLogs("core.backends.posix", level="ERROR"):
            runner = self.start("pass", complete=broken)
            result = runner.wait(5)
        self.assertEqual(calls, [result])
        self.assertEqual(result.returncode, 0)
        self.assertFalse(runner._backend._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
