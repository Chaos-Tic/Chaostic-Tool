"""Windows runner contracts; native process tests are skipped on other hosts."""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from ctypes import wintypes
from pathlib import Path
from unittest import mock

from core.backends.windows import WindowsBackend
from core.runner import Runner, RunRequest

ROOT = Path(__file__).resolve().parents[1]


class WindowsBackendContractTests(unittest.TestCase):
    def test_factory_selects_windows_without_loading_ui(self):
        with mock.patch("core.runner.os.name", "nt"):
            self.assertIsInstance(Runner()._backend, WindowsBackend)

    def test_import_does_not_load_ui_or_windows_dll_on_posix(self):
        code = """
import sys
class NoUI:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'rich', 'PySide6', 'PyQt6', 'desktop'}:
            raise AssertionError(fullname)
sys.meta_path.insert(0, NoUI())
from core.backends.windows import WindowsBackend
WindowsBackend()
"""
        subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True, timeout=5)

    def test_failed_supervision_is_not_retried_uncontained(self):
        completed = []
        runner = Runner(WindowsBackend())
        with (mock.patch("core.backends.windows.WindowsProcess", side_effect=OSError("job denied")) as create,
              self.assertLogs("core.backends.windows", level="ERROR")):
            runner.start(RunRequest(["never-run"]), on_complete=completed.append)
            result = runner.wait(5)
        self.assertIn("job denied", result.error)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(completed, [result])
        create.assert_called_once()

    def test_input_limit_includes_pending_overlapped_write(self):
        backend = WindowsBackend()
        backend._thread = mock.Mock()
        backend.send_input("x" * (1024 * 1024))
        process = mock.Mock()
        process.write.return_value = 0  # asynchronous write has not completed
        backend._write_input(process)
        with self.assertRaises(BufferError):
            backend.send_input("y")
        process.write.return_value = 65536
        backend._write_input(process)
        self.assertTrue(backend.send_input("y"))
        backend.stop()
        self.assertFalse(backend.send_input("late"))

    def test_eof_waits_for_pending_input(self):
        backend = WindowsBackend()
        backend._thread = mock.Mock()
        backend.send_input("hello")
        backend.close_input()
        process = mock.Mock()
        process.write.return_value = 0
        backend._write_input(process)
        process.close_input.assert_not_called()
        process.write.return_value = 5
        backend._write_input(process)
        process.close_input.assert_called_once()
        self.assertFalse(backend.send_input("late"))


