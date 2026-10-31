"""CLI flow contracts: deduplicated built-in flows and the chained run model.

These exercise core.flows / core.ui without a TTY or any real subprocess, by
scripting the shared console and stubbing the single-step runner.
"""
import unittest
from unittest.mock import patch

from core import flows, ui
from core.flow_definitions import FLOWS
from core.tools import TOOLS, get_tool


class FakeConsole:
    """Shared-console stand-in: scripted inputs, captured prints."""
    def __init__(self, inputs=()):
        self.inputs = list(inputs)
        self.prints = []

    def print(self, *args, **kwargs):
        self.prints.append(" ".join(str(a) for a in args))

    def input(self, *args, **kwargs):
        return self.inputs.pop(0)

    @property
    def text(self):
        return "\n".join(self.prints)


class DedupTests(unittest.TestCase):
    def test_builtin_flows_have_the_expected_deduplicated_steps(self):
        self.assertEqual(FLOWS["1"]["steps"],
                         [("dig", 0), ("subfinder", 0), ("nmap", 0), ("httpx", 1), ("nuclei", 0)])
        self.assertEqual(FLOWS["2"]["steps"],
                         [("dig", 0), ("subfinder", 1), ("nmap", 1), ("httpx", 1),
                          ("katana", 1), ("gau", 1), ("nuclei", 2), ("sslscan", 0)])
        self.assertEqual(FLOWS["3"]["steps"],
                         [("amass", 0), ("subfinder", 1), ("rustscan", 2), ("ffuf", 0),
                          ("katana", 2), ("nuclei", 2), ("testssl.sh", 0), ("nikto", 0)])

    def test_removed_overlaps_are_gone_but_tools_stay_in_the_registry(self):
        basic = [t for t, _ in FLOWS["1"]["steps"]]
        inter = [t for t, _ in FLOWS["2"]["steps"]]
        adv = [t for t, _ in FLOWS["3"]["steps"]]
        # Basic keeps a single web fingerprint (httpx), not whatweb too.
        self.assertIn("httpx", basic)
        self.assertNotIn("whatweb", basic)
        # Intermediate drops naabu (subset of nmap -p-) and waybackurls (subset of gau --subs).
        self.assertNotIn("naabu", inter)
        self.assertNotIn("waybackurls", inter)
        self.assertIn("gau", inter)
        # Advanced keeps one full port scanner (rustscan) and one dir-buster (ffuf).
        self.assertNotIn("nmap", adv)
        self.assertIn("rustscan", adv)
        self.assertNotIn("gobuster", adv)
        self.assertIn("ffuf", adv)
        # A single, merged nuclei pass in Advanced.
        self.assertEqual(adv.count("nuclei"), 1)
        # The tools only left the flows; they remain available in the registry.
        for removed in ("whatweb", "naabu", "waybackurls", "gobuster"):
            self.assertIn(removed, TOOLS)

    def test_advanced_keeps_amass_and_subfinder_as_declared_cross_validation(self):
        adv = [t for t, _ in FLOWS["3"]["steps"]]
        self.assertIn("amass", adv)
        self.assertIn("subfinder", adv)
        self.assertIn("cross-validate", FLOWS["3"]["desc"])

    def test_every_flow_step_resolves_to_a_real_preset(self):
        for key, flow in FLOWS.items():
            for tool_key, preset_idx in flow["steps"]:
                with self.subTest(flow=key, tool=tool_key, preset=preset_idx):
                    self.assertIn(tool_key, TOOLS)
                    self.assertTrue(0 <= preset_idx < len(TOOLS[tool_key]["presets"]))


