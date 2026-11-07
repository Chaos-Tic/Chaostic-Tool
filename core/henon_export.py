"""Henon export engine: turn ChaosticTool recon into the Henon contract.

Henon (``github.com/Chaos-Tic/Henon``) is a separate offensive attack-path
engine. ChaosticTool is *step 1* (recon, this repo); Henon is *step 2*
(analysis). The two tools are coupled by **one thing only**: a versioned JSON
file on disk, ingested with ``henon ingest chaostictool <file.json>`` — no build
dependency, no shared library, no network call. Either side evolves freely as
long as this file keeps emitting the shape below.

Authoritative contract (the single source of truth both sides implement):
``docs/CONTRACT-CHAOSTICTOOL.md`` and ``docs/CONTRACT-CLOUD.md`` in the Henon
repository. Top level::

    { "schema_version": 1,
      "assets": [...], "services": [...],
      "web_endpoints": [...], "cloud_resources": [...] }

Only ``schema_version`` is mandatory; every collection is optional; Henon
tolerates unknown fields and skips malformed records individually. This module
emits exactly that shape, reusing the recon ChaosticTool already saved under
``<data_home>/targets/<name>/<category>/`` (the same tree ``core.report`` reads).

Pure data in, a dict / JSON string out: stdlib only, no Rich, no Qt, no
third-party module, mirroring ``core.report``. A security invariant applies to
``web_endpoints``: URLs are sanitised before storage — embedded credentials
(userinfo), query *values* and fragments are dropped so no secret is ever
persisted in clear (contract §2.3, security policy). Only the parameter *names*
survive, because Henon uses them to drive its SSRF inference.
"""
from __future__ import annotations

import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from core.version import VERSION

# The schema version Henon currently ingests. Bump only on a breaking change to
# the shapes below (adding an optional field is backwards-compatible).
SCHEMA_VERSION = 1

# A generous ceiling on endpoints harvested from historical-URL / crawler lists
# (gau, waybackurls, katana), which can run to tens of thousands of lines. The
# cap keeps the emitted file bounded; the first N (sorted) are kept so the
# output stays deterministic.
MAX_WEB_ENDPOINTS = 5000

# Per-run stamp appended by ``executor.unique_target_path``
# (``YYYYMMDD-HHMMSS-<6 hex>``); stripped before a filename is classified, the
# same way ``core.report`` recovers the tool/host from a result filename.
_RUN_STAMP = re.compile(r"_\d{8}-\d{6}-[0-9a-f]{6}$")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CVE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)
# A query parameter name worth keeping: a conservative identifier shape. Anything
# else (a bare secret dropped into the query string with no ``=``, an encoded
# blob) is never emitted, so a secret can never masquerade as a "param name".
_PARAM_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.\[\]-]{0,64}")
# A plain "host:port" line (naabu -silent). Host is an IP or a DNS name.
_HOSTPORT = re.compile(r"^(\[?[0-9A-Fa-f:.\-]+\]?|[A-Za-z0-9.\-]+):(\d{1,5})$")
# nmap/rustscan port row: "80/tcp   open   http    nginx 1.18.0".
_NMAP_PORT = re.compile(r"^(\d{1,5})/(tcp|udp)\s+(open|open\|filtered)\s+(\S+)(?:\s+(.*))?$")
# masscan text row: "Discovered open port 80/tcp on 203.0.113.5".
_MASSCAN = re.compile(r"Discovered open port (\d{1,5})/(tcp|udp) on (\S+)", re.IGNORECASE)
# nmap "scan report" header, with or without the resolved IP in parentheses.
_NMAP_HOST = re.compile(r"Nmap scan report for (\S+?)(?:\s+\(([0-9a-fA-F:.]+)\))?\s*$")


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value.strip("[]"))
        return True
    except ValueError:
        return False


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def sanitize_url(url: str) -> tuple[str, list[str]]:
    """Return ``(clean_url, param_names)`` with every secret-bearing part removed.

    Userinfo, the query *string* and the fragment are dropped; only the query
    parameter *names* are returned (Henon's SSRF rule R03 keys on them). A value
    that cannot be parsed yields ``("", [])`` so the caller skips it.
    """
    # ``hostname``/``port`` parse the authority and can raise ValueError on a
    # malformed URL, so they stay inside the guard: one bad URL yields
    # ``("", [])`` and is skipped, never aborting the export (contract §1).
    try:
        parts = urlsplit(url.strip())
        scheme, host, port = parts.scheme, parts.hostname, parts.port
    except ValueError:
        return "", []
    if scheme not in ("http", "https") or not host:
        return "", []
    # Keep a param name only when the raw segment actually carries a value
    # (``name=…``) and the name is a plain identifier; ``?token`` alone, or a
    # bare secret in the query, is dropped rather than leaked as a "name".
    seen: dict[str, None] = {}
    for segment in parts.query.split("&"):
        if "=" not in segment:
            continue
        name = segment.split("=", 1)[0]
        if _PARAM_NAME.fullmatch(name):
            seen.setdefault(name, None)
    # Strip ``;``-path parameters (e.g. ``;jsessionid=…``) from each segment so a
    # session token embedded in the path never persists.
    path = "/".join(seg.split(";", 1)[0] for seg in parts.path.split("/"))
    netloc = f"[{host}]" if ":" in host and not host.startswith("[") else host
    if port:
        netloc += f":{port}"
    clean = urlunsplit((scheme, netloc, path, "", ""))
    return clean, list(seen)


