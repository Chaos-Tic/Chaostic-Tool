"""Symlink-safe, atomic writes for files ChaosticTool creates in a results tree.

The CLI usually runs under ``sudo`` (root) while its results land in a directory
owned by the invoking user. A tool output, mission report, scope cache or export
whose destination — or any parent directory component — is a planted symlink
would otherwise let an unprivileged user redirect a *root* write outside the
tree (CWE-59), with a check-then-write race (CWE-367). This module is the single
place result writers go through so that guarantee holds everywhere instead of
being reimplemented per call site.

Two shapes are offered:

* ``atomic_write`` / ``atomic_copyfileobj`` — the content is written to a fresh
  temp file in the destination directory and then ``os.replace``'d onto the
  name. ``os.replace`` replaces a pre-existing symlink at the destination rather
  than following it, and the write is atomic (no reader ever sees a half-file).
  Use it for one-shot writes (reports, caches, exports, a finished tool output).
* ``open_nofollow`` — opens the destination with ``O_NOFOLLOW`` so a symlinked
  final component is refused rather than followed, for a streaming/live-tailed
  writer that cannot use an atomic replace.

Both refuse a symlinked *parent* component when a ``within`` root (a directory
the application owns and created) is supplied, walking it the same way
``desktop.storage.Store._check_history_tree`` does. Pure stdlib; cross-platform
(``O_NOFOLLOW`` is absent on Windows, where it degrades to a plain open, and
``os.replace`` stays atomic there too).
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import IO

# Absent on Windows; 0 is a no-op flag, so open() there is a plain open (Windows
# has no POSIX symlink-following semantics for these paths — see module docstring).
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def reject_symlinked_parent(within: Path | str, path: Path | str) -> None:
    """Refuse ``path`` when a *parent directory* under ``within`` is a symlink.

    ``within`` is a directory the application owns and created. Every component
    between it and ``path``'s parent must be a real directory (no symlink or
    junction), and the resolved parent must stay inside the resolved root — so a
    symlinked parent cannot redirect the write outside the tree under ``sudo``
    (CWE-59). The *final* component is not checked here: ``atomic_write`` replaces
    it with ``os.replace`` (which never follows it), while ``open_nofollow``
    refuses a symlinked final component via ``O_NOFOLLOW``. Mirrors
    ``desktop.storage.Store._check_history_tree``; raises ``OSError`` on refusal."""
    root = Path(within)
    parent = Path(path).parent
    try:
        parts = parent.relative_to(root).parts
    except ValueError as exc:
        raise OSError(f"write path escapes its root: {path}") from exc
    current = root
    for part in parts:
        current = current / part
        is_junction = getattr(current, "is_junction", None)
        if current.is_symlink() or (callable(is_junction) and is_junction()):
            raise OSError(f"refusing to write through a symlinked directory: {current}")
    if parent.exists() and parent.resolve() != root.resolve().joinpath(*parts):
        raise OSError(f"write parent resolves outside its root: {parent}")


def _atomic(path: Path, within: Path | str | None, writer) -> Path:
    """Shared temp-file + ``os.replace`` core; ``writer(fd)`` fills the temp."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if within is not None:
        reject_symlinked_parent(within, path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        writer(fd)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def atomic_write(path: Path | str, data: str | bytes, *,
                 within: Path | str | None = None, encoding: str = "utf-8") -> Path:
    """Atomically, symlink-safely write ``data`` (str or bytes) to ``path``."""
    path = Path(path)
    if not isinstance(data, (bytes, bytearray)):
        data = data.encode(encoding)

    def writer(fd: int) -> None:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)

    return _atomic(path, within, writer)


def atomic_copyfileobj(src: IO, path: Path | str, *,
                       within: Path | str | None = None, text: bool = False,
                       encoding: str = "utf-8", newline: str = "") -> Path:
    """Stream ``src`` (a readable file object) into ``path`` atomically and
    symlink-safely, without loading it all into memory. ``text=True`` copies a
    text source (preserving ``newline`` as-is); the default copies bytes."""
    path = Path(path)

    def writer(fd: int) -> None:
        if text:
            with os.fdopen(fd, "w", encoding=encoding, newline=newline) as stream:
                shutil.copyfileobj(src, stream)
        else:
            with os.fdopen(fd, "wb") as stream:
                shutil.copyfileobj(src, stream)

    return _atomic(path, within, writer)


def open_nofollow(path: Path | str, mode: str = "w", *,
                  within: Path | str | None = None, encoding: str | None = "utf-8",
                  buffering: int = -1):
    """Open ``path`` for writing without following a symlinked final component
    (``O_NOFOLLOW`` where supported), for a streaming/live-tailed writer that
    cannot use an atomic replace. ``mode`` is ``"w"``/``"a"`` (text) or
    ``"wb"``/``"ab"`` (binary). The parent is checked against ``within`` first.
    The caller owns the returned file object."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if within is not None:
        reject_symlinked_parent(within, path)
    binary = "b" in mode
    append = "a" in mode
    flags = os.O_WRONLY | os.O_CREAT | _O_NOFOLLOW
    flags |= os.O_APPEND if append else os.O_TRUNC
    fd = os.open(path, flags, 0o644)
    return os.fdopen(fd, mode, buffering=buffering,
                     encoding=None if binary else encoding)
