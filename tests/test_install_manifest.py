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
from types import SimpleNamespace
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


class PipMethodRecordingTests(unittest.TestCase):
    """The pip method records ``pip:<pkg>`` exactly when it installed the package.

    pip was the one install method that recorded nothing for the package itself
    (only the /usr/local/bin symlink), so pip-installed tools were not reversed
    on uninstall. These tests pin the record-what-you-install contract for it.
    """

    PW = SimpleNamespace(pw_name="tester", pw_uid=1000, pw_gid=1000, pw_dir="/home/tester")

    def _install(self, *, already_installed, run_ok=True):
        recorded, commands = [], []

        def fake_run(cmd, as_user_pw=None, env=None):
            commands.append((cmd, as_user_pw, env))
            return run_ok

        with patch.object(installer, "_pip_already_installed", return_value=already_installed), \
                patch.object(installer, "_run", side_effect=fake_run), \
                patch.object(installer, "_link_user_binary") as link, \
                patch.object(installer.manifest, "record",
                             side_effect=lambda entry, **_: recorded.append(entry)), \
                patch.object(installer.console, "print"):
            ok = installer._pip_user_install("xsstrike", "xsstrike", "/usr/bin/python3", self.PW)
        return ok, recorded, commands, link

    @unittest.skipIf(os.name == "nt", "pip --user layout (~/.local/bin) is a POSIX path contract")
    def test_fresh_pip_install_is_recorded_for_the_original_user(self):
        ok, recorded, commands, link = self._install(already_installed=False)
        self.assertTrue(ok)
        self.assertEqual(len(commands), 1)
        cmd, as_user_pw, env = commands[0]
        self.assertEqual(cmd, ["/usr/bin/python3", "-m", "pip", "install", "--user",
                               "--break-system-packages", "xsstrike"])
        self.assertIs(as_user_pw, self.PW, "pip --user must run as the invoking user, not root")
        self.assertEqual(env["HOME"], "/home/tester")
        self.assertEqual(recorded, ["pip:xsstrike"])
        link.assert_called_once_with("xsstrike", ["/home/tester/.local/bin"])

    def test_pre_existing_pip_package_is_neither_reinstalled_nor_recorded(self):
        ok, recorded, commands, link = self._install(already_installed=True)
        self.assertTrue(ok, "an already available package counts as satisfied")
        self.assertEqual(commands, [], "a package the user already had must not be touched")
        self.assertEqual(recorded, [], "and must never be recorded for removal")
        link.assert_called_once()

    def test_failed_pip_install_records_nothing(self):
        ok, recorded, commands, link = self._install(already_installed=False, run_ok=False)
        self.assertFalse(ok)
        self.assertEqual(len(commands), 1)
        self.assertEqual(recorded, [])
        link.assert_not_called()

    def test_install_missing_routes_the_pip_method_through_the_recording_helper(self):
        # End to end from install_missing: a PIP_PACKAGES tool restricted to the
        # pip method must reach _pip_user_install, which is the only place that
        # records pip:<pkg>. Everything that touches the system is patched out.
        calls = []
        with patch.object(installer, "_detect_pkg_manager", return_value=("apt", None)), \
                patch.object(installer, "_get_original_user", return_value=("tester", self.PW)), \
                patch.object(installer, "_tool_available", return_value=False), \
                patch.object(installer, "_install_build_deps"), \
                patch.object(installer, "_package_installed", return_value=True), \
                patch.object(installer.shutil, "which", return_value="/usr/bin/python3"), \
                patch.object(installer, "_pip_user_install",
                             side_effect=lambda *args: calls.append(args) or True), \
                patch.object(installer, "_run") as run, \
                patch.object(installer.console, "print"):
            installer.install_missing([("xsstrike", "xsstrike")], assume_yes=True,
                                      allowed_methods=["pip"])
        run.assert_not_called()
        self.assertEqual(calls, [("xsstrike", "xsstrike", "/usr/bin/python3", self.PW)])

    def test_every_pip_package_target_is_a_name_the_uninstaller_can_pass_to_pip(self):
        # uninstall.sh runs `pip uninstall -y <recorded value>`: the recorded value
        # must be a plain distribution name (no URLs, no version specifiers).
        for binary, pkg in installer.PIP_PACKAGES.items():
            if pkg is None:
                continue
            with self.subTest(binary=binary):
                self.assertRegex(pkg, r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
