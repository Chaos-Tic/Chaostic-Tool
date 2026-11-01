import logging
import os
import shutil
import tempfile
import threading
import time
from collections import deque

try:
    import pwd
except ImportError:
    pwd = None
import re
import shlex
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.redaction import redact
from core.run_session import RunSession
from core.runner import Runner, RunRequest
from core.theme import COLORS, THEME

LOG = logging.getLogger(__name__)
console = Console(theme=THEME, style=f"{COLORS['text']} on {COLORS['bg']}")
# ACTIVE_PROCS tracks every live child so Ctrl+C / shutdown can reap them. It is
# touched from the UI thread and from capture worker threads, so a lock guards
# all of its mutations and iterations.
ACTIVE_PROCS = []
_ACTIVE_PROCS_LOCK = threading.Lock()


def _register_process(proc):
    with _ACTIVE_PROCS_LOCK:
        ACTIVE_PROCS.append(proc)


def _build_env():
    """Return a copy of os.environ with HOME/USER set to the invoking user.
    Under sudo, the default HOME=/root breaks pip --user installed tools."""
    env = os.environ.copy()
    sudo_user = env.get("SUDO_USER")
    if sudo_user and sudo_user != "root" and pwd is not None:
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
            LOG.exception("Could not switch the environment to the sudo user; "
                          "using the inherited root environment")
    from core import api_keys
    api_keys.apply_to_env(env)
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


def _result_panel(rc, output_path, saved, timed_out=False):
    style = "brand.ok" if rc == 0 else "bright_red"
    result = "SUCCESS" if rc == 0 else "TIMEOUT" if timed_out else "NON-ZERO EXIT"
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
        self.timed_out = False
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


def _capture_worker(state, cmd, output_path, textual, timeout, redactions):
    session = RunSession(redactions)

    def present(redacted, final):
        # The shared session has already masked these bytes; decode them (the
        # CLI journals decoded text) and, outside fullscreen, echo them live.
        text = session.decode(redacted, final=final)
        if not text:
            return
        state.append(text)
        if textual:
            console.print(Text.from_ansi(text), end="", soft_wrap=True)

    session.sink = present
    try:
        runner = Runner()
        runner.start(RunRequest(cmd, env=_build_env(), timeout=timeout, stop_grace=2,
                               inherit_stdin=True, raw_output=True), session.feed)
        state.proc = runner
        _register_process(state.proc)
        if state.aborted.is_set():
            state.proc.stop()
        result = state.proc.wait()
        state.rc = result.returncode
        state.timed_out = result.timed_out
        if result.error:
            if state.rc == 127:
                state.append(f"Binary not found: {cmd[0]}\n")
            else:
                state.append(f"Execution failed: {result.error}\n")
                state.rc = state.rc or 1
    except OSError as exc:
        state.append(f"Execution failed: {exc}\n")
        state.rc = 1
        _stop_process(state.proc)
    finally:
        # One final flush releases the redactor's held-back tail (and the
        # decoder's pending bytes) through the same sink, so a secret spanning
        # the last chunk is masked and journaled rather than dropped.
        session.flush()
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
            _forget_process(state.proc)
            # Freeze the elapsed clock at the instant everything is finished
            # (process reaped + output saved) so the scan view can stop ticking.
            state.finished = time.monotonic()
            state.done.set()


def _fileno(stream):
    """Return a stream's real OS descriptor, or None when it has none."""
    try:
        fd = stream.fileno()
    except (AttributeError, OSError, ValueError):
        return None
    return fd if isinstance(fd, int) and fd >= 0 else None


def _write_all(fd, data):
    """Write every byte to a descriptor, tolerating a vanished terminal."""
    view = memoryview(data)
    while view:
        try:
            written = os.write(fd, view)
        except BlockingIOError:
            continue
        except OSError:
            return
        view = view[written:]


