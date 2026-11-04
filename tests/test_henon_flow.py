"""The built-in Henon attack-map flow (FLOWS['4']) and its auto-export.

Covers the three things the flow adds on top of the export engine already
exercised by ``tests/test_henon_export.py``:

* the flow definition is valid under *both* front-end validators
  (``core.flows._valid_flow`` and ``desktop.flows.validate_flow``) and the
  desktop validator preserves its ``export`` marker (CLI/GUI parity);
* the CLI flow runner writes a conforming ``recon.json`` when — and only when —
  a completed flow declares ``export: henon``;
* the Desktop runner maps its own per-run output tree to the same contract,
  and neither path ever persists a secret from a crawled URL.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import flows
from core import henon_export as henon
from core import target as tgt
from core.flow_definitions import FLOWS
from desktop import flows as dflows


_SECRET = "s3cr3t-token-value"


def _cli_results(target_dir):
    """A per-target CLI results tree with one file per Henon-flow family."""
    for cat in tgt.CATEGORIES:
        (target_dir / cat).mkdir(parents=True, exist_ok=True)
    (target_dir / "osint" / "dig_a_example.com.txt").write_text(
        "203.0.113.10\n", encoding="utf-8")
    (target_dir / "osint" / "subfinder_example.com.txt").write_text(
        "api.example.com\nwww.example.com\n", encoding="utf-8")
    (target_dir / "recon" / "nmap_svcver_example.com.txt").write_text(
        "Nmap scan report for example.com (203.0.113.10)\n"
        "PORT   STATE SERVICE VERSION\n"
        "80/tcp open  http    nginx 1.18.0\n", encoding="utf-8")
    (target_dir / "web_enum" / "httpx_info_example.com.txt").write_text(
        "https://example.com [200] [Example] [nginx]\n", encoding="utf-8")
    # A crawled/probed URL carrying a secret query value: the value must never
    # reach the exported file; only the parameter name survives.
    (target_dir / "vulnscan" / "nuclei_default_example.com.txt").write_text(
        f"[CVE-2021-41773] [http] [critical] https://example.com/a?token={_SECRET}\n",
        encoding="utf-8")


class HenonFlowDefinitionTests(unittest.TestCase):
    def test_flow_present_and_shaped(self):
        flow = FLOWS["4"]
        self.assertEqual(flow["export"], "henon")
        self.assertTrue(flow["name"])
        self.assertEqual(flow["steps"][0], ("dig", 0))
        # Every step points at a real tool/preset.
        self.assertTrue(flows._valid_flow(flow))

    def test_valid_under_desktop_validator_and_export_preserved(self):
        cleaned = dflows.validate_flow(FLOWS["4"])
        self.assertEqual(cleaned["export"], "henon")
        self.assertEqual([tuple(s) for s in cleaned["steps"]], list(FLOWS["4"]["steps"]))

    def test_desktop_validator_drops_unknown_export_marker(self):
        # Only a non-empty string marker survives; anything else is ignored so a
        # corrupt custom flow cannot smuggle in a bogus export behaviour.
        cleaned = dflows.validate_flow({"name": "x", "steps": [["dig", 0]], "export": 123})
        self.assertNotIn("export", cleaned)


class _TargetSandbox(unittest.TestCase):
    """Point ``core.target`` at a throwaway results root for the whole test."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="chaostic-henon-flow-")
        self.root = Path(self.temp.name)
        self._saved_root = tgt.TARGETS_ROOT
        self._saved_target = dict(tgt.TARGET)
        self._saved_scope = dict(tgt.SCOPE)
        tgt.TARGETS_ROOT = self.root / "targets"
        tgt.TARGET.update(host="example.com", url="https://example.com", port="443")
        tgt.SCOPE.update(include_subdomains=True,
                         subdomains=["api.example.com", "www.example.com"], excluded=[])
        self.addCleanup(self._restore)

    def _restore(self):
        tgt.TARGETS_ROOT = self._saved_root
        tgt.TARGET.clear(); tgt.TARGET.update(self._saved_target)
        tgt.SCOPE.clear(); tgt.SCOPE.update(self._saved_scope)
        self.temp.cleanup()


