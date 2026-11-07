"""Henon export engine (core.henon_export) and its CLI / Results export paths.

The emitted file is validated against the Henon contract
(``docs/CONTRACT-CHAOSTICTOOL.md`` / ``docs/CONTRACT-CLOUD.md`` in the Henon
repo): top-level ``schema_version`` 1, optional collections, each record shaped
as documented, and — the security invariant — no secret ever persisted in a
``web_endpoints`` URL (userinfo, query values and fragments dropped).
"""
import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from unittest.mock import patch

from core import henon_export as henon
from core import target as tgt


def _cli_fixture(root):
    """A CLI results tree for example.com covering every mapped tool family."""
    d = root / "targets" / "example.com"
    for cat in tgt.CATEGORIES:
        (d / cat).mkdir(parents=True)
    (d / "osint" / "subfinder_example.com.txt").write_text(
        "api.example.com\nwww.example.com\n[INF] noise, not a host\n", encoding="utf-8")
    (d / "osint" / "dig_a_example.com.txt").write_text("203.0.113.10\n", encoding="utf-8")
    (d / "recon" / "nmap_quick_example.com.txt").write_text(
        "Nmap scan report for example.com (203.0.113.10)\n"
        "PORT     STATE  SERVICE VERSION\n"
        "22/tcp   open   ssh     OpenSSH 7.4 (protocol 2.0)\n"
        "80/tcp   open   http    nginx 1.18.0\n"
        "6379/tcp open   redis\n"
        "443/tcp  closed https\n", encoding="utf-8")
    (d / "web_enum" / "httpx_info_example.com.txt").write_text(
        "https://example.com [200] [Example Domain] [nginx,PHP]\n"
        "https://api.example.com/login [403] [Forbidden] [nginx]\n", encoding="utf-8")
    # Secret-bearing URLs: the query values and the userinfo must never persist;
    # only the parameter names survive.
    (d / "web_enum" / "gau_example.com.txt").write_text(
        "https://example.com/search?q=secretvalue&token=abc123\n"
        "https://admin:hunter2@example.com/panel\n"
        "not-a-url\n", encoding="utf-8")
    (d / "vulnscan" / "nuclei_cve_example.com.txt").write_text(
        "[CVE-2021-41773] [http] [critical] https://example.com/cgi-bin/\n"
        "[tech-detect:nginx] [http] [info] https://example.com\n", encoding="utf-8")
    # Operator-provided cloud projection (CONTRACT-CLOUD). The second record has
    # no provider and must be skipped.
    (d / "postexploit" / "cloud_aws_example.com.json").write_text(json.dumps({
        "schema_version": 1,
        "resources": [
            {"provider": "aws", "kind": "iam_role", "name": "app-prod",
             "arn": "arn:aws:iam::123456789012:role/app-prod",
             "permissions": ["*:*"], "assumable_by": ["*"]},
            {"kind": "bucket", "name": "no-provider-skip-me"},
        ],
    }), encoding="utf-8")
    # Unknown family (ffuf is not mapped) and a binary file: both skipped.
    (d / "web_enum" / "ffuf_example.com.txt").write_bytes(b"\0\1\2binary")
    return d


_TARGET = {"host": "example.com", "url": "https://example.com", "port": "443"}
_SCOPE = {"include_subdomains": True, "subdomains": ["api.example.com", "www.example.com"],
          "excluded": [], "fanout_limit": None}


class HenonExportEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="chaostic-henon-")
        self.root = Path(self.temp.name)
        self.doc = henon.from_cli_results(_cli_fixture(self.root), _TARGET, _SCOPE)

    def tearDown(self):
        self.temp.cleanup()

    def _assets(self, kind):
        return [a for a in self.doc.get("assets", []) if a["kind"] == kind]

    def _endpoint(self, url):
        return next((e for e in self.doc["web_endpoints"] if e["url"] == url), None)

    def test_top_level_shape(self):
        self.assertEqual(self.doc["schema_version"], 1)
        self.assertTrue(self.doc["generated_by"].startswith("chaostictool/"))
        for key in ("assets", "services", "web_endpoints", "cloud_resources"):
            self.assertIsInstance(self.doc[key], list)

    def test_assets_cover_domain_subdomains_and_ip(self):
        domains = {a["fqdn"] for a in self._assets("domain")}
        subs = {a["fqdn"] for a in self._assets("subdomain")}
        ips = {a["addr"] for a in self._assets("ip")}
        self.assertEqual(domains, {"example.com"})
        self.assertEqual(subs, {"api.example.com", "www.example.com"})
        self.assertIn("203.0.113.10", ips)
        # The subdomain carries its registrable apex hint.
        self.assertTrue(all(a.get("apex") == "example.com" for a in self._assets("subdomain")))

    def test_services_from_nmap_and_base_target(self):
        by_port = {(s["host"], s["port"]): s for s in self.doc["services"]}
        self.assertIn(("example.com", 443), by_port)  # base target host:port
        ssh = by_port[("example.com", 22)]
        self.assertEqual(ssh["service_name"], "ssh")
        self.assertEqual(ssh["product"], "OpenSSH")
        self.assertEqual(ssh["version"], "7.4")
        self.assertEqual(ssh.get("ip"), "203.0.113.10")
        self.assertEqual(by_port[("example.com", 80)]["service_name"], "http")
        self.assertIn(("example.com", 6379), by_port)
        self.assertNotIn(("example.com", 443), {(s["host"], s["port"]): s
                         for s in self.doc["services"] if s.get("service_name") == "https"})

    def test_web_endpoints_and_nuclei_cve(self):
        git = self._endpoint("https://example.com/cgi-bin/")
        self.assertIsNotNone(git)
        self.assertIn("CVE-2021-41773", git["cve"])
        login = self._endpoint("https://api.example.com/login")
        self.assertEqual(login["status_code"], 403)

    def test_urls_are_sanitised_params_kept(self):
        search = self._endpoint("https://example.com/search")
        self.assertIsNotNone(search, "query string must be stripped from the stored URL")
        self.assertEqual(search["params"], ["q", "token"])
        # userinfo dropped: the panel endpoint keeps no credentials.
        panel = self._endpoint("https://example.com/panel")
        self.assertIsNotNone(panel)

    def test_no_secret_is_ever_persisted(self):
        blob = json.dumps(self.doc)
        for secret in ("secretvalue", "abc123", "hunter2", "admin:"):
            self.assertNotIn(secret, blob)
        self.assertFalse(any("?" in e["url"] for e in self.doc["web_endpoints"]))

    def test_cloud_resources_validity(self):
        self.assertEqual(len(self.doc["cloud_resources"]), 1)
        role = self.doc["cloud_resources"][0]
        self.assertEqual(role["provider"], "aws")
        self.assertEqual(role["arn"], "arn:aws:iam::123456789012:role/app-prod")
        # A record with neither provider nor (name|arn) requirement unmet is gone.
        self.assertTrue(all(c.get("provider") and (c.get("name") or c.get("arn"))
                            for c in self.doc["cloud_resources"]))

    def test_every_record_meets_contract_minimums(self):
        for s in self.doc["services"]:
            self.assertTrue(1 <= s["port"] <= 65535)
            self.assertIn(s["proto"], ("tcp", "udp"))
        for a in self.doc["assets"]:
            self.assertIn(a["kind"], ("domain", "subdomain", "ip"))
        self.assertTrue(json.dumps(self.doc))  # fully JSON-serialisable

    def test_excluded_hosts_are_never_exported(self):
        # An operator-excluded subdomain, with its own scanned result file and a
        # crawl of the base host that references it, must not reach the engine.
        root = self.root / "excl"
        d = root / "targets" / "example.com"
        for cat in tgt.CATEGORIES:
            (d / cat).mkdir(parents=True)
        # subfinder still lists the excluded host in its output: it must not be
        # re-introduced from file content either.
        (d / "osint" / "subfinder_example.com.txt").write_text(
            "api.example.com\nlegacy.example.com\n", encoding="utf-8")
        (d / "recon" / "nmap_quick_example.com__legacy.example.com.txt").write_text(
            "Nmap scan report for legacy.example.com (203.0.113.9)\n"
            "23/tcp open telnet\n", encoding="utf-8")
        (d / "web_enum" / "gau_example.com.txt").write_text(
            "https://legacy.example.com/old\nhttps://example.com/ok\n", encoding="utf-8")
        scope = {"subdomains": ["api.example.com", "legacy.example.com"],
                 "excluded": ["legacy.example.com"], "include_subdomains": True}
        doc = henon.from_cli_results(d, _TARGET, scope)
        fqdns = {a.get("fqdn") for a in doc.get("assets", [])}
        self.assertNotIn("legacy.example.com", fqdns)
        self.assertIn("api.example.com", fqdns)
        hosts = {s["host"] for s in doc.get("services", [])}
        self.assertNotIn("legacy.example.com", hosts)
        urls = {e["url"] for e in doc.get("web_endpoints", [])}
        self.assertNotIn("https://legacy.example.com/old", urls)
        self.assertIn("https://example.com/ok", urls)

    def test_empty_tree_is_still_valid(self):
        empty = self.root / "targets" / "nothing.test"
        doc = henon.from_cli_results(empty, {"host": "nothing.test", "url": "", "port": ""}, {})
        self.assertEqual(doc["schema_version"], 1)
        self.assertEqual([a["fqdn"] for a in doc.get("assets", [])], ["nothing.test"])


