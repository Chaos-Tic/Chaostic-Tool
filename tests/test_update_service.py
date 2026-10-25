"""Release checks and downloads must never trigger an unverified installation."""
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core import update_service as service


@contextmanager
def response(content):
    yield io.BytesIO(content)


class UpdateServiceTests(unittest.TestCase):
    def test_editions_are_independent_and_prereleases_rejected(self):
        payload = {"tag_name": "desktop-v1.2.0", "body": '<!-- chaostictool-versions: {"cli":"1.4.0","desktop":"1.1.5"} -->'}
        self.assertEqual(service.release_versions(payload), {"cli": "1.4.0", "desktop": "1.2.0"})
        unified = {"tag_name": "v2.0.0"}
        self.assertEqual(service.release_versions(unified), {"cli": "2.0.0", "desktop": "2.0.0"})
        with self.assertRaises(ValueError):
            service.release_versions({**payload, "prerelease": True})
        with self.assertRaises(ValueError):
            service.release_versions({**payload, "body": '<!-- chaostictool-versions: {"cli":"; touch bad"} -->'})

    def test_one_automatic_request_per_day_but_manual_can_refresh(self):
        data = json.dumps({"tag_name": "desktop-v1.2.0", "body": '<!-- chaostictool-versions: {"cli":"1.4.0"} -->'}).encode()
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "urlopen", side_effect=lambda *a, **kw: response(data)) as fetch, patch.object(service.time, "time", return_value=100000):
            cache = Path(directory) / "cache.json"
            self.assertTrue(service.check("cli", "1.3.2", cache)["available"])
            self.assertFalse(service.check("cli", "1.4.0", cache)["available"])
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(fetch.call_args.args[0].full_url, service.API)
            service.check("desktop", "1.1.5", cache, force=True)
            self.assertEqual(fetch.call_count, 2)
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "urlopen", side_effect=OSError("offline")) as fetch:
            cache = Path(directory) / "cache.json"
            self.assertTrue(service.check("cli", "1.4.0", cache)["error"])
            service.check("cli", "1.4.0", cache)
            self.assertEqual(fetch.call_count, 1)

    def test_unified_release_uses_the_same_tag_for_both_editions(self):
        data = json.dumps({"tag_name": "v2.1.0"}).encode()
        with tempfile.TemporaryDirectory() as directory, patch.object(
            service, "urlopen", side_effect=lambda *a, **kw: response(data)
        ):
            cache = Path(directory) / "cache.json"
            desktop = service.check("desktop", "2.0.0", cache, force=True)
            self.assertEqual(desktop["tag"], "v2.1.0")
            self.assertEqual(desktop["url"], service.REPOSITORY + "/releases/tag/v2.1.0")

    def test_invalid_or_old_cache_is_refreshed(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "urlopen", side_effect=lambda *a, **kw: response(b'{"tag_name":"v1.4.0"}')) as fetch:
            cache = Path(directory) / "cache.json"
            cache.write_text('{"checked_at":0,"versions":null}')
            self.assertEqual(service.check("cli", "1.3.2", cache)["version"], "1.4.0")
            self.assertEqual(fetch.call_count, 1)

    def test_source_checkout_is_never_treated_as_system_package(self):
        with patch.object(service.subprocess, "run") as run:
            self.assertEqual(service.native_commands("chaostictool", Path("/home/operator/project/main.py")), [])
            run.assert_not_called()

    @unittest.skipUnless(__import__('os').name == 'posix', 'Linux package managers use POSIX paths')
    def test_native_package_uses_its_manager(self):
        with patch.object(service.shutil, "which", return_value="/usr/bin/dpkg-query"), patch.object(service.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="install ok installed")):
            self.assertEqual(service.native_commands("chaostictool", Path("/usr/share/chaostictool/chaostictool.py")), [["apt-get", "update"], ["apt-get", "install", "--only-upgrade", "chaostictool"]])
        with patch.object(service.shutil, "which", side_effect=lambda name: "/usr/bin/rpm" if name in ("rpm", "dnf") else None), patch.object(service.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="")):
            self.assertEqual(service.native_commands("chaostictool-desktop", Path("/usr/libexec/chaostictool-desktop/ChaosticTool")), [["dnf", "upgrade", "--refresh", "chaostictool-desktop"]])

    def test_download_requires_correct_digest_and_exact_filename(self):
        payload = b"test installer bytes, never executed"
        filename = "installer.exe"
        checksum = (hashlib.sha256(payload).hexdigest()+"  "+filename+"\n").encode()
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "urlopen", side_effect=[response(checksum), response(payload)]):
            path = service.download_verified("desktop-v1.2.0", filename, Path(directory))
            self.assertEqual(path.read_bytes(), payload)
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "urlopen", side_effect=[response(checksum), response(b"tampered")]):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                service.download_verified("desktop-v1.2.0", filename, Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "urlopen", return_value=response(checksum.replace(b"installer.exe", b"different.exe"))):
            with self.assertRaises(ValueError):
                service.download_verified("desktop-v1.2.0", filename, Path(directory))
        with self.assertRaises(ValueError):
            service.download_verified("desktop-v1.2.0", "../outside", Path("/tmp"))

    def test_cancelled_download_is_discarded(self):
        payload = b"installer"
        checksum = (hashlib.sha256(payload).hexdigest()+"  installer.exe").encode()
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "urlopen", side_effect=[response(checksum), response(payload)]):
            with self.assertRaises(InterruptedError):
                service.download_verified("desktop-v1.2.0", "installer.exe", Path(directory), cancelled=lambda: True)
            self.assertEqual(list(Path(directory).iterdir()), [])

    @unittest.skipUnless(__import__('os').name == 'posix', 'AppImage is a Linux distribution format')
    def test_appimage_replacement_preserves_previous_version_and_rolls_back_on_error(self):
        with tempfile.TemporaryDirectory() as directory:
            original, downloaded = Path(directory)/'current.AppImage', Path(directory)/'new.AppImage'
            original.write_bytes(b'old'); original.chmod(0o755)
            downloaded.write_bytes(b'new verified bytes')
            backup = service.replace_appimage(downloaded, original)
            self.assertEqual(original.read_bytes(), b'new verified bytes')
            self.assertEqual(backup.read_bytes(), b'old')
            with patch.object(service.os, 'replace', side_effect=OSError('rename failed')):
                with self.assertRaises(OSError):
                    service.replace_appimage(downloaded, original)
            self.assertEqual(original.read_bytes(), b'new verified bytes')
            self.assertEqual(list(Path(directory).glob('.chaostic-update-*')), [])
