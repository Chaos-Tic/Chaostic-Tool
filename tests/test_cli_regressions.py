"""Local-only CLI regressions; no external tools or privileged installs."""
import importlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == 'nt', 'CLI requires POSIX; run on Linux')
class CliRegressions(unittest.TestCase):
    def test_ipv6_target_and_url_keep_the_complete_host(self):
        from core import target
        with tempfile.TemporaryDirectory() as directory, patch.object(target, 'TARGETS_ROOT', Path(directory)), patch.dict(target.TARGET, clear=False):
            target.set_target(host='2001:db8::1', port='8443')
            self.assertEqual(target.TARGET['host'], '2001:db8::1')
            self.assertEqual(target.TARGET['url'], 'https://[2001:db8::1]:8443')
            target.set_target(url='https://[::1]:8443/path')
            self.assertEqual(target.TARGET['host'], '::1')
            target.set_target(host='[::1]:8080', port='8080')
            self.assertEqual(target.TARGET['url'], 'http://[::1]:8080')

    def test_all_cli_modules_import(self):
        for path in (ROOT / 'modules').glob('[0-9]*.py'):
            with self.subTest(module=path.stem):
                self.assertTrue(callable(importlib.import_module('modules.' + path.stem).run))

    def test_output_without_newline_is_saved(self):
        from core import executor
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output.txt'
            with patch.object(executor.console, 'print'):
                rc = executor.run_tool([sys.executable, '-c',
                    "import sys; sys.stdout.buffer.write(b'first\\nlast\\xff')"], output)
            self.assertEqual(rc, 0)
            self.assertEqual(output.read_text(encoding='utf-8'), 'first\nlast\ufffd')
            self.assertEqual(executor.ACTIVE_PROCS, [])

    def test_nonzero_exit_and_partial_output_are_preserved(self):
        from core import executor
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output.txt'
            with patch.object(executor.console, 'print'):
                rc = executor.run_tool([sys.executable, '-c',
                    "import sys; sys.stdout.write('failure details'); sys.exit(7)"], output)
            self.assertEqual(rc, 7)
            self.assertEqual(output.read_text(), 'failure details')

    def test_secret_prompt_is_masked_but_process_receives_original(self):
        from core import ui

        secret = 'unique-private-password'
        panels = []
        tool = {'name': 'Fixture', 'binary': sys.executable,
                'category': 'passwords', 'output_dir': 'passwords'}
        preset = {'label': 'Secret fixture', 'cmd': [sys.executable, '-c', 'pass',
                                                    '{passwd}'],
                  'prompt': {'passwd': 'Password'}, 'output': None}

        class FakeConsole:
            def print(self, value):
                panels.append(value)

            def input(self, _prompt):
                return 'y'

        def panel(renderable, *args, **kwargs):
            panels.append(renderable)
            return renderable

        with patch.object(ui, 'ask', return_value=secret), \
                patch.object(ui, 'console', FakeConsole()), \
                patch.object(ui, 'Panel', side_effect=panel), \
                patch.object(ui.tui, 'available', return_value=False), \
                patch.object(ui, 'resolve_tool_binary', return_value=sys.executable), \
                patch.object(ui.executor, 'run_tool') as run:
            ui.run_preset(tool, preset, pause_after=False)

        args, kwargs = run.call_args
        self.assertIn(secret, args[0])
        self.assertEqual(kwargs['redactions'], [secret])
        self.assertNotIn(secret, ' '.join(str(value) for value in panels))
        self.assertIn('[redacted]', ' '.join(str(value) for value in panels))

    def test_uninstall_restores_tor_and_proxy_backups(self):
        # Exercise the actual manifest parser/removal/restoration code in a
        # temporary filesystem. Never run the real uninstaller as root.
        script = (ROOT / 'uninstall.sh').read_text()
        block = script[script.index('declare -a M_FILES=()'):script.index('echo -e "\\n${CYAN}[2]')]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            etc = root / 'etc'
            (etc / 'tor').mkdir(parents=True)
            for relative in ('tor/torrc', 'proxychains.conf', 'proxychains4.conf'):
                original = etc / relative
                original.write_text('modified')
                original.with_name(original.name + '.chaostictool.bak').write_text('original')
            (root / 'manifest').write_text('torrc:/etc/tor/torrc\nproxychains:/etc/proxychains.conf\nproxychains:/etc/proxychains4.conf\n')
            block = block.replace('/etc/', str(etc) + '/')
            harness = 'set -eu\nREMOVED=0\n_rm_file() { rm -f -- "$1"; }\n' + block
            env = dict(os.environ, MANIFEST=str(root / 'manifest'),
                       CYAN='', NC='', DIM='', GREEN='')
            subprocess.run(['bash', '-c', harness], env=env, check=True, capture_output=True)
            for relative in ('tor/torrc', 'proxychains.conf', 'proxychains4.conf'):
                original = etc / relative
                self.assertEqual(original.read_text(), 'original')
                self.assertFalse(original.with_name(original.name + '.chaostictool.bak').exists())

    def test_installer_help_and_invalid_option(self):
        result = subprocess.run(['bash', str(ROOT / 'install.sh'), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--profile', result.stdout)
        result = subprocess.run(['bash', str(ROOT / 'install.sh'), '--invalid-audit-option'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
