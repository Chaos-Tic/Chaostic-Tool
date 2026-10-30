"""Single source of truth for the runtime install manifest.

The manifest at ``/var/lib/chaostictool/manifest`` records *exactly* what
ChaosticTool installed on the host, one ``type:value`` line per artifact, so
``uninstall.sh`` can reverse precisely those changes and nothing else. This is
the record-what-you-install contract the uninstaller depends on.

Historically the path was only exported by ``install.sh`` (via the
``CHAOSTICTOOL_MANIFEST`` environment variable), so installs triggered from the
TUI/CLI (``sudo chaostictool`` -> readiness scan -> "Install missing tools now?")
recorded nothing and could not be undone. This module gives the path a single
definition shared by ``core.installer`` and ``install.sh``: the environment
variable still wins when set, otherwise a root process falls back to the system
default. An unprivileged process has no system manifest and simply records
nothing (it cannot install system-wide anyway).
"""
from __future__ import annotations

import datetime
import logging
import os
from pathlib import Path

LOG = logging.getLogger(__name__)

#: System manifest directory (root-owned, created ``0700``).
MANIFEST_DIR = "/var/lib/chaostictool"
#: Default system manifest file inside :data:`MANIFEST_DIR`.
DEFAULT_MANIFEST = os.path.join(MANIFEST_DIR, "manifest")

_ENV_VAR = "CHAOSTICTOOL_MANIFEST"


def _is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def resolve_path() -> str | None:
    """Return the manifest path to record into, or ``None`` to record nothing.

    Resolution order, so one invariant holds everywhere: the environment
    variable (set by ``install.sh``) wins, otherwise a root process uses the
    system default. A non-root process returns ``None`` — it has no writable
    system manifest and performs no system-wide install.
    """
    env = os.environ.get(_ENV_VAR, "")
    if env:
        return env
    if _is_root():
        return DEFAULT_MANIFEST
    return None


def _ensure_parent(path: str) -> None:
    """Create the manifest directory. The system manifest stays root-owned 0700."""
    parent = os.path.dirname(path) or "."
    if parent == MANIFEST_DIR:
        os.makedirs(parent, mode=0o700, exist_ok=True)
    else:
        os.makedirs(parent, exist_ok=True)


def _write_header(path: str, source: str) -> None:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("# ChaosticTool manifest\n")
        handle.write(f"# date={stamp} source={source}\n")


def record(entry: str, *, source: str = "cli") -> None:
    """Append ``entry`` to the active manifest, creating it on first use.

    Silently does nothing when there is no manifest to write to (unprivileged
    process with no ``CHAOSTICTOOL_MANIFEST``). Failures are logged, never
    fatal: a recording error must not abort an install.
    """
    path = resolve_path()
    if not path:
        return
    try:
        first_use = not os.path.exists(path)
        _ensure_parent(path)
        if first_use:
            _write_header(path, source)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(entry + "\n")
    except OSError:
        LOG.warning("Could not record install manifest entry %r to %s",
                    entry, path, exc_info=True)


def records(path: str | None = None) -> list[str]:
    """Return the manifest's payload lines (comments and blanks stripped)."""
    target = path or resolve_path()
    if not target or not os.path.exists(target):
        return []
    try:
        with open(target, encoding="utf-8") as handle:
            return [line.strip() for line in handle
                    if line.strip() and not line.lstrip().startswith("#")]
    except OSError:
        LOG.warning("Could not read install manifest at %s", target, exc_info=True)
        return []


def has_record(entry: str, path: str | None = None) -> bool:
    """Whether ``entry`` is already recorded in the manifest."""
    return entry in records(path)


def manifest_file() -> Path | None:
    """The resolved manifest path as a :class:`~pathlib.Path`, if any."""
    resolved = resolve_path()
    return Path(resolved) if resolved else None
