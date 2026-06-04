import os
import pwd
import re
import shlex
import signal
import subprocess
from pathlib import Path
from datetime import datetime

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

THEME = Theme(
    {
        "brand.red": "bold #ff3131",
        "brand.red_soft": "#ff6b6b",
        "brand.warn": "bold #ffb84d",
        "brand.ok": "bold #31ff83",
        "brand.info": "bold #67e8f9",
        "brand.muted": "#a98c91",
        "brand.white": "bold #f8fafc",
        "brand.command": "#ffb4b4",
    }
)

console = Console(theme=THEME)
ACTIVE_PROCS = []


def _build_env():
    """Return a copy of os.environ with HOME/USER set to the invoking user.
    Under sudo, the default HOME=/root breaks pip --user installed tools."""
    env = os.environ.copy()
    sudo_user = env.get("SUDO_USER")
    if sudo_user and sudo_user != "root":
        try:
            pw = pwd.getpwnam(sudo_user)
            env["HOME"] = pw.pw_dir
            env["USER"] = sudo_user
            env["LOGNAME"] = sudo_user
            # Prepend the user's local bin dirs so pipx/pip tools are found
            local_bins = ":".join([
                f"{pw.pw_dir}/.local/bin",
                f"{pw.pw_dir}/go/bin",
                f"{pw.pw_dir}/.local/share/go/bin",
                f"{pw.pw_dir}/.cargo/bin",
            ])
            env["PATH"] = local_bins + ":" + env.get("PATH", "")
        except Exception:
            pass
    return env


def timestamped_path(directory, basename, ext="txt"):
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    return Path(directory) / f"{basename}_{stamp}.{ext}"


def target_path(directory, basename, target_name, ext="txt"):
    """Returns path: directory/basename_targetname.ext"""
    safe = re.sub(r'[^\w.\-]', '_', target_name) if target_name else "unknown"
    return Path(directory) / f"{basename}_{safe}.{ext}"


def _print_command_panel(cmd, output_path, interactive):
    body = Table.grid(expand=True)
    body.add_column(ratio=1)
    body.add_row(
        f"[brand.muted]MODE[/brand.muted] "
        f"[brand.info]{'interactive' if interactive else 'captured'}[/brand.info]    "
        f"[brand.muted]OUTPUT[/brand.muted] "
        f"[brand.command]{escape(str(output_path or 'not saved'))}[/brand.command]"
    )
    body.add_row(Text(shlex.join(cmd), style="brand.command", overflow="fold"))
    console.print(
        Panel(
            body,
            title="[brand.red] EXECUTION [/brand.red]",
            border_style="brand.red",
            box=box.HEAVY,
            padding=(1, 2),
        )
    )


def _result_panel(rc, output_path, saved):
    style = "brand.ok" if rc == 0 else "bright_red"
    result = "SUCCESS" if rc == 0 else "NON-ZERO EXIT"
    save_state = str(output_path) if saved else "no captured output saved"
    table = Table.grid(expand=True)
    table.add_column(ratio=1)
    table.add_column(ratio=1)
    table.add_row(
        f"[brand.muted]RESULT[/brand.muted]\n[{style}]{result}[/{style}]",
        f"[brand.muted]EXIT CODE[/brand.muted]\n[{style}]{rc}[/{style}]",
    )
    table.add_row(
        f"[brand.muted]SAVED[/brand.muted]\n[brand.command]{escape(save_state)}[/brand.command]",
        "[brand.muted]CONTROL[/brand.muted]\n[brand.red]Ctrl+C armed[/brand.red]",
    )
    return Panel(
        table,
        title="[brand.red] RUN SUMMARY [/brand.red]",
        border_style=style,
        box=box.HEAVY,
        padding=(1, 2),
    )


def run_tool(cmd, output_path=None, interactive=False):
    _print_command_panel(cmd, output_path, interactive)

    if interactive:
        proc = None
        try:
            console.print("[brand.info]Interactive terminal attached. Return here when the tool exits.[/brand.info]")
            proc = subprocess.Popen(cmd, start_new_session=True, env=_build_env())
            ACTIVE_PROCS.append(proc)
            rc = proc.wait()
        except FileNotFoundError:
            console.print(f"[bright_red][!] Binary not found: {cmd[0]}[/bright_red]")
            return 127
        except KeyboardInterrupt:
            _stop_process(proc)
            console.print("\n[bright_yellow][!] Tool interrupted with Ctrl+C.[/bright_yellow]")
            return 130
        finally:
            _forget_process(proc)
        console.print(_result_panel(rc, output_path, False))
        return rc

    lines = []
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
            env=_build_env(),
        )
        ACTIVE_PROCS.append(proc)
    except FileNotFoundError:
        console.print(f"[bright_red][!] Binary not found: {cmd[0]}[/bright_red]")
        return 127

    try:
        progress = Progress(
            SpinnerColumn("dots"),
            TextColumn("[brand.red]EXECUTING[/brand.red]"),
            BarColumn(bar_width=None, pulse_style="brand.red_soft"),
            TimeElapsedColumn(),
            TextColumn("[brand.muted]Ctrl+C to stop[/brand.muted]"),
            console=console,
            transient=True,
            refresh_per_second=12,
        )
        with progress:
            task_id = progress.add_task("running", total=None)
            buf = ""
            for chunk in iter(lambda: proc.stdout.read(256), ""):
                buf += chunk
                # flush on newline or carriage-return (hashcat/john/nmap status lines)
                while "\n" in buf or "\r" in buf:
                    for sep in ("\n", "\r"):
                        if sep in buf:
                            part, buf = buf.split(sep, 1)
                            line = part + sep
                            progress.console.print(Text.from_ansi(part), end="\n" if sep == "\n" else "\r")
                            lines.append(line)
                            progress.advance(task_id, 1)
                            break
        proc.wait()
    except KeyboardInterrupt:
        _stop_process(proc)
        console.print("\n[bright_yellow][!] Tool interrupted (Ctrl+C). Partial results saved if any.[/bright_yellow]")

    saved = False
    if output_path and lines:
        Path(output_path).write_text("".join(lines))
        _chown_to_sudo_user(output_path)
        saved = True

    rc = proc.returncode if proc.returncode is not None else 130
    console.print(_result_panel(rc, output_path, saved))
    _forget_process(proc)
    return rc


def cleanup_processes():
    for proc in list(ACTIVE_PROCS):
        if proc.poll() is None:
            _stop_process(proc)
        _forget_process(proc)


def _forget_process(proc):
    try:
        ACTIVE_PROCS.remove(proc)
    except ValueError:
        pass


def _stop_process(proc):
    if proc is None:
        return
    try:
        os.killpg(proc.pid, signal.SIGINT)
        proc.wait(timeout=3)
    except Exception:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            proc.terminate()


def _chown_to_sudo_user(path):
    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user or sudo_user == "root":
        return
    try:
        pw = pwd.getpwnam(sudo_user)
        os.chown(path, pw.pw_uid, pw.pw_gid)
    except Exception:
        return
