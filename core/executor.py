import os
import codecs
import shutil
import tempfile
import threading
import time
from collections import deque
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

from core.theme import THEME, COLORS

console = Console(theme=THEME, style=f"{COLORS['text']} on {COLORS['bg']}")
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
        f"[brand.faint]MODE[/brand.faint] "
        f"[brand.info]{'interactive' if interactive else 'captured'}[/brand.info]    "
        f"[brand.faint]OUTPUT[/brand.faint] "
        f"[brand.command]{escape(str(output_path or 'not saved'))}[/brand.command]"
    )
    body.add_row(Text(shlex.join(cmd), style="brand.command", overflow="fold"))
    console.print(
        Panel(
            body,
            title="[brand.accent] EXECUTION [/brand.accent]",
            border_style="brand.dim",
            box=box.ROUNDED,
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
        f"[brand.faint]RESULT[/brand.faint]\n[{style}]{result}[/{style}]",
        f"[brand.faint]EXIT CODE[/brand.faint]\n[{style}]{rc}[/{style}]",
    )
    table.add_row(
        f"[brand.faint]SAVED[/brand.faint]\n[brand.command]{escape(save_state)}[/brand.command]",
        "[brand.faint]CONTROL[/brand.faint]\n[brand.accent]Ctrl+C armed[/brand.accent]",
    )
    return Panel(
        table,
        title="[brand.accent] RUN SUMMARY [/brand.accent]",
        border_style=style,
        box=box.ROUNDED,
        padding=(1, 2),
    )


class _Capture:
    """Bounded display state and a disk-backed complete output journal."""

    def __init__(self):
        self.lock = threading.Lock()
        self.done = threading.Event()
        self.aborted = threading.Event()
        self.visible = deque(maxlen=2000)
        self.fragment = ""
        self.started = time.monotonic()
        # Monotonic timestamp of completion, set once in _capture_worker's finally
        # block (just before self.done). Presentation reads this to FREEZE the
        # displayed elapsed time instead of recomputing time.monotonic()-started
        # on every refresh forever; None while the process is still running.
        self.finished = None
        self.proc = None
        self.rc = 127
        self.saved = False
        self.save_error = None
        self.journal = tempfile.TemporaryFile(mode="w+", encoding="utf-8", newline="")

    def append(self, text):
        self.journal.write(text)
        with self.lock:
            # A tool can emit a huge single line: retain only its display tail.
            pieces = re.split(r"[\r\n]", self.fragment + text)
            if len(pieces) > 1:
                self.visible.extend(part[-4096:] for part in pieces[:-1])
            self.fragment = pieces[-1][-4096:]
            if self.fragment:
                self.visible.append(self.fragment)
                self.fragment = ""


def _capture_worker(state, cmd, output_path, textual):
    try:
        state.proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True, env=_build_env(),
        )
        ACTIVE_PROCS.append(state.proc)
        if state.aborted.is_set():
            _stop_process(state.proc)
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        stream = state.proc.stdout
        read = getattr(stream, "read1", stream.read)
        while True:
            chunk = read(4096)
            if not chunk:
                break
            text = chunk if isinstance(chunk, str) else decoder.decode(chunk)
            state.append(text)
            if textual:
                console.print(Text.from_ansi(text), end="", soft_wrap=True)
        tail = decoder.decode(b"", final=True)
        if tail:
            state.append(tail)
            if textual:
                console.print(Text.from_ansi(tail), end="", soft_wrap=True)
        state.rc = state.proc.wait()
    except FileNotFoundError:
        state.append(f"Binary not found: {cmd[0]}\n")
        state.rc = 127
    except OSError as exc:
        state.append(f"Execution failed: {exc}\n")
        state.rc = 1
        _stop_process(state.proc)
    finally:
        if state.aborted.is_set():
            state.rc = 130
        try:
            if output_path and state.journal.tell():
                state.journal.seek(0)
                with Path(output_path).open("w", encoding="utf-8", newline="") as destination:
                    shutil.copyfileobj(state.journal, destination)
                _chown_to_sudo_user(output_path)
                state.saved = True
        except OSError as exc:
            state.save_error = str(exc)
        finally:
            if state.proc is not None and state.proc.stdout is not None:
                state.proc.stdout.close()
            _forget_process(state.proc)
            # Freeze the elapsed clock at the instant everything is finished
            # (process reaped + output saved) so the scan view can stop ticking.
            state.finished = time.monotonic()
            state.done.set()


def run_tool(cmd, output_path=None, interactive=False, context=None):
    """Run an argv command; TTY capture uses a fullscreen bounded live view.

    context accepts category/tool/preset/route labels and wait=False for flows.
    Redirected input/output never waits for a completion key.
    """
    context = dict(context or {})
    if interactive:
        # The menu application has already exited. Child input remains untouched.
        _print_command_panel(cmd, output_path, True)
        proc = None
        terminal = None
        try:
            import sys
            if sys.stdin.isatty():
                import termios
                terminal = (sys.stdin.fileno(), termios.tcgetattr(sys.stdin.fileno()))
            proc = subprocess.Popen(cmd, start_new_session=True, env=_build_env())
            ACTIVE_PROCS.append(proc)
            rc = proc.wait()
        except FileNotFoundError:
            console.print(f"[bright_red]Binary not found: {escape(cmd[0])}[/bright_red]")
            rc = 127
        except KeyboardInterrupt:
            _stop_process(proc)
            rc = 130
        except OSError as exc:
            console.print(Text(f"Execution failed: {exc}", style="bright_red"))
            _stop_process(proc)
            rc = 1
        finally:
            _forget_process(proc)
            if terminal is not None:
                import termios
                termios.tcsetattr(terminal[0], termios.TCSADRAIN, terminal[1])
        console.print(_result_panel(rc, output_path, False))
        return rc

    from core.scan_view import available, run_scan
    fullscreen = available()
    state = _Capture()
    worker = threading.Thread(target=_capture_worker, args=(state, cmd, output_path, not fullscreen), daemon=True)

    def abort():
        if not state.aborted.is_set():
            state.aborted.set()
            threading.Thread(target=_stop_process, args=(state.proc,), daemon=True).start()

    try:
        if fullscreen:
            run_scan(state, worker.start, abort, context, cmd, output_path)
        else:
            _print_command_panel(cmd, output_path, False)
            worker.start()
            while not state.done.wait(0.1):
                pass
    except (KeyboardInterrupt, EOFError):
        abort()
    finally:
        # A UI exception/closed terminal must never leave a child running.
        if worker.ident is not None:
            if not state.done.is_set():
                abort()
            worker.join(timeout=12)
        state.journal.close()
    if not fullscreen:
        if state.save_error:
            console.print(Text(f"Could not save output: {state.save_error}", style="bright_red"))
        console.print(_result_panel(state.rc, output_path, state.saved))
    return state.rc


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
    """Stop the child's session, escalating with bounded waits and reaping it."""
    if proc is None:
        return
    for sig, timeout in ((signal.SIGINT, 2), (signal.SIGTERM, 2), (signal.SIGKILL, 2)):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass
        except OSError:
            try:
                proc.send_signal(sig)
            except ProcessLookupError:
                pass
        try:
            proc.wait(timeout=timeout)
            return
        except subprocess.TimeoutExpired:
            continue


def _chown_to_sudo_user(path):
    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user or sudo_user == "root":
        return
    try:
        pw = pwd.getpwnam(sudo_user)
        os.chown(path, pw.pw_uid, pw.pw_gid)
    except Exception:
        return
