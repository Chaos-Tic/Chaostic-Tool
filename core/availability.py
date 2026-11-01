"""Single source of truth for tool availability, shared by the CLI and the GUI.

Every tool resolves to one of a few stable states, keyed by an untranslated
constant so the value is safe to store, compare and route through a theme. Each
state carries a short human reason and a *tone* that both front-ends map onto
their own badges/pills, so a tool is never described one way in the terminal and
another in the desktop app.

States (confirmed against live testing):
    ready          binary present and usable
    not_installed  binary not found on PATH / not configured
    needs_key      installed, but its capability is gated behind a missing API key
    blocked        installed/declared but a known failure makes it unusable
"""
from __future__ import annotations

from dataclasses import dataclass

# Stable, never-translated state keys.
READY = "ready"
NOT_INSTALLED = "not_installed"
NEEDS_KEY = "needs_key"
BLOCKED = "blocked"

# state -> tone (ok|warn|bad|info|accent|muted); a front-end turns a tone into a colour.
_TONES = {READY: "ok", NOT_INSTALLED: "bad", NEEDS_KEY: "warn", BLOCKED: "bad"}

# Tools whose primary capability is gated behind a stored API key: when the
# binary is present but the key is missing the tool is NEEDS_KEY, not READY.
# (nmap gates only ONE preset, so it stays READY at tool level — the preset list
# and the flow preview surface that preset's key need on their own.)
KEY_GATED = {"shodan": "shodan", "wpscan": "wpscan", "theharvester": "shodan"}


@dataclass(frozen=True)
class Availability:
    """A tool's resolved availability, understood identically by both UIs."""

    state: str
    label: str = ""   # French source label (an i18n key); shown via T() in the GUI
    tone: str = ""     # overrides the state's default tone when set
    reason: str = ""   # short human "why", e.g. which key to set

    @property
    def ready(self) -> bool:
        return self.state == READY

    @property
    def shade(self) -> str:
        return self.tone or _TONES.get(self.state, "muted")


# --- CLI badge vocabulary ---------------------------------------------------
# Short badge word + brand style per state, read by core.ui / core.tui so the
# terminal reads Ready / Not installed / Needs key / Blocked, not just OK/MISSING.
CLI_BADGE = {
    READY: ("READY", "brand.badge.ok"),
    NOT_INSTALLED: ("MISSING", "brand.badge.bad"),
    NEEDS_KEY: ("NEEDS KEY", "brand.badge.warn"),
    BLOCKED: ("BLOCKED", "brand.badge.bad"),
}
# Row-accent style per state for the menu key column.
CLI_ROW_STYLE = {READY: "brand.ok", NOT_INSTALLED: "brand.danger",
                 NEEDS_KEY: "brand.warn", BLOCKED: "brand.danger"}


def key_present(key_id: str) -> bool:
    """True when an API key is stored for ``key_id`` (safe if the store is absent)."""
    if not key_id:
        return False
    try:
        from core import api_keys
        return bool(api_keys.get(key_id))
    except Exception:
        return False


def for_cli(tool_key: str, tool: dict, installed: bool) -> Availability:
    """Availability of a CLI tool, given whether its binary resolved on PATH."""
    if not installed:
        return Availability(NOT_INSTALLED, reason=f"{tool.get('binary', '')} not found")
    gated = KEY_GATED.get(tool_key)
    if gated and not key_present(gated):
        return Availability(NEEDS_KEY, reason=f"set the {gated} API key (menu: k)")
    return Availability(READY)


def preset_key_missing(preset) -> str | None:
    """The API-key id a preset needs but that is not stored yet, else None."""
    need = preset.get("needs_key") if isinstance(preset, dict) else None
    return need if need and not key_present(need) else None