class HenonParserUnitTests(unittest.TestCase):
    def test_sanitize_url(self):
        self.assertEqual(henon.sanitize_url("https://u:p@h.tld/a?x=1&y=2#frag"),
                         ("https://h.tld/a", ["x", "y"]))
        self.assertEqual(henon.sanitize_url("ftp://h.tld/x"), ("", []))
        self.assertEqual(henon.sanitize_url("https://h.tld:8443/p"), ("https://h.tld:8443/p", []))

    def test_sanitize_drops_valueless_and_path_params(self):
        # A bare query segment with no '=' is never emitted as a param name: a
        # secret dropped there must not leak. A ';jsessionid=…' path param is
        # stripped from the path.
        clean, params = henon.sanitize_url("https://h.tld/app;jsessionid=SECRET/x?SECRETBLOB&id=5")
        self.assertEqual(clean, "https://h.tld/app/x")
        self.assertEqual(params, ["id"])
        self.assertNotIn("SECRETBLOB", params)

    def test_sanitize_malformed_url_never_raises(self):
        # A port that ValueError's on parse must yield ("", []) instead of
        # aborting the export; any other odd input must simply not raise.
        self.assertEqual(henon.sanitize_url("https://h.tld:99999999999/x"), ("", []))
        clean, params = henon.sanitize_url("http://[::bad]/x")
        self.assertIsInstance(clean, str)
        self.assertIsInstance(params, list)

    def test_parse_hosts_skips_noise(self):
        self.assertEqual(henon.parse_hosts("a.x.tld\n[INF] foo bar\n1.2.3.4\nb.x.tld\n"),
                         ["a.x.tld", "b.x.tld"])

    def test_parse_ports_naabu_and_masscan(self):
        _ips, svc = henon.parse_ports("1.2.3.4:22\nhost.tld:443\n")
        self.assertEqual({(s["host"], s["port"]) for s in svc}, {("1.2.3.4", 22), ("host.tld", 443)})
        ips, _svc = henon.parse_ports("Discovered open port 80/tcp on 203.0.113.9\n")
        self.assertIn("203.0.113.9", ips)

    def test_parse_nuclei_extracts_cve(self):
        rows = henon.parse_nuclei("[CVE-2020-1234] [http] [high] https://h.tld/p\n")
        self.assertEqual(rows[0]["cve"], ["CVE-2020-1234"])
        self.assertEqual(rows[0]["url"], "https://h.tld/p")

    def test_add_cloud_resource_requires_provider_and_identity(self):
        exp = henon.HenonExport()
        exp.add_cloud_resource({"provider": "aws", "name": "x"})
        exp.add_cloud_resource({"name": "no-provider"})
        exp.add_cloud_resource("not a dict")
        self.assertEqual(len(exp.document().get("cloud_resources", [])), 1)


class HenonCliExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="chaostic-henon-cli-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_export_henon_cli_writes_recon_json(self):
        import chaostictool
        _cli_fixture(self.root)
        out = self.root / "out.json"
        with patch.object(tgt, "TARGETS_ROOT", self.root / "targets"):
            chaostictool._export_henon("https://example.com", str(out))
        doc = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(doc["schema_version"], 1)
        self.assertTrue(doc["services"])
        self.assertNotIn("secretvalue", out.read_text(encoding="utf-8"))