class HenonExport:
    """Accumulates contract records with per-collection de-duplication.

    Records are keyed by their canonical identity so repeated recon (the same
    host seen by several tools, re-runs, the base target plus a subdomain scope)
    collapses onto one entry, the richer fields winning on merge.
    """

    def __init__(self) -> None:
        self._assets: dict[tuple[str, str], dict] = {}
        self._services: dict[tuple[str, int, str], dict] = {}
        self._web: dict[str, dict] = {}
        self._cloud: dict[tuple[str, str], dict] = {}

    # ---- assets -----------------------------------------------------------
    def add_asset(self, kind: str, *, fqdn: str = "", addr: str = "",
                  apex: str = "", cloud_provider: str = "") -> None:
        fqdn = (fqdn or "").strip().rstrip(".").lower()
        addr = (addr or "").strip().strip("[]")
        if kind == "ip":
            if not _is_ip(addr):
                return
            key = ("ip", addr)
            rec = self._assets.setdefault(key, {"kind": "ip", "addr": addr})
            if cloud_provider:
                rec["cloud_provider"] = cloud_provider
            return
        if kind not in ("domain", "subdomain") or not fqdn:
            return
        key = (kind, fqdn)
        rec = self._assets.setdefault(key, {"kind": kind, "fqdn": fqdn})
        if apex:
            rec["apex"] = apex.strip().rstrip(".").lower()

    # ---- services ---------------------------------------------------------
    def add_service(self, host: str, port: int, proto: str = "tcp", *,
                    ip: str = "", service_name: str = "", product: str = "",
                    version: str = "") -> None:
        host = (host or "").strip().strip("[]").rstrip(".")
        if not host or not (1 <= port <= 65535):
            return
        proto = proto if proto in ("tcp", "udp") else "tcp"
        key = (host.lower(), port, proto)
        rec = self._services.setdefault(key, {"host": host, "port": port, "proto": proto})
        if ip and _is_ip(ip):
            rec["ip"] = ip.strip("[]")
        for field, value in (("service_name", service_name), ("product", product), ("version", version)):
            value = (value or "").strip()
            if value and not rec.get(field):
                rec[field] = value

    # ---- web endpoints ----------------------------------------------------
    def add_web_endpoint(self, url: str, *, host: str = "", ip: str = "",
                         status_code: int | None = None, title: str = "",
                         tech: list[str] | None = None, params: list[str] | None = None,
                         cve: list[str] | None = None, interesting: list[str] | None = None) -> None:
        clean, parsed_params = sanitize_url(url)
        if not clean:
            return
        rec = self._web.setdefault(clean, {"url": clean})
        merged_params = list(dict.fromkeys((params or []) + parsed_params))
        if merged_params:
            rec["params"] = list(dict.fromkeys(rec.get("params", []) + merged_params))
        if host and not rec.get("host"):
            rec["host"] = host.strip().strip("[]").rstrip(".")
        if ip and _is_ip(ip) and not rec.get("ip"):
            rec["ip"] = ip.strip("[]")
        if status_code is not None and 100 <= status_code <= 599:
            rec["status_code"] = status_code
        if title and not rec.get("title"):
            rec["title"] = title.strip()
        for field, values in (("tech", tech), ("cve", cve), ("interesting", interesting)):
            values = [v.strip() for v in (values or []) if v and v.strip()]
            if values:
                rec[field] = list(dict.fromkeys(rec.get(field, []) + values))

    # ---- cloud resources --------------------------------------------------
    def add_cloud_resource(self, record: object) -> None:
        """Ingest a cloud record already shaped like the contract (CONTRACT-CLOUD).

        A record needs at least ``provider`` and (``name`` or ``arn``); anything
        else is skipped, exactly as Henon's ingestor does.
        """
        if not isinstance(record, dict):
            return
        provider = str(record.get("provider", "")).strip()
        arn = str(record.get("arn", "")).strip()
        name = str(record.get("name", "")).strip()
        if not provider or not (arn or name):
            return
        key = (provider, arn or f"{record.get('kind', 'other')}|{name}|{record.get('region', '')}")
        # Keep only known contract fields; unknown keys are harmless to Henon but
        # we stay conservative and forward a clean record.
        clean = {k: record[k] for k in (
            "provider", "kind", "name", "region", "arn", "public", "permissions",
            "assumable_by", "metadata_endpoint", "principal", "grants_access_to",
            "host", "ip") if k in record and record[k] not in (None, "", [])}
        self._cloud[key] = {**self._cloud.get(key, {}), **clean}

    def drop_web_hosts(self, hosts: set[str]) -> None:
        """Remove every web endpoint served by one of ``hosts`` (excluded scope).

        A crawl of an in-scope host can surface URLs on an excluded subdomain;
        this drops them so an operator exclusion is honoured end to end.
        """
        if not hosts:
            return
        for url in list(self._web):
            try:
                served = (urlsplit(url).hostname or "").lower().rstrip(".")
            except ValueError:
                continue
            if served in hosts:
                del self._web[url]

    # ---- output -----------------------------------------------------------
    def document(self) -> dict:
        """The contract document: ``schema_version`` plus every non-empty list."""
        # ``generated_by`` is an unknown top-level field Henon tolerates; it keeps
        # provenance of which ChaosticTool build produced the file.
        doc: dict = {"schema_version": SCHEMA_VERSION, "generated_by": f"chaostictool/{VERSION}"}
        assets = sorted(self._assets.values(), key=lambda r: (r["kind"], r.get("fqdn") or r.get("addr", "")))
        services = sorted(self._services.values(), key=lambda r: (r["host"], r["port"], r["proto"]))
        web = sorted(self._web.values(), key=lambda r: r["url"])[:MAX_WEB_ENDPOINTS]
        cloud = sorted(self._cloud.values(), key=lambda r: (r["provider"], r.get("arn") or r.get("name", "")))
        if assets:
            doc["assets"] = assets
        if services:
            doc["services"] = services
        if web:
            doc["web_endpoints"] = web
        if cloud:
            doc["cloud_resources"] = cloud
        return doc


