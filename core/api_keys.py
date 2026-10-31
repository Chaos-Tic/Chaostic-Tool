"""Persistent API keys for the embedded tools that read them.

Some catalog tools unlock features when an API credential is present (Shodan
host lookups, the Shodan nmap script, the WPScan vulnerability database, higher
GitHub rate limits for the OSINT sources). Both front-ends share this module, so
a key saved in one is visible to the other.

Storage, in order of preference:

1. The operating system's secret store through ``keyring`` (Windows Credential
   Manager, macOS Keychain, Linux Secret Service): encrypted at rest by the OS.
2. A file under the shared data directory (``core.paths.data_home()``), used
   only once the user opts in. Its directory is 0700, the file 0600 and writes
   are atomic. When the optional ``cryptography`` library is importable the
   file is encrypted (PBKDF2-HMAC-SHA256 -> Fernet) with a passphrase asked
   once per session; otherwise the values are merely base64-encoded and the
   file permissions are the only protection. ``storage_status()`` tells the
   interfaces which of these applies so they never overstate the guarantee.
3. Memory for the current process only, when neither of the above is in use.

A value already exported in the environment always takes precedence.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import stat
from collections import namedtuple
from pathlib import Path

SERVICE = "ChaosticTool"
STORE_FILE = "api_keys.json"
PBKDF2_ITERATIONS = 600_000

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

# In-memory fallback for the current process when no persistent store is in use.
_SESSION: dict[str, str] = {}
_backend = None  # resolved lazily; tests may override via set_backend().
_passphrase_prompt = None  # callable(reason) -> str | None, installed by the UI.

# kind: "keyring" | "file-encrypted" | "file-plain" | "session".
# locked: an encrypted file exists but no passphrase unlocked it this session.
# can_encrypt: the optional `cryptography` library is importable.
StorageStatus = namedtuple("StorageStatus", "kind path locked can_encrypt")


def encryption_available():
    """True when the optional `cryptography` library can encrypt the file store."""
    try:
        import cryptography  # noqa: F401
        return True
    except Exception:
        return False


def set_passphrase_prompt(prompt):
    """Install the UI callback used to ask for the file-store passphrase.

    `prompt(reason)` receives "new" (choose a passphrase for a fresh store) or
    "unlock" (open an existing encrypted store) and returns the passphrase, or
    None/"" when the user declines. It is only ever called from this module.
    """
    global _passphrase_prompt
    _passphrase_prompt = prompt


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
    """OS secret store. `available` is proven by a real round-trip, not by the
    backend's own claim: keyring's ChainerBackend reports itself usable even
    when no store is unlocked, and only the first write would then fail."""

    CANARY = "chaostictool-probe"

    def __init__(self, keyring):
        self._keyring = keyring
        self._probe = None

    @property
    def available(self):
        if self._probe is None:
            self._probe = self._round_trip()
        return self._probe

    def _round_trip(self):
        try:
            from keyring.backends import fail
            if isinstance(self._keyring.get_keyring(), fail.Keyring):
                return False
        except Exception:
            pass
        try:
            token = secrets.token_hex(8)
            self._keyring.set_password(SERVICE, self.CANARY, token)
            ok = self._keyring.get_password(SERVICE, self.CANARY) == token
            self._keyring.delete_password(SERVICE, self.CANARY)
            return ok
        except Exception:
            return False

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


def store_path():
    """Location of the shared file store (same for the CLI and the desktop app)."""
    from core import paths
    return paths.data_home() / STORE_FILE


def _derive_fernet(passphrase, salt):
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERATIONS)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8"))))


def _chown_to_sudo_user(path):
    """Under sudo the file lives in the invoking user's home: hand it back."""
    sudo_user = os.environ.get("SUDO_USER")
    if not (hasattr(os, "geteuid") and os.geteuid() == 0 and sudo_user and sudo_user != "root"):
        return
    try:
        import pwd
        account = pwd.getpwnam(sudo_user)
        os.chown(path, account.pw_uid, account.pw_gid)
    except Exception:
        pass


