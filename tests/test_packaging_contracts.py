"""Native packages must ship one application with both supported interfaces."""
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from core.version import VERSION

ROOT = Path(__file__).resolve().parents[1]


class PackagingMetadataTests(unittest.TestCase):
    def test_public_metadata_uses_gpl_3_or_later(self):
        license_id = 'GPL-3.0-or-later'
        license_text = (ROOT / 'LICENSE').read_text()
        self.assertIn('SPDX-License-Identifier: GPL-3.0-or-later', license_text)
        self.assertTrue(license_text.endswith(
            (ROOT / 'docs/licenses/GPL-3.0-only.txt').read_text()
        ))
        self.assertIn('GPL-3.0-or-later', (ROOT / 'README.md').read_text())
        self.assertIn('GPL-3.0-or-later', (ROOT / 'docs/THIRD_PARTY.md').read_text())
        self.assertIn("license=('GPL-3.0-or-later')",
                      (ROOT / 'packaging/arch/PKGBUILD').read_text())
        self.assertIsNotNone(re.search(
            rf'^License:\s+{re.escape(license_id)}$',
            (ROOT / 'packaging/fedora/chaostictool.spec').read_text(),
            re.M,
        ))
        self.assertIn('License: GPL-3+\n',
                      (ROOT / 'packaging/debian/copyright').read_text())
        self.assertIn('set(CPACK_RPM_PACKAGE_LICENSE "GPL-3.0-or-later")',
                      (ROOT / 'CMakeLists.txt').read_text())
        self.assertTrue((ROOT / 'TRADEMARKS.md').is_file())
        contributing = (ROOT / 'CONTRIBUTING.md').read_text()
        self.assertIn('written agreement', contributing)
        self.assertIn('relicense', contributing)

    def test_source_recipes_share_name_version_and_runtime(self):
        arch = (ROOT / 'packaging/arch/PKGBUILD').read_text()
        rpm = (ROOT / 'packaging/fedora/chaostictool.spec').read_text()
        deb = (ROOT / 'packaging/debian/control').read_text()
        self.assertIn('pkgname=chaostictool\n', arch)
        self.assertIn(f'pkgver={VERSION}\n', arch)
        self.assertRegex(rpm, rf'Version:\s+{re.escape(VERSION)}\n')
        self.assertTrue((ROOT / 'packaging/debian/changelog').read_text().startswith(f'chaostictool ({VERSION}-'))
        self.assertEqual(re.findall(r'^Package: (.+)$', deb, re.M), ['chaostictool'])
        for recipe in (arch, rpm, deb):
            for dependency in ('rich', 'prompt'):
                self.assertIn(dependency, recipe)
        for recipe in (arch, deb):
            for dependency in ('pyside6', 'psutil', 'dns', 'py7zr', 'pyte'):
                self.assertIn(dependency, recipe)
        self.assertIn('CHAOSTIC_BUNDLE_DIR=', rpm)
        self.assertIn('sha256sum -c %{SOURCE2}', rpm)
        self.assertNotIn('python3-py7zr', rpm)
        for obsolete in ('packaging/arch/PKGBUILD-cli', 'packaging/arch/PKGBUILD-desktop',
                         'packaging/fedora/chaostictool-desktop.spec'):
            self.assertFalse((ROOT / obsolete).exists(), obsolete)
        self.assertNotIn('chaostictool-desktop.spec', (ROOT / '.copr/Makefile').read_text())

    def test_every_package_ships_the_uninstaller_and_notifies_on_removal(self):
        cmake = (ROOT / 'CMakeLists.txt').read_text()
        self.assertIn('RENAME chaostictool-uninstall', cmake,
                      'CMake must install uninstall.sh on PATH as chaostictool-uninstall')

        prerm = (ROOT / 'packaging/debian/prerm').read_text()
        postrm = (ROOT / 'packaging/debian/postrm').read_text()
        preun = (ROOT / 'packaging/fedora/preun.sh').read_text()
        spec = (ROOT / 'packaging/fedora/chaostictool.spec').read_text()
        pkgbuild = (ROOT / 'packaging/arch/PKGBUILD').read_text()
        archinstall = (ROOT / 'packaging/arch/chaostictool.install').read_text()

        # Debian maintainer scripts are picked up by debhelper (source/PPA) and by
        # CPack via CONTROL_EXTRA; they fire on real removal, not on upgrade.
        self.assertIn('"$1" = remove', prerm)
        self.assertIn('"$1" = purge', postrm)
        # rpm %preun and the CPack preun file both guard on the removal count.
        self.assertIn('"$1" = 0', preun)
        self.assertRegex(spec, r'(?s)%preun.*?/var/lib/chaostictool/manifest')
        self.assertIn('%{_bindir}/chaostictool-uninstall', spec)
        # Arch wires a pacman scriptlet with pre_remove.
        self.assertIn("install='chaostictool.install'", pkgbuild)
        self.assertIn('pre_remove()', archinstall)

        # Every notice points at the manifest and the uninstaller, and NONE of the
        # scriptlets auto-removes anything (notify-only is the safe behaviour).
        for text in (prerm, postrm, preun, spec, archinstall):
            self.assertIn('/var/lib/chaostictool/manifest', text)
            self.assertIn('chaostictool-uninstall', text)
        for script in (prerm, postrm, preun, archinstall):
            for destructive in ('rm -rf', 'rm -f', 'pacman -R', 'apt-get purge',
                                 'apt remove', 'dnf remove'):
                self.assertNotIn(destructive, script,
                                 'maintainer scripts must notify, never auto-delete')

    def test_aur_publish_ships_the_pacman_scriptlet_next_to_the_pkgbuild(self):
        pkgbuild = (ROOT / 'packaging/arch/PKGBUILD').read_text()
        aur = (ROOT / 'packaging/arch/aur.sh').read_text()
        match = re.search(r"^install='([^']+)'$", pkgbuild, re.M)
        self.assertIsNotNone(match, 'PKGBUILD must wire the pacman scriptlet')
        scriptlet = match.group(1)
        self.assertTrue((ROOT / 'packaging/arch' / scriptlet).is_file(), scriptlet)
        # makepkg --printsrcinfo (and every user's makepkg) fails when install=
        # names a file that is not next to the PKGBUILD, so the AUR update must
        # copy the scriptlet into the clone and commit it together with PKGBUILD.
        self.assertIn(f'packaging/arch/{scriptlet}', aur)
        self.assertRegex(aur, rf'cp [^\n]*"\$work/aur/{re.escape(scriptlet)}"')
        self.assertRegex(aur, rf'(?m)^git add [^\n]*\b{re.escape(scriptlet)}\b[^\n]*\.SRCINFO')

    @unittest.skipUnless(sys.platform.startswith('linux') and shutil.which('cmake'),
                         'Native package staging requires Linux and CMake')
    def test_staged_install_and_cpack_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            for frozen in (False, True):
                with self.subTest(frozen=frozen):
                    build = work / ('frozen' if frozen else 'source')
                    command = ['cmake', '-S', str(ROOT), '-B', str(build), '-DCMAKE_INSTALL_PREFIX=/usr']
                    if frozen:
                        if os.name == 'nt':
                            continue  # Frozen native packages target Linux and query glibc.
                        bundle = work / 'bundle'
                        bundle.mkdir()
                        (bundle / 'ChaosticTool').write_text('#!/bin/sh\nexit 0\n')
                        command.extend([f'-DCHAOSTIC_BUNDLE_DIR={bundle}', '-DCMAKE_INSTALL_LIBDIR=lib64'])
                    subprocess.run(command, check=True, capture_output=True, text=True)
                    config = (build / 'CPackConfig.cmake').read_text()
                    self.assertIn(f'set(CPACK_PACKAGE_VERSION "{VERSION}")', config)
                    self.assertIn('set(CPACK_PACKAGE_NAME "chaostictool")', config)
                    self.assertIn('CPACK_DEBIAN_PACKAGE_REPLACES "chaostictool-desktop (<< 2.0.0)"', config)
                    # The uninstaller and its removal-time notices travel with the package.
                    self.assertIn('packaging/debian/prerm', config)
                    self.assertIn('packaging/debian/postrm', config)
                    self.assertIn('CPACK_RPM_PRE_UNINSTALL_SCRIPT_FILE', config)
                    # Even a frozen GUI still ships a Python CLI requiring both libraries.
                    for dependency in ('python3-rich', 'python3-prompt-toolkit'):
                        self.assertIn(dependency, config)
                    stage = build / 'stage'
                    subprocess.run(['cmake', '--install', str(build)], check=True,
                                   env=dict(os.environ, DESTDIR=str(stage)), capture_output=True, text=True)
                    for relative in ('bin/chaostictool', 'bin/chaostictool-desktop',
                                     'bin/chaostictool-uninstall',
                                     'share/chaostictool/chaostictool.py', 'share/chaostictool/core/version.py',
                                     'share/applications/chaostictool-desktop.desktop',
                                     'share/licenses/chaostictool/LICENSE'):
                        self.assertTrue((stage / 'usr' / relative).is_file(), relative)
                    if frozen:
                        self.assertTrue((stage / 'usr/lib64/chaostictool-desktop/ChaosticTool').is_file())
                        self.assertIn('/usr/lib64/chaostictool-desktop/ChaosticTool',
                                      (stage / 'usr/bin/chaostictool-desktop').read_text())
                    else:
                        self.assertTrue((stage / 'usr/share/chaostictool/desktop/__init__.py').is_file())
                        self.assertTrue((stage / 'usr/share/chaostictool/chaostic_desktop.py').is_file())
                    self.assertFalse(list(stage.rglob('*.pyc')))