# --------------------------------------------------------------------------- parsers

def parse_hosts(text: str) -> list[str]:
    """One hostname / subdomain per line (subfinder, amass, the subdomains copy)."""
    out = []
    for raw in strip_ansi(text).splitlines():
        line = raw.strip().rstrip(".")
        if not line or line.startswith(("#", "[")) or " " in line:
            continue
        # amass "name --> record --> value" rows: keep the left name only.
        line = line.split(" ")[0]
        if "." in line and not _is_ip(line):
            out.append(line.lower())
    return out


def parse_a_records(text: str) -> list[str]:
    """IP literals from a ``dig ... +short`` A/AAAA answer (ignores CNAME rows)."""
    return [l.strip() for l in strip_ansi(text).splitlines() if _is_ip(l.strip())]


def parse_ports(text: str) -> tuple[list[str], list[dict]]:
    """Parse nmap / rustscan / naabu / masscan output.

    Returns ``(ips, services)`` where each service is a dict with
    ``host``/``port``/``proto`` and best-effort ``ip``/``service_name``/
    ``product``/``version``. Only ``open`` ports are kept.
    """
    ips: list[str] = []
    services: list[dict] = []
    current_host = ""
    current_ip = ""
    for raw in strip_ansi(text).splitlines():
        line = raw.strip()
        if not line:
            continue
        header = _NMAP_HOST.search(line)
        if header:
            current_host = header.group(1).strip("[]")
            current_ip = (header.group(2) or "").strip()
            if _is_ip(current_host):
                current_ip = current_ip or current_host
                ips.append(current_host)
            if current_ip and current_ip not in ips:
                ips.append(current_ip)
            continue
        mass = _MASSCAN.search(line)
        if mass:
            port, proto, host = int(mass.group(1)), mass.group(2), mass.group(3)
            svc = {"host": host, "port": port, "proto": proto}
            if _is_ip(host):
                ips.append(host.strip("[]"))
                svc["ip"] = host.strip("[]")
            services.append(svc)
            continue
        row = _NMAP_PORT.match(line)
        if row and current_host:
            port, proto, _state, service = int(row.group(1)), row.group(2), row.group(3), row.group(4)
            rest = (row.group(5) or "").strip()
            svc = {"host": current_host, "port": port, "proto": proto, "service_name": service}
            if current_ip:
                svc["ip"] = current_ip
            if rest:
                product, version = _split_product_version(rest)
                if product:
                    svc["product"] = product
                if version:
                    svc["version"] = version
            services.append(svc)
            continue
        hp = _HOSTPORT.match(line)
        if hp:
            host, port = hp.group(1).strip("[]"), int(hp.group(2))
            svc = {"host": host, "port": port, "proto": "tcp"}
            if _is_ip(host):
                ips.append(host)
                svc["ip"] = host
            services.append(svc)
    return list(dict.fromkeys(ips)), services


