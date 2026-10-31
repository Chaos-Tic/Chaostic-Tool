"""API keys: keyring-backed storage, persistent file fallback and env injection.

A fake backend stands in for the OS secret store; the file backend is exercised
in a temporary data home so no secret ever reaches the real one.
"""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import api_keys

try:  # import before any sys.modules patch so the patch never evicts these submodules
    import cryptography.fernet  # noqa: F401
    import cryptography.hazmat.primitives.kdf.pbkdf2  # noqa: F401
except Exception:
    pass


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


class FakeKeyring:
    """Minimal keyring module double: a dict store that can be told to fail."""

    def __init__(self, fail_on_write=False):
        self.store, self.fail_on_write = {}, fail_on_write

    def get_keyring(self):
        return self

    def set_password(self, service, key, value):
        if self.fail_on_write:
            raise RuntimeError("locked")
        self.store[(service, key)] = value

    def get_password(self, service, key):
        return self.store.get((service, key))

    def delete_password(self, service, key):
        self.store.pop((service, key), None)


class _Reset(unittest.TestCase):
    def tearDown(self):
        api_keys._backend = None
        api_keys._SESSION.clear()
        api_keys.set_passphrase_prompt(None)


class ApiKeyKeyringTests(_Reset):
    def setUp(self):
        self.backend = FakeBackend(available=True)
        api_keys.set_backend(self.backend)

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

    def test_persistent_storage_reflects_backend(self):
        self.assertTrue(api_keys.persistent_storage_available())


class KeyringProbeTests(_Reset):
    def test_working_keyring_is_secure_store(self):
        with patch.dict("sys.modules", {"keyring": FakeKeyring(), "keyring.backends": None, "keyring.backends.fail": None}):
            self.assertTrue(api_keys.secure_storage_available())
            self.assertEqual(api_keys.storage_status().kind, "keyring")
            self.assertTrue(api_keys.set_key("github", "tok"))
            self.assertEqual(api_keys.get("github"), "tok")

    def test_probe_leaves_no_canary_behind(self):
        fake = FakeKeyring()
        with patch.dict("sys.modules", {"keyring": fake, "keyring.backends": None, "keyring.backends.fail": None}):
            api_keys.secure_storage_available()
        self.assertEqual(fake.store, {})

    def test_keyring_that_fails_on_write_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as home, \
                patch.dict(os.environ, {"CHAOSTIC_CLI_HOME": home}), \
                patch.dict("sys.modules", {"keyring": FakeKeyring(fail_on_write=True),
                                           "keyring.backends": None, "keyring.backends.fail": None}):
            self.assertFalse(api_keys.secure_storage_available())
            self.assertEqual(api_keys.storage_status().kind, "session")
            self.assertFalse(api_keys.set_key("github", "tok"))  # no crash, session fallback
            self.assertEqual(api_keys.get("github"), "tok")

    def test_late_keyring_failure_falls_back_instead_of_raising(self):
        fake = FakeKeyring()
        with tempfile.TemporaryDirectory() as home, \
                patch.dict(os.environ, {"CHAOSTIC_CLI_HOME": home}), \
                patch.dict("sys.modules", {"keyring": fake, "keyring.backends": None, "keyring.backends.fail": None}):
            self.assertTrue(api_keys.secure_storage_available())
            fake.fail_on_write = True  # the store locked after the probe
            self.assertFalse(api_keys.set_key("shodan", "later"))
            self.assertEqual(api_keys.get("shodan"), "later")
            self.assertEqual(api_keys.storage_status().kind, "session")


class ApiKeySessionFallbackTests(_Reset):
    def setUp(self):
        api_keys.set_backend(FakeBackend(available=False))

    def test_without_persistent_store_keys_live_in_session_only(self):
        self.assertFalse(api_keys.secure_storage_available())
        self.assertFalse(api_keys.persistent_storage_available())
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


