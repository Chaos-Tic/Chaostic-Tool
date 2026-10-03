"""Package commands are simulated; these tests never install system packages."""
import contextlib
import io
import subprocess
import sys
import unittest
from unittest.mock import patch

from desktop.backends import install_plan
from desktop import linux_install


class PackageTarget:
    def __init__(self, manager, available=(), installed=()):
        self.manager = manager
        self.available = set(available)
        self.installed = set(installed)
        self.commands = []
        self.failure = None
        self.confirm_install = True
        self.empty_available_success = False

    def which(self, name):
        binary = 'apt-get' if self.manager == 'apt' else self.manager
        return '/usr/bin/' + name if name == binary else None

    def run(self, command, **kwargs):
        self.commands.append(command)
        if self.failure and command[:len(self.failure)] == self.failure:
            raise subprocess.CalledProcessError(1, command)
        package = command[-1]
        code, output = 0, ''
        if command[0] in ('dpkg-query', 'rpm') or command[:2] == ['pacman', '-Q']:
            code = 0 if package in self.installed else 1
            output = 'installed' if code == 0 else ''
        elif command[0] == 'apt-cache' or command[:2] == ['pacman', '-Si'] or command[:3] == ['dnf', '-q', 'list']:
            code = 0 if package in self.available or self.empty_available_success else 1
            if package in self.available:
                output = ('Package: ' + package + '\n' if self.manager == 'apt'
                          else package + '.x86_64 1.0 repository\n')
        elif 'install' in command or command[:2] == ['pacman', '-S']:
            if self.confirm_install:
                self.installed.update(argument for argument in command if argument in self.available)
        self_test_env = kwargs.get('env', {})
        if self_test_env.get('LC_ALL') != 'C':
            raise AssertionError('Queries must use stable locale')
        return subprocess.CompletedProcess(command, code, output, '')


