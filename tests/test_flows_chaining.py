"""Attack-flow chaining in the desktop GUI.

Covers the overhaul of the Attack flows panel: a single "run the whole flow"
that chains steps automatically, visible step i/N progress, fields collected
once in the preparation screen, and the subdomain fan-out fix where a step is
only marked done after its final host.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Importing the harness builds the one offscreen QApplication the GUI needs.
from desktop_harness import wait_run
from PySide6.QtWidgets import QDialog

from desktop.window import Window
from desktop.storage import Store
from desktop.flow_panel import FlowPrepareDialog


def _run(flow_id, step, status, last=True, rid="r"):
    return {"flow_id": flow_id, "flow_step": step, "status": status, "flow_last": last, "id": rid}


class FlowChainingTests(unittest.TestCase):
    def test_run_all_prepares_once_then_chains_on_success_and_stops_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)); store.add_target("localhost"); window = Window(store)
            panel = window.flow_panel
            try:
                with patch.object(FlowPrepareDialog, "exec", return_value=QDialog.DialogCode.Accepted), \
                     patch.object(window, "launch", return_value=True) as launch:
                    panel.run_all()
                    sid = panel.session.record["id"]
                    # Preparation accepted: auto-run armed, first step launched once,
                    # with no per-step modal (show_dialog=False).
                    self.assertTrue(panel.auto_run); self.assertFalse(panel.confirm_each)
                    self.assertEqual(launch.call_count, 1)
                    self.assertFalse(launch.call_args.kwargs["show_dialog"])
                    self.assertEqual(panel.session.record["steps"][0]["status"], "running")
                    # Success chains straight into the next step.
                    panel.completed(_run(sid, 0, "success", rid="r0"))
                    self.assertEqual(panel.session.record["steps"][0]["status"], "success")
                    self.assertEqual(panel.list.currentRow(), 1)
                    self.assertEqual(launch.call_count, 2)
                    # A failure stops the chain; nothing else is launched.
                    panel.completed(_run(sid, 1, "failed", rid="r1"))
                    self.assertEqual(panel.session.record["steps"][1]["status"], "failed")
                    self.assertFalse(panel.auto_run)
                    self.assertEqual(launch.call_count, 2)
            finally:
                window.close()

    def test_confirm_each_keeps_values_but_does_not_autolaunch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)); store.add_target("localhost"); window = Window(store)
            panel = window.flow_panel
            try:
                created = {}
                original_init = FlowPrepareDialog.__init__
                def capture_init(self, *args, **kwargs):
                    original_init(self, *args, **kwargs); created["dialog"] = self
                def accept():
                    created["dialog"].confirm_each.setChecked(True); return QDialog.DialogCode.Accepted
                with patch.object(FlowPrepareDialog, "__init__", capture_init), \
                     patch.object(FlowPrepareDialog, "exec", side_effect=accept), \
                     patch.object(window, "launch", return_value=True) as launch:
                    panel.run_all()
                    sid = panel.session.record["id"]
                    # Step-by-step: preparation stored, but no step launched yet.
                    self.assertTrue(panel.auto_run); self.assertTrue(panel.confirm_each)
                    self.assertEqual(launch.call_count, 0)
                    # The user triggers each step; prepared values are reused (no modal).
                    panel.list.setCurrentRow(0); panel.start_step()
                    self.assertEqual(launch.call_count, 1)
                    self.assertFalse(launch.call_args.kwargs["show_dialog"])
                    # Success advances the selection but does not auto-launch the next.
                    panel.completed(_run(sid, 0, "success", rid="r0"))
                    self.assertEqual(panel.list.currentRow(), 1)
                    self.assertEqual(launch.call_count, 1)
            finally:
                window.close()

    def test_fanout_step_marked_done_only_after_last_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)); store.add_target("localhost"); window = Window(store)
            panel = window.flow_panel; panel.ensure_session(); sid = panel.session.record["id"]
            try:
                with patch.object(window, "launch", return_value=True):
                    panel.list.setCurrentRow(0); panel.start_step()
                    self.assertEqual(panel.session.record["steps"][0]["status"], "running")
                    # Intermediate hosts (success and failure) must not finalise the step.
                    panel.completed(_run(sid, 0, "success", last=False, rid="h1"))
                    self.assertEqual(panel.session.record["steps"][0]["status"], "running")
                    panel.completed(_run(sid, 0, "failed", last=False, rid="h2"))
                    self.assertEqual(panel.session.record["steps"][0]["status"], "running")
                    # The final host finalises it.
                    panel.completed(_run(sid, 0, "success", last=True, rid="h3"))
                    self.assertEqual(panel.session.record["steps"][0]["status"], "success")
                    # Aborting mid fan-out finalises the running step as cancelled.
                    panel.list.setCurrentRow(1); panel.start_step()
                    panel.completed(_run(sid, 1, "cancelled", last=False, rid="h4"))
                    self.assertEqual(panel.session.record["steps"][1]["status"], "cancelled")
            finally:
                window.close()

    def test_flow_run_shows_step_progress_and_determinate_bar(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)); window = Window(store)
            meta = {"flow_id": "f", "flow_name": "Démo", "flow_step": 2, "flow_total": 6, "flow_target": None}
            captured = {}
            try:
                def start():
                    window.launch("desktop-diagnostic", show_dialog=False, metadata=meta)
                    captured["title"] = window.run_title.text()
                    captured["max"] = window.progress.maximum()
                    captured["val"] = window.progress.value()
                    captured["text"] = window.progress.isTextVisible()
                result = wait_run(window.runner, start)
                self.assertEqual(result["status"], "success")
                self.assertIn("3/6", captured["title"])
                self.assertEqual(captured["max"], 6)
                self.assertEqual(captured["val"], 3)
                self.assertTrue(captured["text"])
                # The record carries the fan-out position used by the fix above.
                self.assertTrue(result["flow_last"])
                self.assertEqual(result["flow_total"], 6)
            finally:
                window.close()

    def test_prepare_dialog_collects_typed_fields_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)); store.add_target("https://example.test"); window = Window(store)
            panel = window.flow_panel; panel.ensure_session()
            try:
                dialog = FlowPrepareDialog(panel, window, panel.session.flow,
                                           panel.session.record.get("target"), panel.session.flow["steps"])
                # The first step (dig) exposes a typed field; it is editable here, once.
                self.assertIn(0, dialog.editors); self.assertIn("nameserver", dialog.editors[0])
                dialog.editors[0]["nameserver"].setText("1.1.1.1")
                self.assertEqual(dialog.values()[0]["nameserver"], "1.1.1.1")
                dialog.deleteLater()
            finally:
                window.close()

    def test_step_list_shows_previewed_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)); store.add_target("https://example.test"); window = Window(store)
            panel = window.flow_panel; panel.ensure_session()
            try:
                key, index = panel.session.flow["steps"][0]
                preview = panel._step_command(key, index, panel.session.record.get("target"))
                self.assertTrue(preview)
                self.assertNotIn("\n", preview)
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()
