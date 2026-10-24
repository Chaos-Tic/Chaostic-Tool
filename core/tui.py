"""Reusable full-screen terminal surfaces, independent from application flows."""
from __future__ import annotations

import os
import re
import sys
from collections.abc import Sequence
from typing import Any

from rich.errors import MarkupError
from rich.text import Text

from core.theme import COLORS, EYEBROW

try:
    from prompt_toolkit.application import Application
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.document import Document
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl, UIContent, UIControl
    from prompt_toolkit.data_structures import Point
    from prompt_toolkit.styles import Style
    from prompt_toolkit.utils import get_cwidth
except ImportError:
    Application = None
    UIControl = object


# EYEBROW (the constant "RED OPS CONTROL SURFACE / ..." chrome line) is shared
# from core.theme so this path and the Rich fallback never drift apart.
_BADGE_RE = re.compile(r"brand\.badge\.(ok|bad|warn|info)")


def available() -> bool:
    """Full-screen mode needs the optional dependency and a real terminal."""
    return bool(Application and sys.stdin.isatty() and sys.stdout.isatty()
                and os.environ.get("TERM", "") != "dumb")


def _badge_class(raw: Any) -> str:
    """Map a status markup string to its pill style class (bg-filled badge)."""
    if isinstance(raw, str):
        match = _BADGE_RE.search(raw)
        if match:
            return "class:badge." + match.group(1)
    return "class:muted"


def plain(value: Any) -> str:
    """Strip existing Rich markup, preserving malformed markup literally."""
    if isinstance(value, Text):
        return value.plain
    text = str(value)
    if "\x1b[" in text:
        return Text.from_ansi(text).plain
    try:
        return Text.from_markup(text).plain
    except MarkupError:
        return text


def _fit(text: str, width: int) -> str:
    text = text.replace("\n", " ").replace("\r", " ").replace("\x1b", "")
    width = max(0, width)
    if get_cwidth(text) > width:
        while text and get_cwidth(text) > max(0, width - 1):
            text = text[:-1]
        text += "…" if width else ""
    return text + " " * max(0, width - get_cwidth(text))


# Words that live-state helpers emit as a status; mapped to a pill colour so the
# routing/stat strips read the same way as the menu badges (data, not decoration).
_STATUS_OK = {"ACTIVE", "AVAILABLE", "MATCH", "ON", "READY", "ENABLED"}
_STATUS_BAD = {"UNAVAILABLE", "MISSING", "MISMATCH", "FAILED", "ERROR", "NOT VERIFIED"}
_STATUS_WARN = {"OFF", "DISABLED", "NOT CHECKED", "PENDING", "SKIPPED"}

# Display keys for the home "direct actions" deck. These mirror the home key
# aliases in MenuScreen._bindings (11→r Results, 12→g Attack flows, p/x→Proxy):
# presentation only, so the letter shown is the letter that actually works.
_HOME_DECK_KEYS = {"0": "0", "11": "r", "12": "g", "p": "p", "w": "w", "99": "q"}

# --- Kill-chain information architecture -------------------------------------
# The banner's tagline is the attack kill-chain: RECON // EXPLOIT // PERSIST //
# CONTROL // IMPACT. The ten assessment phases are grouped under those five brand
# stages so the home screen is organised the way the product thinks about an
# engagement, not as a flat 1–10 list. This is presentation/ordering ONLY — the
# keys (and therefore every binding) are untouched; a stage simply decides which
# phase rows sit under which band, and in what visual order arrows walk them.
_KILL_CHAIN = [
    ("RECON",   "understand the surface",        ["1", "2", "3"]),
    ("ASSESS", "validate the findings",  ["4", "5"]),
    ("REVIEW", "access and credentials", ["6", "7"]),
    ("DIRECTORY", "Windows and Active Directory", ["8"]),
    ("NETWORK", "wireless and network assessment", ["9", "10"]),
]
# Flattened phase order used for arrow-key navigation on the home screen, so the
# selection walks the bands top-to-bottom exactly as they are drawn.
_HOME_ORDER = [k for _, _, ks in _KILL_CHAIN for k in ks]

