"""Fullscreen presentation of a captured process; process ownership stays in executor.

Rendering concerns only. The process, its abort and the on-disk journal are owned
by core.executor; this module reads a bounded snapshot of that state and draws it.
Two deliberate behaviours matter here:

* The elapsed clock FREEZES the moment the run completes. The executor stamps
  ``state.finished`` just before ``state.done``; we read that instead of
  recomputing ``time.monotonic() - started`` on every frame, and we stop the
  periodic invalidation once done so the screen genuinely stops ticking.
* The screen never stretches a few lines of output across a 50-row terminal.
  A short run is composed as a centred panel; a long run fills the pane and
  scrolls. Every cell keeps the terminal's native background.
"""
import asyncio
import re
import shlex
import time

from prompt_toolkit.application import Application
from prompt_toolkit.data_structures import Point
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl, UIContent, UIControl
from prompt_toolkit.styles import Style
from prompt_toolkit.utils import get_cwidth

from core.theme import COLORS

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)")


def available():
    import os
    import sys
    return sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"


def _clean(line):
    return _ANSI.sub("", line).replace("\x1b", "")


def _fit(text, width):
    """Truncate with an ellipsis / pad to exactly ``width`` display columns."""
    text = text.replace("\n", " ").replace("\r", " ")
    width = max(0, width)
    if get_cwidth(text) > width:
        while text and get_cwidth(text) > max(0, width - 1):
            text = text[:-1]
        text += "…" if width else ""
    return text + " " * max(0, width - get_cwidth(text))


def _seg(frags):
    return sum(get_cwidth(t) for _, t in frags)


def _frame_row(left, right, inner_w):
    """A chamfered-frame content row (left fragments, flush-right fragments),
    the banner's cut-corner HUD border in red on each side."""
    gap = max(1, inner_w - _seg(left) - _seg(right))
    return ([("class:frame", " │ ")] + left + [("", " " * gap)] + right
            + [("class:frame", " │ ")])


