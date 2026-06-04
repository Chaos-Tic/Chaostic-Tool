import re
import os
import pwd
from urllib.parse import urlparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
TARGETS_ROOT = SCRIPT_DIR / "targets"

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
    return host.split("/")[0].split(":")[0], ""


def set_target(host="", url="", port="80", wordlist=None):
    clean_host, host_url = _split_host_input(host)
    TARGET["host"] = clean_host
    TARGET["port"] = port.strip() or "80"
    TARGET["url"] = _normalize_url((url.strip() or host_url), TARGET["host"], TARGET["port"])
    if not TARGET["host"] and TARGET["url"]:
        TARGET["host"] = re.sub(r"^https?://", "", TARGET["url"]).split("/")[0].split(":")[0]
    if wordlist:
        TARGET["wordlist"] = wordlist

    name = target_name()
    if name:
        for cat in CATEGORIES:
            (TARGETS_ROOT / name / cat).mkdir(parents=True, exist_ok=True)
        _chown_tree(TARGETS_ROOT / name)
    return target_dir()


def summary():
    if not is_defined():
        return "No target defined"
    parts = []
    if TARGET["host"]:
        parts.append(f"host={TARGET['host']}")
    if TARGET["url"]:
        parts.append(f"url={TARGET['url']}")
    parts.append(f"port={TARGET['port']}")
    return " | ".join(parts)


def _chown_tree(path):
    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user or sudo_user == "root":
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
