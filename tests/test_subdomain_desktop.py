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

    def test_excluded_persisted_and_filtered(self):
        with tempfile.TemporaryDirectory() as temp:
            store, tid = self._store(temp)
            store.set_target_scope(tid, subdomains=["a.example.com", "b.example.com"], include=True)
            store.set_target_scope(tid, excluded=["b.example.com", "evil.net"])  # evil.net ignored
            self.assertEqual(store.targets[0]["excluded"], ["b.example.com"])
            self.assertEqual(store.scope_hosts(store.targets[0]), ["example.com", "a.example.com"])
            # persisted across reload
            reloaded = Store(Path(temp)).targets[0]
            self.assertEqual(reloaded["excluded"], ["b.example.com"])

    def test_scope_hosts_default_capped_and_fanout_count_uncapped(self):
        from core import subdomains as sd
        with tempfile.TemporaryDirectory() as temp:
            store, tid = self._store(temp)
            subs = [f"s{i}.example.com" for i in range(sd.MAX_FANOUT + 10)]
            store.set_target_scope(tid, subdomains=subs, include=True)
            self.assertEqual(len(store.scope_hosts(store.targets[0])), sd.MAX_FANOUT)
            self.assertEqual(len(store.scope_hosts(store.targets[0], limit=sd.WARN_FANOUT)), sd.WARN_FANOUT)
            self.assertEqual(store.fanout_count(store.targets[0]), sd.MAX_FANOUT + 11)

    def test_edit_same_host_keeps_exclusions(self):
        with tempfile.TemporaryDirectory() as temp:
            store, tid = self._store(temp)
            store.set_target_scope(tid, subdomains=["a.example.com", "b.example.com"], include=True)
            store.set_target_scope(tid, excluded=["a.example.com"])
            store.update_target(tid, "https://example.com", "renamed")
            self.assertEqual(store.targets[0]["excluded"], ["a.example.com"])


class DesktopWindowScopeTests(unittest.TestCase):
    def test_scope_targets_drops_excluded(self):
        from desktop_harness import APP  # noqa: F401 (ensures a QApplication exists)
        from desktop.window import Window
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp))
            store.settings.update(animations=False, check_updates=False)
            store.add_target("https://example.com")
            tid = store.targets[0]["id"]
            store.set_target_scope(tid, subdomains=["a.example.com", "b.example.com", "c.example.com"],
                                   include=True)
            store.set_target_scope(tid, excluded=["b.example.com"])
            window = Window(store)
            try:
                preset = {"args": ["{host}"], "needs_target": True}
                targets = window._scope_targets(preset, store.active_target)
                self.assertEqual([t["host"] for t in targets],
                                 ["example.com", "a.example.com", "c.example.com"])
            finally:
                window.close()
                window.deleteLater()
                APP.processEvents()


if __name__ == "__main__":
    unittest.main()