class ResolveAndPreviewTests(unittest.TestCase):
    def test_resolve_steps_flags_missing_registry_and_preset(self):
        flow = {"name": "x", "desc": "", "steps": [("nmap", 0), ("does-not-exist", 0), ("nmap", 999)]}
        with patch.object(flows.ui, "tool_available", return_value=True):
            records = flows._resolve_steps(flow)
        self.assertTrue(records[0]["enabled"] and records[0]["available"])
        self.assertIsNone(records[1]["tool"])
        self.assertEqual(records[1]["problem"], "missing registry entry")
        self.assertFalse(records[1]["enabled"])
        self.assertTrue(records[2]["problem"].startswith("missing preset"))
        self.assertFalse(records[2]["enabled"])

    def test_preview_command_fills_target_but_keeps_other_placeholders(self):
        with patch.dict(flows.tgt.TARGET,
                        {"host": "example.test", "url": "http://example.test", "port": "80"},
                        clear=False):
            nmap_cmd = flows._preview_command(get_tool("nmap"), get_tool("nmap")["presets"][0])
            ffuf_cmd = flows._preview_command(get_tool("ffuf"), get_tool("ffuf")["presets"][0])
        self.assertIn("example.test", nmap_cmd)
        self.assertTrue(any("{wordlist}" in part for part in ffuf_cmd))

    def test_preview_toggle_disables_a_step_then_go_launches(self):
        flow = FLOWS["1"]
        with patch.object(flows.ui, "tool_available", return_value=True):
            records = flows._resolve_steps(flow)
        console = FakeConsole(["2", "go"])  # toggle step 2 off, then launch
        with patch.object(flows.ui, "header"), \
                patch.object(flows.ui, "console", console), \
                patch.dict(flows.tgt.TARGET,
                           {"host": "example.test", "url": "http://example.test", "port": "80"},
                           clear=False), \
                patch.object(flows.tgt, "summary", return_value="host=example.test"):
            launched = flows._preview_flow(flow, records)
        self.assertTrue(launched)
        self.assertFalse(records[1]["enabled"])
        self.assertTrue(records[0]["enabled"])

    def test_preview_cancel_returns_false(self):
        flow = FLOWS["1"]
        with patch.object(flows.ui, "tool_available", return_value=True):
            records = flows._resolve_steps(flow)
        console = FakeConsole(["r"])
        with patch.object(flows.ui, "header"), \
                patch.object(flows.ui, "console", console), \
                patch.dict(flows.tgt.TARGET,
                           {"host": "example.test", "url": "http://example.test", "port": "80"},
                           clear=False), \
                patch.object(flows.tgt, "summary", return_value="host=example.test"):
            self.assertFalse(flows._preview_flow(flow, records))

    def test_ask_mode_maps_input_to_auto_or_step(self):
        for raw, expected in [("2", "auto"), ("all", "auto"), ("auto", "auto"),
                              ("1", "step"), ("", "step"), ("x", "step")]:
            with patch.object(flows.ui, "console", FakeConsole([raw])):
                self.assertEqual(flows._ask_mode(), expected)


class RunFlowTests(unittest.TestCase):
    def _run(self, inputs):
        """Drive run_flow(FLOWS['1']) with scripted console input; return the
        run_preset mock so callers can inspect how steps were launched."""
        console = FakeConsole(inputs)
        with patch.object(flows.tgt, "is_defined", return_value=True), \
                patch.object(flows.tgt, "summary", return_value="host=example.test"), \
                patch.dict(flows.tgt.TARGET,
                           {"host": "example.test", "url": "http://example.test", "port": "80"},
                           clear=False), \
                patch.object(flows.ui, "tool_available", return_value=True), \
                patch.object(flows.ui, "header"), \
                patch.object(flows.ui, "pause"), \
                patch.object(flows.ui, "console", console), \
                patch.object(flows.ui, "run_preset", return_value=0) as run_preset:
            flows.run_flow(FLOWS["1"])
        return run_preset

    def test_run_all_launches_every_step_with_flow_context(self):
        run_preset = self._run(["go", "2"])  # preview launch, run-all
        self.assertEqual(run_preset.call_count, 5)
        indices = [c.kwargs["flow_context"]["index"] for c in run_preset.call_args_list]
        totals = {c.kwargs["flow_context"]["total"] for c in run_preset.call_args_list}
        self.assertEqual(indices, [1, 2, 3, 4, 5])
        self.assertEqual(totals, {5})
        self.assertTrue(all(c.kwargs["pause_after"] is False for c in run_preset.call_args_list))
        self.assertTrue(all(c.kwargs["flow_context"]["name"] == "Basic attack flow"
                            for c in run_preset.call_args_list))

    def test_step_mode_skip_then_quit_runs_only_confirmed_steps(self):
        # preview go, mode step, skip step1, run step2, quit at step3.
        run_preset = self._run(["go", "1", "s", "y", "q"])
        self.assertEqual(run_preset.call_count, 1)
        self.assertEqual(run_preset.call_args.args[1]["label"], "Passive subdomains (fast)")
        self.assertTrue(run_preset.call_args.kwargs["pause_after"])  # step mode pauses

    def test_step_mode_replay_reruns_the_previous_step(self):
        # run step1, replay (back to step1), run step1 again, then quit.
        run_preset = self._run(["go", "1", "y", "r", "y", "q"])
        self.assertEqual(run_preset.call_count, 2)
        self.assertTrue(all(c.args[0]["name"] == "Dig" for c in run_preset.call_args_list))

    def test_cancelled_preview_runs_nothing(self):
        run_preset = self._run(["r"])  # cancel at preview
        self.assertEqual(run_preset.call_count, 0)


