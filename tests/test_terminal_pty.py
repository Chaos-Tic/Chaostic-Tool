"""Exercise actual POSIX terminal rendering without privileged startup or targets."""
import errno
import os
from pathlib import Path
import select
import signal
import struct
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

try:
    import fcntl
    import pty
    import termios
except ImportError:
    fcntl = None
    pty = None
    termios = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform.startswith('linux') and fcntl is not None and pty is not None and termios is not None, 'Linux terminal test')
class TerminalTests(unittest.TestCase):
    def drive(self, source, keys=b'', *, columns=80, rows=24, mode='light', send_after=b''):
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, columns, 0, 0))
        original = termios.tcgetattr(slave)
        env = dict(os.environ, TERM='xterm-256color', CHAOSTIC_THEME=mode, PYTHONUTF8='1')
        process = subprocess.Popen([sys.executable, '-u', '-c', source], cwd=ROOT,
                                   stdin=slave, stdout=slave, stderr=slave, env=env,
                                   start_new_session=True)
        data = bytearray()
        sent = False
        deadline = time.monotonic() + 8
        try:
            while time.monotonic() < deadline:
                if select.select([master], [], [], .05)[0]:
                    try:
                        part = os.read(master, 65536)
                    except OSError as exc:
                        if exc.errno == errno.EIO:
                            break
                        raise
                    data.extend(part)
                    if keys and not sent and b'\x1b[?1049h' in data and (not send_after or send_after in data):
                        # Send keys only after the full-screen application owns the terminal.
                        os.write(master, keys)
                        sent = True
                if process.poll() is not None:
                    break
            self.assertIsNotNone(process.poll(), 'Terminal application did not exit')
            self.assertEqual(process.returncode, 0, data.decode(errors='replace'))
            self.assertEqual(termios.tcgetattr(slave), original, 'Terminal settings were not restored')
            text = data.decode(errors='replace')
            self.assertIn('\x1b[?1049h', text)
            self.assertIn('\x1b[?1049l', text)
            self.assertNotIn('Traceback', text)
            return text
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)
            os.close(master)
            os.close(slave)

    def test_real_menu_sizes_restore_terminal_and_keep_keyboard_navigation(self):
        source = "from core.tui import MenuScreen; from chaostictool import MAIN_ENTRIES; print('CHOICE='+MenuScreen('Home',MAIN_ENTRIES,home=True).run())"
        for mode in ('light', 'dark'):
            for columns, rows in ((116, 40), (80, 24), (60, 20)):
                with self.subTest(mode=mode, columns=columns, rows=rows):
                    text = self.drive(source, b'\x1b[B\r', columns=columns, rows=rows, mode=mode)
                    self.assertIn('CHOICE=2', text)

    def test_local_execution_fullscreen_keeps_output_and_restores_terminal(self):
        source = '''
import sys,tempfile
from pathlib import Path
from core.executor import run_tool,ACTIVE_PROCS
with tempfile.TemporaryDirectory() as directory:
    output=Path(directory)/'demo.txt'
    rc=run_tool([sys.executable,'-c',"print('synthetic output')"],output,context={'wait':False,'tool':'Demo'})
    assert rc==0 and output.read_text()=='synthetic output\\n'
    assert not ACTIVE_PROCS
    print('SYNTHETIC_EXECUTION_OK')
'''
        self.assertIn('SYNTHETIC_EXECUTION_OK', self.drive(source, mode='dark'))

    def test_terminal_interrupt_saves_partial_output_and_reaps_child(self):
        source = """
import sys,tempfile
from pathlib import Path
from core.executor import run_tool,ACTIVE_PROCS
with tempfile.TemporaryDirectory() as directory:
    output=Path(directory)/'partial.txt'
    code="import signal,sys,time; signal.signal(signal.SIGINT,lambda *args: sys.exit(130)); print('STREAM_READY',flush=True); time.sleep(10)"
    rc=run_tool([sys.executable,'-u','-c',code],output,context={'wait':False,'tool':'Demo'})
    assert rc==130 and 'STREAM_READY' in output.read_text()
    assert not ACTIVE_PROCS
    print('INTERRUPT_CLEANUP_OK')
"""
        self.assertIn('INTERRUPT_CLEANUP_OK', self.drive(source, b'\x03', send_after=b'STREAM_READY'))

    def test_dumb_terminal_uses_the_plain_output_path(self):
        from core import scan_view
        with patch.object(sys.stdin, 'isatty', return_value=True), patch.object(sys.stdout, 'isatty', return_value=True), patch.dict(os.environ, TERM='dumb'):
            self.assertFalse(scan_view.available())