class FileStoreTests(_Reset):
    """No usable keyring: the opt-in file store persists keys across launches."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / "data"
        self._env = patch.dict(os.environ, {"CHAOSTIC_CLI_HOME": str(self.home)})
        self._env.start()
        self._mods = patch.dict("sys.modules", {"keyring": None})
        self._mods.start()
        api_keys._backend = None

    def tearDown(self):
        super().tearDown()
        self._mods.stop()
        self._env.stop()
        self._tmp.cleanup()

    def relaunch(self):
        api_keys._backend = None
        api_keys._SESSION.clear()

    def test_offered_but_not_used_until_enabled(self):
        self.assertTrue(api_keys.file_store_offerable())
        self.assertFalse(api_keys.set_key("shodan", "s"))
        self.assertFalse(api_keys.store_path().exists())
        self.assertEqual(api_keys.storage_status().kind, "session")

    def test_plain_store_persists_across_relaunch_with_0600(self):
        api_keys.set_key("shodan", "pending")  # session until opt-in
        self.assertEqual(api_keys.enable_file_store(None), "plain")
        self.assertEqual(api_keys.get("shodan"), "pending")  # session key moved into the file
        self.assertTrue(api_keys.set_key("github", "gh-token"))
        path = api_keys.store_path()
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertFalse(list(path.parent.glob("*.tmp")))
        self.relaunch()
        self.assertFalse(api_keys.file_store_offerable())
        self.assertTrue(api_keys.persistent_storage_available())
        self.assertFalse(api_keys.secure_storage_available())
        self.assertEqual(api_keys.load(), {"shodan": "pending", "github": "gh-token"})
        self.assertEqual(api_keys.storage_status().kind, "file-plain")
        self.assertEqual(api_keys.storage_status().path, str(path))

    def test_plain_store_is_encoded_not_clear_and_truthfully_labelled(self):
        api_keys.enable_file_store(None)
        api_keys.set_key("wpscan", "wp-secret-value")
        raw = api_keys.store_path().read_text(encoding="utf-8")
        self.assertNotIn("wp-secret-value", raw)
        self.assertEqual(json.loads(raw)["mode"], "plain")
        self.assertEqual(api_keys.storage_status().kind, "file-plain")

    def test_blank_removes_from_file(self):
        api_keys.enable_file_store(None)
        api_keys.set_key("shodan", "s")
        api_keys.set_key("shodan", "")
        self.relaunch()
        self.assertEqual(api_keys.load(), {})

    def test_env_already_set_wins_over_file(self):
        api_keys.enable_file_store(None)
        api_keys.set_key("shodan", "file")
        with patch.dict(os.environ, {"SHODAN_API_KEY": "shell"}, clear=False):
            env = dict(os.environ)
            api_keys.apply_to_env(env)
            self.assertEqual(env["SHODAN_API_KEY"], "shell")

    def test_no_secret_in_world_readable_path(self):
        api_keys.enable_file_store(None)
        api_keys.set_key("github", "gh-world")
        for path in self.home.rglob("*"):
            mode = stat.S_IMODE(path.stat().st_mode)
            self.assertFalse(mode & (stat.S_IRGRP | stat.S_IROTH), f"{path} readable by others: {oct(mode)}")
            if path.is_file():
                self.assertNotIn("gh-world", path.read_text(encoding="utf-8", errors="replace"))

    def test_unwritable_directory_falls_back_to_session_without_raising(self):
        api_keys.enable_file_store(None)
        with patch.object(api_keys._FileBackend, "_write", side_effect=OSError("read-only")):
            self.assertFalse(api_keys.set_key("shodan", "s"))
        self.assertEqual(api_keys.get("shodan"), "s")

    def _victim(self):
        victim = Path(self._tmp.name) / "victim"
        victim.write_text("root-owned content", encoding="utf-8")
        return victim

    @unittest.skipUnless(hasattr(os, "symlink") and os.name != "nt", "POSIX symlinks")
    def test_symlink_planted_at_store_path_is_never_followed(self):
        victim = self._victim()
        self.home.mkdir(mode=0o700)
        os.symlink(victim, self.home / api_keys.STORE_FILE)
        self.assertTrue(api_keys.file_store_offerable())  # a symlink is not an existing store
        api_keys.enable_file_store(None)
        self.assertEqual(api_keys.load(), {})  # the symlink target is not read
        self.assertTrue(api_keys.set_key("shodan", "s3cret"))
        self.assertEqual(victim.read_text(encoding="utf-8"), "root-owned content")
        self.assertTrue(stat.S_ISREG(os.lstat(self.home / api_keys.STORE_FILE).st_mode))
        self.assertNotIn("s3cret", victim.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os, "symlink") and os.name != "nt", "POSIX symlinks")
    def test_symlink_planted_at_predictable_temp_name_is_never_followed(self):
        victim = self._victim()
        self.home.mkdir(mode=0o700)
        os.symlink(victim, self.home / (api_keys.STORE_FILE + ".tmp"))
        before = victim.stat()
        api_keys.enable_file_store(None)
        self.assertTrue(api_keys.set_key("github", "gh-s3cret"))
        self.assertEqual(victim.read_text(encoding="utf-8"), "root-owned content")
        after = victim.stat()
        self.assertEqual((before.st_mode, before.st_uid, before.st_gid), (after.st_mode, after.st_uid, after.st_gid))
        self.assertEqual(api_keys.load(), {"github": "gh-s3cret"})
        self.assertEqual([p.name for p in self.home.iterdir() if p.name.endswith(".tmp")], [api_keys.STORE_FILE + ".tmp"])

    @unittest.skipUnless(hasattr(os, "symlink") and os.name != "nt", "POSIX symlinks")
    def test_store_directory_symlink_is_refused(self):
        elsewhere = Path(self._tmp.name) / "elsewhere"
        elsewhere.mkdir()
        os.symlink(elsewhere, self.home)
        with self.assertRaises(RuntimeError):
            api_keys._FileBackend().enable(None)
        self.assertEqual(list(elsewhere.iterdir()), [])
        api_keys._backend = None
        self.assertFalse(api_keys.set_key("shodan", "s"))  # session fallback, no crash
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_temp_file_is_random_exclusive_and_0600(self):
        api_keys.enable_file_store(None)
        seen = []
        real_open = os.open

        def spy(path, flags, *args, **kwargs):
            if str(path).endswith(".tmp"):
                seen.append((str(path), flags))
            return real_open(path, flags, *args, **kwargs)
        with patch.object(os, "open", spy):
            api_keys.set_key("wpscan", "w")
        self.assertEqual(len(seen), 1)
        name, flags = seen[0]
        self.assertNotEqual(name, api_keys.STORE_FILE + ".tmp")
        self.assertTrue(flags & os.O_EXCL)
        if hasattr(os, "O_NOFOLLOW"):
            self.assertTrue(flags & os.O_NOFOLLOW)
        self.assertEqual(stat.S_IMODE(api_keys.store_path().stat().st_mode), 0o600)

    def test_encrypt_requires_cryptography(self):
        with patch.object(api_keys, "encryption_available", return_value=False):
            with self.assertRaises(RuntimeError):
                api_keys.enable_file_store("pw")


@unittest.skipUnless(api_keys.encryption_available(), "cryptography not installed")
class EncryptedFileStoreTests(FileStoreTests):
    def test_encrypted_round_trip_and_lock(self):
        self.assertEqual(api_keys.enable_file_store("correct horse"), "fernet")
        self.assertTrue(api_keys.set_key("shodan", "shodan-secret"))
        raw = api_keys.store_path().read_text(encoding="utf-8")
        self.assertNotIn("shodan-secret", raw)
        header = json.loads(raw)
        self.assertEqual((header["mode"], header["kdf"]), ("fernet", "pbkdf2-hmac-sha256"))
        self.assertGreaterEqual(header["iterations"], 600_000)
        self.assertEqual(api_keys.storage_status().kind, "file-encrypted")
        self.assertFalse(api_keys.storage_status().locked)

        self.relaunch()
        status = api_keys.storage_status()
        self.assertEqual((status.kind, status.locked), ("file-encrypted", True))
        self.assertEqual(api_keys.load(), {})  # locked: nothing leaks, nothing prompts
        self.assertFalse(api_keys.unlock_file_store("wrong"))
        self.assertTrue(api_keys.storage_status().locked)
        self.assertTrue(api_keys.unlock_file_store("correct horse"))
        self.assertEqual(api_keys.load(), {"shodan": "shodan-secret"})

    def test_passphrase_prompt_unlocks_lazily_once(self):
        api_keys.enable_file_store("pw")
        api_keys.set_key("github", "gh")
        self.relaunch()
        calls = []
        api_keys.set_passphrase_prompt(lambda reason: calls.append(reason) or "pw")
        env = {}
        api_keys.apply_to_env(env)
        self.assertEqual(env["GITHUB_TOKEN"], "gh")
        api_keys.apply_to_env({})
        self.assertEqual(calls, ["unlock"])  # cached for the session

    def test_declined_prompt_is_not_repeated_and_write_degrades_to_session(self):
        api_keys.enable_file_store("pw")
        api_keys.set_key("github", "gh")
        self.relaunch()
        calls = []
        api_keys.set_passphrase_prompt(lambda reason: calls.append(reason))
        self.assertEqual(api_keys.load(), {})
        self.assertEqual(api_keys.load(), {})
        self.assertEqual(calls, ["unlock"])
        self.assertFalse(api_keys.set_key("shodan", "s"))  # locked store never raises
        self.assertEqual(api_keys.get("shodan"), "s")
        self.assertNotIn("s", json.loads(api_keys.store_path().read_text()).get("keys", {}))


class NullBackendTests(_Reset):
    def test_missing_keyring_degrades_to_session(self):
        with tempfile.TemporaryDirectory() as home, \
                patch.dict(os.environ, {"CHAOSTIC_CLI_HOME": home}), \
                patch.dict("sys.modules", {"keyring": None}):
            self.assertFalse(api_keys.secure_storage_available())
            self.assertFalse(api_keys.set_key("github", "tok"))
            self.assertEqual(api_keys.get("github"), "tok")


if __name__ == "__main__":
    unittest.main()
