"""API keys: keyring-backed storage, session fallback and env injection.

A fake backend stands in for the OS secret store so these tests never touch the
real keyring and never write secrets to disk.
"""
import os
import unittest
from unittest.mock import patch

from core import api_keys


class FakeBackend:
    def __init__(self, available=True):
        self.available = available
        self.store = {}

    def get(self, key_id):
        return self.store.get(key_id)

    def set(self, key_id, value):
        self.store[key_id] = value

    def delete(self, key_id):
        self.store.pop(key_id, None)


class ApiKeyKeyringTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend(available=True)
        api_keys.set_backend(self.backend)

    def tearDown(self):
        api_keys._backend = None
        api_keys._SESSION.clear()

    def test_set_and_get_round_trip(self):
        self.assertTrue(api_keys.set_key("shodan", "  abc123  "))
        self.assertEqual(api_keys.get("shodan"), "abc123")
        self.assertEqual(self.backend.store["shodan"], "abc123")

    def test_blank_clears_key(self):
        api_keys.set_key("wpscan", "token")
        api_keys.set_key("wpscan", "   ")
        self.assertIsNone(api_keys.get("wpscan"))

    def test_unknown_id_rejected(self):
        with self.assertRaises(KeyError):
            api_keys.set_key("nope", "x")
        self.assertIsNone(api_keys.get("nope"))

    def test_load_and_configured(self):
        api_keys.set_key("shodan", "s")
        api_keys.set_key("github", "g")
        self.assertEqual(api_keys.load(), {"shodan": "s", "github": "g"})
        self.assertEqual(api_keys.configured(), {"shodan", "github"})

    def test_env_overrides_maps_ids_to_variables(self):
        self.assertEqual(
            api_keys.env_overrides({"shodan": "s", "wpscan": "w", "github": "g"}),
            {"SHODAN_API_KEY": "s", "WPSCAN_API_TOKEN": "w", "GITHUB_TOKEN": "g"},
        )

    def test_apply_to_env_fills_missing_only(self):
        api_keys.set_key("shodan", "stored")
        api_keys.set_key("github", "stored-gh")
        env = {"GITHUB_TOKEN": "from-shell"}
        api_keys.apply_to_env(env)
        self.assertEqual(env["SHODAN_API_KEY"], "stored")
        self.assertEqual(env["GITHUB_TOKEN"], "from-shell")

    def test_secure_storage_available_reflects_backend(self):
        self.assertTrue(api_keys.secure_storage_available())


class ApiKeySessionFallbackTests(unittest.TestCase):
    def setUp(self):
        api_keys.set_backend(FakeBackend(available=False))

    def tearDown(self):
        api_keys._backend = None
        api_keys._SESSION.clear()

    def test_without_secure_store_keys_live_in_session_only(self):
        self.assertFalse(api_keys.secure_storage_available())
        persisted = api_keys.set_key("shodan", "ephemeral")
        self.assertFalse(persisted)
        self.assertEqual(api_keys.get("shodan"), "ephemeral")
        self.assertEqual(api_keys.load(), {"shodan": "ephemeral"})

    def test_env_already_set_wins_over_session(self):
        api_keys.set_key("shodan", "session")
        with patch.dict(os.environ, {"SHODAN_API_KEY": "shell"}, clear=False):
            env = dict(os.environ)
            api_keys.apply_to_env(env)
            self.assertEqual(env["SHODAN_API_KEY"], "shell")


class NullBackendTests(unittest.TestCase):
    def tearDown(self):
        api_keys._backend = None
        api_keys._SESSION.clear()

    def test_missing_keyring_degrades_to_session(self):
        # Simulate keyring import failing entirely.
        api_keys._backend = None
        with patch.dict("sys.modules", {"keyring": None}):
            self.assertFalse(api_keys.secure_storage_available())
            self.assertFalse(api_keys.set_key("github", "tok"))
            self.assertEqual(api_keys.get("github"), "tok")


if __name__ == "__main__":
    unittest.main()
