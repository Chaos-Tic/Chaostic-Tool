"""Unified target input: one canonical normalization shared by CLI and GUI.

``core.target.normalize_target`` is the single source of truth. The CLI path
(``core.target.set_target``) and the GUI path (``desktop.storage.parse_target``)
must derive the same host, URL and port from the same input, validate it the same
way, and echo how it was understood.
"""
import os
import tempfile
import unittest
from unittest.mock import patch


class _CliEnv:
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


PARITY_INPUTS = [
    "chaostic.cloud",
    "whecks.chaostic.cloud",
    "https://whecks.chaostic.cloud",
    "http://ex.com:8080/app?x=1",
    "192.0.2.10",
    "2001:db8::1",
]


class ParityTests(unittest.TestCase):
    """The same input yields the same (host, url, port) on the CLI and GUI paths."""

    def test_cli_and_gui_agree_on_host_url_and_port(self):
        from desktop.storage import parse_target
        for raw in PARITY_INPUTS:
            with self.subTest(raw=raw), _CliEnv() as tgt:
                with patch.dict(tgt.TARGET, clear=False):
                    tgt.set_target(host=raw)
                    cli = (tgt.TARGET["host"], tgt.TARGET["url"], int(tgt.TARGET["port"]))
                gui_target = parse_target(raw)
                gui = (gui_target["host"], gui_target["url"], gui_target["port"])
                self.assertEqual(cli, gui)

    def test_bare_entry_defaults_to_https_443(self):
        from core.target import normalize_target
        info = normalize_target("chaostic.cloud")
        self.assertEqual((info["scheme"], info["port"], info["url"]),
                         ("https", 443, "https://chaostic.cloud"))

    def test_url_scheme_and_explicit_port_are_respected(self):
        from core.target import normalize_target
        info = normalize_target("http://ex.com:8080/app?x=1")
        self.assertEqual((info["scheme"], info["port"], info["url"]),
                         ("http", 8080, "http://ex.com:8080/app?x=1"))

    def test_port_override_does_not_change_the_scheme(self):
        from core.target import normalize_target
        info = normalize_target("chaostic.cloud", port_override="8080")
        self.assertEqual((info["scheme"], info["port"], info["url"]),
                         ("https", 8080, "https://chaostic.cloud:8080"))

    def test_bare_host_url_has_no_superfluous_trailing_slash(self):
        from core.target import normalize_target
        self.assertEqual(normalize_target("example.com")["url"], "https://example.com")
        self.assertEqual(normalize_target("::1")["url"], "https://[::1]")

    def test_entered_path_query_and_fragment_are_preserved(self):
        from core.target import normalize_target
        self.assertEqual(normalize_target("https://example.com:8443/app?x=1#top")["url"],
                         "https://example.com:8443/app?x=1#top")


class ValidationTests(unittest.TestCase):
    """Strict validation on both sides, each rejection with its own error code."""

    REJECTIONS = [
        ("", "empty"),
        ("example.com -p 22", "whitespace"),
        ("host\nInjected", "whitespace"),
        ("ftp://host", "scheme"),
        ("https://user:pass@host", "credentials"),
        ("*.example.com", "host"),
        ("../..", "idna"),
        ("-oN", "host"),
        ("example.com:0", "port"),
        ("https://host:99999", "malformed"),
    ]

    def test_normalize_target_rejects_with_the_expected_code(self):
        from core.target import normalize_target, TargetError
        for raw, code in self.REJECTIONS:
            with self.subTest(raw=raw):
                with self.assertRaises(TargetError) as ctx:
                    normalize_target(raw)
                self.assertEqual(ctx.exception.code, code)

    def test_port_override_out_of_range_is_rejected(self):
        from core.target import normalize_target, TargetError
        for bad in ("0", "70000", "notaport"):
            with self.subTest(bad=bad), self.assertRaises(TargetError) as ctx:
                normalize_target("example.com", port_override=bad)
            self.assertEqual(ctx.exception.code, "port")

    def test_cli_set_target_raises_target_error_on_invalid_input(self):
        from core.target import TargetError
        with _CliEnv() as tgt, patch.dict(tgt.TARGET, clear=False):
            with self.assertRaises(TargetError):
                tgt.set_target(host="ftp://host")

    def test_gui_parse_target_raises_value_error_on_invalid_input(self):
        from desktop.storage import parse_target
        for raw, _code in self.REJECTIONS:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_target(raw)

    def test_target_error_is_a_value_error(self):
        from core.target import TargetError
        self.assertTrue(issubclass(TargetError, ValueError))


class EchoTests(unittest.TestCase):
    """Both front ends can show how the input was interpreted."""

    def test_normalize_target_echo_names_host_scheme_and_port(self):
        from core.target import normalize_target
        echo = normalize_target("whecks.chaostic.cloud")["echo"]
        self.assertEqual(
            echo,
            "https://whecks.chaostic.cloud:443 — host whecks.chaostic.cloud · scheme https · port 443",
        )

    def test_describe_target_reflects_the_active_cli_target(self):
        with _CliEnv() as tgt, patch.dict(tgt.TARGET, clear=False):
            tgt.set_target(host="whecks.chaostic.cloud")
            self.assertEqual(
                tgt.describe_target(),
                "https://whecks.chaostic.cloud:443 — host whecks.chaostic.cloud · scheme https · port 443",
            )


if __name__ == "__main__":
    unittest.main()
