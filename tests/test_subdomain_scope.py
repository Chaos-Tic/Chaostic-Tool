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

    def test_excluded_persists_and_filters_scope_hosts(self):
        tgt = self.tgt
        tgt.set_target(host="example.com")
        tgt.set_subdomains(["a.example.com", "b.example.com", "c.example.com"])
        tgt.set_scope_enabled(True)
        tgt.set_excluded(["b.example.com"])
        self.assertEqual(tgt.scope_hosts(), ["example.com", "a.example.com", "c.example.com"])
        # toggling restores it, and persists across a reload
        tgt.toggle_excluded("b.example.com")  # was excluded -> now included
        tgt.toggle_excluded("a.example.com")  # now excluded
        tgt.SCOPE["excluded"] = []
        tgt.load_scope()
        self.assertEqual(tgt.SCOPE["excluded"], ["a.example.com"])
        self.assertEqual(tgt.scope_hosts(), ["example.com", "b.example.com", "c.example.com"])

    def test_default_scope_hosts_capped_at_hard_max(self):
        from core import subdomains as sd
        tgt = self.tgt
        tgt.set_target(host="example.com")
        tgt.set_subdomains([f"s{i}.example.com" for i in range(sd.MAX_FANOUT + 20)])
        tgt.set_scope_enabled(True)
        self.assertEqual(len(tgt.scope_hosts()), sd.MAX_FANOUT)
        self.assertEqual(tgt.fanout_count(), sd.MAX_FANOUT + 21)  # uncapped (base + subs)


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

    def _run(self, preset, tool=None, answer=None):
        import contextlib
        ui = self.ui
        tool = tool or {"name": "X", "binary": "ZZ", "category": "recon",
                        "output_dir": "recon", "interactive": False}
        calls = []
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(ui.executor, "run_tool",
                                             lambda cmd, **kw: calls.append((cmd, kw.get("context")))))
            stack.enter_context(patch.object(ui.tui, "available", lambda: False))
            stack.enter_context(patch.object(ui, "should_proxy_tool", lambda t: False))
            stack.enter_context(patch.object(ui, "route_status", lambda t=None: "LOCAL"))
            if answer is not None:
                stack.enter_context(patch.object(ui.console, "input", lambda *a, **k: answer))
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

    def test_excluded_subdomain_skipped_in_fanout(self):
        tgt = self.tgt
        tgt.set_subdomains(["a.example.com", "b.example.com", "c.example.com"])
        tgt.set_scope_enabled(True)
        tgt.set_excluded(["b.example.com"])
        calls = self._run({"label": "scan", "cmd": ["nmap", "{host}"], "output": "nmap"})
        self.assertEqual([cmd[-1] for cmd, _ in calls],
                         ["example.com", "a.example.com", "c.example.com"])

    def test_large_fanout_requires_confirmation_and_can_limit(self):
        from core import subdomains as sd
        tgt = self.tgt
        tgt.set_subdomains([f"s{i:03d}.example.com" for i in range(40)])
        tgt.set_scope_enabled(True)
        preset = {"label": "scan", "cmd": ["nmap", "{host}"], "output": "nmap"}
        # No answer -> prompt would block; a prompt MUST happen here (>25 hosts).
        limited = self._run(preset, answer="k")  # first K
        self.assertEqual(len(limited), sd.WARN_FANOUT)
        cancelled = self._run(preset, answer="n")
        self.assertEqual(len(cancelled), 0)
        every = self._run(preset, answer="y")
        self.assertEqual(len(every), 41)

    def test_prompt_less_tool_below_threshold_runs_without_gate(self):
        tgt = self.tgt
        tgt.set_subdomains(["a.example.com", "b.example.com"])
        tgt.set_scope_enabled(True)
        # answer stays None: if a prompt were triggered the lambda-less input would
        # raise, so reaching 3 clean calls proves no gate fired below the threshold.
        calls = self._run({"label": "scan", "cmd": ["nmap", "{host}"], "output": "nmap"})
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
