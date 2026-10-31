import json
import logging
import re
import os
try:
    import pwd
except ImportError:
    pwd = None
import ipaddress
from urllib.parse import urlparse

from core.paths import data_home, ensure_directory

LOG = logging.getLogger(__name__)

TARGETS_ROOT = data_home() / "targets"

CATEGORIES = [
    "osint", "recon", "web_enum", "vulnscan", "exploitation",
    "postexploit", "passwords", "wireless", "network",
]

TARGET = {
    "host": "",
    "url": "",
    "port": "80",
    "wordlist": "/usr/share/wordlists/dirb/common.txt",
}

# Subdomain scope for the active target. When enabled, host-targeted tools run
# against the base host and every discovered subdomain (minus any excluded).
# Cached per target so an enumeration is reused across launches. ``excluded``
# holds discovered subdomains the user chose to skip; ``fanout_limit`` is an
# optional per-target override of the shared hard cap (None = use the default).
SCOPE = {"include_subdomains": False, "subdomains": [], "excluded": [], "fanout_limit": None}


def _safe_name(value):
    name = re.sub(r"^https?://", "", value).strip("/")
    name = name.split("/")[0]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    name = name.strip(".")  # empêche "." ".." "..."
    return name or "target"


def is_defined():
    return bool(TARGET["host"] or TARGET["url"])


def target_name():
    base = TARGET["host"] or TARGET["url"]
    return _safe_name(base) if base else ""


def target_dir():
    name = target_name()
    if not name:
        return None
    return TARGETS_ROOT / name


def category_dir(category):
    d = target_dir()
    if d is None:
        return None
    cat = d / category
    ensure_directory(cat)
    return cat


def _normalize_url(url, host, port):
    if url:
        if not re.match(r"^https?://", url):
            url = "http://" + url
        return url
    if host:
        # Literal IPv6 addresses need brackets in an HTTP authority.
        host = f"[{host}]" if ":" in host and not host.startswith("[") else host
        scheme = "https" if port in ("443", "8443") else "http"
        if port in ("80", "443"):
            return f"{scheme}://{host}"
        return f"{scheme}://{host}:{port}"
    return ""


def _split_host_input(host):
    host = host.strip()
    if not host:
        return "", ""
    if re.match(r"^https?://", host):
        parsed = urlparse(host)
        return parsed.hostname or "", host
    authority = host.split("/")[0]
    try:
        return str(ipaddress.ip_address(authority)), ""
    except ValueError:
        parsed = urlparse("//" + authority)
        return parsed.hostname or "", ""


def set_target(host="", url="", port="80", wordlist=None):
    clean_host, host_url = _split_host_input(host)
    TARGET["host"] = clean_host
    TARGET["port"] = port.strip() or "80"
    TARGET["url"] = _normalize_url((url.strip() or host_url), TARGET["host"], TARGET["port"])
    if not TARGET["host"] and TARGET["url"]:
        TARGET["host"] = urlparse(TARGET["url"]).hostname or ""
    if wordlist:
        TARGET["wordlist"] = wordlist

    name = target_name()
    if name:
        for cat in CATEGORIES:
            ensure_directory(TARGETS_ROOT / name / cat)
    load_scope()
    return target_dir()


def _scope_path():
    d = target_dir()
    return (d / "subdomains.json") if d is not None else None


def load_scope():
    """Reload the active target's cached subdomain scope from disk."""
    SCOPE["include_subdomains"] = False
    SCOPE["subdomains"] = []
    SCOPE["excluded"] = []
    SCOPE["fanout_limit"] = None
    path = _scope_path()
    if path is None or not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(data, dict):
        subs = data.get("subdomains", [])
        SCOPE["subdomains"] = [s for s in subs if isinstance(s, str)] if isinstance(subs, list) else []
        excluded = data.get("excluded", [])
        SCOPE["excluded"] = [s for s in excluded if isinstance(s, str)] if isinstance(excluded, list) else []
        limit = data.get("fanout_limit")
        SCOPE["fanout_limit"] = limit if isinstance(limit, int) and limit > 0 else None
        SCOPE["include_subdomains"] = bool(data.get("include_subdomains")) and bool(SCOPE["subdomains"])


def save_scope():
    path = _scope_path()
    if path is None:
        return
    ensure_directory(path.parent)
    path.write_text(json.dumps({"include_subdomains": SCOPE["include_subdomains"],
                                "subdomains": SCOPE["subdomains"],
                                "excluded": SCOPE["excluded"],
                                "fanout_limit": SCOPE["fanout_limit"]}, indent=2), encoding="utf-8")
    _chown_path(path)


