"""Persistent local API keys: storage, sanitising and environment injection."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import api_keys
from desktop.storage import Store


class ApiKeyStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"CHAOSTIC_CLI_HOME": self.temp.name}, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_missing_file_reads_as_empty(self):
        self.assertEqual(api_keys.load(), {})

    def test_save_and_reload_round_trip(self):
        api_keys.save({"shodan": "  abc123  ", "github": "ghp_tok"})
        self.assertEqual(api_keys.load(), {"shodan": "abc123", "github": "ghp_tok"})

    def test_sanitise_drops_unknown_blank_and_non_string(self):
        api_keys.save({"shodan": "ok", "unknown": "x", "wpscan": "   ", "github": 123})
        self.assertEqual(api_keys.load(), {"shodan": "ok"})

    def test_set_key_sets_and_clears(self):
        api_keys.set_key("wpscan", "token")
        self.assertEqual(api_keys.load(), {"wpscan": "token"})
        api_keys.set_key("wpscan", "")
        self.assertEqual(api_keys.load(), {})

    def test_set_key_rejects_unknown_id(self):
        with self.assertRaises(KeyError):
            api_keys.set_key("nope", "x")

    def test_saved_file_is_owner_only(self):
        api_keys.save({"shodan": "secret"})
        path = Path(self.temp.name) / api_keys.FILENAME
        self.assertTrue(path.exists())
        if os.name == "posix":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_env_overrides_maps_ids_to_variables(self):
        self.assertEqual(
            api_keys.env_overrides({"shodan": "s", "wpscan": "w", "github": "g"}),
            {"SHODAN_API_KEY": "s", "WPSCAN_API_TOKEN": "w", "GITHUB_TOKEN": "g"},
        )

    def test_apply_to_env_fills_missing_only(self):
        api_keys.save({"shodan": "stored", "github": "stored-gh"})
        env = {"GITHUB_TOKEN": "from-shell"}
        api_keys.apply_to_env(env)
        self.assertEqual(env["SHODAN_API_KEY"], "stored")
        self.assertEqual(env["GITHUB_TOKEN"], "from-shell")

    def test_corrupt_file_is_ignored(self):
        (Path(self.temp.name) / api_keys.FILENAME).write_text("not json", encoding="utf-8")
        self.assertEqual(api_keys.load(), {})


class DesktopApiKeyTests(unittest.TestCase):
    def test_store_persists_and_clears_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = Store(root)
            store.set_api_key("shodan", "  key  ")
            self.assertEqual(Store(root).settings["api_keys"], {"shodan": "key"})
            store.set_api_key("shodan", "")
            self.assertEqual(Store(root).settings["api_keys"], {})

    def test_invalid_api_keys_type_is_quarantined(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "settings.json").write_text(
                '{"targets": [], "active_target": "", "executables": {}, "api_keys": []}',
                encoding="utf-8")
            store = Store(root)
            self.assertEqual(store.settings["api_keys"], {})
            self.assertTrue(store.warning)


if __name__ == "__main__":
    unittest.main()