@unittest.skipUnless(os.name == "nt", "native Windows Job Objects and pipes")
class WindowsRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runners = []
        self.handles = []
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL

    def tearDown(self):
        for runner in self.runners:
            runner.stop()
            self.assertIsNotNone(runner.wait(5), "runner leaked a worker")
        for handle in self.handles:
            self.kernel.CloseHandle(handle)

    def start(self, code, output=None, complete=None, **kwargs):
        runner = Runner()
        self.runners.append(runner)
        runner.start(RunRequest([sys.executable, "-u", "-X", "utf8", "-c", code],
                                stop_grace=0.1, **kwargs), output, complete)
        return runner

    def observe(self, pid):
        # Keep a handle to this exact process, avoiding PID-reuse races.
        handle = self.kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
        self.assertTrue(handle, ctypes.get_last_error())
        self.handles.append(handle)
        return handle

    def test_nonzero_merged_output_and_completion(self):
        output, completed = [], []
        runner = self.start("import sys; print('out'); print('err',file=sys.stderr); sys.exit(7)",
                            output.append, completed.append)
        result = runner.wait(5)
        self.assertEqual(result.returncode, 7)
        self.assertEqual("".join(output).replace("\r\n", "\n"), "out\nerr\n")
        self.assertFalse(result.cancelled or result.timed_out)
        self.assertIsNone(result.error)
        self.assertEqual(completed, [result])

    def test_partial_utf8_output_and_stdin_eof(self):
        ready, output = threading.Event(), []

        def receive(text):
            output.append(text)
            ready.set()

        runner = self.start("import os,sys; os.write(1,b'prompt:'); sys.stdin.readline(); "
                            "os.write(1,b'\\xe2'); sys.stdin.read(); "
                            "os.write(1,b'\\x82\\xac\\xff\\xe2')", receive)
        self.assertTrue(ready.wait(5))
        self.assertIsNone(runner.wait(0))
        self.assertTrue(runner.send_input("héllo\n"))
        time.sleep(0.05)
        runner.close_input()
        self.assertFalse(runner.send_input("late"))
        self.assertEqual(runner.wait(5).returncode, 0)
        self.assertEqual("".join(output), "prompt:€\ufffd\ufffd")

    def test_cwd_environment_and_literal_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            output = []
            literal = ' & echo unwanted | < > %PATH% "quoted" \\ '
            runner = Runner()
            self.runners.append(runner)
            runner.start(RunRequest([sys.executable, "-X", "utf8", "-c",
                "import json,os,sys; print(json.dumps([os.getcwd(),os.getenv('RUNNER_TEST'),sys.argv[1]]))",
                literal], cwd=directory, env={**os.environ, "RUNNER_TEST": "présent"}), output.append)
            self.assertEqual(runner.wait(5).returncode, 0)
            actual = json.loads("".join(output))
            self.assertEqual(Path(actual[0]), Path(directory))
            self.assertEqual(actual[1:], ["présent", literal])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_missing_executable_and_single_use(self):
        runner, completed = Runner(), []
        self.runners.append(runner)
        runner.start(RunRequest([r"C:\nonexistent\chaostic-runner-test.exe"]),
                     on_complete=completed.append)
        result = runner.wait(5)
        self.assertEqual(result.returncode, 127)
        self.assertIsNotNone(result.error)
        self.assertEqual(completed, [result])
        with self.assertRaises(RuntimeError):
            runner.start(RunRequest([sys.executable]))

    def test_timeout_retains_partial_output(self):
        output = []
        runner = self.start("import time; print('partial'); time.sleep(30)", output.append, timeout=1)
        result = runner.wait(5)
        self.assertTrue(result.timed_out)
        self.assertFalse(result.cancelled)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("partial", "".join(output))

    def test_large_output_and_utf8_input(self):
        output = []
        runner = self.start("import os,sys; os.write(1,b'x' * (2 * 1024 * 1024)); "
                            "print(sys.stdin.read(),end='')", output.append)
        runner.send_input("héllo\n")
        runner.close_input()
        self.assertEqual(runner.wait(10).returncode, 0)
        self.assertEqual("".join(output).replace("\r\n", "\n"), "x" * (2 * 1024 * 1024) + "héllo\n")

    def test_full_input_pipe_and_repeated_stop(self):
        ready, completed = threading.Event(), []
        runner = self.start("import signal,time; signal.signal(signal.SIGBREAK,signal.SIG_IGN); "
                            "print('ready'); time.sleep(30)", lambda text: ready.set(), completed.append)
        self.assertTrue(ready.wait(5))
        runner.send_input("x" * (1024 * 1024))
        with self.assertRaises(BufferError):
            runner.send_input("x" * (1024 * 1024))
        started = time.monotonic()
        callers = [threading.Thread(target=runner.stop) for _ in range(8)]
        for caller in callers:
            caller.start()
        for caller in callers:
            caller.join()
        result = runner.wait(5)
        self.assertLess(time.monotonic() - started, 3)
        self.assertTrue(result.cancelled)
        self.assertEqual(completed, [result])
        self.assertFalse(runner.send_input("late"))
        self.assertFalse(runner._backend._thread.is_alive())

    def test_immediate_stop(self):
        runner = self.start("import time; time.sleep(30)")
        runner.stop()
        self.assertTrue(runner.wait(5).cancelled)

    def test_descendants_terminated_after_exit_cancel_and_timeout(self):
        for action in ("exit", "cancel", "timeout"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as directory:
                child_file = Path(directory) / "child.pid"
                child = ("import json,os,signal,subprocess,sys,time; "
                         "signal.signal(signal.SIGBREAK,signal.SIG_IGN); "
                         "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'], "
                         "creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS); "
                         f"open({str(child_file)!r},'w').write(json.dumps([os.getpid(),p.pid])); "
                         "os.close(1); os.close(2); time.sleep(30)")
                parent = ("import subprocess,sys,pathlib,time; "
                          f"subprocess.Popen([sys.executable,'-c',{child!r}]); "
                          f"p=pathlib.Path({str(child_file)!r}); "
                          "\nwhile not p.exists() or not p.read_text(): time.sleep(0.01)\n"
                          "print(p.read_text(),flush=True)\nsys.stdin.readline()\n")
                if action != "exit":
                    parent += "time.sleep(30)\n"
                ready, output = threading.Event(), []

                def receive(text, output=output, ready=ready):
                    output.append(text)
                    if "\n" in "".join(output):
                        ready.set()

                runner = self.start(parent, receive, timeout=2 if action == "timeout" else None)
                self.assertTrue(ready.wait(5))
                handles = [self.observe(pid) for pid in json.loads("".join(output))]
                if action == "cancel":
                    runner.stop()
                elif action == "exit":
                    runner.send_input("finish\n")
                result = runner.wait(6)
                self.assertIsNotNone(result)
                self.assertEqual(result.cancelled, action == "cancel")
                self.assertEqual(result.timed_out, action == "timeout")
                self.assertIsNone(result.error)
                if action == "exit":
                    self.assertEqual(result.returncode, 0)
                for handle in handles:
                    self.assertEqual(self.kernel.WaitForSingleObject(handle, 2000), 0,
                                     "descendant survived job termination")

    def test_job_closes_if_supervisor_crashes(self):
        with tempfile.TemporaryDirectory() as directory:
            pid_file, release_file = Path(directory) / "child.pid", Path(directory) / "release"
            child = ("import os,time; "
                     f"open({str(pid_file)!r},'w').write(str(os.getpid())); time.sleep(30)")
            supervisor = ("import os,sys,time,pathlib; from core.runner import Runner,RunRequest; "
                          f"r=Runner(); r.start(RunRequest([sys.executable,'-c',{child!r}])); "
                          f"p=pathlib.Path({str(release_file)!r}); "
                          "\nwhile not p.exists(): time.sleep(0.01)\nos._exit(0)\n")
            process = subprocess.Popen([sys.executable, "-c", supervisor], cwd=ROOT)
            try:
                deadline = time.monotonic() + 5
                while (not pid_file.exists() or not pid_file.read_text()) and time.monotonic() < deadline:
                    time.sleep(0.02)
                handle = self.observe(int(pid_file.read_text()))
                release_file.touch()
                self.assertEqual(process.wait(5), 0)
                self.assertEqual(self.kernel.WaitForSingleObject(handle, 2000), 0)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(5)

    def test_callback_failure_cleans_up_and_completes_once(self):
        completed = []

        def broken(text):
            raise RuntimeError("consumer failed")

        with self.assertLogs("core.backends.windows", level="ERROR"):
            runner = self.start("import time; print('ready'); time.sleep(30)", broken, completed.append)
            result = runner.wait(5)
        self.assertIn("consumer failed", result.error)
        self.assertEqual(completed, [result])
        self.assertFalse(runner._backend._thread.is_alive())

    def test_inherited_stdin_is_not_queued(self):
        runner = self.start("pass", inherit_stdin=True)
        self.assertFalse(runner.send_input("not queued"))
        runner.close_input()
        self.assertEqual(runner.wait(5).returncode, 0)

    def test_inherited_redirected_stdin_reaches_child(self):
        child = "import sys; print(sys.stdin.read(),end='')"
        supervisor = ("import sys; from core.runner import Runner,RunRequest; r=Runner(); "
                      f"r.start(RunRequest([sys.executable,'-X','utf8','-c',{child!r}],inherit_stdin=True),"
                      "lambda text:sys.stdout.buffer.write(text.encode('utf-8'))); "
                      "r.close_input(); assert not r.send_input('unwanted'); "
                      "result=r.wait(5); r.stop(); r.wait(5); assert result.returncode == 0")
        process = subprocess.run([sys.executable, "-X", "utf8", "-c", supervisor],
                                 cwd=ROOT, input="héllo\n".encode(), capture_output=True,
                                 check=False, timeout=15)
        self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", "replace"))
        self.assertEqual(process.stdout.decode("utf-8").replace("\r\n", "\n"), "héllo\n")

    def test_interrupt_in_shared_console_is_not_cancellation(self):
        if hasattr(ctypes.WinDLL("ntdll"), "wine_get_version"):
            self.skipTest("Wine CTRL_BREAK also exits a plain subprocess with status 1; requires native Windows")
        child = ("import signal,sys,time; signal.signal(signal.SIGBREAK,lambda *args:sys.exit(12)); "
                 "print('ready',flush=True)\nwhile True: time.sleep(0.01)\n")
        supervisor = ("import json,sys,threading; from core.runner import Runner,RunRequest; "
                      "ready=threading.Event(); r=Runner(); "
                      f"r.start(RunRequest([sys.executable,'-u','-c',{child!r}]),lambda text:ready.set()); "
                      "assert ready.wait(5); r.interrupt(); result=r.wait(5); "
                      "r.stop(); r.wait(5); assert result is not None; "
                      "print(json.dumps([result.returncode,result.cancelled,result.error]))")
        startup = subprocess.STARTUPINFO()
        startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        process = subprocess.run([sys.executable, "-c", supervisor], check=False, cwd=ROOT,
                                 creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup,
                                 capture_output=True, timeout=15)
        self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", "replace"))
        self.assertEqual(json.loads(process.stdout), [12, False, None])

    def test_repeated_runs_release_kernel_handles(self):
        self.kernel.GetCurrentProcess.restype = wintypes.HANDLE
        self.kernel.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.GetProcessHandleCount.restype = wintypes.BOOL

        def count():
            value = wintypes.DWORD()
            self.assertTrue(self.kernel.GetProcessHandleCount(self.kernel.GetCurrentProcess(),
                                                             ctypes.byref(value)))
            return value.value

        self.assertEqual(self.start("pass").wait(5).returncode, 0)
        baseline = count()
        for _ in range(10):
            result = self.start("pass").wait(5)
            self.assertEqual(result.returncode, 0)
            self.assertIsNone(result.error)
        self.assertLessEqual(count(), baseline + 2)


if __name__ == "__main__":
    unittest.main()
