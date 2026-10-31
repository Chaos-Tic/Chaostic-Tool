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
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

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


# name -> (command builder, writes_to_outfile). subfinder is primary and prints
# hosts to stdout. amass (v5+) prints only progress to stdout and must be told
# to write results to a file with ``-o`` — ``-passive`` was removed in v5, so we
# no longer pass it; amass stays best-effort (0 results is never a failure).
ENUMERATORS = [
    ("subfinder", lambda domain, outfile=None: ["subfinder", "-silent", "-all", "-d", domain], False),
    ("amass", lambda domain, outfile=None: ["amass", "enum", "-norecursive", "-d", domain]
     + (["-o", outfile] if outfile else []), True),
]

# Fan-out safety limits, shared by the CLI and the desktop so both behave the
# same. Launching a host-targeted profile with subdomain scope on runs the tool
# once per in-scope host (sequentially); a large scope can therefore mean hours
# of work, so we warn before a big fan-out and cap it hard.
WARN_FANOUT = 25    # ask for confirmation beyond this many hosts (base + subs)
MAX_FANOUT = 100    # never silently fan out to more than this many hosts
MAX_ENUM_RESULTS = 500  # cap on subdomains stored from one enumeration


def _normalize_set(values):
    """Lower-cased, trailing-dot-stripped set of hostnames, ignoring blanks."""
    out = set()
    for value in values or []:
        if isinstance(value, str):
            host = value.strip().lower().rstrip(".")
            if host:
                out.add(host)
    return out


def available_enumerators(path=None):
    """Enumerator names whose binary is on PATH."""
    return [name for name, _, _ in ENUMERATORS if shutil.which(name, path=path)]


def command_for(name, domain, outfile=None):
    """The argv for one enumerator (e.g. to run it through the shared runner)."""
    for enum_name, build, _ in ENUMERATORS:
        if enum_name == name:
            return build(domain, outfile)
    raise KeyError(name)


def _enumerator_spec(name):
    for enum_name, build, use_outfile in ENUMERATORS:
        if enum_name == name:
            return build, use_outfile
    raise KeyError(name)


def run_enumerator(name, domain, env=None, timeout=None, runner=None):
    """Run one enumerator and return (hosts, returncode, error).

    When the tool writes to a file (amass), its output is read back from a
    temporary file and parsed together with whatever reached stdout, so a tool
    that prints only progress to stdout still yields hosts.
    """
    build, use_outfile = _enumerator_spec(name)
    runner = runner or _run
    outfile = None
    if use_outfile:
        handle, outfile = tempfile.mkstemp(prefix="chaostic-subs-", suffix=".txt")
        os.close(handle)
    try:
        code, out, err = runner(build(domain, outfile), env, timeout)
        text = out or ""
        if outfile:
            try:
                text = text + "\n" + Path(outfile).read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
    finally:
        if outfile:
            try:
                os.unlink(outfile)
            except OSError:
                pass
    return parse_hosts(text, domain), code, err


