"""Tor routing policy in ``core.proxy`` (pro plan Lot 0, R01).

When Tor routing is enabled but proxychains is not installed, ``wrap_command``
hands the bare command back and the tool runs in the clear, while
``route_status`` keeps announcing "TOR via proxychains". The expected policy is
to block (return nothing, or raise), never to fall back to a direct launch
silently, and to report a route that matches what actually happens.

The bug-demonstrating tests are plain pytest functions marked
``xfail(strict=True)``: ``python -m unittest discover`` (the CI runner) does not
collect them, so CI stays green, and under pytest they turn red (XPASS) the day
the bug is fixed without the marker being removed. The ``unittest`` class
anchors the neighbouring behaviour that is already correct.
"""
import unittest
from unittest.mock import patch

import pytest

from core import proxy

CMD = ["httpx", "-u", "https://example.com"]
TOOL = {"name": "httpx", "binary": "httpx", "category": "web_enum"}
PROXYCHAINS = "/usr/bin/proxychains4"

R01 = pytest.mark.xfail(
    strict=True,
    reason="R01: Tor requested without proxychains silently launches the command directly — pro plan Lot 0",
)


class _TorRequested:
    """Tor routing enabled (auto-rotate off), console silenced; global state restored afterwards."""

    def __enter__(self):
        self.saved = dict(proxy.PROXY_STATE)
        proxy.PROXY_STATE.update(enabled=True, mode="tor", interface=None, tor_auto_rotate=False)
        self.console = patch.object(proxy, "console")
        self.console.start()
        return proxy

    def __exit__(self, *exc):
        self.console.stop()
        proxy.PROXY_STATE.clear()
        proxy.PROXY_STATE.update(self.saved)
        return False


class TorRoutingAnchorTests(unittest.TestCase):
    """Behaviour that already holds and must keep holding once R01 is fixed."""

    def test_tor_with_proxychains_wraps_the_command_and_reports_it(self):
        with _TorRequested(), patch.object(proxy, "proxychains_binary", return_value=PROXYCHAINS):
            self.assertEqual(proxy.wrap_command(list(CMD)), [PROXYCHAINS, "-q", *CMD])
            self.assertEqual(proxy.route_status(), "TOR via proxychains")
            self.assertEqual(proxy.route_status(TOOL), "TOR via proxychains")

    def test_direct_mode_leaves_the_command_alone(self):
        saved = dict(proxy.PROXY_STATE)
        try:
            proxy.PROXY_STATE.update(enabled=False, mode=None, interface=None)
            self.assertEqual(proxy.wrap_command(list(CMD)), CMD)
            self.assertEqual(proxy.route_status(), "DIRECT")
        finally:
            proxy.PROXY_STATE.clear()
            proxy.PROXY_STATE.update(saved)


@R01
def test_tor_without_proxychains_blocks_instead_of_launching_directly():
    with _TorRequested(), patch.object(proxy, "proxychains_binary", return_value=None):
        try:
            wrapped = proxy.wrap_command(list(CMD))
        except (RuntimeError, ValueError, OSError):
            return  # refusing by raising is an acceptable blocking policy
    assert not wrapped, (
        "Tor was requested but proxychains is missing: wrap_command must block, "
        "not hand back a runnable command"
    )


@R01
def test_route_status_does_not_claim_proxychains_when_it_is_missing():
    with _TorRequested(), patch.object(proxy, "proxychains_binary", return_value=None):
        assert proxy.route_status() != "TOR via proxychains"
        assert proxy.route_status(TOOL) != "TOR via proxychains"


if __name__ == "__main__":
    unittest.main()
