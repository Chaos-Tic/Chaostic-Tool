"""Writable CLI state, separate from system-managed application files."""
import os
try:
    import pwd
except ImportError:
    pwd = None
from pathlib import Path


def data_home() -> Path:
    """Use the invoking user's home under sudo; never root's inherited XDG path."""
    sudo_user = os.environ.get("SUDO_USER")
    if hasattr(os, "geteuid") and os.geteuid() == 0 and sudo_user and sudo_user != "root" and pwd is not None:
        home = Path(pwd.getpwnam(sudo_user).pw_dir)
        return home / ".local/share/chaostictool"
    override = os.environ.get("CHAOSTIC_CLI_HOME")
    if override:
        path = Path(override)
        if not path.is_absolute():
            raise ValueError("CHAOSTIC_CLI_HOME must be an absolute path")
        return path
    xdg = os.environ.get("XDG_DATA_HOME", "")
    base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".local/share"
    return base / "chaostictool"


def ensure_directory(path: Path) -> None:
    """Create writable state directories and give new ones back to the sudo user."""
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    path.mkdir(parents=True, exist_ok=True)
    sudo_user = os.environ.get("SUDO_USER")
    if hasattr(os, "geteuid") and os.geteuid() == 0 and sudo_user and sudo_user != "root" and pwd is not None and hasattr(os, "chown"):
        try:
            account = pwd.getpwnam(sudo_user)
            for directory in missing:
                os.chown(directory, account.pw_uid, account.pw_gid)
        except (KeyError, OSError):
            pass
