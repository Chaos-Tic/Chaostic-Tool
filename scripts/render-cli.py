"""Render a synthetic CLI home preview without running a tool or startup checks.

CHAOSTIC_THEME=light|dark python scripts/render-cli.py [output.svg]
Only Rich and prompt_toolkit are needed. Run once per palette in a fresh process.
"""
from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from rich.console import Console
from rich.text import Text
from rich.terminal_theme import TerminalTheme
from core.theme import COLORS, MODE
from core.tui import MenuScreen, _style
from chaostictool import MAIN_ENTRIES


def render(destination: Path) -> None:
    screen = MenuScreen("Main menu", MAIN_ENTRIES, home=True,
                        metrics=[("Target", "staging.example.com"), ("Route", "DEMO / NOT CHECKED"),
                                 ("Tools", "Demo catalog"), ("Results", "3 sample records")],
                        footer_extra=["DEMO", "No operation started"],
                        input=DummyInput(), output=DummyOutput())
    os.environ["TERM"] = "xterm-256color"  # synthetic renderer, not the user shell
    width = 116
    screen.width = width
    styles = dict(_style().style_rules)
    base = f"{COLORS['text']} on {COLORS['bg']}"
    canvas = Console(file=io.StringIO(), width=width, record=True,
                     color_system="truecolor", force_terminal=True, style=base)

    def line(fragments):
        text = Text()
        for name, value, *_ in fragments:
            rule = styles.get(name.removeprefix("class:"), "")
            text.append(value, style=rule.replace("bg:", "on "))
        return text

    canvas.print(line(screen._masthead(width)))
    canvas.print()
    rows, _ = screen.render_body(width)
    for row in rows:
        canvas.print(line(row))
    canvas.print()
    canvas.print(line(screen._footer()))
    rgb = lambda key: tuple(int(COLORS[key][i:i+2], 16) for i in (1, 3, 5))
    terminal = TerminalTheme(rgb("bg"), rgb("text"), [rgb("text")] * 8, [rgb("accent")] * 8)
    destination.parent.mkdir(parents=True, exist_ok=True)
    svg = canvas.export_svg(title="ChaosticTool · CLI · demo", theme=terminal)
    svg = re.sub(r"@font-face\s*\{.*?\}", "", svg, flags=re.S)
    svg = svg.replace("Fira Code", "DejaVu Sans Mono")
    destination.write_text(svg, encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    render(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / f"docs/images/cli-{MODE}.svg")
