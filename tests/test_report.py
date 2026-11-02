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
                           "api.example.com", "--key '[redacted]'",
                           "Declared scope (operator configuration at report time)",
                           "… 20 more line(s) in the raw log", "Raw log"):
                self.assertIn(needle, doc)
            self.assertNotIn("Whois", doc)
            self.assertNotIn("line 59", doc)  # excerpt bounded to EXCERPT_LINES
            # R02: the report never certifies what traffic was emitted.
            self.assertNotIn("No host outside this scope was targeted", doc)
            self.assertNotIn("Testing stayed within", doc)
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

    def test_cli_results_group_timestamped_reruns_under_one_tool(self):
        # R06: unique per-run output files (stamp appended by executor) must still
        # be recovered as the same tool/host and all preserved in the report.
        d = self.root / "targets" / "example.com"
        (d / "recon").mkdir(parents=True)
        (d / "recon" / "nmap_quick_example.com_20261101-100000-aaaaaa.txt").write_text("run1\n", encoding="utf-8")
        (d / "recon" / "nmap_quick_example.com_20261102-110000-bbbbbb.txt").write_text("run2\n", encoding="utf-8")
        (d / "recon" / "nmap_quick_example.com__api.example.com_20261102-120000-cccccc.txt").write_text("run3\n", encoding="utf-8")
        target = {"host": "example.com", "url": "https://example.com", "port": "443"}
        mission = report.from_cli_results(d, target)
        self.assertEqual([(r.tool, r.host) for r in mission.runs],
                         [("nmap_quick", ""), ("nmap_quick", ""), ("nmap_quick", "api.example.com")])

    def test_scope_is_declared_not_certified(self):
        # R02: the scope statement describes the operator's configuration and
        # the hosts the runs were planned against; it never asserts, as proven
        # fact, that nothing outside the scope was contacted.
        store, target = _gui_fixture(self.root)
        mission = report.from_gui_history(target, store.history())
        for fmt in ("md", "txt"):
            doc = " ".join(report.render(mission, fmt).split())  # undo the 80-column wrapping
            self.assertIn("Declared scope (operator configuration at report time): example.com + 2 subdomain(s)", doc)
            self.assertIn("not a verification of the traffic", doc)
            self.assertIn("planned against, from the run records: example.com", doc)
            self.assertNotIn("No host outside this scope was targeted", doc)
            self.assertNotIn("stayed within", doc)
        pdf_text = _pdf_text(report.render_pdf(mission))  # parentheses are escaped in PDF streams
        self.assertIn("Declared scope", pdf_text)
        self.assertNotIn("No host outside this scope", pdf_text)
        data = json.loads(report.render_json(mission))
        self.assertEqual(data["target"]["scope_kind"], "declared")
        self.assertEqual(data["findings"]["declared_scope"], "example.com + 2 subdomain(s)")
        self.assertEqual(data["findings"]["planned_hosts"], ["example.com"])
        self.assertNotIn("No host outside", data["findings"]["scope_statement"])
        self.assertNotIn("stayed within", data["findings"]["scope_statement"])

    def test_gui_runs_keep_their_recorded_scope_not_the_current_one(self):
        # R02: a run recorded under the base-host-only scope keeps that scope in the
        # report even after the operator enables subdomains on the same target.
        store, target = _gui_fixture(self.root)
        store.set_target_scope(target["id"], include=False)
        store.save()
        folder, rec = store.new_run("Nmap", "Later", store.active_target, ["nmap", "example.com"])
        rec.update(status="success", finished=rec["started"], exit_code=0)
        write_json(folder / "run.json", rec)
        (folder / "output.txt").write_text("ok\n", encoding="utf-8")
        store.set_target_scope(target["id"], include=True)
        store.save()
        mission = report.from_gui_history(store.active_target, store.history())
        self.assertEqual(mission.scope_text(), "example.com + 2 subdomain(s)")
        by_preset = {r.preset: r.scope for r in mission.runs}
        self.assertEqual(by_preset["Later"], "example.com (base host only)")
        self.assertEqual(by_preset["Profil 0"], "example.com + 2 subdomain(s)")
        self.assertEqual(mission.runs_without_scope(), 0)
        txt = " ".join(report.render_text(mission).split())
        self.assertIn("Scope at run time: example.com (base host only)", txt)
        self.assertNotIn("carry no recorded scope snapshot", txt)

    def test_cli_results_are_not_attributed_to_the_current_scope(self):
        # R02: CLI result files carry no scope snapshot; the report says so
        # instead of stamping the live SCOPE globals onto historical results.
        d = _cli_fixture(self.root)
        target = {"host": "example.com", "url": "https://example.com", "port": "443"}
        mission = report.from_cli_results(d, target, {"include_subdomains": True, "subdomains": ["api.example.com"]})
        self.assertEqual([r.scope for r in mission.runs], ["", "", ""])
        self.assertEqual(mission.runs_without_scope(), 3)
        self.assertEqual(mission.planned_hosts(), ["api.example.com", "example.com"])
        txt = " ".join(report.render_text(mission).split())
        self.assertIn("Scope at run time: not recorded", txt)
        self.assertIn("3 of 3 operation(s) carry no recorded scope snapshot", txt)
        self.assertIn("not necessarily the one in force when they ran", txt)
        self.assertIn("planned against, from the run records: api.example.com, example.com", txt)
        self.assertNotIn("No host outside this scope was targeted", txt)
        data = json.loads(report.render_json(mission))
        self.assertEqual(data["findings"]["runs_without_scope_snapshot"], 3)
        self.assertEqual(data["findings"]["planned_hosts"], ["api.example.com", "example.com"])

    def test_excerpt_reads_a_bounded_window_of_a_large_log(self):
        # R05: the excerpt must never materialise the whole log. A spy on the
        # file handle counts every byte read; the total must stay far below the
        # file size, and the report must flag the truncation.
        log = self.root / "output.txt"
        line = ("x" * 200 + "\n").encode()
        size = 0
        with log.open("wb") as fh:
            for n in range(20_000):  # ~4 MB, far above EXCERPT_MAX_BYTES
                size += fh.write(f"line {n} ".encode() + line)
        self.assertGreater(size, 50 * report.EXCERPT_MAX_BYTES)
        reads = []
        real_open = Path.open

        class Spy:
            def __init__(self, handle):
                self.handle = handle

            def read(self, n=-1):
                data = self.handle.read(n)
                reads.append(len(data))
                return data

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return self.handle.__exit__(*exc)

            def __getattr__(self, name):
                return getattr(self.handle, name)

        with patch.object(Path, "read_bytes", side_effect=AssertionError("whole-file read")), \
                patch.object(Path, "open", lambda self, *a, **k: Spy(real_open(self, *a, **k))):
            shown, more, truncated = report._excerpt(log, report.EXCERPT_LINES)
        self.assertTrue(reads, "the excerpt must read through the file handle")
        self.assertLessEqual(sum(reads), report.EXCERPT_MAX_BYTES + 1)
        self.assertLess(sum(reads), size // 50)
        self.assertEqual(len(shown), report.EXCERPT_LINES)
        self.assertEqual(shown[0][:7], "line 0 ")
        self.assertTrue(all(len(l) <= report.EXCERPT_WIDTH + 1 for l in shown))
        self.assertTrue(truncated)
        self.assertGreater(more, 0)
        self.assertLess(more, 20_000 - report.EXCERPT_LINES)  # counted inside the window only
        run = report.ReportRun(tool="t", excerpt=shown, excerpt_more=more, excerpt_truncated=truncated)
        mission = report.MissionReport(target="x.test", host="x.test", runs=[run])
        txt = report.render_text(mission)
        self.assertIn(f"… at least {more} more line(s) in the raw log", txt)
        self.assertIn(f"only the first {report.EXCERPT_MAX_BYTES} bytes were inspected", txt)
        self.assertNotIn("line 19999", txt)
        # Small files keep the exact, untruncated behaviour.
        small = self.root / "small.txt"
        small.write_text("\n".join(f"l{n}" for n in range(60)), encoding="utf-8")
        shown, more, truncated = report._excerpt(small, report.EXCERPT_LINES)
        self.assertEqual((len(shown), more, truncated), (report.EXCERPT_LINES, 20, False))
        # A huge single line without newline is cut at the window, not loaded whole.
        huge = self.root / "huge.txt"
        with huge.open("wb") as fh:
            for _ in range(300):
                fh.write(b"y" * 10_000)
        shown, more, truncated = report._excerpt(huge, report.EXCERPT_LINES)
        self.assertTrue(truncated)
        self.assertLessEqual(len(shown), 1)
        self.assertTrue(all(len(l) <= report.EXCERPT_WIDTH + 1 for l in shown))

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
