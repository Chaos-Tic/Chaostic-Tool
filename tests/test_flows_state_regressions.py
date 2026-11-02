"""Prepared attack-flow state in the desktop GUI (pro plan Lot 0: R08, R09, R10, R11).

Each regression states the result the operator should get:

* R08 — editing a target card must not rewrite the target of a flow session
  that was already prepared (``FlowSession`` keeps a reference to the store's
  dict and ``Store.update_target`` mutates that dict in place).
* R09 — a flow step that expands to more than ``WARN_FANOUT`` hosts must ask
  the same confirmation as a manual launch (``Window.launch`` only gates the
  fan-out when ``show_dialog`` is true, and prepared steps launch with
  ``show_dialog=False``).
* R10 — a fan-out step with a failed host must not chain into the next step as
  if it had succeeded (only the last host finalises the step, so the earlier
  failures vanish).
* R11 — changing the flow target after preparation must reset the prepared
  state; ``start_step`` otherwise dereferences ``session.flow`` on ``None``.

The bug-demonstrating tests are plain pytest functions marked
``xfail(strict=True)``: ``python -m unittest discover`` (the CI runner) does not
collect them, so CI stays green, and under pytest they turn red (XPASS) the day
the bug is fixed without the marker being removed. The ``unittest`` class
anchors the neighbouring behaviour that is already correct.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

# Importing the harness builds the one offscreen QApplication the GUI needs.
from desktop_harness import APP
from PySide6.QtWidgets import QDialog, QMessageBox

from core.subdomains import WARN_FANOUT
from desktop.flow_panel import FlowPrepareDialog
from desktop.launch_dialog import LaunchDialog
from desktop.storage import Store
from desktop.window import Window

FIRST = "https://first.example"
SECOND = "https://second.example"
ACCEPTED = QDialog.DialogCode.Accepted

R08 = pytest.mark.xfail(
    strict=True,
    reason="R08: FlowSession keeps a reference to the store target and Store.update_target mutates it in place — pro plan Lot 0",
)
R09 = pytest.mark.xfail(
    strict=True,
    reason="R09: the fan-out confirmation is skipped when a prepared flow step launches with show_dialog=False — pro plan Lot 0",
)
R10 = pytest.mark.xfail(
    strict=True,
    reason="R10: only the last host of a fan-out finalises a flow step, so earlier failed hosts count as success — pro plan Lot 0",
)
R11 = pytest.mark.xfail(
    strict=True,
    reason="R11: change_target drops the session but keeps auto_run/prepared, so start_step crashes on session=None — pro plan Lot 0",
)


class _Desktop:
    """A Store in a temporary directory with one target, and a Window on it; closed afterwards."""

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name))
        self.store.settings.update(animations=False, check_updates=False)
        self.store.add_target(FIRST)
        self.window = Window(self.store)
        self.panel = self.window.flow_panel
        return self

    def __exit__(self, *exc):
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()
        self.temp.cleanup()
        return False


def _run(flow_id, step, status, last=True, rid="r"):
    return {"flow_id": flow_id, "flow_step": step, "status": status, "flow_last": last, "id": rid}


def _fanout_tool():
    """A host-targeted native tool, so a launch expands over the subdomain scope."""
    return dict(key="fanout-helper", name="Fan-out helper", mode="native", binary=sys.executable,
                category="recon", desc="Host-targeted helper", linux_presets=[],
                presets=[dict(label="Host", args=["-c", "pass", "{host}"], needs_target=True)])


def _wide_scope(store, extra=15):
    """Enable a subdomain scope that expands well past the confirmation threshold."""
    target_id = store.targets[0]["id"]
    subdomains = [f"s{i:03d}.first.example" for i in range(WARN_FANOUT + extra)]
    store.set_target_scope(target_id, subdomains=subdomains, include=True)
    return store.active_target


def _prepare_whole_flow(desktop):
    """Accept the preparation screen (auto-run armed) with the first step launched through a stub."""
    with patch.object(FlowPrepareDialog, "exec", return_value=ACCEPTED), \
         patch.object(desktop.window, "launch", return_value=True) as launch:
        desktop.panel.run_all()
    return launch


def _switch_target(panel, target_id):
    """Pick another flow target in the combo, answering Yes to the "new session" question."""
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        panel.refresh_targets()
        panel.target_select.setCurrentIndex(panel.target_select.findData(target_id))


class FlowStateAnchorTests(unittest.TestCase):
    """Behaviour that already holds and must keep holding once the bugs are fixed."""

    def test_update_target_rewrites_the_card_in_the_store(self):
        with _Desktop() as d:
            target_id = d.store.targets[0]["id"]
            d.store.update_target(target_id, SECOND, "Edited")
            self.assertEqual(d.store.targets[0]["host"], "second.example")
            self.assertEqual(d.store.targets[0]["label"], "Edited")

    def test_manual_launch_asks_before_a_large_fanout(self):
        with _Desktop() as d:
            target = _wide_scope(d.store)
            with patch.object(LaunchDialog, "exec", return_value=ACCEPTED), \
                 patch.object(d.window, "_confirm_fanout", side_effect=lambda t, hosts: hosts[:WARN_FANOUT]) as confirm, \
                 patch.object(d.window, "_start_run") as start:
                self.assertTrue(d.window.launch("fanout-helper", tool_override=_fanout_tool(), target_override=target))
            confirm.assert_called_once()
            self.assertEqual(len(confirm.call_args.args[1]), WARN_FANOUT + 16)
            start.assert_called_once()
            # The operator's choice ("first K only") is what gets queued.
            self.assertEqual(len(d.window._fanout), WARN_FANOUT - 1)

    def test_changing_target_after_preparation_drops_the_session(self):
        with _Desktop() as d:
            _prepare_whole_flow(d)
            self.assertIsNotNone(d.panel.session)
            second = d.store.add_target(SECOND)
            _switch_target(d.panel, second["id"])
            self.assertIsNone(d.panel.session)
            self.assertEqual(d.panel.target_select.currentData(), second["id"])


@R08
def test_editing_the_target_card_does_not_rewrite_the_prepared_session_target():
    with _Desktop() as d:
        d.panel.ensure_session()
        target_id = d.store.targets[0]["id"]
        d.store.update_target(target_id, SECOND, "Edited")
        assert d.panel.session.record["target"]["host"] == "first.example"
        assert d.panel.session.record["target"]["url"].startswith(FIRST)


@R09
def test_prepared_flow_step_asks_before_the_same_large_fanout():
    with _Desktop() as d:
        target = _wide_scope(d.store)
        meta = {"flow_id": "f", "flow_name": "Flow", "flow_step": 0, "flow_total": 1, "flow_target": target}
        with patch.object(d.window, "_confirm_fanout", side_effect=lambda t, hosts: hosts[:WARN_FANOUT]) as confirm, \
             patch.object(d.window, "_start_run"):
            d.window.launch("fanout-helper", show_dialog=False, tool_override=_fanout_tool(),
                            target_override=target, metadata=meta)
        confirm.assert_called_once()
        # The operator's choice ("first K only") must be applied, not the whole scope.
        assert len(d.window._fanout) == WARN_FANOUT - 1


@R10
def test_run_all_does_not_chain_past_a_step_whose_host_failed():
    with _Desktop() as d:
        with patch.object(FlowPrepareDialog, "exec", return_value=ACCEPTED), \
             patch.object(d.window, "launch", return_value=True) as launch:
            d.panel.run_all()
            sid = d.panel.session.record["id"]
            assert launch.call_count == 1
            # Three hosts of step 1 fail, the last one succeeds.
            for k in range(3):
                d.panel.completed(_run(sid, 0, "failed", last=False, rid=f"h{k}"))
            d.panel.completed(_run(sid, 0, "success", last=True, rid="h3"))
            assert d.panel.session.record["steps"][0]["status"] != "success"
            assert launch.call_count == 1, "step 2 must not start after a partially failed step 1"


@R11
def test_changing_target_after_preparation_resets_the_prepared_state():
    with _Desktop() as d:
        _prepare_whole_flow(d)
        assert d.panel.auto_run
        second = d.store.add_target(SECOND)
        _switch_target(d.panel, second["id"])
        assert d.panel.session is None
        assert not d.panel.auto_run
        assert not d.panel.confirm_each
        assert d.panel.prepared == {}


@R11
def test_starting_a_step_after_a_target_change_runs_against_the_new_target():
    with _Desktop() as d:
        _prepare_whole_flow(d)
        second = d.store.add_target(SECOND)
        _switch_target(d.panel, second["id"])
        with patch.object(d.window, "launch", return_value=True) as launch:
            d.panel.list.setCurrentRow(0)
            d.panel.start_step()  # must not raise
        assert launch.call_count == 1
        assert launch.call_args.kwargs["target_override"]["host"] == "second.example"


if __name__ == "__main__":
    unittest.main()
