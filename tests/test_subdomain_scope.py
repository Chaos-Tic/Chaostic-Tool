"""Per-target subdomain scope persistence and CLI fan-out over subdomains."""
import os
import tempfile
import unittest
from unittest.mock import patch


class TargetScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"CHAOSTIC_CLI_HOME": self.temp.name}, clear=False)
        self.env.start()
        from core import target as tgt
        self.tgt = tgt
        tgt.TARGETS_ROOT = tgt.data_home() / "targets"

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_scope_persists_per_target(self):
        tgt = self.tgt
        tgt.set_target(host="example.com")
        tgt.set_subdomains(["a.example.com", "b.example.com", "evil.net", "example.com"])
        tgt.set_scope_enabled(True)
        # out-of-scope and the bare domain are dropped
        self.assertEqual(tgt.SCOPE["subdomains"], ["a.example.com", "b.example.com"])
        # a fresh load of the same target restores the scope
        tgt.SCOPE["subdomains"], tgt.SCOPE["include_subdomains"] = [], False
        tgt.load_scope()
        self.assertEqual(tgt.SCOPE["subdomains"], ["a.example.com", "b.example.com"])
        self.assertTrue(tgt.SCOPE["include_subdomains"])
        self.assertEqual(tgt.scope_hosts(), ["example.com", "a.example.com", "b.example.com"])

    def test_switching_target_resets_scope(self):
        tgt = self.tgt
        tgt.set_target(host="example.com")
        tgt.set_subdomains(["a.example.com"])
        tgt.set_scope_enabled(True)
        tgt.set_target(host="other.com")  # no cache for this one
        self.assertEqual(tgt.SCOPE["subdomains"], [])
        self.assertFalse(tgt.SCOPE["include_subdomains"])


class RunPresetFanoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"CHAOSTIC_CLI_HOME": self.temp.name}, clear=False)
        self.env.start()
        from core import target as tgt, ui
        self.tgt, self.ui = tgt, ui
        tgt.TARGETS_ROOT = tgt.data_home() / "targets"
        tgt.set_target(host="example.com")

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _run(self, preset, tool=None):
        ui = self.ui
        tool = tool or {"name": "X", "binary": "ZZ", "category": "recon",
                        "output_dir": "recon", "interactive": False}
        calls = []
        with patch.object(ui.executor, "run_tool", lambda cmd, **kw: calls.append((cmd, kw.get("context")))), \
             patch.object(ui.tui, "available", lambda: False), \
             patch.object(ui, "should_proxy_tool", lambda t: False), \
             patch.object(ui, "route_status", lambda t=None: "LOCAL"):
            ui.run_preset(tool, preset, pause_after=False)
        return calls

    def test_host_preset_fans_out_over_subdomains(self):
        tgt = self.tgt
        tgt.set_subdomains(["a.example.com", "b.example.com"])
        tgt.set_scope_enabled(True)
        calls = self._run({"label": "scan", "cmd": ["nmap", "{host}"], "output": "nmap"})
        self.assertEqual(len(calls), 3)
        targeted = [cmd[-1] for cmd, _ in calls]
        self.assertEqual(targeted, ["example.com", "a.example.com", "b.example.com"])

    def test_scope_off_runs_once(self):
        tgt = self.tgt
        tgt.set_subdomains(["a.example.com"])
        tgt.set_scope_enabled(False)
        calls = self._run({"label": "scan", "cmd": ["nmap", "{host}"], "output": "nmap"})
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0][-1], "example.com")

    def test_non_host_preset_runs_once_even_with_scope(self):
        tgt = self.tgt
        tgt.set_subdomains(["a.example.com", "b.example.com"])
        tgt.set_scope_enabled(True)
        calls = self._run({"label": "local", "cmd": ["sometool", "--version"], "output": "v"})
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
