"""Subdomain enumeration and target-scope expansion.

When a target is a registrable domain, the user can choose to reach every
discovered subdomain as well, so launching a tool runs it against the base host
*and* each subdomain. Discovery is delegated to subfinder (fast, passive and
reliable) first; amass is used only as a complement/fallback and is allowed to
return nothing without failing the enumeration. Every candidate is validated to
stay within the domain, so scope never silently widens to unrelated hosts.

This module is UI-independent: both the terminal and the desktop interface use
it. Process execution is injected (``runner``) so it is fully testable.
"""
from __future__ import annotations

import ipaddress
import re
import shutil
import subprocess

_LABEL = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")
# A hostname-looking token anywhere in a line of tool output.
_HOST_TOKEN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")


def is_domain(host: str) -> bool:
    """True for a DNS name that can be enumerated (not an IP, not empty)."""
    if not host:
        return False
    stripped = host.strip().strip("[]")
    try:
        ipaddress.ip_address(stripped)
        return False
    except ValueError:
        pass
    labels = stripped.rstrip(".").split(".")
    return len(labels) >= 2 and all(_LABEL.match(part) for part in labels)


def within_domain(candidate: str, domain: str) -> bool:
    """True when candidate is the domain itself or one of its subdomains."""
    candidate = candidate.lower().strip().rstrip(".")
    domain = domain.lower().strip().rstrip(".")
    return bool(domain) and (candidate == domain or candidate.endswith("." + domain))


def parse_hosts(text: str, domain: str) -> list[str]:
    """Extract valid, in-scope subdomains from tool output, deduplicated.

    Liberal about surrounding noise (amass decorates lines), but every result
    must be a syntactically valid hostname ending in the target domain, and the
    bare domain itself is excluded.
    """
    found: list[str] = []
    seen: set[str] = set()
    domain_l = domain.lower().rstrip(".")
    for line in text.splitlines():
        for token in _HOST_TOKEN.findall(line):
            host = token.lower().rstrip(".")
            if (host and host != domain_l and host not in seen
                    and is_domain(host) and within_domain(host, domain_l)):
                seen.add(host)
                found.append(host)
    return sorted(found)


def _run(cmd, env, timeout):
    """Execute an enumerator, returning (returncode, stdout, stderr)."""
    try:
        # errors="replace": enumerator banners/stderr may carry non-UTF-8 bytes;
        # strict decoding would raise and crash the caller.
        completed = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                                   env=env, timeout=timeout, check=False)
        return completed.returncode, completed.stdout or "", completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        return 124, (exc.stdout or "") if isinstance(exc.stdout, str) else "", "timeout"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)


# name -> command builder. subfinder is primary; amass is a best-effort
# complement (the user reports it is often slow or empty, so it never decides
# success on its own).
ENUMERATORS = [
    ("subfinder", lambda domain: ["subfinder", "-silent", "-all", "-d", domain]),
    ("amass", lambda domain: ["amass", "enum", "-passive", "-norecursive", "-d", domain]),
]


def available_enumerators(path=None):
    """Enumerator names whose binary is on PATH."""
    return [name for name, _ in ENUMERATORS if shutil.which(name, path=path)]


def enumerate_subdomains(domain, env=None, timeout=240, runner=None, path=None):
    """Discover subdomains of ``domain``.

    Returns (subdomains, sources, error): ``sources`` lists the tools that
    produced results; ``error`` is set only when no enumerator could run at all.
    """
    if not is_domain(domain):
        return [], [], "Enter a domain name (subdomain scope needs a domain, not an IP)."
    runner = runner or _run
    results: set[str] = set()
    sources: list[str] = []
    ran_any = False
    last_error = ""
    for name, build in ENUMERATORS:
        if runner is _run and not shutil.which(name, path=(env or {}).get("PATH") if path is None else path):
            continue
        ran_any = True
        code, out, err = runner(build(domain), env, timeout)
        hosts = parse_hosts(out, domain)
        if hosts:
            sources.append(name)
            results.update(hosts)
        elif code not in (0, None):
            last_error = err.strip() or last_error
    if not ran_any:
        return [], [], "No subdomain enumerator found. Install subfinder (recommended) or amass."
    return sorted(results), sources, "" if (results or not last_error) else last_error


def scope_hosts(host, subdomains, include):
    """Base host first, then in-scope subdomains, deduplicated.

    The base host is always included, even when ``include`` is false, so callers
    can use this as the single source of truth for what a run targets.
    """
    hosts = [host] if host else []
    if include and host:
        for sub in subdomains or []:
            sub = (sub or "").strip().lower().rstrip(".")
            if sub and sub != host.lower() and sub not in hosts and within_domain(sub, host):
                hosts.append(sub)
    return hosts
