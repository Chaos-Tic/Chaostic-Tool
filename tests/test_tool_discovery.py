"""Reproduce GUI launch with a PATH that omits CLI-installed tools."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from desktop.backends import bridge_command
from desktop.catalog import find_executable, native_command
from desktop.packages import extract_archive
from desktop.tool_paths import resolve_tool


class ArchiveDependencyTests(unittest.TestCase):
    def test_tar_install_does_not_import_7z_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root/'tool.tar.gz'
            with tarfile.open(archive, 'w:gz') as stream:
                member = tarfile.TarInfo('tool'); member.size = 2
                stream.addfile(member, io.BytesIO(b'ok'))
            with patch.dict(sys.modules, {'py7zr': None}):
                extract_archive(archive, root/'out')
            self.assertEqual((root/'out/tool').read_bytes(), b'ok')


@unittest.skipIf(os.name == 'nt', 'POSIX user installations')
class LinuxDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'HOME': str(self.root), 'PATH': '/usr/bin:/bin',
                                         'SUDO_USER': '', 'GOBIN': '', 'GOPATH': '',
                                         'CARGO_HOME': '', 'PIPX_BIN_DIR': ''})
        self.env.start()

    def tearDown(self):
        self.env.stop(); self.temp.cleanup()

    def binary(self, relative, output='fixture', code=0):
        path = self.root/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'#!/bin/sh\nprintf "%s\\n" "{output}"\nexit {code}\n')
        path.chmod(0o755)
        return str(path)

    def test_all_cli_user_directories_and_executable_bit(self):
        for suffix in ('.local/bin', 'go/bin', '.local/share/go/bin', '.cargo/bin'):
            path = self.binary(suffix+'/chaostic-fixture')
            self.assertEqual(resolve_tool(['chaostic-fixture']), path)
            Path(path).chmod(0o644)
            self.assertIsNone(resolve_tool(['chaostic-fixture']))

    def test_alternative_name_and_preserved_python_shebang(self):
        path = self.binary('.local/bin/impacket-fixture.py')
        tool = dict(key='fixture', mode='native', binary='missing-fixture',
                    binary_alternatives=['impacket-fixture.py'])
        self.assertEqual(find_executable(tool), path)
        self.assertEqual(native_command(tool), [path])

    def test_wrong_httpx_does_not_shadow_projectdiscovery(self):
        wrong = self.binary('system/httpx', 'Python HTTP client')
        right = self.binary('go/bin/httpx', 'ProjectDiscovery -title', 1)
        with patch.dict(os.environ, {'PATH': str(Path(wrong).parent)+':/usr/bin:/bin'}):
            self.assertEqual(resolve_tool(['httpx'], ['projectdiscovery']), right)

    def test_standalone_bridge_finds_cli_tools_without_project_imports(self):
        path = self.binary('.cargo/bin/chaostic-fixture')
        request = {'op': 'inventory', 'tools': {'fixture': ['chaostic-fixture']}}
        command = bridge_command({'backend': 'local'})
        result = subprocess.run(command, cwd=self.root, input=json.dumps(request)+'\n',
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['tools']['fixture'], path)

    def test_existing_cli_tool_skips_package_install_and_sudo(self):
        self.binary('go/bin/chaostic-fixture')
        request = {'op': 'run', 'argv': ['/must/not/run', 'fixture'], 'elevate': True,
                   'skip_installed': {'fixture': {'candidates': ['chaostic-fixture']}}}
        result = subprocess.run(bridge_command({'backend': 'local'}), cwd=self.root,
                                input=json.dumps(request)+'\n', capture_output=True,
                                text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('fixture', result.stdout)

    def test_mixed_install_only_passes_missing_tools_to_installer(self):
        self.binary('.local/bin/chaostic-fixture')
        request = {'op': 'run', 'cwd': str(self.root),
                   'argv': [sys.executable, '-c', 'import sys; print(sys.argv[1:])', 'present', 'missing'],
                   'skip_installed': {'present': {'candidates': ['chaostic-fixture']},
                                      'missing': {'candidates': ['chaostic-missing-fixture']}}}
        process = subprocess.Popen(bridge_command({'backend': 'local'}), cwd=self.root,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        try:
            process.stdin.write(json.dumps(request)+'\n'); process.stdin.flush()
            output = process.stdout.read()
            self.assertEqual(process.wait(timeout=10), 0, output)
            self.assertIn("['missing']", output)
            self.assertNotIn("['present', 'missing']", output)
        finally:
            if process.poll() is None: process.kill(); process.wait()
            process.stdin.close(); process.stdout.close()