def run_scan(state, start, abort, context, cmd, output_path):
    """Render a bounded output tail, stopping only after process cleanup/save."""
    keys = KeyBindings()
    offset = [0]

    @keys.add("c-c")
    def stop(event):
        if state.done.is_set():
            event.app.exit()
        else:
            abort()

    @keys.add("enter")
    def finish(event):
        if state.done.is_set():
            event.app.exit()

    @keys.add("pageup")
    def older(event):
        offset[0] += 10

    @keys.add("pagedown")
    def newer(event):
        offset[0] = max(0, offset[0] - 10)

    @keys.add("end")
    def tail(event):
        offset[0] = 0

    # --- live, read-only derivations of executor state ----------------------
    def status_word():
        if not state.done.is_set():
            return "RUNNING"
        return ("SUCCESS" if state.rc == 0
                else "ABORTED" if state.rc == 130 else "FAILED")

    def status_badge(word):
        return ("class:badge.ok" if word in ("RUNNING", "SUCCESS")
                else "class:badge.warn" if word == "ABORTED" else "class:badge.bad")

    def elapsed_seconds():
        # Freeze on completion: executor stamps state.finished just before done,
        # so the clock stops instead of recomputing from "now" on every refresh.
        end = state.finished if (state.done.is_set() and state.finished) else time.monotonic()
        return max(0.0, end - state.started)

    def tool_name():
        return str(context.get("tool") or cmd[0])

    def category():
        return str(context.get("category") or "Tools")

    def activity():
        # A small live scan bar while running (btop-style motion), a static
        # marker once finished. Driven by the frozen clock so it stops too.
        if state.done.is_set():
            return [("class:faint", "────────")]
        phase = int(elapsed_seconds() * 6) % 8
        cells = "".join("▓" if i == phase else "░" for i in range(8))
        return [("class:accent", cells)]

    # --- header: chamfered OPERATION masthead with the live mission clock -----
    def header():
        width = app.output.get_size().columns
        word = status_word()
        inner = max(24, width - 6)
        secs = f"{elapsed_seconds():.1f}s"
        # Row 1: brand + OPERATION, status pill, mission clock.
        r1l = [("class:mark", "⌖  "), ("class:wordmark", "CHAOSTIC "),
               ("class:wordmark2", "TOOL"), ("class:muted", "   ·   OPERATION")]
        r1r = [(status_badge(word), f" {word} "), ("", "   "),
               ("class:faint", "ELAPSED "), ("class:clock", secs)]
        # Row 2: tool · breadcrumb, live activity bar.
        r2l = [("class:name", tool_name()), ("class:muted", "   —   Home / "),
               ("class:muted", category())]
        r2r = activity()
        top = [("class:frame", " ╭" + "─" * (width - 4) + "╮ \n")]
        bot = [("class:frame", " ╰" + "─" * (width - 4) + "╯ ")]
        return (top
                + _frame_row(r1l, r1r, inner) + [("", "\n")]
                + _frame_row(r2l, r2r, inner) + [("", "\n")]
                + bot)

    def _section(label, width, right=None):
        used = 2 + get_cwidth(label) + 1
        rw = (get_cwidth(right) + 1) if right else 0
        rule = "─" * max(2, width - used - rw - 1)
        row = [("class:eyebrow", " " + label + " "), ("class:line", rule)]
        if right:
            row += [("", " "), ("class:faint", right)]
        return row

    def _telemetry(width):
        # Always-visible console readout row: clock, output volume, exit, route.
        done = state.done.is_set()
        secs = f"{elapsed_seconds():.1f}s"
        route = str(context.get("route") or "n/a")
        exit_txt = str(state.rc) if done else "—"
        with state.lock:
            lines = len(state.visible)
        cells = [("ELAPSED", secs), ("LINES", str(lines)),
                 ("EXIT", exit_txt), ("ROUTE", route)]
        row = [("", " ")]
        for i, (lab, val) in enumerate(cells):
            if i:
                row.append(("class:sep", "   ·   "))
            row.append(("class:faint", lab + " "))
            row.append(("class:clock" if lab == "ELAPSED" else "class:text", val))
        return row

    # --- body: telemetry, command, operation output, run result -------------
    def build_body(width, height):
        pre = []
        preset = str(context.get("preset") or "Custom command")
        pre.append(_telemetry(width))
        pre.append([("", "")])
        pre.append(_section("COMMAND", width))
        pre.append([("class:accent", " $ "), ("class:cmd", shlex.join(cmd))])
        pre.append([("class:faint", " PRESET  "), ("class:muted", preset)])
        pre.append([("", "")])

        with state.lock:
            all_lines = [_clean(line) for line in state.visible]
        total = len(all_lines)
        count = f"{total} line" + ("" if total == 1 else "s")
        pre.append(_section("OPERATION OUTPUT", width, right=count))

        post = [_rule(width), [("", "")]]
        post += result_block(width)

        # How many output rows fit between the framed sections and the footer.
        capacity = max(1, height - len(pre) - len(post))
        if total == 0:
            shown = [[("class:faint", "   (no output captured)")]]
        else:
            offset[0] = min(offset[0], max(0, total - capacity))
            end = total - offset[0]
            window = all_lines[max(0, end - capacity):end]
            shown = [[("class:gutter", " │ "), ("class:term", ln)] for ln in window]

        body = pre + shown + post
        # Short run → compose as a centred panel so there is no dead void below.
        # Long run (overflow) → top-aligned, the output window scrolls instead.
        free = height - len(body)
        top = free // 2 if free > 0 else 0
        return ([[("", "")] for _ in range(top)] + body), top + len(pre)

    def result_block(width):
        done = state.done.is_set()
        word = status_word()
        if done:
            saved = (str(output_path) if state.saved
                     else f"save failed: {state.save_error}" if state.save_error
                     else "no captured output saved")
            save_cls = "class:text" if state.saved else "class:warn"
            return [
                [("class:eyebrow", " // RESULT"), ("", "  "),
                 (status_badge(word), f" {word} "),
                 ("class:faint", f"   exit {state.rc}")],
                _rule(width),
                [("class:faint", f" {'OUTPUT':<9}"), (save_cls, _fit(saved, max(4, width - 11)))],
            ]
        return [
            [("class:eyebrow", " // STATUS"), ("", "  "),
             ("class:accent", _pulse()), ("class:text", "  working")],
            _rule(width),
            [("class:faint", f" {'DEST':<9}"),
             ("class:muted", _fit(str(output_path or "not saved"), max(4, width - 11)))],
        ]

    def _pulse():
        tick = int(elapsed_seconds() * 3) % 3
        return "● ○ ○" if tick == 0 else "○ ● ○" if tick == 1 else "○ ○ ●"

    def _rule(width):
        return [("class:line", " " + "─" * max(1, width - 2))]

    # --- footer: controls only ----------------------------------------------
    def footer():
        if state.done.is_set():
            left = "Enter  return to menu"
            right = "PgUp/PgDn  scroll"
        else:
            left = "Ctrl+C  abort run"
            right = "PgUp/PgDn  scroll   ·   End  follow output"
        width = app.output.get_size().columns
        gap = max(2, width - 1 - get_cwidth(left) - get_cwidth(right))
        return [("class:ctrl", " " + left), ("", " " * gap), ("class:ctrl", right + " ")]

    class _Body(UIControl):
        def create_content(self, width, height):
            lines, cursor = build_body(width, height)
            return UIContent(get_line=lambda i: lines[i], line_count=max(1, len(lines)),
                             cursor_position=Point(x=0, y=min(cursor, max(0, len(lines) - 1))),
                             show_cursor=False)

        def is_focusable(self):
            return True

    style = Style.from_dict({
        # Keep blank cells and panels transparent so the terminal owns its canvas.
        "": COLORS["text"],
        "brand": f"bold {COLORS['text']}",
        "name": f"bold {COLORS['text']}",
        "accent": f"bold {COLORS['accent']}",
        "cmd": COLORS["accent"],
        "muted": COLORS["muted"], "faint": COLORS["faint"],
        "eyebrow": COLORS["faint"], "line": COLORS["line_soft"],
        "info": COLORS["info"], "text": COLORS["text"], "warn": COLORS["warning"],
        "gutter": COLORS["accent_line"], "term": COLORS["term_text"],
        "ctrl": COLORS["muted"],
        # masthead HUD frame + wordmark + mission clock
        "frame": COLORS["accent_line"],
        "mark": f"bold {COLORS['accent']}",
        "wordmark": f"bold {COLORS['text']}",
        "wordmark2": f"bold {COLORS['accent']}",
        "clock": f"bold {COLORS['text']}",
        "sep": COLORS["line"],
        "badge.ok": f"bold {COLORS['good']}",
        "badge.warn": f"bold {COLORS['warning']}",
        "badge.bad": f"bold {COLORS['danger']}",
    })
    app = Application(
        layout=Layout(HSplit([
            Window(FormattedTextControl(header), height=4),
            Window(_Body(), wrap_lines=False, always_hide_cursor=True),
            Window(FormattedTextControl(footer), height=1, style="class:footer"),
        ])),
        key_bindings=keys, style=style, full_screen=True,
        # No built-in refresh_interval: we drive our OWN ticker below so it can
        # be stopped the instant the run completes (see _ticker), instead of
        # invalidating forever.
        refresh_interval=None,
    )

    def refresh(application):
        if state.done.is_set() and not context.get("wait", True) and not application.is_done:
            application.exit()

    app.before_render += refresh

    async def _ticker():
        # Repaint ~10x/s ONLY while the process runs (and one final frame once it
        # finishes, to show the frozen clock + result). Then stop. This is what
        # makes the timer actually stop instead of running forever.
        try:
            while not state.done.is_set():
                app.invalidate()
                await asyncio.sleep(0.1)
        finally:
            app.invalidate()

    def _begin():
        start()
        app.create_background_task(_ticker())

    app.run(pre_run=_begin)