class LinuxInstallTests(unittest.TestCase):
    def invoke(self, target, keys):
        output = io.StringIO()
        with patch.object(linux_install.shutil, 'which', target.which), \
                patch.object(linux_install.subprocess, 'run', target.run), \
                patch.object(sys, 'argv', ['linux_install.py', *keys]), \
                contextlib.redirect_stdout(output):
            result = linux_install.main()
        return result, output.getvalue()

    def test_apt_resolves_kali_names_and_deduplicates_shared_packages(self):
        target = PackageTarget('apt', available=['dnsutils', 'impacket-scripts'])
        result, output = self.invoke(target, ['dig', 'secretsdump.py', 'psexec.py', 'dig'])
        self.assertEqual(result, 0, output)
        self.assertIn(['apt-get', 'update'], target.commands)
        self.assertIn(['apt-get', 'install', '-y', 'dnsutils', 'impacket-scripts'], target.commands)

    def test_pacman_names_use_official_packages_without_partial_upgrade(self):
        target = PackageTarget('pacman', available=['bind', 'python-impacket', 'metasploit'])
        result, output = self.invoke(target, ['dig', 'secretsdump.py', 'msfconsole'])
        self.assertEqual(result, 0, output)
        self.assertIn(['pacman', '-S', '--noconfirm', '--needed', 'bind', 'metasploit', 'python-impacket'], target.commands)
        self.assertIn(['pacman', '-Si', 'bind'], target.commands)
        self.assertFalse(any('-Sy' in command or '-Syu' in command for command in target.commands))

    def test_dnf_resolves_bind_utils(self):
        target = PackageTarget('dnf', available=['bind-utils', 'nmap'])
        result, output = self.invoke(target, ['dig', 'nmap'])
        self.assertEqual(result, 0, output)
        self.assertIn(['dnf', 'makecache', '-y'], target.commands)
        self.assertIn(['dnf', '-q', 'list', '--available', 'bind-utils'], target.commands)
        self.assertIn(['dnf', 'install', '-y', 'bind-utils', 'nmap'], target.commands)

    def test_available_packages_install_but_missing_selection_is_not_success(self):
        for manager in ('apt', 'pacman', 'dnf'):
            with self.subTest(manager=manager):
                target = PackageTarget(manager, available=['nmap'])
                result, output = self.invoke(target, ['nmap', 'tcpdump'])
                self.assertEqual(result, 2)
                self.assertEqual(target.installed, {'nmap'})
                self.assertIn('tcpdump', output)
                self.assertNotIn('Installation Linux terminée', output)

    def test_unmapped_tools_are_reported_without_running_commands(self):
        for manager in ('pacman', 'dnf'):
            with self.subTest(manager=manager):
                target = PackageTarget(manager)
                result, output = self.invoke(target, ['subfinder'])
                self.assertEqual(result, 2)
                self.assertIn('subfinder', output)
                self.assertEqual(target.commands, [])

    def test_empty_repository_output_never_confirms_availability(self):
        for manager in ('apt', 'dnf'):
            with self.subTest(manager=manager):
                target = PackageTarget(manager)
                target.empty_available_success = True
                result, output = self.invoke(target, ['nmap'])
                self.assertEqual(result, 2, output)
                self.assertFalse(any('install' in command for command in target.commands))

    def test_already_installed_packages_need_no_repository_entry(self):
        for manager in ('apt', 'pacman', 'dnf'):
            with self.subTest(manager=manager):
                target = PackageTarget(manager, installed=['nmap'])
                result, output = self.invoke(target, ['nmap'])
                self.assertEqual(result, 0, output)
                self.assertEqual(len(target.commands), 1)

    def test_install_and_metadata_errors_produce_failure(self):
        for manager, prefix in [('apt', ['apt-get', 'update']),
                                ('apt', ['apt-get', 'install']),
                                ('pacman', ['pacman', '-S']),
                                ('dnf', ['dnf', 'install'])]:
            with self.subTest(prefix=prefix):
                target = PackageTarget(manager, available=['nmap'])
                target.failure = prefix
                result, output = self.invoke(target, ['nmap'])
                self.assertEqual(result, 1)
                self.assertNotIn('Installation Linux terminée', output)

    def test_successful_transaction_must_confirm_installed_packages(self):
        for manager in ('apt', 'pacman', 'dnf'):
            with self.subTest(manager=manager):
                target = PackageTarget(manager, available=['nmap'])
                target.confirm_install = False
                result, output = self.invoke(target, ['nmap'])
                self.assertEqual(result, 1)
                self.assertIn('Installation non confirmée', output)

    def test_invalid_tools_and_unsupported_managers_never_install(self):
        for keys in ([], ['nmap; id'], ['--help'], ['unknown']):
            target = PackageTarget('apt')
            result, output = self.invoke(target, keys)
            self.assertEqual(result, 1, output)
            self.assertEqual(target.commands, [])
            with self.assertRaises(ValueError):
                install_plan(keys)
        result, output = self.invoke(PackageTarget('unsupported'), ['nmap'])
        self.assertEqual(result, 1)
        self.assertIn('apt, pacman ou dnf', output)

    def test_bridge_source_is_standalone_and_resolves_names_on_target(self):
        command = install_plan(['dig', 'secretsdump.py'])
        self.assertEqual(command[:3], ['python3', '-u', '-c'])
        self.assertEqual(command[4:], ['dig', 'secretsdump.py'])
        namespace = {'__name__': 'target_installer'}
        exec(compile(command[3], '<bridge-installer>', 'exec'), namespace)
        target = PackageTarget('dnf', available=['bind-utils'])
        with patch('shutil.which', target.which), patch('subprocess.run', target.run), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(namespace['install_tools'](['dig']), 0)
        self.assertIn(['dnf', 'install', '-y', 'bind-utils'], target.commands)


if __name__ == '__main__':
    unittest.main()
