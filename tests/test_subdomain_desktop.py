"""Desktop Store subdomain scope: persistence, validation, host variants."""
import tempfile
import unittest
from pathlib import Path

from desktop.storage import Store, retarget


class DesktopScopeTests(unittest.TestCase):
    def _store(self, temp):
        store = Store(Path(temp))
        store.add_target("https://example.com")
        return store, store.targets[0]["id"]

    def test_scope_stored_and_filtered(self):
        with tempfile.TemporaryDirectory() as temp:
            store, tid = self._store(temp)
            store.set_target_scope(tid, subdomains=["a.example.com", "b.example.com", "evil.net", "example.com"])
            store.set_target_scope(tid, include=True)
            target = store.targets[0]
            self.assertEqual(target["subdomains"], ["a.example.com", "b.example.com"])
            self.assertTrue(target["include_subdomains"])
            # persisted across reload
            self.assertEqual(Store(Path(temp)).targets[0]["subdomains"], ["a.example.com", "b.example.com"])

    def test_scope_hosts_base_first(self):
        with tempfile.TemporaryDirectory() as temp:
            store, tid = self._store(temp)
            store.set_target_scope(tid, subdomains=["a.example.com"], include=True)
            self.assertEqual(store.scope_hosts(store.targets[0]),
                             ["example.com", "a.example.com"])

    def test_include_cannot_be_set_without_subdomains(self):
        with tempfile.TemporaryDirectory() as temp:
            store, tid = self._store(temp)
            store.set_target_scope(tid, include=True)
            self.assertFalse(store.targets[0]["include_subdomains"])

    def test_retarget_keeps_scheme_and_port(self):
        t = {"host": "example.com", "url": "https://example.com:8443/path", "port": 8443}
        v = retarget(t, "api.example.com")
        self.assertEqual(v["host"], "api.example.com")
        self.assertEqual(v["url"], "https://api.example.com:8443/path")


if __name__ == "__main__":
    unittest.main()
