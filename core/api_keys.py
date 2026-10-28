"""Persistent API keys for the embedded tools that read them.

Some catalog tools unlock features when an API credential is present (Shodan
host lookups, the Shodan nmap script, the WPScan vulnerability database, higher
GitHub rate limits for the OSINT sources). Keys are stored in the operating
system's own secret store through ``keyring`` — Windows Credential Manager,
macOS Keychain, or the Linux Secret Service — so they are encrypted at rest and
never written to disk in clear text.

When no secure store is available (for example a headless root shell with no
Secret Service), keys are kept in memory for the current process only and the
interfaces warn that they will not persist; a value exported in the environment
still takes precedence and is always honoured.
"""
from __future__ import annotations

import os

SERVICE = "ChaosticTool"

# Each spec is one credential the user sets once and reuses across launches.
# `env` is the environment variable the embedded tool reads; `tools` is shown
# in the UI. Adding a provider is a matter of appending a spec here.
KEY_SPECS = [
    {
        "id": "shodan",
        "env": "SHODAN_API_KEY",
        "label": "Shodan",
        "tools": "shodan, nmap (shodan-api), theHarvester",
        "help": "Shodan account key (Account → API). Enables host lookups, the nmap shodan-api script and the passive source.",
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

# In-memory fallback for the current process when no OS secret store is usable.
_SESSION: dict[str, str] = {}
_backend = None  # resolved lazily; tests may override via set_backend().


class _NullBackend:
    """Used when keyring is missing or has no working backend."""
    available = False

    def get(self, key_id):
        return None

    def set(self, key_id, value):
        raise RuntimeError("no secure store")

    def delete(self, key_id):
        pass


class _KeyringBackend:
    def __init__(self, keyring):
        self._keyring = keyring

    @property
    def available(self):
        try:
            from keyring.backends import fail
            if isinstance(self._keyring.get_keyring(), fail.Keyring):
                return False
        except Exception:
            pass
        return True

    def get(self, key_id):
        try:
            return self._keyring.get_password(SERVICE, key_id)
        except Exception:
            return None

    def set(self, key_id, value):
        self._keyring.set_password(SERVICE, key_id, value)

    def delete(self, key_id):
        try:
            self._keyring.delete_password(SERVICE, key_id)
        except Exception:
            pass


def _resolve_backend():
    global _backend
    if _backend is None:
        try:
            import keyring
            candidate = _KeyringBackend(keyring)
            _backend = candidate if candidate.available else _NullBackend()
        except Exception:
            _backend = _NullBackend()
    return _backend


def set_backend(backend):
    """Install a backend (tests) and clear any session fallback."""
    global _backend
    _backend = backend
    _SESSION.clear()


def secure_storage_available():
    """True when keys will persist across launches (an OS secret store exists)."""
    return bool(getattr(_resolve_backend(), "available", False))


def get(key_id):
    """Return the stored value for a key id, or None."""
    if key_id not in SPEC_BY_ID:
        return None
    backend = _resolve_backend()
    if backend.available:
        value = backend.get(key_id)
        return value.strip() if isinstance(value, str) and value.strip() else None
    return _SESSION.get(key_id)


def set_key(key_id, value):
    """Store or, when the value is blank, clear a single key.

    Returns True when the value will persist across launches, False when it was
    only kept for this process because no secure store is available.
    """
    if key_id not in SPEC_BY_ID:
        raise KeyError(key_id)
    value = (value or "").strip()
    backend = _resolve_backend()
    if backend.available:
        if value:
            backend.set(key_id, value)
        else:
            backend.delete(key_id)
        return True
    if value:
        _SESSION[key_id] = value
    else:
        _SESSION.pop(key_id, None)
    return False


def load():
    """Return the currently set keys as {id: value}."""
    result = {}
    for spec in KEY_SPECS:
        value = get(spec["id"])
        if value:
            result[spec["id"]] = value
    return result


def configured():
    """Return the set of key ids that currently have a value."""
    return set(load())


def env_overrides(values=None):
    """Map set keys to the {ENV_VAR: value} pairs the tools read."""
    if values is None:
        values = load()
    return {SPEC_BY_ID[key_id]["env"]: value
            for key_id, value in values.items()
            if key_id in SPEC_BY_ID and value}


def apply_to_env(env):
    """Merge the set keys into an environment mapping in place.

    A value already present in the environment always wins, so a stored key only
    fills a variable the environment does not already define.
    """
    for var, value in env_overrides().items():
        if not env.get(var):
            env[var] = value
    return env
