"""Tor routing policy in ``core.proxy`` (pro plan Lot 0, R01).

When Tor routing is enabled but proxychains is not installed, ``wrap_command``
must block (raise ``ProxyRouteError``) instead of handing the bare command back
for a direct launch, ``route_status`` must report the blocked route instead of
"TOR via proxychains", and ``core.ui.run_preset`` must honour the block: no
launch, a message to the operator, and a "never launched" result.
"""
import contextlib
import unittest
from unittest.mock import patch

from core import proxy

CMD = ["httpx", "-u", "https://example.com"]
TOOL = {"name": "httpx", "binary": "httpx", "category": "web_enum"}
PROXYCHAINS = "/usr/bin/proxychains4"


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
    """Neighbouring behaviour that held before the R01 fix and must keep holding."""

    def test_tor_with_proxychains_wraps_the_command_and_reports_it(self):
        with _TorRequested(), patch.object(proxy, "proxychains_binary", return_value=PROXYCHAINS):
            self.assertEqual(proxy.wrap_command(list(CMD)), [PROXYCHAINS, "-q", *CMD])
            self.assertEqual(proxy.route_status(), "TOR via proxychains")
            self.assertEqual(proxy.route_status(TOOL), "TOR via proxychains")
            self.assertFalse(proxy.tor_route_blocked())

    def test_direct_mode_leaves_the_command_alone(self):
        saved = dict(proxy.PROXY_STATE)
        try:
            proxy.PROXY_STATE.update(enabled=False, mode=None, interface=None)
            self.assertEqual(proxy.wrap_command(list(CMD)), CMD)
            self.assertEqual(proxy.route_status(), "DIRECT")
            self.assertFalse(proxy.tor_route_blocked())
        finally:
            proxy.PROXY_STATE.clear()
            proxy.PROXY_STATE.update(saved)


class TorWithoutProxychainsTests(unittest.TestCase):
    """R01: Tor requested without proxychains blocks instead of launching directly."""

    def test_wrap_command_blocks_instead_of_launching_directly(self):
        with _TorRequested(), patch.object(proxy, "proxychains_binary", return_value=None):
            self.assertTrue(proxy.tor_route_blocked())
            with self.assertRaises(proxy.ProxyRouteError) as caught:
                proxy.wrap_command(list(CMD))
            self.assertIsInstance(caught.exception, RuntimeError)
            self.assertIn("proxychains", str(caught.exception))

    def test_route_status_does_not_claim_proxychains_when_it_is_missing(self):
        with _TorRequested(), patch.object(proxy, "proxychains_binary", return_value=None):
            for status in (proxy.route_status(), proxy.route_status(TOOL)):
                self.assertNotEqual(status, "TOR via proxychains")
                self.assertIn("BLOCKED", status)

    def test_run_preset_does_not_launch_and_reports_never_launched(self):
        """The caller honours the block: no executor call, a message, ``None`` returned."""
        from core import ui
        tool = dict(TOOL, output_dir="web_enum", interactive=False)
        preset = {"label": "probe", "cmd": ["httpx", "-u", "{url}"], "output": None}
        with contextlib.ExitStack() as stack:
            stack.enter_context(_TorRequested())
            stack.enter_context(patch.object(proxy, "proxychains_binary", return_value=None))
            run_tool = stack.enter_context(patch.object(ui.executor, "run_tool", return_value=0))
            console = stack.enter_context(patch.object(ui, "console"))
            stack.enter_context(patch.object(ui.tui, "available", return_value=False))
            stack.enter_context(patch.dict(ui.tgt.TARGET,
                                           {"host": "example.com", "url": "https://example.com", "port": "443"},
                                           clear=False))
            rc = ui.run_preset(tool, preset, pause_after=False)
        run_tool.assert_not_called()
        self.assertIsNone(rc)
        printed = " ".join(str(c.args[0]) for c in console.print.call_args_list)
        self.assertIn("proxychains", printed)

    def test_run_preset_safety_net_when_wrap_command_itself_blocks(self):
        """Even if the early guard is bypassed, a blocking ``wrap_command`` never reaches the executor."""
        from core import ui
        tool = dict(TOOL, output_dir="web_enum", interactive=False)
        preset = {"label": "probe", "cmd": ["httpx", "-u", "{url}"], "output": None}
        with contextlib.ExitStack() as stack:
            stack.enter_context(_TorRequested())
            stack.enter_context(patch.object(proxy, "proxychains_binary", return_value=None))
            stack.enter_context(patch.object(ui, "tor_route_blocked", return_value=False))
            run_tool = stack.enter_context(patch.object(ui.executor, "run_tool", return_value=0))
            stack.enter_context(patch.object(ui, "console"))
            stack.enter_context(patch.object(ui.tui, "available", return_value=False))
            stack.enter_context(patch.dict(ui.tgt.TARGET,
                                           {"host": "example.com", "url": "https://example.com", "port": "443"},
                                           clear=False))
            rc = ui.run_preset(tool, preset, pause_after=False)
        run_tool.assert_not_called()
        self.assertIsNone(rc)


if __name__ == "__main__":
    unittest.main()
