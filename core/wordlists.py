import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

from rich import box
from rich.markup import escape
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table
from rich.text import Text

from core import ui

WORDLIST_URLS: dict[str, str] = {
    "/usr/share/wordlists/dirb/common.txt":
        "https://raw.githubusercontent.com/v0re/dirb/master/wordlists/common.txt",
    "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt":
        "https://raw.githubusercontent.com/daviddias/node-dirbuster/master/lists/directory-list-2.3-medium.txt",
    "/usr/share/wordlists/dirbuster/directory-list-2.3-big.txt":
        "https://raw.githubusercontent.com/daviddias/node-dirbuster/master/lists/directory-list-2.3-big.txt",
    "/usr/share/wordlists/rockyou.txt":
        "https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt",
    "/usr/share/seclists/Discovery/Web-Content/raft-large-words.txt":
        "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/raft-large-words.txt",
    "/usr/share/seclists/Passwords/rockyou.txt":
        "https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt",
}

ESTIMATED_SIZES: dict[str, str] = {
    "/usr/share/wordlists/dirb/common.txt": "36 KB",
    "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt": "1.8 MB",
    "/usr/share/wordlists/dirbuster/directory-list-2.3-big.txt": "6.4 MB",
    "/usr/share/wordlists/rockyou.txt": "133 MB",
    "/usr/share/seclists/Discovery/Web-Content/raft-large-words.txt": "3.5 MB",
    "/usr/share/seclists/Passwords/rockyou.txt": "133 MB",
}

_PKG_CMDS: dict[str, list[str]] = {
    "apt-get": ["apt-get", "install", "-y", "wordlists", "seclists"],
    "pacman":  ["pacman", "-S", "--noconfirm", "wordlists"],
    "dnf":     ["dnf", "install", "-y", "wordlists"],
}


def _detect_pkg_manager() -> str | None:
    for mgr in ("apt-get", "pacman", "dnf"):
        if shutil.which(mgr):
            return mgr
    return None


def try_package_manager(path: str) -> bool:
    """Attempt distro package install. Return True if path exists afterwards."""
    mgr = _detect_pkg_manager()
    if not mgr:
        return False
    ui.console.print(f"[brand.muted][*] Trying {mgr} install of wordlists package...[/brand.muted]")
    try:
        subprocess.run(_PKG_CMDS[mgr], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        return False
    return os.path.exists(path)


def download_wordlist(path: str) -> bool:
    """Download a single wordlist from its URL to path. Returns True on success."""
    url = WORDLIST_URLS.get(path)
    if not url:
        ui.console.print(f"[bright_red][!] No download URL registered for {escape(path)}[/bright_red]")
        return False

    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    ui.console.print(f"[brand.muted][*] Downloading {escape(dest.name)}...[/brand.muted]")
    try:
        with Progress(
            TextColumn("[brand.muted]{task.description}[/brand.muted]"),
            BarColumn(bar_width=30),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=ui.console,
        ) as progress:
            task_id = progress.add_task(dest.name, total=None)

            def _hook(count: int, block_size: int, total_size: int) -> None:
                if total_size > 0:
                    progress.update(task_id, total=total_size, completed=count * block_size)
                else:
                    progress.update(task_id, advance=block_size)

            urllib.request.urlretrieve(url, dest, _hook)

        ui.console.print(f"[brand.ok][+] {escape(dest.name)} ready.[/brand.ok]")
        return True
    except Exception as exc:
        ui.console.print(f"[bright_red][!] Download failed: {exc}[/bright_red]")
        if dest.exists():
            dest.unlink()
        return False


def wordlist_menu() -> None:
    """Interactive wordlist manager: shows status and downloads missing ones."""
    while True:
        ui.header("Wordlist Manager")

        table = Table(box=box.SIMPLE_HEAVY, border_style="brand.red", expand=True, pad_edge=True)
        table.add_column("KEY", justify="center", width=5)
        table.add_column("PATH", style="brand.white", ratio=1)
        table.add_column("PROFILE", style="brand.muted", no_wrap=True)
        table.add_column("SIZE", style="brand.muted", no_wrap=True)
        table.add_column("STATUS", justify="right", no_wrap=True)

        missing: dict[str, str] = {}
        idx = 1
        for path, desc in ui.WORDLISTS:
            exists = os.path.exists(path)
            size = ESTIMATED_SIZES.get(path, "?")
            if exists:
                table.add_row(
                    Text(" - ", style="bold brand.muted"),
                    escape(path), desc, size,
                    "[brand.ok]READY[/brand.ok]",
                )
            else:
                table.add_row(
                    Text(f" {idx} ", style="bold brand.warn"),
                    f"[bright_red]{escape(path)}[/bright_red]", desc, size,
                    "[bright_red]MISSING[/bright_red]",
                )
                missing[str(idx)] = path
                idx += 1

        ui.console.print(table)

        if not missing:
            ui.console.print("[brand.ok][+] All wordlists are present.[/brand.ok]")
            ui.pause()
            return

        ui.console.print(
            "\n[brand.muted]Enter numbers (space-separated), [/brand.muted]"
            "[brand.red]all[/brand.red][brand.muted] to download all missing, or [/brand.muted]"
            "[brand.red]r[/brand.red][brand.muted] to cancel.[/brand.muted]"
        )
        raw = ui.console.input("[brand.red]WORDLISTS[/brand.red] [brand.white]›[/brand.white] ").strip().lower()

        if raw in ui.BACK_KEYS:
            return

        targets = list(missing.values()) if raw == "all" else [
            missing[k] for k in raw.split() if k in missing
        ]
        if not targets:
            continue

        ui.console.print(f"\n[brand.warn]About to download {len(targets)} wordlist(s). Continue? [Y/n][/brand.warn]")
        if ui.console.input("[brand.white]›[/brand.white] ").strip().lower() in ("n", "no", "non"):
            continue

        for path in targets:
            if not try_package_manager(path):
                download_wordlist(path)