_ASCII_CHAOSTIC = [
    r"  ____ _                     _   _      ",
    r" / ___| |__   __ _  ___  ___| |_(_) ___ ",
    r"| |   | '_ \ / _` |/ _ \/ __| __| |/ __|",
    r"| |___| | | | (_| | (_) \__ \ |_| | (__ ",
    r" \____|_| |_|\__,_|\___/|___/\__|_|\___|",
]
_ASCII_TOOL = [
    r" _____            _ ",
    r"|_   _|__   ___  | |",
    r"  | |/ _ \ / _ \ | |",
    r"  | | (_) | (_) || |",
    r"  |_|\___/ \___/ |_|",
]


def _seg_width(frags) -> int:
    return sum(get_cwidth(t) for _, t in frags)


def _row(left, right, inner_w):
    """A chamfered-frame content row: left fragments, flush-right fragments, a
    red HUD border each side — echoing the banner's cut-corner control frame."""
    gap = max(1, inner_w - _seg_width(left) - _seg_width(right))
    return ([("class:frame", " │ ")] + left + [("", " " * gap)] + right
            + [("class:frame", " │ ")])


def _status_pill_class(word: str) -> str:
    w = (word or "").strip().upper()
    if w in _STATUS_OK:
        return "class:badge.ok"
    if w in _STATUS_BAD:
        return "class:badge.bad"
    if w in _STATUS_WARN:
        return "class:badge.warn"
    return "class:muted"


def _style():
    return Style.from_dict({
        # Explicit canvas colors keep contrast stable on light and dark terminals.
        "": f"{COLORS['text']} bg:{COLORS['bg']}",
        "title": f"bold {COLORS['text']}",
        "accent": f"bold {COLORS['accent']}",
        "eyebrow": COLORS["faint"],
        "muted": COLORS["muted"], "line": COLORS["line"],
        "faint": COLORS["faint"],
        "selected": f"bg:{COLORS['accent_strong']} {COLORS['on_accent']} bold",
        "status": COLORS["good"], "footer": f"bg:{COLORS['surface']} {COLORS['muted']}",
        # brand masthead (the chamfered HUD frame + wordmark + kill-chain tagline)
        "frame": COLORS["accent_line"],
        "mark": f"bold {COLORS['accent']}",
        "wordmark": f"bold {COLORS['text']}",
        "wordmark2": f"bold {COLORS['accent']}",
        "surface_cap": COLORS["faint"],
        "tagverb": f"bold {COLORS['accent']}",
        "tagsep": COLORS["accent_line"],
        "ok": f"bold {COLORS['good']}",
        "band": f"bold {COLORS['accent']}",
        "keybadge": f"bold {COLORS['accent']}",
        "tool": COLORS["muted"],
        "tag": COLORS["faint"],
        # pill-style status badges: coloured text on a filled background,
        # square edges (the terminal equivalent of the desktop's tag chips).
        "badge.ok": f"bold {COLORS['good']} bg:{COLORS['good_soft']}",
        "badge.bad": f"bold {COLORS['danger']} bg:{COLORS['danger_soft']}",
        "badge.warn": f"bold {COLORS['warning']} bg:{COLORS['accent_soft']}",
        "badge.info": f"bold {COLORS['info']} bg:{COLORS['surface2']}",
    })


class _MenuControl(UIControl):
    def __init__(self, screen: MenuScreen):
        self.screen = screen

    def is_focusable(self):
        return True

    def create_content(self, width: int, height: int) -> UIContent:
        self.screen.width = width
        lines, cursor = self.screen.render_body(width)
        # Vertically balance the body so a short menu reads as a composed panel
        # instead of leaving a dead void below it. Equal-ish top/bottom margins;
        # skipped entirely when the content already fills (or overflows) the pane.
        free = max(0, height - len(lines))
        pad = free // 2
        if pad:
            lines = [[("", "")] for _ in range(pad)] + lines
            cursor += pad
        return UIContent(get_line=lambda i: lines[i], line_count=len(lines),
                         cursor_position=Point(x=0, y=cursor), show_cursor=False)