def _window_size(fd):
    """Current (rows, cols) of a terminal descriptor, with a sane fallback."""
    if fd is not None:
        import fcntl, struct, termios
        try:
            packed = fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\x00" * 8)
            rows, cols = struct.unpack("HHHH", packed)[:2]
            if rows and cols:
                return rows, cols
        except (OSError, ValueError):
            pass
    return 24, 80


def _final_rc(result):
    return result.returncode if result is not None else 1


def _report_interactive_error(result, rc, cmd):
    """Mirror the capture path's missing-binary / failure messages."""
    if result is None or not result.error:
        return
    if rc == 127:
        console.print(f"[bright_red]Binary not found: {escape(cmd[0])}[/bright_red]")
    else:
        console.print(Text(f"Execution failed: {result.error}", style="bright_red"))


def _pump_terminal(runner, backend, stdin_fd, size_fd=None):
    """Bridge the user's terminal to the PTY master until the child exits.

    Output already reaches the real terminal through the Runner's on_output
    callback on the worker thread; this loop forwards keystrokes the other way,
    signals EOF when the user's stdin closes, and tracks window-size changes.
    Size is polled rather than driven from a SIGWINCH handler so it never has to
    take the backend lock from inside a signal handler."""
    import select
    last_size = [None]

    def track_size():
        if size_fd is None:
            return
        size = _window_size(size_fd)
        if size != last_size[0]:
            last_size[0] = size
            backend.resize(*size)

    forwarding = stdin_fd is not None
    if not forwarding:
        runner.close_input()
    while True:
        track_size()
        result = runner.wait(timeout=0)
        if result is not None:
            return result
        if not forwarding:
            runner.wait(timeout=0.05)
            continue
        ready, _, _ = select.select([stdin_fd], [], [], 0.05)
        if not ready:
            continue
        try:
            data = os.read(stdin_fd, 65536)
        except OSError:
            data = b""
        if data:
            backend.write_bytes(data)
        else:
            runner.close_input()
            forwarding = False


def _run_interactive(cmd):
    """Run an interactive tool through the neutral Runner over a real PTY.

    On POSIX the child gets its own controlling terminal (isatty, job control,
    window size) through PtyBackend, and this process bridges the user's
    terminal to it: raw mode so keystrokes and a typed Ctrl-C reach the tool
    untouched, window-size tracking, and a termios restore on exit. Elsewhere
    there is no POSIX PTY -- native interactive tools run through the WSL2
    (POSIX) backend -- so a plain Runner stream keeps the one lifecycle."""
    import sys
    env = _build_env()
    env.setdefault("TERM", "xterm-256color")
    if os.name != "posix":
        return _run_interactive_plain(cmd, env)
    import termios
    import tty
    from core.backends.pty import PtyBackend

    stdin_fd = _fileno(sys.stdin)
    out_fd = _fileno(sys.stdout)
    sink_fd = out_fd if out_fd is not None else 1
    size_fd = out_fd if (out_fd is not None and os.isatty(out_fd)) else None
    backend = PtyBackend(winsize=_window_size(size_fd if size_fd is not None else stdin_fd))
    runner = Runner(backend)

    raw_stdin = stdin_fd is not None and os.isatty(stdin_fd)
    saved_attr = None
    result = None
    rc = 1
    try:
        if raw_stdin:
            saved_attr = termios.tcgetattr(stdin_fd)
            tty.setraw(stdin_fd)
        runner.start(RunRequest(cmd, env=env, stop_grace=2, inherit_stdin=False,
                                raw_output=True), lambda data: _write_all(sink_fd, data))
        _register_process(runner)
        result = _pump_terminal(runner, backend, stdin_fd, size_fd)
        rc = _final_rc(result)
    except KeyboardInterrupt:
        _stop_process(runner)
        rc = 130
    except OSError as exc:
        _stop_process(runner)
        console.print(Text(f"Execution failed: {exc}", style="bright_red"))
        rc = 1
    finally:
        if saved_attr is not None:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, saved_attr)
        _forget_process(runner)
    _report_interactive_error(result, rc, cmd)
    return rc