class HenonFlowCliAutoExportTests(_TargetSandbox):
    def test_runner_exports_on_completion(self):
        target_dir = tgt.target_dir()
        assert target_dir is not None
        _cli_results(target_dir)

        # Drive run_flow without any real UI or tool launch: keep every step on,
        # auto-chain, and report each launch as a success.
        with patch.object(flows, "_preview_flow", return_value=True), \
             patch.object(flows, "_ask_mode", return_value="auto"), \
             patch.object(flows.ui, "run_preset", return_value=0), \
             patch.object(flows.ui, "tool_available", return_value=True), \
             patch.object(flows.ui, "pause"), \
             patch.object(flows.ui, "header"), \
             patch.object(flows.ui.console, "print"):
            flows.run_flow(FLOWS["4"])

        recon = target_dir / "recon.json"
        self.assertTrue(recon.exists(), "the Henon flow must leave recon.json")
        doc = json.loads(recon.read_text(encoding="utf-8"))
        self.assertEqual(doc["schema_version"], 1)
        self.assertTrue(doc.get("assets"), "assets expected from dig/subfinder")
        blob = recon.read_text(encoding="utf-8")
        self.assertNotIn(_SECRET, blob, "a crawled secret must never be exported")
        # The CVE id is preserved for Henon's R08 inference.
        self.assertIn("CVE-2021-41773", blob)

    def test_runner_does_not_export_without_marker(self):
        target_dir = tgt.target_dir()
        assert target_dir is not None
        _cli_results(target_dir)
        plain = {k: v for k, v in FLOWS["1"].items()}  # Basic flow: no export marker
        self.assertNotIn("export", plain)
        with patch.object(flows, "_preview_flow", return_value=True), \
             patch.object(flows, "_ask_mode", return_value="auto"), \
             patch.object(flows.ui, "run_preset", return_value=0), \
             patch.object(flows.ui, "tool_available", return_value=True), \
             patch.object(flows.ui, "pause"), \
             patch.object(flows.ui, "header"), \
             patch.object(flows.ui.console, "print"):
            flows.run_flow(plain)
        self.assertFalse((target_dir / "recon.json").exists())

    def test_auto_export_skips_when_no_target(self):
        # Clearing the target makes target_dir() None; the helper must not raise.
        tgt.TARGET.update(host="", url="")
        with patch.object(flows.ui.console, "print"):
            flows._auto_export_henon(FLOWS["4"])  # no exception == pass


class HenonFlowDesktopExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="chaostic-henon-desk-")
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def _run(self, run_id, output_base_text):
        d = self.root / "runs" / run_id
        d.mkdir(parents=True)
        (d / "output.txt").write_text(output_base_text, encoding="utf-8")

    def test_export_flow_henon_maps_runs_and_redacts(self):
        (self.root / "flows" / "history").mkdir(parents=True)
        self._run("r-dig", "203.0.113.10\n")
        self._run("r-sub", "api.example.com\nwww.example.com\n")
        self._run("r-nuclei",
                  f"[CVE-2021-41773] [http] [critical] https://example.com/a?token={_SECRET}\n")
        target = {"host": "example.com", "url": "https://example.com", "port": "443",
                  "subdomains": ["api.example.com", "www.example.com"], "excluded": []}
        record = {
            "id": "flow-1", "target": target,
            "steps": [
                {"tool": "dig", "cli_index": 0, "status": "success", "run_id": "r-dig"},
                {"tool": "subfinder", "cli_index": 0, "status": "success", "run_id": "r-sub"},
                {"tool": "nuclei", "cli_index": 0, "status": "success", "run_id": "r-nuclei"},
                # A pending step with no run_id must be ignored, never crash.
                {"tool": "httpx", "cli_index": 1, "status": "pending"},
            ],
        }
        path = dflows.export_flow_henon(self.root, FLOWS["4"], record)
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(doc["schema_version"], 1)
        self.assertTrue(doc.get("assets"))
        blob = Path(path).read_text(encoding="utf-8")
        self.assertNotIn(_SECRET, blob)
        self.assertIn("CVE-2021-41773", blob)

    def test_excluded_subdomain_never_exported(self):
        (self.root / "flows" / "history").mkdir(parents=True)
        self._run("r-sub", "api.example.com\nlegacy.example.com\n")
        target = {"host": "example.com", "url": "https://example.com",
                  "subdomains": ["api.example.com", "legacy.example.com"],
                  "excluded": ["legacy.example.com"]}
        record = {"id": "flow-2", "target": target,
                  "steps": [{"tool": "subfinder", "cli_index": 0,
                             "status": "success", "run_id": "r-sub"}]}
        path = dflows.export_flow_henon(self.root, FLOWS["4"], record)
        blob = Path(path).read_text(encoding="utf-8")
        self.assertIn("api.example.com", blob)
        self.assertNotIn("legacy.example.com", blob)


