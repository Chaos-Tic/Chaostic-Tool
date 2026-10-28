"""Subdomain enumeration parsing, scope expansion and in-scope validation."""
import unittest

from core import subdomains as sd


class DomainValidationTests(unittest.TestCase):
    def test_is_domain(self):
        self.assertTrue(sd.is_domain("example.com"))
        self.assertTrue(sd.is_domain("a.b.example.co.uk"))
        self.assertFalse(sd.is_domain("127.0.0.1"))
        self.assertFalse(sd.is_domain("::1"))
        self.assertFalse(sd.is_domain("localhost"))
        self.assertFalse(sd.is_domain(""))

    def test_within_domain(self):
        self.assertTrue(sd.within_domain("api.example.com", "example.com"))
        self.assertTrue(sd.within_domain("example.com", "example.com"))
        self.assertFalse(sd.within_domain("example.com.evil.net", "example.com"))
        self.assertFalse(sd.within_domain("notexample.com", "example.com"))


class ParseHostsTests(unittest.TestCase):
    def test_subfinder_style_bare_hosts(self):
        text = "api.example.com\nwww.example.com\nexample.com\n"
        self.assertEqual(sd.parse_hosts(text, "example.com"),
                         ["api.example.com", "www.example.com"])

    def test_amass_style_decorated_lines_and_out_of_scope_dropped(self):
        text = ("mail.example.com (FQDN) --> a_record --> 10.0.0.1\n"
                "cdn.evil.net (FQDN)\n"
                "DUP.example.com\nmail.example.com\n")
        self.assertEqual(sd.parse_hosts(text, "example.com"),
                         ["dup.example.com", "mail.example.com"])


class ScopeHostsTests(unittest.TestCase):
    def test_base_first_then_subdomains(self):
        self.assertEqual(
            sd.scope_hosts("example.com", ["b.example.com", "a.example.com"], True),
            ["example.com", "b.example.com", "a.example.com"])

    def test_disabled_returns_base_only(self):
        self.assertEqual(sd.scope_hosts("example.com", ["a.example.com"], False),
                         ["example.com"])

    def test_out_of_scope_and_duplicates_dropped(self):
        self.assertEqual(
            sd.scope_hosts("example.com", ["a.example.com", "evil.net", "example.com"], True),
            ["example.com", "a.example.com"])


class EnumerateTests(unittest.TestCase):
    def test_not_a_domain_is_rejected(self):
        subs, sources, error = sd.enumerate_subdomains("127.0.0.1", runner=lambda *a: (0, "", ""))
        self.assertEqual(subs, [])
        self.assertTrue(error)

    def test_subfinder_results_used_amass_empty_is_fine(self):
        def runner(cmd, env, timeout):
            if cmd[0] == "subfinder":
                return 0, "api.example.com\nwww.example.com\n", ""
            return 0, "", ""  # amass found nothing — must not fail
        subs, sources, error = sd.enumerate_subdomains("example.com", runner=runner)
        self.assertEqual(subs, ["api.example.com", "www.example.com"])
        self.assertEqual(sources, ["subfinder"])
        self.assertEqual(error, "")

    def test_results_merged_across_tools(self):
        def runner(cmd, env, timeout):
            if cmd[0] == "subfinder":
                return 0, "api.example.com\n", ""
            return 0, "vpn.example.com\napi.example.com\n", ""
        subs, sources, error = sd.enumerate_subdomains("example.com", runner=runner)
        self.assertEqual(subs, ["api.example.com", "vpn.example.com"])
        self.assertEqual(sources, ["subfinder", "amass"])

    def test_error_only_when_nothing_found_and_a_tool_failed(self):
        def runner(cmd, env, timeout):
            return 1, "", "boom"
        subs, sources, error = sd.enumerate_subdomains("example.com", runner=runner)
        self.assertEqual(subs, [])
        self.assertEqual(error, "boom")


if __name__ == "__main__":
    unittest.main()
