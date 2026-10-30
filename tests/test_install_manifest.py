"""The install manifest records exactly what ChaosticTool installed.

These tests prove the two load-bearing safety properties of the
record-what-you-install / reverse-exactly design:

* a tool that is already present is never (re)installed and never recorded, so
  the uninstaller can only ever remove what ChaosticTool itself placed;
* no installer primitive overwrites — or records — a pre-existing file it did
  not create.

They are pure Python, need no root and touch no real system path.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import installer, manifest


class ManifestModuleTests(unittest.TestCase):
    def test_resolve_path_prefers_env_then_root_default_then_nothing(self):
        with patch.dict(os.environ, {"CHAOSTICTOOL_MANIFEST": "/tmp/explicit"}):
            self.assertEqual(manifest.resolve_path(), "/tmp/explicit")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHAOSTICTOOL_MANIFEST", None)
            with patch.object(manifest.os, "geteuid", return_value=0, create=True):
                self.assertEqual(manifest.resolve_path(), manifest.DEFAULT_MANIFEST)
            with patch.object(manifest.os, "geteuid", return_value=1000, create=True):
                self.assertIsNone(manifest.resolve_path())

    def test_record_creates_header_once_and_appends(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "manifest")
            with patch.dict(os.environ, {"CHAOSTICTOOL_MANIFEST": path}):
                manifest.record("file:/usr/local/bin/x")
                manifest.record("dir:/opt/chaostictool/Y")
                text = Path(path).read_text()
                self.assertEqual(text.count("# ChaosticTool manifest"), 1)
                self.assertIn("source=cli", text)
                self.assertEqual(manifest.records(path),
                                 ["file:/usr/local/bin/x", "dir:/opt/chaostictool/Y"])
                self.assertTrue(manifest.has_record("file:/usr/local/bin/x", path))
                self.assertFalse(manifest.has_record("file:/usr/local/bin/z", path))

    def test_record_is_a_no_op_without_a_manifest(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHAOSTICTOOL_MANIFEST", None)
            with patch.object(manifest.os, "geteuid", return_value=1000, create=True):
                manifest.record("file:/should/not/be/written")  # must not raise


class PreExistingToolGuaranteeTests(unittest.TestCase):
    def test_install_missing_skips_present_tools_without_recording(self):
        recorded = []
        with patch.object(installer, "_tool_available", return_value=True), \
                patch.object(installer, "_run") as run, \
                patch.object(installer.manifest, "record", side_effect=recorded.append), \
                patch.object(installer.console, "print"), \
                patch.object(installer.console, "input", return_value="y"):
            installer.install_missing([("nmap", "nmap"), ("subfinder", "subfinder")],
                                      assume_yes=True)
        run.assert_not_called()
        self.assertEqual(recorded, [],
                         "a tool already present must never be recorded for removal")


class ClaimPathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest = self.root / "manifest"
        self.env = patch.dict(os.environ, {"CHAOSTICTOOL_MANIFEST": str(self.manifest)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_free_slot_and_dangling_symlink_are_claimable(self):
        with patch.object(installer.console, "print"):
            self.assertTrue(installer._claim_path(str(self.root / "free")))
            link = self.root / "dangling"
            link.symlink_to(self.root / "missing-target")
            self.assertTrue(installer._claim_path(str(link)))

    def test_pre_existing_unrecorded_file_is_refused_and_left_untouched(self):
        victim = self.root / "stranger"
        victim.write_text("do-not-touch")
        with patch.object(installer.console, "print"):
            self.assertFalse(installer._claim_path(str(victim)))
        self.assertEqual(victim.read_text(), "do-not-touch")

    def test_a_path_already_recorded_as_ours_is_claimable(self):
        ours = self.root / "ours"
        ours.write_text("v1")
        manifest.record(f"file:{ours}")
        with patch.object(installer.console, "print"):
            self.assertTrue(installer._claim_path(str(ours)))


class FileWriterRoundTripTests(unittest.TestCase):
    """Each file-writing primitive records exactly the path uninstall reverses."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest = self.root / "manifest"
        self.env = patch.dict(os.environ, {"CHAOSTICTOOL_MANIFEST": str(self.manifest)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_python_module_wrapper_refuses_pre_existing_file(self):
        wrapper = self.root / "secretsdump.py"
        wrapper.write_text("#!/bin/sh\necho users own script\n")
        spec = {"module": "os", "wrapper": str(wrapper)}
        with patch.object(installer.console, "print"):
            self.assertFalse(installer._install_python_module_wrapper("secretsdump.py", spec))
        self.assertEqual(wrapper.read_text(), "#!/bin/sh\necho users own script\n")
        self.assertEqual(manifest.records(str(self.manifest)), [],
                         "a refused writer must not record the stranger's path")

    def test_python_module_wrapper_installs_and_records_on_free_slot(self):
        wrapper = self.root / "bin" / "GetUserSPNs.py"
        spec = {"module": "os", "wrapper": str(wrapper)}
        with patch.object(installer.console, "print"):
            self.assertTrue(installer._install_python_module_wrapper("GetUserSPNs.py", spec))
        self.assertTrue(wrapper.is_file())
        # The single recorded entry is exactly what uninstall.sh removes as file:.
        self.assertEqual(manifest.records(str(self.manifest)), [f"file:{wrapper}"])

    def test_direct_download_refuses_pre_existing_file(self):
        target = self.root / "rustscan"
        target.write_text("users own binary")
        payload = b"#!/bin/sh\nexit 0\n"
        import hashlib
        spec = {"url": "https://example.invalid/rustscan", "path": str(target),
                "sha256": hashlib.sha256(payload).hexdigest()}

        class FakeResponse:
            def read(self_inner):
                return payload

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

        with patch.object(installer.urllib.request, "urlopen", return_value=FakeResponse()), \
                patch.object(installer.console, "print"):
            self.assertFalse(installer._install_direct_download("rustscan", spec))
        self.assertEqual(target.read_text(), "users own binary")
        self.assertEqual(manifest.records(str(self.manifest)), [])


if __name__ == "__main__":
    unittest.main()