def set_subdomains(subdomains):
    """Store a freshly enumerated subdomain list for the active target."""
    from core import subdomains as sd
    host = TARGET["host"]
    SCOPE["subdomains"] = sorted({s.strip().lower().rstrip(".") for s in subdomains
                                  if isinstance(s, str) and s.strip() and sd.within_domain(s, host) and s.strip().lower().rstrip(".") != host.lower()})
    # Drop exclusions that no longer refer to a discovered subdomain.
    SCOPE["excluded"] = [s for s in SCOPE["excluded"] if s in SCOPE["subdomains"]]
    if not SCOPE["subdomains"]:
        SCOPE["include_subdomains"] = False
    save_scope()


def set_scope_enabled(enabled):
    SCOPE["include_subdomains"] = bool(enabled) and bool(SCOPE["subdomains"])
    save_scope()


def set_excluded(excluded):
    """Replace the set of discovered subdomains excluded from the fan-out."""
    allowed = set(SCOPE["subdomains"])
    SCOPE["excluded"] = sorted({s.strip().lower().rstrip(".") for s in excluded
                                if isinstance(s, str) and s.strip().lower().rstrip(".") in allowed})
    save_scope()


def toggle_excluded(host):
    """Flip the exclusion of one discovered subdomain; returns True if excluded."""
    host = (host or "").strip().lower().rstrip(".")
    if host not in set(SCOPE["subdomains"]):
        return host in SCOPE["excluded"]
    excluded = set(SCOPE["excluded"])
    excluded.symmetric_difference_update({host})
    SCOPE["excluded"] = sorted(excluded)
    save_scope()
    return host in excluded


def effective_fanout_limit():
    """The hard cap on hosts for the active target (per-target override or default)."""
    from core import subdomains as sd
    limit = SCOPE.get("fanout_limit")
    return limit if isinstance(limit, int) and limit > 0 else sd.MAX_FANOUT


def fanout_count():
    """Hosts the active target would expand to, uncapped (base plus subs)."""
    from core import subdomains as sd
    return sd.fanout_count(TARGET["host"], SCOPE["subdomains"],
                           SCOPE["include_subdomains"], excluded=SCOPE["excluded"])


def scope_hosts(limit="default"):
    """Hosts the active target expands to: base first, then subdomains.

    Exclusions are always applied. ``limit`` caps the count (base first); the
    default applies the per-target hard cap so a run never fans out silently to
    an unbounded number of hosts. Pass an explicit integer to run only the first
    K, or ``None`` to disable the cap entirely.
    """
    from core import subdomains as sd
    cap = effective_fanout_limit() if limit == "default" else limit
    return sd.scope_hosts(TARGET["host"], SCOPE["subdomains"], SCOPE["include_subdomains"],
                          limit=cap, excluded=SCOPE["excluded"])


def scope_url(host):
    """URL for a given scope host, following the active target's port/scheme."""
    return _normalize_url("", host, TARGET["port"])


def summary():
    if not is_defined():
        return "No target defined"
    parts = []
    if TARGET["host"]:
        parts.append(f"host={TARGET['host']}")
    if TARGET["url"]:
        parts.append(f"url={TARGET['url']}")
    parts.append(f"port={TARGET['port']}")
    if SCOPE["include_subdomains"] and SCOPE["subdomains"]:
        active = len([s for s in SCOPE["subdomains"] if s not in set(SCOPE["excluded"])])
        extra = f"+{active} subdomains"
        if SCOPE["excluded"]:
            extra += f" ({len(SCOPE['excluded'])} excluded)"
        parts.append(extra)
    return " | ".join(parts)


def _chown_path(path):
    """Give a single newly created path back to the sudo-invoking user.

    Only the exact path is chowned. The previous implementation walked the whole
    target tree (``rglob("*")``) on every save, which grew O(files) as scan
    outputs accumulated. Directory creation goes through ``ensure_directory``,
    which already chowns just the directories it creates, so no recursive walk
    is needed any more.
    """
    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user or sudo_user == "root" or pwd is None or not hasattr(os, "chown"):
        return
    try:
        pw = pwd.getpwnam(sudo_user)
        os.chown(path, pw.pw_uid, pw.pw_gid)
    except (KeyError, OSError):
        LOG.warning("Could not chown %s to the sudo user", path,
                    exc_info=True)
        return