@unittest.skipUnless(sys.platform.startswith('linux') and fcntl is not None and pty is not None and termios is not None, 'Linux PTY backend test')
class PtyBackendTests(unittest.TestCase):
    """Headless contract for the PTY backend behind the neutral Runner.

    These prove what CI can prove without a real interactive tool or a human: the
    child gets a genuine controlling TTY (isatty + foreground group), inherits the
    requested window size, keystrokes are relayed and EOF honoured, a programmatic
    interrupt reaches the foreground group, and stop reaps a running child. The
    behaviours a user actually feels -- curses redraw, live resize, non-echoed
    sudo, msfconsole aborting on Ctrl-C -- still need a hands-on terminal run."""

    def _collector(self):
        lock = threading.Lock()
        buffer = bytearray()

        def sink(data):
            with lock:
                buffer.extend(data)

        def snapshot():
            with lock:
                return bytes(buffer)

        return sink, snapshot

    def _wait_for(self, snapshot, marker, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if marker in snapshot():
                return True
            time.sleep(0.02)
        return False

    def test_backend_gives_a_controlling_tty_and_relays_input_to_eof(self):
        from core.backends.pty import PtyBackend
        from core.runner import RunRequest, Runner
        sink, snapshot = self._collector()
        backend = PtyBackend(winsize=(30, 120))
        runner = Runner(backend)
        self.addCleanup(runner.stop)
        child = (
            "import os, sys, struct, fcntl, termios\n"
            "assert os.isatty(0) and os.isatty(1)\n"
            "assert os.tcgetpgrp(0) == os.getpgrp()\n"
            "ws = struct.unpack('HHHH', fcntl.ioctl(0, termios.TIOCGWINSZ, b'\\0' * 8))\n"
            "sys.stdout.write('ROWS=%d COLS=%d\\n' % (ws[0], ws[1])); sys.stdout.flush()\n"
            "sys.stdout.write('ECHO:' + sys.stdin.readline()); sys.stdout.flush()\n"
        )
        runner.start(RunRequest([sys.executable, '-u', '-c', child],
                                env=dict(os.environ, TERM='xterm-256color'),
                                raw_output=True), sink)
        self.assertTrue(self._wait_for(snapshot, b'ROWS='), snapshot())
        self.assertTrue(backend.send_input('hello\n'))
        backend.close_input()
        result = runner.wait(8)
        self.assertIsNotNone(result)
        self.assertEqual(result.returncode, 0, snapshot().decode(errors='replace'))
        text = snapshot().decode(errors='replace')
        self.assertIn('ROWS=30 COLS=120', text)
        self.assertIn('ECHO:hello', text)

    def test_backend_resize_tracks_a_new_window_size(self):
        from core.backends.pty import PtyBackend
        from core.runner import RunRequest, Runner
        sink, snapshot = self._collector()
        backend = PtyBackend(winsize=(24, 80))
        runner = Runner(backend)
        self.addCleanup(runner.stop)
        child = (
            "import os, sys, struct, fcntl, termios, signal\n"
            "signal.signal(signal.SIGWINCH, lambda *a: None)\n"
            "sys.stdout.write('READY\\n'); sys.stdout.flush()\n"
            "sys.stdin.readline()\n"
            "ws = struct.unpack('HHHH', fcntl.ioctl(0, termios.TIOCGWINSZ, b'\\0' * 8))\n"
            "sys.stdout.write('SIZE=%d x %d\\n' % (ws[0], ws[1])); sys.stdout.flush()\n"
        )
        runner.start(RunRequest([sys.executable, '-u', '-c', child], raw_output=True), sink)
        self.assertTrue(self._wait_for(snapshot, b'READY'), snapshot())
        backend.resize(40, 132)
        backend.send_input('go\n')
        result = runner.wait(8)
        self.assertIsNotNone(result)
        self.assertIn('SIZE=40 x 132', snapshot().decode(errors='replace'))

    def test_backend_interrupt_delivers_sigint_to_the_foreground_group(self):
        from core.backends.pty import PtyBackend
        from core.runner import RunRequest, Runner
        sink, snapshot = self._collector()
        backend = PtyBackend()
        runner = Runner(backend)
        self.addCleanup(runner.stop)
        child = (
            "import signal, sys, time\n"
            "signal.signal(signal.SIGINT, lambda *a: (sys.stdout.write('ABORTED\\n'), "
            "sys.stdout.flush(), sys.exit(3)))\n"
            "sys.stdout.write('READY\\n'); sys.stdout.flush()\n"
            "time.sleep(10)\n"
        )
        runner.start(RunRequest([sys.executable, '-u', '-c', child], raw_output=True), sink)
        self.assertTrue(self._wait_for(snapshot, b'READY'), snapshot())
        runner.interrupt()
        result = runner.wait(8)
        self.assertIsNotNone(result)
        self.assertEqual(result.returncode, 3)
        self.assertIn('ABORTED', snapshot().decode(errors='replace'))

    def test_backend_stop_cancels_and_reaps_a_running_child(self):
        from core.backends.pty import PtyBackend
        from core.runner import RunRequest, Runner
        sink, snapshot = self._collector()
        backend = PtyBackend()
        runner = Runner(backend)
        self.addCleanup(runner.stop)
        child = "import sys, time; sys.stdout.write('UP\\n'); sys.stdout.flush(); time.sleep(30)"
        runner.start(RunRequest([sys.executable, '-u', '-c', child], stop_grace=0.2,
                                raw_output=True), sink)
        self.assertTrue(self._wait_for(snapshot, b'UP'), snapshot())
        runner.stop()
        result = runner.wait(8)
        self.assertIsNotNone(result)
        self.assertTrue(result.cancelled)
