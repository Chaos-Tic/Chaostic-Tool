"""Target URL preservation across the subdomain scope (pro plan Lot 0, R07).

A target entered as a full URL ("https://example.com/app?x=1") must reach a
``{url}`` preset intact. ``core.ui.run_preset`` rebuilds ``fill["url"]`` from
``tgt.scope_url(host)`` for every scoped host, including the base host when the
subdomain scope is off, and ``scope_url`` derives the URL from host and port
alone: the scheme follows the port and the path, query and fragment are lost.

The bug-demonstrating tests are plain pytest functions marked
``xfail(strict=True)``: ``python -m unittest discover`` (the CI runner) does not
collect them, so CI stays green, and under pytest they turn red (XPASS) the day
the bug is fixed without the marker being removed. The ``unittest`` class
anchors the neighbouring behaviour that is already correct.
"""
import contextlib
import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest

FULL_URL = "https://example.com/app?x=1"

R07 = pytest.mark.xfail(
    strict=True,
    reason="R07: scope_url rebuilds the URL from host+port and drops scheme, path and query — pro plan Lot 0",
)


class _TargetEnv:
    """Isolated CLI data home with ``core.target`` pointed at it; restored afterwards."""

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"CHAOSTIC_CLI_HOME": self.temp.name}, clear=False)
        self.env.start()
        from core import target as tgt
        self.tgt = tgt
        self.saved_root = tgt.TARGETS_ROOT
        tgt.TARGETS_ROOT = tgt.data_home() / "targets"
        return tgt

    def __exit__(self, *_exc):
        self.tgt.TARGETS_ROOT = self.saved_root
        self.env.stop()
        self.temp.cleanup()
        return False


def _run_preset(preset):
    """Run one preset with the executor stubbed; returns the launched commands."""
    from core import ui
    tool = {"name": "X", "binary": "ZZ", "category": "recon", "output_dir": "recon", "interactive": False}
    calls = []
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(ui.executor, "run_tool", lambda cmd, **_kw: calls.append(cmd)))
        stack.enter_context(patch.object(ui.tui, "available", lambda: False))
        stack.enter_context(patch.object(ui, "should_proxy_tool", lambda _t: False))
        stack.enter_context(patch.object(ui, "route_status", lambda _t=None: "LOCAL"))
        ui.run_preset(tool, preset, pause_after=False)
    return calls


class TargetUrlAnchorTests(unittest.TestCase):
    """Behaviour that already holds and must keep holding once R07 is fixed."""

    def test_target_entered_as_url_keeps_path_query_and_scheme(self):
        with _TargetEnv() as tgt:
            tgt.set_target(host=FULL_URL)
            self.assertEqual(tgt.TARGET["host"], "example.com")
            self.assertEqual(tgt.TARGET["url"], FULL_URL)

    def test_scope_url_follows_the_explicit_port_when_no_url_was_given(self):
        with _TargetEnv() as tgt:
            tgt.set_target(host="example.com", port="8443")
            self.assertEqual(tgt.scope_url("api.example.com"), "https://api.example.com:8443")

    def test_host_preset_receives_the_bare_host(self):
        with _TargetEnv() as tgt:
            tgt.set_target(host=FULL_URL)
            calls = _run_preset({"label": "scan", "cmd": ["ZZ", "{host}"], "output": "scan"})
            self.assertEqual([cmd[-1] for cmd in calls], ["example.com"])


@R07
def test_scope_url_for_the_base_host_returns_the_target_url_unchanged():
    with _TargetEnv() as tgt:
        tgt.set_target(host=FULL_URL)
        assert tgt.scope_url("example.com") == FULL_URL


@R07
def test_scope_url_for_a_subdomain_keeps_scheme_path_and_query():
    with _TargetEnv() as tgt:
        tgt.set_target(host=FULL_URL)
        parsed = urlsplit(tgt.scope_url("api.example.com"))
        assert (parsed.scheme, parsed.hostname, parsed.path, parsed.query) == ("https", "api.example.com", "/app", "x=1")


@R07
def test_url_preset_receives_the_full_target_url_when_scope_is_off():
    """What the operator sees: the command gets the URL they typed, not a rebuilt one."""
    with _TargetEnv() as tgt:
        tgt.set_target(host=FULL_URL)
        calls = _run_preset({"label": "probe", "cmd": ["ZZ", "{url}"], "output": "probe"})
        assert len(calls) == 1
        assert calls[0][-1] == FULL_URL


if __name__ == "__main__":
    unittest.main()