def enumerate_subdomains(domain, env=None, budget=240, runner=None, path=None):
    """Discover subdomains of ``domain``.

    ``budget`` is a single time budget (seconds) shared across *all*
    enumerators, not a per-tool timeout: each enumerator is given only the time
    still left, and once the budget is spent the remaining tools are skipped.
    This bounds the whole discovery at ``budget`` instead of
    ``len(ENUMERATORS) * budget`` when a slow first tool runs to its own limit.

    Returns (subdomains, counts, error): ``counts`` is an insertion-ordered
    mapping of each tool that produced results to how many it returned (before
    merging/dedup across tools), so a caller can report "subfinder: X, amass: Y";
    its keys are the contributing tools. ``error`` is set only when no enumerator
    could run at all. The stored result list is capped at ``MAX_ENUM_RESULTS`` so
    a pathological domain cannot store thousands of hosts.
    """
    if not is_domain(domain):
        return [], {}, "Enter a domain name (subdomain scope needs a domain, not an IP)."
    runner = runner or _run
    results: set[str] = set()
    counts: dict[str, int] = {}
    ran_any = False
    last_error = ""
    deadline = time.monotonic() + budget if budget else None
    for name, _build, _use_outfile in ENUMERATORS:
        if runner is _run and not shutil.which(name, path=(env or {}).get("PATH") if path is None else path):
            continue
        remaining = None
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
        ran_any = True
        hosts, code, err = run_enumerator(name, domain, env=env, timeout=remaining, runner=runner)
        if hosts:
            counts[name] = len(hosts)
            results.update(hosts)
        elif code not in (0, None):
            last_error = err.strip() or last_error
    if not ran_any:
        return [], {}, "No subdomain enumerator found. Install subfinder (recommended) or amass."
    capped = sorted(results)[:MAX_ENUM_RESULTS]
    return capped, counts, "" if (results or not last_error) else last_error


def enumeration_summary(count, counts):
    """One honest result line for the CLI: total plus per-tool breakdown."""
    if not count:
        return "No subdomains found."
    detail = ", ".join(f"{name}: {n}" for name, n in counts.items())
    plural = "" if count == 1 else "s"
    return f"Found {count} subdomain{plural}" + (f" ({detail})" if detail else "") + "."


def scope_hosts(host, subdomains, include, limit=None, excluded=None):
    """Base host first, then in-scope subdomains, deduplicated.

    The base host is always included, even when ``include`` is false, so callers
    can use this as the single source of truth for what a run targets.

    ``excluded`` drops specific discovered subdomains from the fan-out (the base
    host is never excluded). ``limit`` caps the total number of hosts returned
    (base first), so a caller can offer to run only the first K — ``None`` means
    no cap. This is the single fan-out point for both front-ends.
    """
    excluded_set = _normalize_set(excluded)
    hosts = [host] if host else []
    if include and host:
        for sub in subdomains or []:
            sub = (sub or "").strip().lower().rstrip(".")
            if (sub and sub != host.lower() and sub not in hosts
                    and sub not in excluded_set and within_domain(sub, host)):
                hosts.append(sub)
    if limit is not None and limit >= 0:
        hosts = hosts[:limit]
    return hosts


def fanout_count(host, subdomains, include, excluded=None):
    """How many hosts a scoped run expands to (uncapped) — base plus subs."""
    return len(scope_hosts(host, subdomains, include, excluded=excluded))


def resolves(host):
    """True when the host has any A/AAAA record (or is an IP literal).

    Does a live DNS lookup, so callers must keep it off a UI thread.
    """
    host = (host or "").strip().strip("[]")
    if not host:
        return False
    try:
        socket.getaddrinfo(host, None)
        return True
    except (socket.gaierror, UnicodeError, OSError):
        return False


def resolution_status(host):
    """(resolves, www_alternative) for a host, doing a live DNS lookup.

    ``resolves`` is True when the host has an A/AAAA record (non-domains are
    treated as not our concern and report True). ``www_alternative`` is the
    ``www.`` form only when the host itself fails but that form resolves — the
    common Cloudflare case where only ``www`` has a record.
    """
    if not is_domain(host) or resolves(host):
        return True, ""
    if not host.startswith("www."):
        www = "www." + host
        if resolves(www):
            return False, www
    return False, ""


def resolution_warning(host):
    """A clear message (English, for the CLI) when a domain host does not resolve."""
    ok, www = resolution_status(host)
    if ok:
        return ""
    if www:
        return (f"{host} has no A/AAAA record (it does not resolve); only {www} resolves. "
                f"Host-targeted tools against {host} will return nothing — this is the "
                f"target's DNS, not a bug. Set the target to {www} to scan it.")
    return (f"{host} has no A/AAAA record (it does not resolve). Host-targeted tools will return "
            f"nothing until it resolves — this is the target's DNS, not a bug.")