@unittest.skipUnless(hasattr(os, "fchown"), "chown handback is POSIX-only")
class HenonExportChownTests(unittest.TestCase):
    """The export must land readable by the sudo-invoking operator.

    Under ``sudo`` the atomic write lands ``root:root`` 0o600; without a handback
    to the operator, Henon (running unprivileged) cannot read ``recon.json`` and
    the handoff breaks. ``write_export`` resolves the owner via
    ``core.target.sudo_user_ids`` and hands the file over with ``os.fchown`` on
    the temp *descriptor* before the atomic rename (never re-resolving the path
    as root — CWE-59/367 safe). We assert the fchown targets the simulated
    ``SUDO_UID``/``SUDO_GID`` and that the non-elevated path never chowns.
    """

    def setUp(self):
        from core import safe_io
        self.safe_io = safe_io
        self.temp = tempfile.TemporaryDirectory(prefix="chaostic-henon-chown-")
        self.root = Path(self.temp.name)
        self.dest = self.root / "recon.json"
        self.document = {"schema_version": 1}

    def tearDown(self):
        self.temp.cleanup()

    def _fake_pwd(self, uid, gid):
        fake_pw = mock.Mock(pw_uid=uid, pw_gid=gid)
        fake_pwd = mock.Mock()
        fake_pwd.getpwnam.return_value = fake_pw
        return fake_pwd

    def test_chown_to_sudo_user_when_elevated(self):
        # within set (the app-owned results tree) => always hand over, by descriptor.
        fake_pwd = self._fake_pwd(4321, 8765)
        with mock.patch.dict(os.environ, {"SUDO_USER": "operator"}, clear=False), \
                mock.patch.object(tgt, "pwd", fake_pwd), \
                mock.patch.object(self.safe_io.os, "fchown") as fchown:
            written = henon.write_export(self.document, self.dest, within=self.root)
        # The contract file still lands intact...
        self.assertEqual(json.loads(written.read_text(encoding="utf-8"))["schema_version"], 1)
        # ...and is handed back to the operator's uid/gid, through a descriptor.
        fake_pwd.getpwnam.assert_called_once_with("operator")
        fchown.assert_called_once()
        args = fchown.call_args.args
        self.assertEqual((args[1], args[2]), (4321, 8765))
        self.assertIsInstance(args[0], int)  # a file descriptor, not a path

    def test_chown_on_arbitrary_path_when_parent_is_operator_owned(self):
        # within None (user-chosen -o path) but the parent dir is the operator's:
        # hand over. Simulate by setting the operator uid to the dir's real owner.
        owner_uid = self.root.stat().st_uid
        fake_pwd = self._fake_pwd(owner_uid, self.root.stat().st_gid)
        with mock.patch.dict(os.environ, {"SUDO_USER": "operator"}, clear=False), \
                mock.patch.object(tgt, "pwd", fake_pwd), \
                mock.patch.object(self.safe_io.os, "fchown") as fchown:
            henon.write_export(self.document, self.dest)
        fchown.assert_called_once()

    def test_no_chown_to_foreign_user_on_arbitrary_path(self):
        # within None and the parent dir is NOT owned by the operator (a root-only
        # dir like /etc under sudo): the file must stay as written, never handed
        # to a lower-privileged user (CWE-269/732).
        foreign_uid = self.root.stat().st_uid + 99999
        fake_pwd = self._fake_pwd(foreign_uid, foreign_uid)
        with mock.patch.dict(os.environ, {"SUDO_USER": "operator"}, clear=False), \
                mock.patch.object(tgt, "pwd", fake_pwd), \
                mock.patch.object(self.safe_io.os, "fchown") as fchown:
            written = henon.write_export(self.document, self.dest)
        self.assertEqual(json.loads(written.read_text(encoding="utf-8"))["schema_version"], 1)
        fchown.assert_not_called()

    def test_no_chown_without_sudo(self):
        env = {k: v for k, v in os.environ.items() if k != "SUDO_USER"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(self.safe_io.os, "fchown") as fchown:
            written = henon.write_export(self.document, self.dest, within=self.root)
        self.assertEqual(json.loads(written.read_text(encoding="utf-8"))["schema_version"], 1)
        fchown.assert_not_called()

    def test_chown_failure_is_not_fatal(self):
        # An fchown that raises OSError must not abort the export: the content is
        # already written and must still land for the operator to read.
        fake_pwd = self._fake_pwd(1, 1)
        with mock.patch.dict(os.environ, {"SUDO_USER": "operator"}, clear=False), \
                mock.patch.object(tgt, "pwd", fake_pwd), \
                mock.patch.object(self.safe_io.os, "fchown", side_effect=OSError("EPERM")):
            written = henon.write_export(self.document, self.dest, within=self.root)
        self.assertTrue(written.exists())
        self.assertEqual(json.loads(written.read_text(encoding="utf-8"))["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