def _split_product_version(rest: str) -> tuple[str, str]:
    """nmap ``-sV`` tail → (product, version). Best effort: the version is the
    first token carrying a digit; the words before it are the product."""
    tokens = rest.split()
    product_tokens: list[str] = []
    for token in tokens:
        if any(ch.isdigit() for ch in token) and token[0].isdigit():
            return " ".join(product_tokens), token
        product_tokens.append(token)
    return " ".join(product_tokens[:3]), ""


def parse_httpx(text: str) -> list[dict]:
    """Parse ``httpx -title -tech-detect -status-code`` text (no ``-json``).

    Line shape: ``URL [status] [title] [tech,tech]`` with colour stripped. URL
    is required; the first integer bracket is the status code; bracket groups
    are kept best-effort (a mislabelled title/tech is a tolerated optional
    field, never a hard error).
    """
    results: list[dict] = []
    for raw in strip_ansi(text).splitlines():
        line = raw.strip()
        if not line or not line.lower().startswith(("http://", "https://")):
            continue
        url = line.split()[0]
        groups = re.findall(r"\[([^\]]*)\]", line)
        rec: dict = {"url": url}
        leftover: list[str] = []
        for group in groups:
            value = group.strip()
            if value.isdigit() and 100 <= int(value) <= 599 and "status_code" not in rec:
                rec["status_code"] = int(value)
            else:
                leftover.append(value)
        if leftover:
            # The tech-detect group is the comma-separated one; the other is the title.
            tech = next((g for g in leftover if "," in g), "")
            if tech:
                rec["tech"] = [t.strip() for t in tech.split(",") if t.strip()]
                leftover.remove(tech)
            if leftover:
                rec["title"] = leftover[0]
        results.append(rec)
    return results


