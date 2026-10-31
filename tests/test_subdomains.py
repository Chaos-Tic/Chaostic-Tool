"""Subdomain enumeration parsing, scope expansion and in-scope validation."""
import unittest
import unittest.mock

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
        subs, counts, error = sd.enumerate_subdomains("127.0.0.1", runner=lambda *a: (0, "", ""))
        self.assertEqual(subs, [])
        self.assertEqual(counts, {})
        self.assertTrue(error)

    def test_subfinder_results_used_amass_empty_is_fine(self):
        def runner(cmd, env, timeout):
            if cmd[0] == "subfinder":
                return 0, "api.example.com\nwww.example.com\n", ""
            return 0, "", ""  # amass found nothing — must not fail
        subs, counts, error = sd.enumerate_subdomains("example.com", runner=runner)
        self.assertEqual(subs, ["api.example.com", "www.example.com"])
        self.assertEqual(counts, {"subfinder": 2})
        self.assertEqual(error, "")

    def test_results_merged_across_tools_with_per_source_counts(self):
        def runner(cmd, env, timeout):
            if cmd[0] == "subfinder":
                return 0, "api.example.com\n", ""
            return 0, "vpn.example.com\napi.example.com\n", ""
        subs, counts, error = sd.enumerate_subdomains("example.com", runner=runner)
        self.assertEqual(subs, ["api.example.com", "vpn.example.com"])
        # Per-source raw counts (pre-merge); keys preserve run order.
        self.assertEqual(counts, {"subfinder": 1, "amass": 2})
        self.assertEqual(list(counts), ["subfinder", "amass"])

    def test_amass_results_read_from_output_file_not_stdout(self):
        # Regression (amass v5): amass prints only progress to stdout and writes
        # hosts to the file named by -o. The shared path must parse that file.
        def runner(cmd, env, timeout):
            if cmd[0] == "subfinder":
                return 0, "", ""  # subfinder found nothing here
            # amass: locate its -o path and write results there, stdout is noise.
            out = cmd[cmd.index("-o") + 1]
            with open(out, "w", encoding="utf-8") as handle:
                handle.write("mail.example.com\nvpn.example.com\n")
            return 0, "...progress bar noise...", ""
        subs, counts, error = sd.enumerate_subdomains("example.com", runner=runner)
        self.assertEqual(subs, ["mail.example.com", "vpn.example.com"])
        self.assertEqual(counts, {"amass": 2})
        # And amass no longer carries the removed -passive flag.
        self.assertNotIn("-passive", sd.command_for("amass", "example.com", "/tmp/x"))
        self.assertIn("-o", sd.command_for("amass", "example.com", "/tmp/x"))

    def test_results_capped_at_max(self):
        big = "".join(f"h{i}.example.com\n" for i in range(sd.MAX_ENUM_RESULTS + 50))
        subs, counts, error = sd.enumerate_subdomains(
            "example.com", runner=lambda cmd, e, t: (0, big, "") if cmd[0] == "subfinder" else (0, "", ""))
        self.assertEqual(len(subs), sd.MAX_ENUM_RESULTS)

    def test_error_only_when_nothing_found_and_a_tool_failed(self):
        def runner(cmd, env, timeout):
            return 1, "", "boom"
        subs, counts, error = sd.enumerate_subdomains("example.com", runner=runner)
        self.assertEqual(subs, [])
        self.assertEqual(error, "boom")

    def test_summary_line_is_explicit(self):
        self.assertEqual(sd.enumeration_summary(0, {}), "No subdomains found.")
        self.assertEqual(sd.enumeration_summary(1, {"subfinder": 1}),
                         "Found 1 subdomain (subfinder: 1).")
        self.assertEqual(sd.enumeration_summary(3, {"subfinder": 2, "amass": 2}),
                         "Found 3 subdomains (subfinder: 2, amass: 2).")


class ScopeCapAndExcludeTests(unittest.TestCase):
    def test_excluded_hosts_are_dropped(self):
        self.assertEqual(
            sd.scope_hosts("example.com", ["a.example.com", "b.example.com"], True,
                           excluded=["b.example.com"]),
            ["example.com", "a.example.com"])

    def test_base_host_never_excluded(self):
        self.assertEqual(
            sd.scope_hosts("example.com", ["a.example.com"], True, excluded=["example.com"]),
            ["example.com", "a.example.com"])

    def test_limit_caps_total_hosts_base_first(self):
        subs = [f"s{i}.example.com" for i in range(10)]
        hosts = sd.scope_hosts("example.com", subs, True, limit=3)
        self.assertEqual(len(hosts), 3)
        self.assertEqual(hosts[0], "example.com")

    def test_fanout_count_is_uncapped(self):
        subs = [f"s{i}.example.com" for i in range(10)]
        self.assertEqual(sd.fanout_count("example.com", subs, True), 11)
        self.assertEqual(sd.fanout_count("example.com", subs, True, excluded=[subs[0]]), 10)


class ResolutionTests(unittest.TestCase):
    def test_status_flags_apex_without_record_but_www_resolving(self):
        with unittest.mock.patch.object(sd, "resolves",
                                        side_effect=lambda h: h == "www.example.com"):
            ok, www = sd.resolution_status("example.com")
            self.assertFalse(ok)
            self.assertEqual(www, "www.example.com")
            self.assertIn("only www.example.com resolves", sd.resolution_warning("example.com"))

    def test_resolving_host_has_no_warning(self):
        with unittest.mock.patch.object(sd, "resolves", return_value=True):
            self.assertTrue(sd.resolution_status("example.com")[0])
            self.assertEqual(sd.resolution_warning("example.com"), "")


class RunResilienceTests(unittest.TestCase):
    def test_run_survives_invalid_utf8_output(self):
        # An enumerator emitting non-UTF-8 bytes must not raise (regression:
        # strict text decoding crashed the CLI's "enumerate now" path).
        import os
        import sys
        cmd = [sys.executable, "-c",
               r"import sys; sys.stdout.buffer.write(b'api.example.com\n\xff\xfe')"]
        code, out, err = sd._run(cmd, dict(os.environ), 30)
        self.assertEqual(code, 0)
        self.assertIn("api.example.com", out)

    def test_run_reports_missing_binary_without_raising(self):
        import os
        code, out, err = sd._run(["definitely-not-a-real-binary-xyz"], dict(os.environ), 10)
        self.assertEqual(code, 127)
        self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
