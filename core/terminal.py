"""Single shared console for the whole CLI.

Two rendering paths share one `console` object:

* **Plain terminal** (no tty, or ``prompt_toolkit`` missing) — behaves exactly
  like a themed :class:`rich.console.Console`; panels and prompts are printed
  and read inline.
* **Full-screen TUI** (real tty + ``prompt_toolkit``) — ``core.tui`` owns the
  screen, so Rich output must not be written straight to stdout or it would
  tear the live layout. Instead, between :meth:`begin_screen` and the next
  :meth:`pause`/:meth:`input`, every ``print`` is *recorded* and then surfaced
  inside a scrollable full-screen dialog.

The capture is intentionally transparent: callers keep using ``console.print``
and ``console.input`` the same way on both paths. Nothing here changes what is
shown, only *where* it is drawn.
"""
from __future__ import annotations

import io
import shutil
from contextlib import nullcontext

from rich.console import Console

from core.theme import THEME, COLORS


def _capture_width() -> int:
    try:
        width = shutil.get_terminal_size().columns
    except Exception:
        width = 100
    return max(60, min(width, 120))


class ScreenConsole(Console):
    """Themed console that can buffer its output for the full-screen TUI."""

    def __init__(self):
        super().__init__(theme=THEME, highlight=False, style=f"{COLORS['text']} on {COLORS['bg']}")
        self._title = "Chaostic Tool"
        self._sink: Console | None = None

    # -- capture lifecycle --------------------------------------------------
    @property
    def _capturing(self) -> bool:
        return self._sink is not None

    def _new_sink(self) -> Console:
        return Console(
            theme=THEME,
            file=io.StringIO(),
            record=True,
            width=_capture_width(),
            highlight=False,
            soft_wrap=True,
        )

    def begin_screen(self, title: str = "") -> None:
        """Start buffering output under a page title (TUI path only)."""
        self._title = str(title) or "Chaostic Tool"
        self._sink = self._new_sink()

    def _drain(self) -> str:
        if self._sink is None:
            return ""
        text = self._sink.export_text(styles=False)
        return text.rstrip("\n")

    # -- overridden Console surface ----------------------------------------
    def print(self, *args, **kwargs):
        if self._sink is not None:
            return self._sink.print(*args, **kwargs)
        return super().print(*args, **kwargs)

    def input(self, prompt="", *, markup=True, emoji=True, password=False,
              stream=None):
        if self._sink is not None:
            from core import tui
            content = self._drain()
            answer = tui.input_dialog(str(prompt), content, self._title)
            # Keep capturing for whatever the caller prints next, but clear the
            # text already shown so dialogs don't repeat earlier output.
            self._sink = self._new_sink()
            return answer
        return super().input(prompt, markup=markup, emoji=emoji,
                              password=password, stream=stream)

    def pause(self) -> None:
        """Flush buffered output into a full-screen message, then stop."""
        if self._sink is None:
            return
        from core import tui
        content = self._drain()
        if content.strip():
            tui.message(content, self._title)
        self._sink = None

    def status(self, *args, **kwargs):
        # Live spinners can't share the full-screen surface; swallow quietly.
        if self._sink is not None:
            return nullcontext()
        return super().status(*args, **kwargs)

    def clear(self, *args, **kwargs):
        if self._sink is not None:
            self._sink = self._new_sink()
            return
        return super().clear(*args, **kwargs)


console = ScreenConsole()