def parse_url_list(text: str) -> list[str]:
    """Absolute URLs, one per line (gau, waybackurls, katana)."""
    out = []
    for raw in strip_ansi(text).splitlines():
        line = raw.strip()
        if line.lower().startswith(("http://", "https://")) and " " not in line:
            out.append(line)
    return out


def parse_nuclei(text: str) -> list[dict]:
    """Parse default nuclei text output into ``{url, cve[], interesting[]}``.

    Line shape: ``[template-id] [protocol] [severity] URL [extra]``. The CVE id
    (when the template is a CVE) and the template id as an offensive tag are
    attached to the URL; Henon's R08 fires on the CVE.
    """
    findings: list[dict] = []
    for raw in strip_ansi(text).splitlines():
        line = raw.strip()
        if not line or not line.startswith("["):
            continue
        tags = re.findall(r"\[([^\]]*)\]", line)
        url_match = re.search(r"https?://\S+", line)
        if not tags or not url_match:
            continue
        template = tags[0].strip()
        cves = _CVE.findall(line)
        rec: dict = {"url": url_match.group(0), "interesting": [template]}
        if cves:
            rec["cve"] = [c.upper() for c in cves]
        findings.append(rec)
    return findings


def parse_cloud_json(text: str) -> list[dict]:
    """Records from an operator-provided cloud projection (CONTRACT-CLOUD shape).

    Accepts either the full ``{schema_version, resources:[...]}`` document or a
    bare list of records. Non-dict entries are ignored.
    """
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return []
    if isinstance(data, dict):
        records = data.get("resources") or data.get("cloud_resources") or []
    elif isinstance(data, list):
        records = data
    else:
        records = []
    if not isinstance(records, list):
        return []
    return [r for r in records if isinstance(r, dict)]


# --------------------------------------------------------------------------- builder

def _classify(tool_base: str) -> str:
    """Map a result-file tool prefix to a parser family."""
    base = tool_base.lower()
    if base.startswith(("subfinder", "amass")) or base == "subdomains":
        return "hosts"
    if base.startswith("dig_a"):
        return "a_record"
    if base.startswith(("nmap", "rustscan", "naabu", "masscan")):
        return "ports"
    if base.startswith("httpx"):
        return "httpx"
    if base.startswith(("gau", "waybackurls", "katana")):
        return "urls"
    if base.startswith("nuclei"):
        return "nuclei"
    if base.startswith("cloud"):
        return "cloud"
    return ""


def _split_cli_name(stem: str, safe_target: str) -> tuple[str, str]:
    """``<base>_<target>`` → (base, ""); ``…__<host>`` → (base, host).

    Same recovery ``core.report`` performs: strip the per-run stamp, split the
    fan-out ``__host`` suffix, then drop the trailing ``_<target>``.
    """
    stem = _RUN_STAMP.sub("", stem)
    host = ""
    if "__" in stem:
        stem, host = stem.rsplit("__", 1)
    suffix = "_" + safe_target
    if stem.endswith(suffix) and len(stem) > len(suffix):
        stem = stem[:-len(suffix)]
    return stem or "result", host


def _registrable_apex(host: str) -> str:
    """eTLD+1 guess without the public-suffix list: the last two labels."""
    labels = host.split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def add_base_target(export: HenonExport, target: dict) -> None:
    """Seed the base target: its domain/subdomain asset, URL endpoint and service."""
    host = (target.get("host") or "").strip().strip("[]").rstrip(".")
    if not host:
        return
    if _is_ip(host):
        export.add_asset("ip", addr=host)
    else:
        apex = _registrable_apex(host)
        kind = "domain" if host == apex else "subdomain"
        export.add_asset(kind, fqdn=host, apex=apex if kind == "subdomain" else "")
    url = (target.get("url") or "").strip()
    if url:
        export.add_web_endpoint(url, host=host if not _is_ip(host) else "")
    port = str(target.get("port") or "").strip()
    if port.isdigit():
        export.add_service(host, int(port))