class MenuScreen:
    """Menu state and rendering, injectable I/O for deterministic keyboard tests."""
    def __init__(self, title: str, entries: Sequence[tuple], footer_extra=None,
                 show_back: bool = True, home: bool = False, metrics=None,
                 routing_rows=None, start_search: bool = False, *, input=None, output=None):
        if Application is None:
            raise RuntimeError("Full-screen mode requires prompt_toolkit>=3,<4")
        self.title = plain(title)
        self.entries = []
        for e in entries:
            raw_status = e[4] if len(e) > 4 and e[4] else ""
            self.entries.append((
                str(e[0]), plain(e[1]), str(e[2]) if len(e) > 2 else "",
                plain(e[3]) if len(e) > 3 and e[3] else "",
                plain(raw_status).strip(), _badge_class(raw_status),
            ))
        self.status_fields = self._as_fields(footer_extra)
        self.show_back, self.home = show_back, home
        self.metrics = [(plain(k), plain(v)) for k, v in (metrics or [])]
        self.routing_rows = [(plain(k), plain(v), plain(s)) for k, v, s in (routing_rows or [])]
        self.searching, self.query, self.typed = start_search, "", ""
        self.selected, self.width = 0, 80
        body = Window(_MenuControl(self), wrap_lines=False, always_hide_cursor=True)
        root = HSplit([
            Window(FormattedTextControl(self._header), dont_extend_height=True),
            body,
            Window(FormattedTextControl(self._footer), height=3, style="class:footer"),
        ])
        self.app = Application(layout=Layout(root, focused_element=body),
                               key_bindings=self._bindings(), style=_style(),
                               full_screen=True, mouse_support=False, input=input, output=output)
        self.app.ttimeoutlen = 0.05

    @staticmethod
    def _as_fields(value) -> list[str]:
        """Normalise footer context (str OR list of markup) to plain fields."""
        if not value:
            return []
        if isinstance(value, str):
            value = [value]
        return [plain(v) for v in value if plain(v).strip()]

    @property
    def visible_entries(self) -> list[tuple]:
        entries = self.entries
        if self.home:
            # Home shows the 10 phases ordered by kill-chain stage (see
            # _KILL_CHAIN). Arrow keys then walk the bands in drawn order.
            by_key = {e[0]: e for e in entries}
            return [by_key[k] for k in _HOME_ORDER if k in by_key]
        query = self.query.casefold()
        return [e for e in entries if query in (e[1] + " " + e[3]).casefold()]

    @property
    def selected_key(self) -> str | None:
        entries = self.visible_entries
        return entries[min(self.selected, len(entries) - 1)][0] if entries else None

    def columns(self, width: int) -> int:
        # Single-column everywhere now: the home phase list is grouped into
        # kill-chain bands (vertical), sub-menus were already one column.
        return 1

    def _header(self):
        width = self.app.output.get_size().columns
        return self._masthead(width) if self.home else self._subheader(width)

    def _masthead(self, width):
        """Rounded, quiet workspace masthead shared by both terminal palettes."""
        inner = max(1, width - 6)
        top = [("class:frame", " ╭" + "─" * max(1, width - 4) + "╮ \n")]
        bottom = [("class:frame", " ╰" + "─" * max(1, width - 4) + "╯ ")]
        rows = []
        if inner >= 60:
            for c, t in zip(_ASCII_CHAOSTIC, _ASCII_TOOL):
                rows.extend(_row([("class:wordmark", c), ("class:wordmark2", t)], [], inner) + [("", "\n")])
        else:
            identity = [("class:wordmark", "Chaostic"), ("class:wordmark2", "Tool")]
            rows.extend(_row(identity, [], inner) + [("", "\n")])
        subtitle = [("class:muted", "Targets, tools and results. One workspace.")]
        eyebrow = [("class:eyebrow", EYEBROW)]
        rows.extend(_row(subtitle, [], inner) + [("", "\n")])
        rows.extend(_row(eyebrow, [], inner) + [("", "\n")])
        return top + rows + bottom

    def _subheader(self, width):
        return [("class:wordmark", "  Chaostic"), ("class:wordmark2", "Tool\n"),
                ("class:line", "  " + "─" * max(1, width - 4) + "\n"),
                ("class:eyebrow", "  " + EYEBROW + "\n"),
                ("class:title", "  " + self.title + "\n"),
                ("class:accent", "  " + "─" * 14)]

    def _footer(self):
        width = max(1, self.width)
        command = "/" + self.query if self.searching else self.typed
        # Keep the footer to navigation only. The home "direct actions" deck in
        # the body carries the labelled action keys, so there is no second place
        # for the key→action copy to drift out of sync with the real bindings.
        keys = "↑↓ move · Enter open · / search"
        if self.home:
            keys += " · q quit"
        elif self.show_back:
            keys += " · Esc/r back"
        # Single-line status bar: READY pill + "/"-separated live context fields.
        fields = " / ".join(self.status_fields)
        return [("class:badge.ok", " READY "),
                ("class:muted", " " + _fit(fields, max(1, width - 8))),
                ("class:muted", "\n " + _fit(keys, width - 1)),
                ("class:accent", "\n > " + command)]

    def render_body(self, width: int):
        if self.home:
            return self._render_home(width)
        return self._render_submenu(width)

    # ---- home ---------------------------------------------------------------
    def _section(self, label, width, right=None):
        """A `// LABEL` eyebrow with a hairline running to the right edge; an
        optional right-aligned fragment list rides the far end of the rule."""
        used = 2 + get_cwidth(label) + 1
        rw = _seg_width(right) + 1 if right else 0
        rule = "─" * max(1, width - used - rw - 1)
        row = [("class:eyebrow", " " + label + " "), ("class:line", rule)]
        if right:
            row += [("", " ")] + right
        return row

    def _telemetry(self, width):
        """Live session scoreboard: two columns of label→value readouts, framed
        top and bottom by a complete hairline. Pure live state, no filler."""
        lines = [self._section("SESSION", width)]
        label_w, cell = 11, max(20, (width - 2) // 2)
        for i in range(0, len(self.metrics), 2):
            row = [("", " ")]
            for k, v in self.metrics[i:i + 2]:
                row.append(("class:faint", _fit(k.upper(), label_w)))
                row.append(("class:title", _fit(v, cell - label_w)))
            lines.append(row)
        lines.append([("", "")])
        return lines

    def _phase_row(self, entry, selected, width):
        key, label, _style, desc, status, _badge = entry
        tools = desc.replace(", ", " · ")
        tag = status.replace("PHASE ", "")
        label_w, tag_w = 24, 5
        # 3 margin + 2 key + 2 gap + label + 2 gap + tools + 1 + tag
        tools_w = max(4, width - 3 - 2 - 2 - label_w - 2 - 1 - tag_w)
        if selected:
            head = f" ▌ {key:>2}  " + _fit(label, label_w) + "  " + tools
            return [("class:selected", _fit(head, width - tag_w - 2)),
                    ("class:selected", _fit(" " + tag + " ", tag_w + 2))]
        return [("", "   "), ("class:keybadge", f"{key:>2}"), ("", "  "),
                ("class:title", _fit(label, label_w)), ("", "  "),
                ("class:tool", _fit(tools, tools_w)),
                ("", " "), ("class:tag", _fit(tag, tag_w))]

    def _render_home(self, width):
        lines: list[list[tuple[str, str]]] = self._telemetry(width)
        entries = self.visible_entries
        by_key = {e[0]: e for e in entries}
        sel = min(self.selected, len(entries) - 1) if entries else -1
        sel_key = entries[sel][0] if entries else None
        cursor = len(lines)
        lines.append(self._section("ASSESSMENT PHASES", width))
        for stage, (name, sub, keys) in enumerate(_KILL_CHAIN):
            # Band header: stage name + its intent, a hairline to the edge.
            cap = f" · {sub} "
            used = 3 + get_cwidth(name) + get_cwidth(cap)
            lines.append([("", "  "), ("class:band", name), ("class:faint", cap),
                          ("class:line", "─" * max(2, width - used - 2))])
            for k in keys:
                if k not in by_key:
                    continue
                selected = k == sel_key
                if selected:
                    cursor = len(lines)
                lines.append(self._phase_row(by_key[k], selected, width))
            if stage != len(_KILL_CHAIN) - 1:
                lines.append([("", "")])
        lines.append([("", "")])
        # Direct-actions dock: off-grid actions, each labelled with the exact key
        # that triggers it (mirrors the _bindings alias map), so it is both the
        # documentation of those keys and the way to discover them.
        deck = [(_HOME_DECK_KEYS.get(key, key), label)
                for key, label, *_ in self.entries
                if not (key.isdigit() and 1 <= int(key) <= 10)]
        deck.insert(1, ("/", "Search tools"))
        dcols = 3 if width >= 100 else (2 if width >= 60 else 1)
        dcell = max(14, (width - 2) // dcols)
        lines.append(self._section("DIRECT ACTIONS", width))
        for offset in range(0, len(deck), dcols):
            row = [("", " ")]
            for dk, dlabel in deck[offset:offset + dcols]:
                tag = f"[{dk}] "
                pad = max(1, dcell - get_cwidth(tag) - get_cwidth(dlabel))
                row.append(("class:accent", tag))
                row.append(("class:muted", dlabel))
                row.append(("", " " * pad))
            lines.append(row)
        return lines or [[("", "")]], min(cursor, max(0, len(lines) - 1))

    # ---- sub-menus (categories, proxy, search) ------------------------------
    def _render_submenu(self, width):
        lines: list[list[tuple[str, str]]] = []
        if self.routing_rows:
            label_w = max((get_cwidth(l) for l, _, _ in self.routing_rows), default=4) + 3
            lines.append(self._section("ROUTING STATE", width))
            for label, detail, status in self.routing_rows:
                pill = f" {status} " if status else ""
                avail = max(1, width - 3 - label_w - get_cwidth(pill))
                lines.append([
                    ("", " "),
                    ("class:title", _fit(label, label_w)),
                    ("class:muted", _fit(detail, avail)),
                    (_status_pill_class(status), pill),
                ])
            lines.append([("", "")])
        entries = self.visible_entries
        cell = max(5, width - 2)
        cursor = len(lines)
        has_status = any(e[4] for e in entries)
        sublines = 3 if has_status else 2
        for index, (key, label, _s, description, status, badge) in enumerate(entries):
            selected = index == min(self.selected, len(entries) - 1)
            if selected:
                cursor = len(lines)
            for subline in range(sublines):
                style = "class:selected" if selected else ("class:title" if subline == 0 else "class:muted")
                if subline == 0:
                    text = f"{'▌' if selected else ' '} {key:>2}  {label}"
                    lines.append([("", " "), (style, _fit(text, cell))])
                elif subline == 1:
                    lines.append([("", " "), (style, _fit("      " + description, cell))])
                else:
                    pill = f" {status} " if status else ""
                    if status and not selected and badge != "class:muted":
                        pad = max(0, cell - 5 - get_cwidth(pill))
                        lines.append([("", " "), ("", " " * 5), (badge, pill), ("", " " * pad)])
                    else:
                        lines.append([("", " "), (style, _fit("      " + (status or ""), cell))])
            lines.append([("", "")])
        if not entries:
            lines.append([("class:muted", "  No matching entries. Press Esc to clear search.")])
        return lines or [[("", "")]], min(cursor, max(0, len(lines) - 1))

    def _bindings(self):
        kb = KeyBindings()

        @kb.add("enter")
        def accept(event):
            valid = {e[0] for e in self.entries}
            key = self.typed if self.typed else self.selected_key
            if key in valid:
                event.app.exit(result=key)

        @kb.add("escape")
        def back(event):
            if self.searching:
                self.searching, self.query, self.selected = False, "", 0
            elif self.home:
                self.typed = ""
            else:
                event.app.exit(result="r")

        @kb.add("c-c")
        def interrupt(event):
            event.app.exit(exception=KeyboardInterrupt())

        @kb.add("up")
        @kb.add("down")
        @kb.add("left")
        @kb.add("right")
        def move(event):
            key = event.key_sequence[-1].key
            delta = self.columns(self.width) if key in ("up", "down") else 1
            if key in ("up", "left"):
                delta = -delta
            self.selected = (self.selected + delta) % max(1, len(self.visible_entries))
            self.typed = ""

        @kb.add("backspace")
        def erase(event):
            if self.searching:
                self.query = self.query[:-1]
                self.selected = 0
            else:
                self.typed = self.typed[:-1]

        @kb.add("<any>")
        def character(event):
            char = event.data
            if not char.isprintable():
                return
            if self.searching:
                self.query += char
                self.selected = 0
                return
            if char == "/":
                if self.home:
                    event.app.exit(result="__search__")
                else:
                    self.searching, self.query, self.typed = True, "", ""
                return
            if char.isdigit():
                self.typed += char
                return
            if char == "q":
                event.app.exit(result="99" if self.home else "r")
                return
            if char == "r" and not self.home:
                event.app.exit(result="r")
                return
            aliases = {"g": "12", "r": "11", "x": "p", "p": "p", "w": "w"} if self.home else {}
            key = aliases.get(char, char)
            if key in {e[0] for e in self.entries}:
                event.app.exit(result=key)
        return kb

    def run(self) -> str:
        return self.app.run()


class DialogScreen:
    """Scrollable output and editable prompt on the same full-screen surface."""
    def __init__(self, prompt: str, content: str = "", title: str = "Chaostic Tool",
                 default: str = "", *, message_only: bool = False, input=None, output=None):
        if Application is None:
            raise RuntimeError("Full-screen mode requires prompt_toolkit>=3,<4")
        self.buffer = Buffer(document=Document(default, len(default)))
        self.content = plain(content)
        self.lines = self.content.splitlines() or [""]
        self.scroll = max(0, len(self.lines) - 12)
        control = FormattedTextControl(lambda: self.content)
        self.body = Window(control, wrap_lines=True, always_hide_cursor=True,
                           get_vertical_scroll=lambda window: self.scroll)
        field = Window(BufferControl(buffer=self.buffer), height=1)
        footer = Window(FormattedTextControl(" Enter close · PgUp/PgDn scroll · Esc cancel"), height=1,
                        style="class:footer")
        root = HSplit([
            Window(FormattedTextControl([
                ("class:accent", " ● chaostictool"), ("class:muted", "  linux-cli\n"),
                ("class:eyebrow", " " + EYEBROW + "\n"),
                ("class:title", " " + plain(title))]), height=3),
            self.body,
            Window(FormattedTextControl([("class:accent", " " + plain(prompt))]), height=1),
            field, footer,
        ])
        kb = KeyBindings()

        @kb.add("enter")
        def accept(event):
            event.app.exit(result="" if message_only else self.buffer.text)

        @kb.add("escape")
        @kb.add("c-c")
        def cancel(event):
            event.app.exit(exception=KeyboardInterrupt())

        @kb.add("pageup")
        @kb.add("pagedown")
        def scroll(event):
            delta = -10 if event.key_sequence[-1].key == "pageup" else 10
            self.scroll = max(0, min(max(0, len(self.lines) - 1), self.scroll + delta))
        self.app = Application(layout=Layout(root, focused_element=field), key_bindings=kb,
                               style=_style(), full_screen=True, input=input, output=output)
        self.app.ttimeoutlen = 0.05

    def run(self) -> str:
        return self.app.run()


def menu(title: str, entries: Sequence[tuple], footer_extra=None, show_back: bool = True,
         home: bool = False, metrics=None, routing_rows=None, start_search: bool = False) -> str:
    return MenuScreen(title, entries, footer_extra, show_back, home, metrics,
                      routing_rows, start_search).run()


def input_dialog(prompt: str, content: str = "", title: str = "Chaostic Tool", default: str = "") -> str:
    return DialogScreen(prompt, content, title, default).run()


def message(content: str, title: str = "Chaostic Tool") -> None:
    DialogScreen("Press Enter to continue", content, title, message_only=True).run()
