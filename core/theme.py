"""Shared pastel terminal palette for Rich, menus and execution output.

The terminal owns the canvas background. Palettes provide foreground colors
selected for the detected light or dark terminal; surface keys remain default.
CHAOSTIC_THEME=light|dark overrides COLORFGBG detection; unknown terminals use
their default foreground color.
Legacy style aliases are preserved for the existing tool modules.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from rich.theme import Theme

EYEBROW = "CHAOSTICTOOL / LINUX CLI"
EYEBROW_COMPACT = "CHAOSTICTOOL / CLI"

LIGHT = {
    "bg": "default", "surface": "default", "surface2": "default",
    "line": "#a3aec7", "line_soft": "#d4d5e5",
    "text": "#151820", "muted": "#4a5060", "faint": "#62697b",
    "accent": "#385cad", "accent_strong": "#364d87", "accent_soft": "#e2eafa",
    "accent_line": "#728dbb", "on_accent": "#ffffff",
    "good": "#1f7657", "good_soft": "#e4f3eb", "info": "#246387",
    "warning": "#895400", "danger": "#b3261e", "danger_soft": "#fbe9e8",
    "danger_line": "#b26666", "term_bg": "default", "term_text": "#24293a",
}
DARK = {
    "bg": "default", "surface": "default", "surface2": "default",
    "line": "#7787a5", "line_soft": "#4d5671",
    "text": "#f3f4f8", "muted": "#c0c7d9", "faint": "#a4aec5",
    "accent": "#a8dafa", "accent_strong": "#425c9c", "accent_soft": "#334766",
    "accent_line": "#91a9d0", "on_accent": "#ffffff",
    "good": "#8fe0bf", "good_soft": "#263f3c", "info": "#9fdcf8",
    "warning": "#ffcf7a", "danger": "#ffaaa8", "danger_soft": "#4b303c",
    "danger_line": "#99606d", "term_bg": "default", "term_text": "#e3e8f4",
}


def resolve_mode(environ: Mapping[str, str] | None = None) -> str:
    """Respect an explicit override, then the terminal's advertised background."""
    environ = os.environ if environ is None else environ
    requested = environ.get("CHAOSTIC_THEME", "auto").lower().strip()
    if requested in ("light", "dark"):
        return requested
    background = environ.get("COLORFGBG", "").split(";")[-1]
    if background in ("7", "15"):
        return "light"
    if background in ("0", "1", "2", "3", "4", "5", "6", "8"):
        return "dark"
    return "auto"


MODE = resolve_mode()
COLORS = dict(LIGHT if MODE == "light" else DARK)
if MODE == "auto":
    # The default foreground is chosen by the terminal for its actual background.
    for role in ("text", "muted", "faint", "line", "line_soft", "accent",
                 "accent_line", "good", "info", "warning", "danger",
                 "danger_line", "term_text"):
        COLORS[role] = "default"

THEME = Theme(
    {
        # --- semantic roles -------------------------------------------------
        "brand.accent": f"bold {COLORS['accent']}",
        "brand.title": f"bold {COLORS['text']}",
        "brand.white": f"bold {COLORS['text']}",
        "brand.muted": COLORS["muted"],
        "brand.faint": COLORS["faint"],
        "brand.ok": f"bold {COLORS['good']}",
        "brand.warn": f"bold {COLORS['warning']}",
        "brand.info": f"bold {COLORS['info']}",
        "brand.danger": f"bold {COLORS['danger']}",
        "brand.command": COLORS["accent"],
        "brand.dim": COLORS["line"],
        # Badge roles retain the terminal background.
        "brand.badge.ok": f"bold {COLORS['good']}",
        "brand.badge.warn": f"bold {COLORS['warning']}",
        "brand.badge.bad": f"bold {COLORS['danger']}",
        "brand.badge.info": f"bold {COLORS['info']}",
        # --- legacy aliases (existing call sites keep working, re-skinned) --
        "brand.red": f"bold {COLORS['accent']}",
        "brand.red_soft": COLORS["accent_line"],
        "brand.dark": COLORS["bg"],
        "bright_red": f"bold {COLORS['danger']}",
        "bright_yellow": f"bold {COLORS['warning']}",
        "green": f"bold {COLORS['good']}",
    }
)


def dot(style="brand.ok"):
    """A small status dot, like the mockup's LIVE / ACTIVE indicators."""
    return f"[{style}]●[/{style}]"