@unittest.skipIf(os.name == 'nt', 'PPA publication requires Bash on Ubuntu')
class PpaScriptTests(unittest.TestCase):
    def run_script(self, uid, upload):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            source = work / f'Chaostic-Tool-{VERSION}'
            source.mkdir()
            (source / 'LICENSE').write_text('fixture')
            archive = work / 'source.tar.gz'
            with tarfile.open(archive, 'w:gz') as output:
                output.add(source, arcname=source.name)
            commands = work / 'bin'
            commands.mkdir()
            fake = commands / 'fake'
            fake.write_text(f'#!{sys.executable}\n' + '''import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['CALLS'], 'a') as log:
    log.write(json.dumps([name, *args]) + '\\n')
if name == 'id':
    print(os.environ['TEST_UID'])
elif name == 'sudo':
    assert args[:2] == ['-n', 'env'], args
    os.execvp(args[1], args[1:])
elif name == 'gpg' and '--list-secret-keys' in args:
    print('fpr:::::::::0123456789ABCDEF0123456789ABCDEF01234567:')
elif name == 'dpkg-buildpackage':
    control = pathlib.Path('debian/control').read_text()
    assert 'Source: chaostictool\\n' in control
    assert 'Package: chaostictool\\n' in control
    assert 'Package: chaostictool-desktop' not in control
    header = pathlib.Path('debian/changelog').read_text().splitlines()[0]
    package, version, *_ = header.split()
    version = version.strip('()')
    pathlib.Path('..', f'{package}_{version}_source.changes').write_text('fixture')
''')
            fake.chmod(0o755)
            for name in ('id', 'sudo', 'apt-get', 'gpg', 'dpkg-buildpackage', 'dput'):
                (commands / name).symlink_to(fake)
            calls = work / 'calls'
            env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ['PATH'],
                       CALLS=str(calls), TEST_UID=str(uid), PPA_UPLOAD=str(int(upload)),
                       PPA_SIGNING_KEY='fixture' if upload else '', PPA_ORIG_TARBALL=str(archive),
                       PPA_OUT='output', PPA_TARGETS='resolute:26.04 stonking:26.10',
                       PPA_ORIG_UPLOADED='', PPA_REVISION='1')
            result = subprocess.run(['bash', str(ROOT / 'packaging/debian/ppa.sh'), VERSION],
                                    cwd=work, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            artifacts = sorted(path.name for path in (work / 'output').iterdir())
            return [json.loads(line) for line in calls.read_text().splitlines()], artifacts

    def test_non_root_runner_publishes_one_source_per_series(self):
        calls, artifacts = self.run_script(uid=1000, upload=True)
        self.assertEqual(sum(call[0] == 'sudo' for call in calls), 2)
        builds = [call for call in calls if call[0] == 'dpkg-buildpackage']
        self.assertEqual(len(builds), 2)
        self.assertIn('-sa', builds[0])
        self.assertIn('-sd', builds[1])
        self.assertEqual(sum(call[0] == 'dput' for call in calls), 2)
        self.assertEqual(len(artifacts), 3)
        self.assertTrue(all(name.startswith('chaostictool_') for name in artifacts))

    def test_root_container_can_build_unsigned_without_upload(self):
        calls, _ = self.run_script(uid=0, upload=False)
        self.assertFalse(any(call[0] in ('sudo', 'gpg', 'dput') for call in calls))
        for call in calls:
            if call[0] == 'dpkg-buildpackage':
                self.assertIn('-us', call)
                self.assertIn('-uc', call)

    def test_old_split_publication_argument_is_rejected(self):
        result = subprocess.run(['bash', str(ROOT / 'packaging/debian/ppa.sh'), VERSION,
                                 'chaostictool-desktop'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