class RunPresetContextTests(unittest.TestCase):
    def test_run_preset_forwards_flow_context_to_the_scan_view(self):
        tool = {"name": "Nmap", "binary": "nmap", "category": "recon", "output_dir": "recon"}
        preset = {"label": "Quick", "cmd": ["nmap", "{host}"], "output": None}
        with patch.object(ui, "console", FakeConsole(["y"])), \
                patch.object(ui.tui, "available", return_value=False), \
                patch.object(ui, "resolve_tool_binary", return_value="nmap"), \
                patch.object(ui.tgt, "scope_hosts", return_value=["example.test"]), \
                patch.dict(ui.tgt.TARGET,
                           {"host": "example.test", "url": "http://example.test", "port": "80"},
                           clear=False), \
                patch.object(ui.executor, "run_tool", return_value=0) as run_tool:
            rc = ui.run_preset(tool, preset, pause_after=False,
                               flow_context={"name": "Basic", "index": 2, "total": 5})
        self.assertEqual(rc, 0)
        self.assertEqual(run_tool.call_args.kwargs["context"]["flow"],
                         {"name": "Basic", "index": 2, "total": 5})

    def test_run_preset_without_flow_context_sets_no_flow_key(self):
        tool = {"name": "Nmap", "binary": "nmap", "category": "recon", "output_dir": "recon"}
        preset = {"label": "Quick", "cmd": ["nmap", "{host}"], "output": None}
        with patch.object(ui, "console", FakeConsole(["y"])), \
                patch.object(ui.tui, "available", return_value=False), \
                patch.object(ui, "resolve_tool_binary", return_value="nmap"), \
                patch.object(ui.tgt, "scope_hosts", return_value=["example.test"]), \
                patch.dict(ui.tgt.TARGET,
                           {"host": "example.test", "url": "http://example.test", "port": "80"},
                           clear=False), \
                patch.object(ui.executor, "run_tool", return_value=0) as run_tool:
            ui.run_preset(tool, preset, pause_after=False)
        self.assertNotIn("flow", run_tool.call_args.kwargs["context"])


class HonestAmassTests(unittest.TestCase):
    def test_cli_amass_drops_deprecated_passive_and_bogus_engine(self):
        presets = TOOLS["amass"]["presets"]
        self.assertEqual(len(presets), 2)
        for p in presets:
            self.assertNotIn("-passive", p["cmd"])
            self.assertNotIn("-engine", p["cmd"])
        self.assertNotIn("-active", presets[0]["cmd"])
        self.assertIn("-active", presets[1]["cmd"])

    def test_cli_and_gui_amass_describe_the_same_thing(self):
        from desktop.catalog import catalog
        cli = TOOLS["amass"]["presets"]
        gui = next(e for e in catalog() if e["key"] == "amass")["presets"]
        self.assertEqual(len(cli), len(gui), 2)
        for p in gui:  # the engine URL was removed from the GUI too
            self.assertNotIn("-engine", p["args"])
            self.assertNotIn("-passive", p["args"])
        self.assertNotIn("-active", gui[0]["args"])
        self.assertIn("-active", gui[1]["args"])


