"""Exercise actual POSIX terminal rendering without privileged startup or targets."""
import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import sys
import termios
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'posix', 'POSIX terminal test')
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
