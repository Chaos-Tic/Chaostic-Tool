"""Lightweight, failure-safe file logging for the CLI.

A single rotating log file under the user's data directory captures diagnostic
exceptions that the interface would otherwise swallow silently (install,
privilege and chown paths). It records only diagnostics raised by the tool
itself, never tool output or secrets.

Design constraints:
- idempotent: :func:`setup_logging` configures the handler at most once;
- non-fatal: if the log file cannot be opened (for example a read-only or
  missing sudo home), logging degrades to a no-op and the CLI keeps running;
- quiet by default: WARNING level unless ``CHAOSTIC_LOG_LEVEL`` overrides it.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.paths import data_home, ensure_directory

#: Root logger namespace. Every module logs through ``logging.getLogger(__name__)``
#: (``core.*``), so a single handler on this parent captures them all.
ROOT_LOGGER = "core"
LOG_FILENAME = "chaostictool.log"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3
_DEFAULT_LEVEL = logging.WARNING
_ENV_LEVEL = "CHAOSTIC_LOG_LEVEL"

_configured = False


def _resolve_level(level: int | None) -> int:
    """Pick the effective level: explicit arg, then env var, then the default."""
    if level is not None:
        return level
    raw = os.environ.get(_ENV_LEVEL, "").strip().upper()
    if not raw:
        return _DEFAULT_LEVEL
    named = logging.getLevelName(raw)
    return named if isinstance(named, int) else _DEFAULT_LEVEL


def log_path() -> Path:
    """Absolute path of the active CLI log file (may not exist yet)."""
    return data_home() / "logs" / LOG_FILENAME


def setup_logging(level: int | None = None) -> bool:
    """Attach a rotating file handler to the ``core`` logger exactly once.

    Returns True when the file handler is active, False when logging had to
    degrade to a no-op (unwritable log location). Safe to call repeatedly.
    """
    global _configured
    logger = logging.getLogger(ROOT_LOGGER)
    if _configured:
        return any(isinstance(h, RotatingFileHandler) for h in logger.handlers)

    _configured = True
    logger.setLevel(_resolve_level(level))
    # Keep diagnostics out of the Rich UI on stderr: do not propagate to root.
    logger.propagate = False

    try:
        path = log_path()
        ensure_directory(path.parent)
        handler: logging.Handler = RotatingFileHandler(
            path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
    except (OSError, ValueError):
        # A read-only or missing home (e.g. an unresolved sudo user) must never
        # take the tool down: swallow the setup failure and keep logging inert.
        logger.addHandler(logging.NullHandler())
        return False

    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    return True
