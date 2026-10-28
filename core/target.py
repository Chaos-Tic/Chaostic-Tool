import json
import re
import os
try:
    import pwd
except ImportError:
    pwd = None
import ipaddress
from urllib.parse import urlparse
from pathlib import Path

from core.paths import data_home, ensure_directory

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
# against the base host and every discovered subdomain. Cached per target so an
# enumeration is reused across launches.
SCOPE = {"include_subdomains": False, "subdomains": []}


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
    cat.mkdir(parents=True, exist_ok=True)
    _chown_tree(d)
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
        _chown_tree(TARGETS_ROOT / name)
    load_scope()
    return target_dir()


def _scope_path():
    d = target_dir()
    return (d / "subdomains.json") if d is not None else None


def load_scope():
    """Reload the active target's cached subdomain scope from disk."""
    SCOPE["include_subdomains"] = False
    SCOPE["subdomains"] = []
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
        SCOPE["include_subdomains"] = bool(data.get("include_subdomains")) and bool(SCOPE["subdomains"])


def save_scope():
    path = _scope_path()
    if path is None:
        return
    ensure_directory(path.parent)
    path.write_text(json.dumps({"include_subdomains": SCOPE["include_subdomains"],
                                "subdomains": SCOPE["subdomains"]}, indent=2), encoding="utf-8")
    _chown_tree(target_dir())


def set_subdomains(subdomains):
    """Store a freshly enumerated subdomain list for the active target."""
    from core import subdomains as sd
    host = TARGET["host"]
    SCOPE["subdomains"] = sorted({s.strip().lower().rstrip(".") for s in subdomains
                                  if isinstance(s, str) and s.strip() and sd.within_domain(s, host) and s.strip().lower().rstrip(".") != host.lower()})
    if not SCOPE["subdomains"]:
        SCOPE["include_subdomains"] = False
    save_scope()


def set_scope_enabled(enabled):
    SCOPE["include_subdomains"] = bool(enabled) and bool(SCOPE["subdomains"])
    save_scope()


def scope_hosts():
    """Hosts the active target expands to: base first, then subdomains."""
    from core import subdomains as sd
    return sd.scope_hosts(TARGET["host"], SCOPE["subdomains"], SCOPE["include_subdomains"])


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
        parts.append(f"+{len(SCOPE['subdomains'])} subdomains")
    return " | ".join(parts)


def _chown_tree(path):
    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user or sudo_user == "root" or pwd is None or not hasattr(os, "chown"):
        return
    try:
        pw = pwd.getpwnam(sudo_user)
        for item in [Path(path)] + list(Path(path).rglob("*")):
            try:
                os.chown(item, pw.pw_uid, pw.pw_gid)
            except OSError:
                pass
    except Exception:
        return
