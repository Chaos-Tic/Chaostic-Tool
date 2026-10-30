"""Installation paths must work with read-only application files and under sudo."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.paths import data_home, ensure_directory
from core import flows, target


@unittest.skipIf(os.name == 'nt', 'POSIX installation paths require Linux/Unix')
class InstallationTests(unittest.TestCase):
    def test_user_paths(self):
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg"}, clear=True), patch("os.geteuid", return_value=1000):
            self.assertEqual(data_home(), Path("/tmp/xdg/chaostictool"))
        with patch.dict(os.environ, {"CHAOSTIC_CLI_HOME": "relative"}, clear=True):
            with self.assertRaises(ValueError):
                data_home()

    def test_targets_live_in_user_data_not_application_sources(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(target, "TARGETS_ROOT", Path(directory) / "data" / "targets"), \
                patch.dict(target.TARGET, clear=False):
            created = target.set_target(host="demo.invalid")
            self.assertEqual(created, Path(directory) / "data" / "targets" / "demo.invalid")
            self.assertTrue((created / "osint").is_dir())

    def test_sudo_ignores_root_or_inherited_overrides(self):
        with patch.dict(os.environ, {"SUDO_USER": "operator", "HOME": "/root", "XDG_DATA_HOME": "/root/.local/share", "CHAOSTIC_CLI_HOME": "/tmp/untrusted"}, clear=True), patch("os.geteuid", return_value=0), patch("pwd.getpwnam", return_value=SimpleNamespace(pw_dir="/home/operator")):
            self.assertEqual(data_home(), Path("/home/operator/.local/share/chaostictool"))

    def test_new_directories_are_owned_by_invoking_user(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"SUDO_USER": "operator"}), patch("os.geteuid", return_value=0), patch("pwd.getpwnam", return_value=SimpleNamespace(pw_uid=1000, pw_gid=1000)), patch("os.chown") as chown:
            destination = Path(directory) / "data" / "targets" / "demo.invalid"
            ensure_directory(destination)
            self.assertTrue(destination.is_dir())
            self.assertEqual({call.args[0] for call in chown.call_args_list}, {destination, destination.parent, destination.parent.parent})

    def test_legacy_flows_are_read_but_new_writes_use_user_data(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy = Path(directory) / "custom_flows.json"
            current = Path(directory) / "data/custom_flows.json"
            legacy.write_text('{"cf-1": {"persistent": true, "name": "demo"}}')
            with patch.object(flows, "LEGACY_FLOWS_PATH", legacy), patch.object(flows, "CUSTOM_FLOWS_PATH", current), patch.object(flows, "CUSTOM_FLOWS", {}), patch.object(flows.tgt, "_chown_path"):
                flows.load_custom_flows()
                self.assertIn("cf-1", flows.CUSTOM_FLOWS)
                flows.save_custom_flows()
                self.assertEqual(current.read_text(), __import__("json").dumps(flows.CUSTOM_FLOWS, indent=2, ensure_ascii=False))
            self.assertTrue(legacy.exists())
