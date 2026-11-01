"""Keycap command bars: one helper, legible with and without colour."""
import io
import unittest
from unittest.mock import patch

from rich.console import Console
from rich.panel import Panel

from core import ui
from core.theme import THEME

SCOPE = [("e", "enumerate now"), ("t", "turn on"), ("x", "exclude / include subdomains"), ("Enter", "done")]
SCOPE_PLAIN = "[e] enumerate now  ·  [t] turn on  ·  [x] exclude / include subdomains  ·  [Enter] done"


def render(renderable, width=100, **kwargs):
    console = Console(theme=THEME, width=width, file=io.StringIO(), record=True, highlight=False, **kwargs)
    console.print(renderable)
    return console.export_text(styles=False)


class KeyHintsTests(unittest.TestCase):
    def test_plain_text_is_stable_and_lists_every_key_and_label(self):
        bar = ui.key_hints(SCOPE)
        self.assertEqual(bar.plain, SCOPE_PLAIN)
        self.assertEqual(str(bar), SCOPE_PLAIN)
        rendered = render(bar)
        for key, label in SCOPE:
            self.assertIn(f"[{key}] {label}", rendered)

    def test_keycap_tokens_fill_the_pill_and_follow_the_palette(self):
        key = THEME.styles["brand.key"]
        self.assertTrue(key.bold)
        self.assertTrue(key.bgcolor is not None or key.reverse)
        self.assertTrue(THEME.styles["brand.key.danger"].reverse)
        self.assertIn("brand.key.sep", THEME.styles)

    def test_colour_free_rendering_keeps_the_brackets_as_delimiters(self):
        for kwargs in ({"color_system": None}, {"no_color": True, "force_terminal": True}):
            console = Console(theme=THEME, width=100, file=io.StringIO(), record=True, highlight=False, **kwargs)
            console.print(ui.key_hints(SCOPE))
            output = console.export_text(styles=True, clear=False)
            self.assertNotIn("[48;", output)
            self.assertIn("[e] enumerate now", console.export_text(styles=False))

    def test_wraps_between_hints_never_inside_one(self):
        for width in (60, 40):
            lines = [line for line in render(ui.key_hints(SCOPE), width=width).splitlines() if line]
            with self.subTest(width=width):
                self.assertGreater(len(lines), 1)
                for line in lines:
                    self.assertTrue(line.startswith("["), line)
                    self.assertFalse(line.endswith("·"), line)
                    self.assertLessEqual(len(line), width)
                for key, label in SCOPE:
                    self.assertTrue(any(f"[{key}] {label}" in line for line in lines), (key, lines))
        # A single hint wider than the console folds instead of overflowing.
        lines = render(ui.key_hints(SCOPE), width=24).splitlines()
        self.assertTrue(all(len(line) <= 24 for line in lines))
        self.assertIn("[Enter] done", lines)

    def test_composes_in_panels_and_accepts_a_style_override(self):
        bar = ui.key_hints([("x", "export"), ("c", "clean", "brand.key.danger"), ("r/0", "back")])
        rendered = render(Panel(bar), width=50)
        self.assertIn("[c] clean", rendered)
        self.assertIn("[r/0] back", rendered)
        self.assertEqual(bar.hints[1].spans[0].style, "brand.key.danger")

    def test_command_bar_keeps_the_status_bits_above_the_keys(self):
        bar = ui.command_bar([("r/0", "back"), ("ctrl+c", "interrupt")],
                             ["[brand.ok]READY[/brand.ok]", "[brand.faint]target:[/brand.faint] example"])
        lines = render(bar).splitlines()
        self.assertEqual(lines[0], "READY / target: example")
        self.assertEqual(lines[1], "[r/0] back  ·  [ctrl+c] interrupt")
        self.assertIs(ui.command_bar([("99", "quit")]).__class__, ui.KeyHints)

    def test_menu_footer_uses_keycaps_for_its_controls(self):
        console = Console(theme=THEME, width=100, file=io.StringIO(), record=True, highlight=False)
        with patch.object(ui.tui, "available", return_value=False), \
                patch.object(ui, "console", console), patch.object(console, "input", return_value="r"):
            self.assertEqual(ui.menu("Demo", [("1", "One", "brand.accent", "first")], footer_extra=["ctx"]), "r")
            ui.menu("Home", [("1", "One", "brand.accent", "first")], show_back=False)
        text = console.export_text(styles=False)
        self.assertIn("READY / ctx", text)
        self.assertIn("[r/0] back  ·  [ctrl+c] interrupt", text)
        self.assertIn("[99] quit  ·  [ctrl+c] interrupt", text)


if __name__ == "__main__":
    unittest.main()
