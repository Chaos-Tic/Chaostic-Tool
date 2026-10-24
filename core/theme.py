"""Shared pastel terminal palette for Rich, menus and execution output.

Terminals render solid colors rather than compositor glass. Both palettes use
explicit surfaces so their contrast does not depend on the terminal background.
CHAOSTIC_THEME=light|dark overrides COLORFGBG detection; unknown terminals use dark.
Legacy style aliases are preserved for the existing tool modules.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from rich.theme import Theme

EYEBROW = "CHAOSTICTOOL / LINUX CLI"
EYEBROW_COMPACT = "CHAOSTICTOOL / CLI"

LIGHT = {
    "bg": "#f4f1fa", "surface": "#ffffff", "surface2": "#eeedf7",
    "line": "#a3aec7", "line_soft": "#d4d5e5",
    "text": "#151820", "muted": "#4a5060", "faint": "#62697b",
    "accent": "#385cad", "accent_strong": "#364d87", "accent_soft": "#e2eafa",
    "accent_line": "#728dbb", "on_accent": "#ffffff",
    "good": "#1f7657", "good_soft": "#e4f3eb", "info": "#246387",
    "warning": "#895400", "danger": "#b3261e", "danger_soft": "#fbe9e8",
    "danger_line": "#b26666", "term_bg": "#fafbff", "term_text": "#24293a",
}
DARK = {
    "bg": "#191d30", "surface": "#252b42", "surface2": "#2c324b",
    "line": "#7787a5", "line_soft": "#4d5671",
    "text": "#f3f4f8", "muted": "#c0c7d9", "faint": "#a4aec5",
    "accent": "#a8dafa", "accent_strong": "#425c9c", "accent_soft": "#334766",
    "accent_line": "#91a9d0", "on_accent": "#ffffff",
    "good": "#8fe0bf", "good_soft": "#263f3c", "info": "#9fdcf8",
    "warning": "#ffcf7a", "danger": "#ffaaa8", "danger_soft": "#4b303c",
    "danger_line": "#99606d", "term_bg": "#181d30", "term_text": "#e3e8f4",
}


def resolve_mode(environ: Mapping[str, str] | None = None) -> str:
    """Respect an explicit override, then the terminal's advertised background."""
    environ = os.environ if environ is None else environ
    requested = environ.get("CHAOSTIC_THEME", "auto").lower().strip()
    if requested in ("light", "dark"):
        return requested
    background = environ.get("COLORFGBG", "").split(";")[-1]
    return "light" if background in ("7", "15") else "dark"


MODE = resolve_mode()
COLORS = dict(LIGHT if MODE == "light" else DARK)

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
        # badge roles (colored text, no border — Rich can't draw per-cell
        # boxes, so an inline bg wash stands in for the mockup's bordered tag)
        "brand.badge.ok": f"bold {COLORS['good']} on {COLORS['good_soft']}",
        "brand.badge.warn": f"bold {COLORS['warning']} on {COLORS['accent_soft']}",
        "brand.badge.bad": f"bold {COLORS['danger']} on {COLORS['danger_soft']}",
        "brand.badge.info": f"bold {COLORS['info']} on {COLORS['surface2']}",
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