def _add_hosts(export: HenonExport, hosts: list[str], base_host: str,
               excluded: set[str] | None = None) -> None:
    excluded = excluded or set()
    apex = _registrable_apex(base_host) if base_host and not _is_ip(base_host) else ""
    for name in hosts:
        # A host the operator excluded must never be re-introduced, even when a
        # tool's output still lists it (subfinder/amass seen it before exclusion).
        if name.strip().lower().rstrip(".") in excluded:
            continue
        if _is_ip(name):
            export.add_asset("ip", addr=name)
        elif apex and name.endswith("." + apex):
            export.add_asset("subdomain", fqdn=name, apex=apex)
        else:
            export.add_asset("subdomain", fqdn=name)


def from_cli_results(target_dir: Path | str, target: dict, scope: dict | None = None) -> dict:
    """Build the Henon contract document from a CLI results tree.

    ``target_dir`` is ``<data_home>/targets/<name>``; ``target`` is
    ``core.target.TARGET`` (host/url/port); ``scope`` is ``core.target.SCOPE``
    (its cached subdomains seed the ``assets``). Each saved result file is
    parsed by the family its filename resolves to; an unrecognised or unreadable
    file is skipped, never fatal.
    """
    target_dir = Path(target_dir)
    scope = scope or {}
    safe = target_dir.name
    base_host = (target.get("host") or "").strip().strip("[]").rstrip(".")
    # Hosts the operator excluded from the fan-out must never reach Henon, an
    # offensive engine: exporting them would re-introduce a host the operator
    # deliberately took out of scope (mirrors ``core.target.scope_hosts``).
    excluded = {s.strip().lower().rstrip(".") for s in scope.get("excluded", []) if isinstance(s, str)}
    subs = [s for s in scope.get("subdomains", [])
            if isinstance(s, str) and s.strip().lower().rstrip(".") not in excluded]
    export = HenonExport()
    add_base_target(export, target)
    _add_hosts(export, subs, base_host)

    if target_dir.is_dir():
        for cat in sorted(p for p in target_dir.iterdir() if p.is_dir()):
            for f in sorted(p for p in cat.glob("*") if p.is_file()):
                tool_base, run_host = _split_cli_name(f.stem, safe)
                if run_host and run_host.strip().lower().rstrip(".") in excluded:
                    continue  # result file for an excluded host: skip it whole
                family = _classify(tool_base)
                if not family:
                    continue
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                # One malformed file is skipped, never fatal (contract §1).
                try:
                    _ingest(export, family, text, host=run_host or base_host, excluded=excluded)
                except (ValueError, TypeError):
                    continue
    # Endpoints harvested from a crawl can point at an excluded subdomain.
    export.drop_web_hosts(excluded)
    return export.document()


def from_run_records(target: dict, records: list[tuple[str, str]],
                     scope: dict | None = None) -> dict:
    """Build the contract from ``(output_base, text)`` pairs.

    The Desktop keeps each run's output in its own ``runs/<id>/output.txt``
    rather than the CLI's per-target tree, so it feeds the engine the preset's
    ``output`` base (``dig_a``, ``nmap_svcver``, …) — the exact token a CLI
    result *filename* would carry — paired with that run's text. Same families,
    same exclusions and same URL redaction as ``from_cli_results``; only the
    source of the text differs, so both front-ends emit an identical contract.
    """
    scope = scope or {}
    base_host = (target.get("host") or "").strip().strip("[]").rstrip(".")
    excluded = {s.strip().lower().rstrip(".") for s in scope.get("excluded", []) if isinstance(s, str)}
    subs = [s for s in scope.get("subdomains", [])
            if isinstance(s, str) and s.strip().lower().rstrip(".") not in excluded]
    export = HenonExport()
    add_base_target(export, target)
    _add_hosts(export, subs, base_host)
    for output_base, text in records:
        if not isinstance(output_base, str) or not isinstance(text, str):
            continue
        family = _classify(output_base)
        if not family:
            continue
        # One malformed run is skipped, never fatal (contract §1).
        try:
            _ingest(export, family, text, host=base_host, excluded=excluded)
        except (ValueError, TypeError):
            continue
    export.drop_web_hosts(excluded)
    return export.document()