class FlowPreviewKeyTests(unittest.TestCase):
    def test_preview_marks_a_preset_that_needs_a_missing_api_key(self):
        # nmap's shodan-api preset is the one preset that is key-gated.
        idx = next(i for i, p in enumerate(TOOLS["nmap"]["presets"])
                   if p.get("needs_key") == "shodan")
        flow = {"name": "Key", "desc": "", "steps": [("nmap", idx)]}
        console = FakeConsole()
        with patch.object(ui, "tool_available", return_value=True), \
                patch("core.availability.key_present", return_value=False), \
                patch.dict(flows.tgt.TARGET,
                           {"host": "example.test", "url": "http://example.test", "port": "80"},
                           clear=False), \
                patch.object(flows.ui, "console", console):
            records = flows._resolve_steps(flow)
            flows._render_preview(records)
        self.assertIn("needs the shodan API key", console.text)

    def test_preview_omits_key_note_once_the_key_is_present(self):
        idx = next(i for i, p in enumerate(TOOLS["nmap"]["presets"])
                   if p.get("needs_key") == "shodan")
        flow = {"name": "Key", "desc": "", "steps": [("nmap", idx)]}
        console = FakeConsole()
        with patch.object(ui, "tool_available", return_value=True), \
                patch("core.availability.key_present", return_value=True), \
                patch.dict(flows.tgt.TARGET,
                           {"host": "example.test", "url": "http://example.test", "port": "80"},
                           clear=False), \
                patch.object(flows.ui, "console", console):
            records = flows._resolve_steps(flow)
            flows._render_preview(records)
        self.assertNotIn("(needs the shodan API key)", console.text)


class CliAvailabilityStateTests(unittest.TestCase):
    def test_states_cover_ready_not_installed_and_needs_key(self):
        from core import availability as av
        shodan = get_tool("shodan")
        nmap = get_tool("nmap")
        self.assertEqual(av.for_cli("nmap", nmap, installed=False).state, av.NOT_INSTALLED)
        self.assertEqual(av.for_cli("nmap", nmap, installed=True).state, av.READY)
        with patch("core.availability.key_present", return_value=False):
            self.assertEqual(av.for_cli("shodan", shodan, installed=True).state, av.NEEDS_KEY)
        with patch("core.availability.key_present", return_value=True):
            self.assertEqual(av.for_cli("shodan", shodan, installed=True).state, av.READY)

    def test_fanout_threads_host_counter_into_the_scan_context(self):
        tool = {"name": "Nmap", "binary": "nmap", "category": "recon", "output_dir": "recon"}
        preset = {"label": "Quick", "cmd": ["nmap", "{host}"], "output": None}
        with patch.object(ui, "console", FakeConsole(["y"])), \
                patch.object(ui.tui, "available", return_value=False), \
                patch.object(ui, "resolve_tool_binary", return_value="nmap"), \
                patch.object(ui.tgt, "scope_hosts", return_value=["example.test", "a.example.test"]), \
                patch.object(ui.tgt, "scope_url", side_effect=lambda h: f"http://{h}"), \
                patch.dict(ui.tgt.TARGET,
                           {"host": "example.test", "url": "http://example.test", "port": "80"},
                           clear=False), \
                patch.object(ui.executor, "run_tool", return_value=0) as run_tool:
            ui.run_preset(tool, preset, pause_after=False)
        totals = {c.kwargs["context"].get("host_total") for c in run_tool.call_args_list}
        indices = [c.kwargs["context"].get("host_index") for c in run_tool.call_args_list]
        self.assertEqual(totals, {2})
        self.assertEqual(indices, [1, 2])


if __name__ == "__main__":
    unittest.main()
