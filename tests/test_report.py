"""Mission report engine (core.report) and its CLI / desktop export paths."""
import json
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from core import report
from core import session
from core import target as tgt
from core import ui
from core.version import VERSION
from desktop.storage import Store, write_json


def _gui_fixture(root):
    """A desktop store with one target (two subdomains) and three finished runs."""
    store = Store(root / "profile")
    target = store.add_target("https://example.com:8443", "Demo")
    store.set_target_scope(target["id"], subdomains=["api.example.com", "www.example.com"], include=True)
    plan = [("success", 0, "2026-10-31T10:00:00+00:00", "2026-10-31T10:01:30+00:00", ""),
            ("failed", 1, "2026-10-31T10:05:00+00:00", "2026-10-31T10:05:04+00:00", "nmap: host down"),
            ("interrupted", None, "2026-10-31T10:10:00+00:00", "2026-10-31T10:10:00+00:00", "")]
    for i, (status, code, started, finished, detail) in enumerate(plan):
        folder, rec = store.new_run("Nmap", f"Profil {i}", target, ["nmap", "-sV", "example.com", "--key", "[redacted]"])
        rec.update(status=status, started=started, finished=finished, exit_code=code, detail=detail)
        write_json(folder / "run.json", rec)
        (folder / "output.txt").write_text("\n".join(f"line {n} (x) \\ é" for n in range(60)), encoding="utf-8")
    # A run on another target must not leak into this target's report.
    other = store.add_target("other.test", "Other")
    folder, rec = store.new_run("Whois", "Local", other, ["whois", "other.test"])
    rec.update(status="success", finished=rec["started"], exit_code=0)
    write_json(folder / "run.json", rec)
    (folder / "output.txt").write_text("registrar: none\n", encoding="utf-8")
    store.settings["active_target"] = target["id"]
    store.save()
    return store, target


def _cli_fixture(root):
    d = root / "targets" / "example.com"
    for cat in tgt.CATEGORIES:
        (d / cat).mkdir(parents=True)
    (d / "recon" / "nmap_quick_example.com.txt").write_text("open 80\nopen 443\n", encoding="utf-8")
    (d / "recon" / "nmap_quick_example.com__api.example.com.txt").write_text("open 443\n", encoding="utf-8")
    (d / "web_enum" / "ffuf_example.com.txt").write_bytes(b"\0\1\2binary")
    return d


def _pdf_text(data):
    """Concatenate the inflated page streams of a built-in-writer PDF."""
    out = b""
    pos = 0
    while (start := data.find(b">>\nstream\n", pos)) != -1:
        start += len(b">>\nstream\n")
        end = data.index(b"\nendstream", start)
        out += zlib.decompress(data[start:end])
        pos = end + len(b"\nendstream")
    return out.decode("cp1252", errors="replace")


class ReportEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="chaostic-report-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_gui_history_report_in_every_format(self):
        store, target = _gui_fixture(self.root)
        mission = report.from_gui_history(target, store.history(), source=str(store.root))
        self.assertEqual(len(mission.runs), 3)
        self.assertEqual(mission.status_counts(), {"success": 1, "failed": 1, "interrupted": 1})
        self.assertEqual([r.duration() for r in mission.runs], ["1 min 30 s", "4.0 s", "0.0 s"])
        self.assertEqual(mission.scope_text(), "example.com + 2 subdomain(s)")
        md, txt, pdf, js = (report.render(mission, f) for f in ("md", "txt", "pdf", "json"))
        for doc in (md, txt):
            for needle in ("Demo", "example.com + 2 subdomain(s)", f"ChaosticTool {VERSION}",
                           "Completed", "Failed", "Interrupted", "1 min 30 s", "nmap: host down",
                           "api.example.com", "--key '[redacted]'", "Testing stayed within the declared scope",
                           "… 20 more line(s) in the raw log", "Raw log"):
                self.assertIn(needle, doc)
            self.assertNotIn("Whois", doc)
            self.assertNotIn("line 59", doc)  # excerpt bounded to EXCERPT_LINES
        self.assertIn("# Mission report — Demo", md)
        self.assertIn("## Summary", md)
        self.assertIn("```text", md)
        self.assertIn("MISSION REPORT — DEMO", txt)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"/Type /Page ", pdf)
        self.assertIn("Mission report", _pdf_text(pdf))
        self.assertIn("1 min 30 s", _pdf_text(pdf))
        data = json.loads(js)
        self.assertEqual(data["schema"], "chaostictool.mission-report")
        self.assertEqual(data["generator"]["version"], VERSION)
        self.assertEqual(data["summary"]["status_counts"], {"success": 1, "failed": 1, "interrupted": 1})
        self.assertEqual(len(data["operations"]), 3)
        self.assertEqual(data["operations"][0]["duration"], "1 min 30 s")
        self.assertEqual([f["status"] for f in data["findings"]["attention"]], ["failed", "interrupted"])
        self.assertEqual(data["target"]["subdomains"], ["api.example.com", "www.example.com"])

    def test_pdf_xref_offsets_and_pagination(self):
        store, target = _gui_fixture(self.root)
        mission = report.from_gui_history(target, store.history())
        mission.runs = mission.runs * 8  # enough content for several pages
        pdf = report.render_pdf(mission)
        pages = pdf.count(b"/Type /Page ")
        self.assertGreater(pages, 1)
        self.assertIn(f"Page {pages} / {pages}", _pdf_text(pdf))
        # Every xref entry must point at "<n> 0 obj".
        xref = pdf.index(b"xref\n")
        count = int(pdf[xref:].split(b"\n")[1].split()[1])
        entries = pdf[xref:].split(b"\n")[3:2 + count]
        for number, entry in enumerate(entries, 1):
            offset = int(entry.split()[0])
            self.assertTrue(pdf[offset:].startswith(f"{number} 0 obj".encode()), f"object {number}")
        self.assertEqual(int(pdf[pdf.rindex(b"startxref\n") + 10:].split()[0]), xref)

    def test_cli_results_report(self):
        d = _cli_fixture(self.root)
        target = {"host": "example.com", "url": "https://example.com", "port": "443"}
        mission = report.from_cli_results(d, target, {"include_subdomains": True, "subdomains": ["api.example.com"]})
        self.assertEqual([(r.tool, r.host, r.group) for r in mission.runs],
                         [("nmap_quick", "", "recon"), ("nmap_quick", "api.example.com", "recon"), ("ffuf", "", "web_enum")])
        self.assertEqual(mission.status_counts(), {"recorded": 3})
        self.assertEqual(mission.runs[2].excerpt, ["[binary file, not shown]"])
        txt = report.render_text(mission)
        self.assertRegex(txt, r"Recorded:\s+3\n")
        self.assertIn("nmap_quick @ api.example.com", txt)
        self.assertIn("Phases / flows: recon, web_enum", txt)
        empty = self.root / "targets" / "none"
        empty.mkdir()
        self.assertIn("No operation recorded", report.render_text(report.from_cli_results(empty, target)))

    def test_write_report_infers_format_and_rejects_unknown(self):
        mission = report.MissionReport(target="x.test", host="x.test", generated="2026-10-31T10:00:00+00:00")
        self.assertEqual(report.default_filename(mission, "pdf"), "mission-report_x.test_2026-10-31_10-00.pdf")
        for fmt in report.FORMATS:
            path = report.write_report(mission, self.root / f"r.{fmt}")
            self.assertTrue(path.exists() and path.stat().st_size > 0, fmt)
        self.assertEqual(report.write_report(mission, self.root / "noext", "json").suffix, ".json")
        self.assertTrue(report.write_report(mission, self.root / "r.pdf").read_bytes().startswith(b"%PDF-"))
        with self.assertRaises(ValueError):
            report.write_report(mission, self.root / "r.docx")

    def test_cli_export_action_writes_requested_format(self):
        d = _cli_fixture(self.root)
        with patch.dict(tgt.TARGET, {"host": "example.com", "url": "https://example.com", "port": "443"}), \
                patch.dict(tgt.SCOPE, {"include_subdomains": False, "subdomains": []}), \
                patch.object(ui, "pause"):
            written = session.export_mission_report(d, fmt="pdf", destination=self.root / "out" / "mission.pdf")
            self.assertTrue(written.read_bytes().startswith(b"%PDF-"))
            # Interactive path: format and destination come from the prompts, defaults inside the target dir.
            with patch.object(ui, "ask", side_effect=lambda prompt, default=None, **_: default):
                written = session.export_mission_report(d)
            self.assertEqual(written.parent, d)
            self.assertEqual(written.suffix, ".md")
            self.assertIn("nmap_quick", written.read_text(encoding="utf-8"))
            with patch.object(ui, "ask", return_value="docx"):
                self.assertIsNone(session.export_mission_report(d))


class DesktopReportExportTests(unittest.TestCase):
    def setUp(self):
        from desktop_harness import APP  # noqa: F401  (offscreen QApplication)
        self.temp = tempfile.TemporaryDirectory(prefix="chaostic-report-gui-")
        self.root = Path(self.temp.name)
        self.store, self.target = _gui_fixture(self.root)

    def tearDown(self):
        from desktop_harness import APP
        APP.processEvents()
        self.temp.cleanup()

    def test_history_export_writes_mission_report_per_format_and_raw_log(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from desktop.i18n import T
        from desktop.window import Window
        w = Window(self.store)
        try:
            with patch.object(QMessageBox, "warning", side_effect=AssertionError("unexpected warning")):
                # No selected run: the active target is reported, through the dialog, format from the filter.
                with patch.object(QFileDialog, "getSaveFileName", return_value=(str(self.root / "no-ext"), T("Rapport de mission PDF (*.pdf)"))):
                    written = w.export_history()
                self.assertEqual(written.suffix, ".pdf")
                self.assertTrue(written.read_bytes().startswith(b"%PDF-"))
                for fmt in ("md", "txt", "json"):
                    written = w.export_history(str(self.root / f"mission.{fmt}"), None)
                    text = written.read_text(encoding="utf-8")
                    self.assertIn("Demo", text)
                    self.assertIn("nmap", text)
                    self.assertNotIn("Whois", text)
                # Same data, same content as the CLI reference renderer.
                mission = report.from_gui_history(self.target, self.store.history(), source=str(self.store.root))
                expected = json.loads(report.render_json(mission))
                produced = json.loads((self.root / "mission.json").read_text(encoding="utf-8"))
                for key in ("target", "summary", "findings"):
                    self.assertEqual(produced[key], expected[key])
                # Selected run: the raw log copy is offered and copied verbatim.
                w.history_table.selectRow(0)
                run = w.selected_history()
                self.assertIsNotNone(run)
                written = w.export_history(str(self.root / "raw.txt"), T("Journal brut de cette opération (*.txt)"))
                self.assertEqual(written.read_bytes(), (Path(run["directory"]) / "output.txt").read_bytes())
                self.assertIsNone(w.export_history("", None))
        finally:
            w.close()
            w.deleteLater()


if __name__ == "__main__":
    unittest.main()