class HenonWriteExportSafetyTests(unittest.TestCase):
    def test_write_export_replaces_symlink_without_following_it(self):
        # A planted recon.json symlink must never redirect the write to its
        # target (CWE-59); the CLI often runs under sudo (see write_export).
        tmp = Path(tempfile.mkdtemp(prefix="chaostic-henon-link-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        victim = tmp / "victim.txt"
        victim.write_text("DO NOT OVERWRITE", encoding="utf-8")
        link = tmp / "recon.json"
        link.symlink_to(victim)
        henon.write_export({"schema_version": 1}, link)
        self.assertFalse(link.is_symlink(), "the symlink must be replaced, not followed")
        self.assertEqual(victim.read_text(encoding="utf-8"), "DO NOT OVERWRITE")
        self.assertEqual(json.loads(link.read_text(encoding="utf-8"))["schema_version"], 1)

    def test_write_export_refuses_a_symlinked_parent_under_root(self):
        # A symlinked *directory* component under the app-owned root must be
        # refused when `within` bounds the write, so it cannot redirect the
        # write outside the tree under sudo (CWE-59, parent-component vector).
        tmp = Path(tempfile.mkdtemp(prefix="chaostic-henon-linkdir-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        root = tmp / "targets"
        root.mkdir()
        outside = tmp / "outside"
        outside.mkdir()
        (root / "acme.tld").symlink_to(outside, target_is_directory=True)
        dest = root / "acme.tld" / "recon.json"
        with self.assertRaises(OSError):
            henon.write_export({"schema_version": 1}, dest, within=root)
        self.assertFalse((outside / "recon.json").exists(),
                         "nothing may be written through the symlinked directory")


class HenonDeletedRunCleanupTests(unittest.TestCase):
    def test_delete_run_drops_the_stale_recon_export(self):
        from desktop.storage import Store, write_json
        temp = tempfile.TemporaryDirectory(prefix="chaostic-henon-del-")
        self.addCleanup(temp.cleanup)
        store = Store(Path(temp.name))
        target = {"id": "t1", "label": "acme", "host": "acme.tld",
                  "port": "443", "url": "https://acme.tld"}
        directory, record = store.new_run("subfinder", "Passive subdomains (fast)", target, ["subfinder"])
        (directory / "output.txt").write_text("api.acme.tld\n", encoding="utf-8")
        record["status"] = "success"
        write_json(directory / "run.json", record)
        # A flow history record that referenced that run, plus its derived export.
        fid = "flow-del-1"
        hist = store.root / "flows" / "history"
        hist.mkdir(parents=True, exist_ok=True)
        write_json(hist / (fid + ".json"), {
            "id": fid, "name": "Henon attack-map flow", "target": target,
            "steps": [{"tool": "subfinder", "cli_index": 0, "status": "success",
                       "run_id": record["id"]}], "status": "success"})
        recon = hist / (fid + ".recon.json")
        recon.write_text('{"schema_version": 1}\n', encoding="utf-8")

        store.delete_run(record["id"])

        self.assertFalse(recon.exists(), "a stale export must not outlive its source runs")
        flow = json.loads((hist / (fid + ".json")).read_text(encoding="utf-8"))
        self.assertEqual(flow["steps"][0]["status"], "deleted")


if __name__ == "__main__":
    unittest.main()
