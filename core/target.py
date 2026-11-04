import json
import logging
import re
import os
try:
    import pwd
except ImportError:
    pwd = None
import ipaddress
from urllib.parse import urlsplit, urlunsplit

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


class TargetError(ValueError):
    """Invalid target input.

    Carries a stable ``code`` so each front end can render the message in its own
    language (the CLI shows the English message directly; the GUI maps the code to
    a French string). ``ValueError`` subclass so existing ``except ValueError``
    handlers keep catching it.
    """

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


_HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")


def _bracket(host):
    """Wrap a literal IPv6 address in brackets for an HTTP authority."""
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def normalize_target(raw, port_override=None):
    """Canonical, validated interpretation of a target address.

    Single source of truth shared by the CLI (:func:`set_target`) and the GUI
    (``desktop.storage.parse_target``) so the same input yields the same host,
    URL and port on both sides. Accepts a bare domain or subdomain, an IPv4 or
    IPv6 literal, or a full URL.

    Scheme and port: a URL's own scheme is respected, along with its explicit
    port (otherwise the scheme default). A bare entry (no scheme) defaults to
    https on port 443 -- the port no longer silently decides the scheme.
    ``port_override`` (an int, a digit string, or ``None``/empty for "no
    override") forces the port without changing the scheme.

    Canonical URL form: ``scheme://host[:port]`` with the port shown only when it
    was given explicitly (an override or a port in the URL); the entered path,
    query and fragment are preserved verbatim and no trailing ``/`` is added to a
    bare host. Raises :class:`TargetError` on invalid input (spaces or control
    characters, a non-http(s) scheme, embedded credentials, an invalid IDNA or
    host label, or a port outside 1-65535).

    Returns a dict with ``host``, ``url``, ``port`` (int), ``scheme`` and
    ``echo`` (a one-line human-readable interpretation).
    """
    raw = (raw or "").strip()
    if not raw:
        raise TargetError("empty", "Enter a target: a domain, an IP address, or a full URL.")
    if any(c.isspace() or ord(c) < 32 for c in raw):
        raise TargetError("whitespace", "The target must not contain spaces or control characters.")
    value = raw
    try:
        ip = ipaddress.ip_address(value)
        value = f"[{ip}]" if ip.version == 6 else str(ip)
    except ValueError:
        pass
    try:
        parsed = urlsplit(value if "://" in value else "https://" + value)
        url_port = parsed.port
        host = parsed.hostname or ""
    except ValueError as exc:
        raise TargetError("malformed", "The address or its port is malformed.") from exc
    if parsed.scheme not in ("http", "https"):
        raise TargetError("scheme", "Use an http:// or https:// address (no other scheme).")
    if parsed.username is not None or parsed.password is not None:
        raise TargetError("credentials", "Remove the embedded username or password from the URL.")
    if not host:
        raise TargetError("host", "Enter a single target: a domain, an IPv4 or an IPv6 address.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        try:
            host = host.encode("idna").decode("ascii").rstrip(".")
        except UnicodeError as exc:
            raise TargetError("idna", "Invalid domain name.") from exc
        if len(host) > 253 or not all(_HOST_LABEL.fullmatch(p) for p in host.split(".")):
            raise TargetError("host", "Enter a single target: a domain, an IPv4 or an IPv6 address.") from None
    # An explicit override wins, else the URL's own port, else the scheme default.
    override = None if port_override is None else str(port_override).strip()
    if override:
        try:
            port = int(override)
        except ValueError as exc:
            raise TargetError("port", "The port must be between 1 and 65535.") from exc
        explicit_port = True
    elif url_port is not None:
        port = url_port
        explicit_port = True
    else:
        port = None
        explicit_port = False
    if port is not None and not 1 <= port <= 65535:
        raise TargetError("port", "The port must be between 1 and 65535.")
    scheme = parsed.scheme
    if port is None:
        port = 443 if scheme == "https" else 80
    netloc = _bracket(host)
    if explicit_port:
        netloc += f":{port}"
    url = urlunsplit((scheme, netloc, parsed.path, parsed.query, parsed.fragment))
    return {"host": host, "url": url, "port": port, "scheme": scheme,
            "echo": _echo(scheme, host, port)}


def _echo(scheme, host, port):
    """One-line, human-readable interpretation of a normalized target."""
    return f"{scheme}://{_bracket(host)}:{port} — host {host} · scheme {scheme} · port {port}"


def describe_target():
    """Echo line for the active target (what the input was understood to mean)."""
    if not is_defined():
        return "No target defined"
    host = TARGET["host"]
    scheme = urlsplit(TARGET["url"]).scheme if TARGET["url"] else "https"
    port = TARGET["port"] or ("443" if scheme == "https" else "80")
    return _echo(scheme, host, port)


def set_target(host="", url="", port=None, wordlist=None):
    raw = (url or "").strip() or (host or "").strip()
    info = normalize_target(raw, port_override=port)
    TARGET["host"] = info["host"]
    TARGET["url"] = info["url"]
    TARGET["port"] = str(info["port"])
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
    from core import safe_io
    safe_io.atomic_write(path, json.dumps({"include_subdomains": SCOPE["include_subdomains"],
                                           "subdomains": SCOPE["subdomains"],
                                           "excluded": SCOPE["excluded"],
                                           "fanout_limit": SCOPE["fanout_limit"]}, indent=2),
                         within=TARGETS_ROOT)
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
    """URL for a given scope host.

    The active target's URL is kept intact (scheme, port, path, query and
    fragment): only its hostname is swapped for ``host``, so the base host gets
    back exactly the URL that was entered. Without a target URL the result is
    derived from the host and the active port.
    """
    url = TARGET["url"]
    if not url:
        return _normalize_url("", host, TARGET["port"])
    if host.lower() == TARGET["host"].lower():
        return url
    parts = urlsplit(url)
    # Literal IPv6 addresses need brackets in an HTTP authority.
    netloc = f"[{host}]" if ":" in host and not host.startswith("[") else host
    try:
        port = parts.port
    except ValueError:  # malformed port in the entered URL: keep the hostname swap only
        port = None
    if port is not None:
        netloc = f"{netloc}:{port}"
    userinfo, sep, _ = parts.netloc.rpartition("@")
    return urlunsplit(parts._replace(netloc=f"{userinfo}{sep}{netloc}"))


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
