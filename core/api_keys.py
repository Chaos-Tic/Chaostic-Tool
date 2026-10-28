"""Persistent, local API keys for the embedded tools that read them.

Some catalog tools unlock features when an API credential is present in the
environment (Shodan host lookups, the WPScan vulnerability database, higher
GitHub rate limits for the OSINT sources). This module keeps those keys in the
user's writable data directory so they survive restarts, and maps them to the
environment variables each tool reads. Keys are never written into the
application installation and never leave the machine.
"""
from __future__ import annotations

import json
import os

try:
    import pwd
except ImportError:  # pragma: no cover - Windows
    pwd = None

from core.paths import data_home, ensure_directory

# Each spec is one credential the user sets once and reuses across launches.
# `env` is the environment variable the embedded tool reads; `tools` is shown
# in the UI so the user knows what the key unlocks. Adding a provider is a
# matter of appending a spec here.
KEY_SPECS = [
    {
        "id": "shodan",
        "env": "SHODAN_API_KEY",
        "label": "Shodan",
        "tools": "shodan, theHarvester",
        "help": "Shodan account key (Account → API). Enables host lookups and the Shodan passive source.",
    },
    {
        "id": "wpscan",
        "env": "WPSCAN_API_TOKEN",
        "label": "WPScan",
        "tools": "wpscan",
        "help": "WPScan API token (wpscan.com profile). Unlocks the WordPress vulnerability database.",
    },
    {
        "id": "github",
        "env": "GITHUB_TOKEN",
        "label": "GitHub token",
        "tools": "amass, subfinder, gau, nuclei",
        "help": "GitHub token (no scopes required). Raises API rate limits for the OSINT sources.",
    },
]

SPEC_BY_ID = {spec["id"]: spec for spec in KEY_SPECS}

FILENAME = "api-keys.json"


def _path():
    return data_home() / FILENAME


def _sanitize(values):
    """Keep only known ids whose value is a non-empty string, trimmed."""
    clean = {}
    if isinstance(values, dict):
        for key_id, value in values.items():
            if key_id in SPEC_BY_ID and isinstance(value, str) and value.strip():
                clean[key_id] = value.strip()
    return clean


def load():
    """Return the stored keys as {id: value}; an unreadable file yields {}."""
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return _sanitize(data)


def _chown(path):
    """Give the file back to the invoking user when running under sudo."""
    sudo_user = os.environ.get("SUDO_USER")
    if (hasattr(os, "geteuid") and os.geteuid() == 0 and sudo_user
            and sudo_user != "root" and pwd is not None and hasattr(os, "chown")):
        try:
            account = pwd.getpwnam(sudo_user)
            os.chown(path, account.pw_uid, account.pw_gid)
        except (KeyError, OSError):
            pass


def save(values):
    """Persist the given keys atomically with owner-only permissions."""
    ensure_directory(data_home())
    clean = _sanitize(values)
    path = _path()
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(temp, 0o600)
    except OSError:
        pass
    temp.replace(path)
    _chown(path)
    return clean


def set_key(key_id, value):
    """Set or, when the value is blank, clear a single key and persist."""
    if key_id not in SPEC_BY_ID:
        raise KeyError(key_id)
    values = load()
    if value and value.strip():
        values[key_id] = value.strip()
    else:
        values.pop(key_id, None)
    return save(values)


def env_overrides(values):
    """Map stored keys to the {ENV_VAR: value} pairs the tools read."""
    return {SPEC_BY_ID[key_id]["env"]: value
            for key_id, value in _sanitize(values).items()}


def apply_to_env(env):
    """Merge the stored keys into an environment mapping in place.

    An existing value already set by the user's shell always wins, so the
    stored key only fills a variable the environment does not define.
    """
    for var, value in env_overrides(load()).items():
        if not env.get(var):
            env[var] = value
    return env
