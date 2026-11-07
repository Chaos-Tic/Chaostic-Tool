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
import uuid
from pathlib import Path
from typing import IO

# Absent on Windows; 0 is a no-op flag, so open() there is a plain open (Windows
# has no POSIX symlink-following semantics for these paths — see module docstring).
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
# A race-free descent needs dir_fd support on each syscall plus both flags; where
# that holds (Linux/macOS) the parent directory is *held by fd* across the whole
# write so no symlink swapped in after a name check can be followed (CWE-367).
_DIRFD_SAFE = (bool(_O_NOFOLLOW) and bool(_O_DIRECTORY)
               and {os.open, os.mkdir, os.replace, os.unlink} <= os.supports_dir_fd)


def results_root(path: Path | str):
    """The results root ``path`` lives under, for use as ``within`` — or ``None``.

    Callers pass this so a file saved *inside* the per-target results tree is
    guarded against symlinked components, while a file saved to an explicit
    user-chosen path is written as given. Centralised here so no writer forgets
    the guard (and so the rule lives in one place)."""
    from core import target
    try:
        root = target.TARGETS_ROOT
        # A ``..`` anywhere stays guarded (never fail-open to within=None): the
        # dir_fd descent then refuses it rather than let abspath collapse it to a
        # different, possibly-outside file.
        if ".." in Path(path).parts:
            return root
        # Normalise relative segments (abspath, NOT resolve — we must not chase
        # symlinks here, that is the guard's job) before the lexical test so a
        # non-canonical path under the tree cannot slip past as "outside".
        if Path(os.path.abspath(path)).is_relative_to(Path(os.path.abspath(root))):
            return root
        return None
    except (ValueError, OSError):
        return None


def reject_symlinked_parent(within: Path | str, path: Path | str) -> None:
    """Refuse ``path`` when a *parent directory* under ``within`` is a symlink.

    ``within`` is a directory the application owns and created. Every component
    between it and ``path``'s parent must be a real directory (no symlink or
    junction), and the resolved parent must stay inside the resolved root — so a
    symlinked parent cannot redirect the write outside the tree under ``sudo``
    (CWE-59). The *final* component is not checked here: ``atomic_write`` replaces
    it with ``os.replace`` (which never follows it), while ``open_nofollow``
    refuses a symlinked final component via ``O_NOFOLLOW``. Mirrors
    ``desktop.storage.Store._check_history_tree``; raises ``OSError`` on refusal.

    This name-based check is the fallback for platforms without race-free
    ``dir_fd`` descent (Windows); where ``_DIRFD_SAFE`` holds, ``_atomic`` instead
    holds each directory by fd so no post-check swap can be followed."""
    root = Path(within)
    if root.is_symlink():
        raise OSError(f"refusing to write under a symlinked root: {root}")
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


def _descend(root: Path, parts: tuple, *, create: bool) -> int:
    """Return an fd for the final parent directory, opening the trusted ``root``
    and then each component with ``O_DIRECTORY | O_NOFOLLOW`` relative to the
    previous fd. Because the directory is held *by descriptor*, a symlink swapped
    into the path after any name check cannot be followed (CWE-367). A symlinked
    ``root`` or component is refused (``O_NOFOLLOW`` → ``OSError``). With
    ``create`` the missing components are made one at a time, never through a
    symlink. The caller closes the returned fd."""
    root = Path(root)
    if create:
        root.mkdir(parents=True, exist_ok=True)  # the app-owned root itself
    flags = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW
    fd = os.open(root, flags)  # O_NOFOLLOW: refuses a symlinked root
    try:
        for part in parts:
            if part in ("..", "."):
                # A ``..`` component would walk the held fd back out of the tree,
                # defeating the descent; refuse it (callers never emit one).
                raise OSError(f"refusing a '{part}' component in a guarded write path")
            if create:
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            nxt = os.open(part, flags, dir_fd=fd)  # O_NOFOLLOW: refuses a symlinked component
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def _atomic_dirfd(path: Path, within: Path | str, writer) -> Path:
    """Race-free ``_atomic``: hold the parent dir by fd, create+rename the temp
    relative to it (``O_EXCL | O_NOFOLLOW``, ``os.replace`` with ``*_dir_fd``)."""
    try:
        parts = path.parent.relative_to(Path(within)).parts
    except ValueError as exc:
        raise OSError(f"write path escapes its root: {path}") from exc
    parent_fd = _descend(Path(within), parts, create=True)
    try:
        tmp = f".{path.name}.{uuid.uuid4().hex}.tmp"
        # 0o600, matching tempfile.mkstemp in the fallback: result files can hold
        # recon data and must not be world-readable (CWE-732). The owner is the
        # sudo-invoking user (callers chown as they already did).
        tfd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        try:
            writer(tfd)  # takes ownership of tfd and closes it
            os.replace(tmp, path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        except BaseException:
            try:
                os.unlink(tmp, dir_fd=parent_fd)
            except OSError:
                pass
            raise
    finally:
        os.close(parent_fd)
    return path


def _atomic(path: Path, within: Path | str | None, writer) -> Path:
    """Shared symlink-safe atomic core; ``writer(fd)`` fills (and closes) a temp.

    With a ``within`` root and ``dir_fd`` support, the parent is held by fd for
    the whole write (race-free). Otherwise — a user-chosen path (``within`` None)
    or a platform without ``dir_fd``/``O_NOFOLLOW`` (Windows) — the check runs
    *before* anything is created and the temp is replaced onto the name
    (``os.replace`` never follows a final symlink)."""
    if within is not None and _DIRFD_SAFE:
        return _atomic_dirfd(path, within, writer)
    if within is not None:
        reject_symlinked_parent(within, path)  # before creating anything
    path.parent.mkdir(parents=True, exist_ok=True)
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
    if within is not None:
        reject_symlinked_parent(within, path)  # before creating anything
    path.parent.mkdir(parents=True, exist_ok=True)
    binary = "b" in mode
    append = "a" in mode
    flags = os.O_WRONLY | os.O_CREAT | _O_NOFOLLOW
    flags |= os.O_APPEND if append else os.O_TRUNC
    fd = os.open(path, flags, 0o644)
    return os.fdopen(fd, mode, buffering=buffering,
                     encoding=None if binary else encoding)