def _ingest(export: HenonExport, family: str, text: str, host: str,
            excluded: set[str] | None = None) -> None:
    """Route one parsed result file into the accumulator for its family."""
    if family == "hosts":
        _add_hosts(export, parse_hosts(text), host, excluded=excluded)
    elif family == "a_record":
        # A/AAAA answers give the resolved IPs; the host↔ip tie is wired through
        # services/web_endpoints (their ``ip`` field), not here.
        for ip in parse_a_records(text):
            export.add_asset("ip", addr=ip)
    elif family == "ports":
        ips, services = parse_ports(text)
        for ip in ips:
            export.add_asset("ip", addr=ip)
        for svc in services:
            export.add_service(svc["host"], svc["port"], svc.get("proto", "tcp"),
                               ip=svc.get("ip", ""), service_name=svc.get("service_name", ""),
                               product=svc.get("product", ""), version=svc.get("version", ""))
    elif family == "httpx":
        # ``host`` is left to default to the URL's own host (contract §2.3): a
        # single httpx file can probe several hosts, so the URL is authoritative.
        for rec in parse_httpx(text):
            export.add_web_endpoint(rec["url"], status_code=rec.get("status_code"),
                                    title=rec.get("title", ""), tech=rec.get("tech"))
    elif family == "urls":
        for url in parse_url_list(text):
            export.add_web_endpoint(url)
    elif family == "nuclei":
        for rec in parse_nuclei(text):
            export.add_web_endpoint(rec["url"], cve=rec.get("cve"), interesting=rec.get("interesting"))
    elif family == "cloud":
        for record in parse_cloud_json(text):
            export.add_cloud_resource(record)


# --------------------------------------------------------------------------- output

def render_json(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def default_filename() -> str:
    return "recon.json"


def write_export(document: dict, path: Path | str, within: Path | str | None = None) -> Path:
    """Write the contract JSON to ``path`` (default extension ``.json``).

    Atomic and symlink-safe via the shared ``core.safe_io`` writer: a planted
    ``recon.json`` symlink (or a symlinked parent under ``within``) can never
    redirect this write — relevant because the CLI often runs under ``sudo``
    (CWE-59). ``within`` is the app-owned root the destination must live under; a
    user-chosen ``-o`` / prompt path passes ``within=None`` and is written as
    given, still refusing to follow a symlink at ``path`` itself.

    The atomic write lands the file ``root:root`` in mode ``0o600`` when the CLI
    runs under ``sudo``; Henon then reads it as the unprivileged operator and
    would hit ``Permission denied``, breaking the ChaosticTool → Henon handoff.
    So the file is handed back to the sudo-invoking user — resolved once through
    the shared ``core.target.sudo_user_ids`` helper (``None`` when not under
    ``sudo``, so the non-elevated path is unchanged) and applied by ``fchown`` on
    the temp descriptor *before* the rename, never by re-resolving the path as
    root (CWE-59 / CWE-367 safe). Covers every caller in one place: flow
    auto-export, ``--export-henon``, TUI ``h`` and the Desktop writer."""
    from core import safe_io
    from core.target import sudo_user_ids
    path = Path(path)
    if not path.suffix:
        path = path.with_suffix(".json")
    return safe_io.atomic_write(path, render_json(document), within=within,
                                chown_to=sudo_user_ids())


def summary(document: dict) -> str:
    """One-line count of what the document carries, for the CLI feedback."""
    return " · ".join(f"{len(document.get(k, []))} {k}" for k in
                      ("assets", "services", "web_endpoints", "cloud_resources"))
