"""CLI update controls: checking is automatic, installation always needs consent."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import threading

from core import update_service
from core.paths import data_home, ensure_directory
from core.version import VERSION

_latest = {}


def enabled():
    if os.environ.get("CHAOSTIC_UPDATE_CHECK") == "0":
        return False
    try:
        return json.loads((data_home() / "cli-settings.json").read_text()).get("check_updates", True) is not False
    except (OSError, ValueError, AttributeError):
        return True


def _check(force=False):
    global _latest
    ensure_directory(data_home())
    _latest = update_service.check("cli", VERSION, data_home() / "update-check.json", force=force)
    from core.target import _chown_path
    _chown_path(data_home() / "update-check.json")
    return _latest


def start_background():
    def run():
        try:
            _check()
        except (OSError, KeyError):
            pass
    if enabled():
        threading.Thread(target=run, daemon=True, name="release-check").start()


def notice():
    return f"CLI {_latest['version']} available · u: updates" if _latest.get("available") else ""


def install(result):
    from core import ui
    if not result.get("available"):
        return False
    commands = update_service.native_commands("chaostictool", Path(__file__))
    if not commands:
        ui.console.print("Use the installer or source instructions for this installation:")
        ui.console.print(result["url"], markup=False)
        return False
    manager = commands[0][0]
    owner = os.environ.get("SUDO_USER")
    euid = getattr(os, "geteuid", lambda: -1)()
    if commands[0][0] in ("yay", "paru") and euid == 0:
        if not owner or owner == "root":
            ui.console.print("Run the AUR helper as your regular user to update this installation.")
            return False
        commands = [["sudo", "-H", "-u", owner, "--", *command] for command in commands]
    elif euid > 0:
        commands = [["sudo", *command] for command in commands]
    ui.console.print(f"Update CLI {VERSION} → {result['version']} using the installed package channel:")
    for command in commands:
        ui.console.print(shlex.join(command), markup=False)
    if ui.console.input("Run these commands? [y/N] ").strip().lower() not in ("y", "yes", "o", "oui"):
        return False
    for command in commands:
        if subprocess.run(command, check=False).returncode:
            ui.console.print("Update did not complete. The package manager output above gives the reason.")
            return False
    installed = update_service.installed_version("chaostictool", manager)
    if not installed or update_service.version_tuple(installed) < update_service.version_tuple(result["version"]):
        ui.console.print("The repository does not yet offer the requested version, or its installation could not be confirmed. Retry after repository synchronization.")
        return False
    ui.console.print("Package update completed. Restart ChaosticTool to load the installed version.")
    return True


def show(*, install_now=False):
    from core import ui
    ui.console.print("Checking the public GitHub release…")
    result = _check(force=True)
    if result.get("error"):
        ui.console.print("Could not verify updates. Try again later.")
    elif result["available"]:
        ui.console.print(f"CLI {result['version']} is available (installed: {VERSION}).")
    else:
        ui.console.print(f"CLI {VERSION} is up to date.")
    if install_now:
        return install(result)
    while True:
        ui.console.print(f"Automatic checks: {'on' if enabled() else 'off'} · once per day")
        action = ui.console.input("[i] Install update  [a] Toggle automatic checks  [r] Return: ").strip().lower()
        if action == "i":
            if install(result):
                return True
        elif action == "a":
            state = not enabled()
            ensure_directory(data_home())
            update_service._write_json(data_home() / "cli-settings.json", {"check_updates": state})
            from core.target import _chown_path
            _chown_path(data_home() / "cli-settings.json")
            if os.environ.get("CHAOSTIC_UPDATE_CHECK") == "0":
                ui.console.print("CHAOSTIC_UPDATE_CHECK=0 still disables automatic checks for this process.")
        else:
            return False