def _run_interactive_plain(cmd, env):
    """Non-POSIX fallback: stream through the default Runner, no PTY or bridge."""
    import sys
    runner = Runner()
    sink_fd = _fileno(sys.stdout)
    result = None
    rc = 1
    try:
        runner.start(RunRequest(cmd, env=env, stop_grace=2, inherit_stdin=True,
                                raw_output=True),
                     lambda data: _write_all(sink_fd if sink_fd is not None else 1, data))
        _register_process(runner)
        result = runner.wait()
        rc = _final_rc(result)
    except KeyboardInterrupt:
        _stop_process(runner)
        rc = 130
    finally:
        _forget_process(runner)
    _report_interactive_error(result, rc, cmd)
    return rc


def run_tool(cmd, output_path=None, interactive=False, context=None, *, timeout=None,
             redactions=()):
    """Run an argv command; TTY capture uses a fullscreen bounded live view.

    context accepts category/tool/preset/route labels and wait=False for flows.
    Redirected input/output never waits for a completion key.
    """
    context = dict(context or {})
    display_cmd = [redact(argument, redactions) for argument in cmd]
    if interactive:
        # The menu application has already exited. The interactive tool runs
        # through the neutral Runner over a real pseudo-terminal (PtyBackend):
        # curses/REPL tools (msfconsole, the console suite) get a genuine
        # controlling TTY, isatty() and job control, while ACTIVE_PROCS cleanup
        # and Ctrl+C reaping flow through the single Runner lifecycle below.
        _print_command_panel(display_cmd, output_path, True)
        from core import tui
        with tui.suspend_screen():  # the tool draws on the normal screen, as before
            rc = _run_interactive(cmd)
        console.print(_result_panel(rc, output_path, False))
        return rc

    from core.scan_view import available, run_scan
    fullscreen = available()
    state = _Capture()
    worker = threading.Thread(target=_capture_worker,
                              args=(state, cmd, output_path, not fullscreen,
                                    timeout, tuple(redactions)), daemon=True)

    def abort():
        if not state.aborted.is_set():
            state.aborted.set()
            threading.Thread(target=_stop_process, args=(state.proc,), daemon=True).start()

    try:
        if fullscreen:
            run_scan(state, worker.start, abort, context, display_cmd, output_path)
        else:
            _print_command_panel(display_cmd, output_path, False)
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
        console.print(_result_panel(state.rc, output_path, state.saved, state.timed_out))
    return state.rc


def cleanup_processes():
    # Snapshot under the lock, then stop/forget outside it: _stop_process can
    # block for seconds and _forget_process takes the same (non-reentrant) lock.
    with _ACTIVE_PROCS_LOCK:
        procs = list(ACTIVE_PROCS)
    for proc in procs:
        _stop_process(proc)
        _forget_process(proc)


def _forget_process(proc):
    with _ACTIVE_PROCS_LOCK:
        try:
            ACTIVE_PROCS.remove(proc)
        except ValueError:
            pass


def _stop_process(proc):
    """Cancel the run through the Runner and reap it with a bounded wait.

    Both execution paths -- the capture worker and the interactive PTY bridge --
    register a Runner, so the lifecycle is uniform: stop() is an idempotent,
    asynchronous cancel the backend turns into its own SIGINT/SIGTERM/SIGKILL
    escalation on the process group (or job termination on Windows), and wait()
    reaps the child within the bound."""
    if proc is None:
        return
    proc.stop()
    proc.wait(timeout=8)


def _chown_to_sudo_user(path):
    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user or sudo_user == "root" or pwd is None or not hasattr(os, "chown"):
        return
    try:
        pw = pwd.getpwnam(sudo_user)
        os.chown(path, pw.pw_uid, pw.pw_gid)
    except Exception:
        LOG.exception("Could not chown %s to the sudo user", path)
        return