class _FileBackend:
    """0600 file under data_home(); encrypted when `cryptography` is present.

    Opt-in: `available` is False until the file exists or the user enabled the
    store this session, so the interfaces can offer it rather than silently
    writing secrets to disk.
    """

    def __init__(self, path=None):
        self.path = Path(path) if path else store_path()
        self._enabled = self.path.exists()
        self._passphrase = None      # cached for this process only
        self._declined = False       # user cancelled the unlock prompt this session
        self._cache = None           # decrypted {id: value} once read

    @property
    def available(self):
        return self._enabled

    def enable(self, passphrase=None):
        """Create the store: encrypted when a passphrase is given, plain otherwise."""
        if self.path.exists():
            self._enabled = True
            return self.mode
        if passphrase and not encryption_available():
            raise RuntimeError("cryptography is not installed; cannot encrypt the key file")
        self._passphrase = passphrase or None
        self._enabled = True
        self._cache = {}
        self._write({})
        return self.mode

    def _header(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @property
    def mode(self):
        """"fernet" or "plain" for an existing or freshly enabled store."""
        if self.path.exists():
            return self._header().get("mode", "plain")
        return "fernet" if self._passphrase else "plain"

    @property
    def locked(self):
        return self.mode == "fernet" and self._passphrase is None

    def _unlock(self):
        if self.mode != "fernet":
            return True
        if self._passphrase or self._declined:
            return self._passphrase is not None
        if _passphrase_prompt is None:
            return False
        answer = _passphrase_prompt("unlock")
        if not answer:
            self._declined = True
            return False
        header = self._header()
        try:
            self._read_payload(header, answer)
        except Exception:
            return False
        self._passphrase = answer
        return True

    def unlock(self, passphrase):
        """Try a passphrase on an encrypted store; True on success."""
        if self.mode != "fernet":
            return True
        try:
            self._read_payload(self._header(), passphrase)
        except Exception:
            return False
        self._passphrase, self._declined, self._cache = passphrase, False, None
        return True

    def _read_payload(self, header, passphrase):
        if header.get("mode") == "fernet":
            salt = base64.b64decode(header["salt"])
            token = header["payload"].encode("ascii")
            return json.loads(_derive_fernet(passphrase, salt).decrypt(token).decode("utf-8"))
        return {key: base64.b64decode(value).decode("utf-8")
                for key, value in header.get("keys", {}).items()}

    def _read(self):
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            return {}
        if not self._unlock():
            return {}
        try:
            self._cache = self._read_payload(self._header(), self._passphrase)
        except Exception:
            self._cache = {}
        return self._cache

    def _write(self, values):
        if self._passphrase:
            salt = secrets.token_bytes(16)
            token = _derive_fernet(self._passphrase, salt).encrypt(json.dumps(values).encode("utf-8"))
            document = {"version": 1, "mode": "fernet", "kdf": "pbkdf2-hmac-sha256",
                        "iterations": PBKDF2_ITERATIONS, "salt": base64.b64encode(salt).decode("ascii"),
                        "payload": token.decode("ascii")}
        else:
            document = {"version": 1, "mode": "plain",
                        "keys": {key: base64.b64encode(value.encode("utf-8")).decode("ascii")
                                 for key, value in values.items()}}
        from core import paths
        directory = self.path.parent
        paths.ensure_directory(directory)
        try:
            os.chmod(directory, stat.S_IRWXU)
        except OSError:
            pass
        temp = self.path.with_name(self.path.name + ".tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(document, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp, stat.S_IRUSR | stat.S_IWUSR)
            _chown_to_sudo_user(temp)
            os.replace(temp, self.path)
        except BaseException:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise
        self._cache = dict(values)

    def get(self, key_id):
        return self._read().get(key_id)

    def set(self, key_id, value):
        if self.locked and not self._unlock():
            raise RuntimeError("encrypted key file is locked")
        values = dict(self._read())
        values[key_id] = value
        self._write(values)

    def delete(self, key_id):
        if self.locked and not self._unlock():
            raise RuntimeError("encrypted key file is locked")
        values = dict(self._read())
        if values.pop(key_id, None) is not None:
            self._write(values)


def _resolve_backend():
    global _backend
    if _backend is None:
        try:
            import keyring
            candidate = _KeyringBackend(keyring)
            _backend = candidate if candidate.available else _FileBackend()
        except Exception:
            _backend = _FileBackend()
    return _backend


def set_backend(backend):
    """Install a backend (tests) and clear any session fallback."""
    global _backend
    _backend = backend
    _SESSION.clear()


def secure_storage_available():
    """True when keys live in the operating system's secret store."""
    return isinstance(_resolve_backend(), _KeyringBackend) and _resolve_backend().available


def persistent_storage_available():
    """True when keys persist across launches (OS store or enabled file store)."""
    return bool(getattr(_resolve_backend(), "available", False))


def file_store_offerable():
    """True when no OS store exists and the file store has not been enabled yet."""
    backend = _resolve_backend()
    return isinstance(backend, _FileBackend) and not backend.available


def enable_file_store(passphrase=None):
    """Opt in to the file store. Returns "fernet" or "plain"; moves session keys into it."""
    backend = _resolve_backend()
    if not isinstance(backend, _FileBackend):
        raise RuntimeError("an OS secret store is in use")
    mode = backend.enable(passphrase)
    for key_id, value in list(_SESSION.items()):
        backend.set(key_id, value)
    _SESSION.clear()
    return mode


def unlock_file_store(passphrase):
    """Unlock an encrypted file store for this session; True on success."""
    backend = _resolve_backend()
    return isinstance(backend, _FileBackend) and backend.unlock(passphrase)


def storage_status():
    """Describe the store in use so the interfaces can state the real guarantee."""
    backend = _resolve_backend()
    can_encrypt = encryption_available()
    if isinstance(backend, _FileBackend):
        if not backend.available:
            return StorageStatus("session", str(backend.path), False, can_encrypt)
        if backend.mode == "fernet":
            return StorageStatus("file-encrypted", str(backend.path), backend.locked, can_encrypt)
        return StorageStatus("file-plain", str(backend.path), False, can_encrypt)
    if getattr(backend, "available", False):
        return StorageStatus("keyring", None, False, can_encrypt)
    return StorageStatus("session", None, False, can_encrypt)


def _demote():
    """A store that passed the probe failed later (locked, D-Bus gone…): drop to
    the file store, which itself degrades to the session dict when not enabled."""
    global _backend
    if isinstance(_backend, _FileBackend):
        return _backend
    _backend = _FileBackend()
    return _backend


def get(key_id):
    """Return the stored value for a key id, or None."""
    if key_id not in SPEC_BY_ID:
        return None
    backend = _resolve_backend()
    if backend.available:
        try:
            value = backend.get(key_id)
        except Exception:
            value = None
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _SESSION.get(key_id)


def set_key(key_id, value):
    """Store or, when the value is blank, clear a single key.

    Returns True when the value will persist across launches, False when it was
    only kept for this process because no persistent store is in use. A store
    that errors (locked keyring, unreachable Secret Service, unwritable file)
    never raises: the key falls back to the file store, then to this session.
    """
    if key_id not in SPEC_BY_ID:
        raise KeyError(key_id)
    value = (value or "").strip()
    backend = _resolve_backend()
    for _ in range(2):
        if not backend.available:
            break
        try:
            if value:
                backend.set(key_id, value)
            else:
                backend.delete(key_id)
            _SESSION.pop(key_id, None)
            return True
        except Exception:
            backend = _demote()
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
