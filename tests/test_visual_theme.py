"""Visual and keyboard contracts; no command, target or service is executed."""
import asyncio
import unittest
from prompt_toolkit.input import create_pipe_input, DummyInput
from prompt_toolkit.output import DummyOutput
from rich.console import Console
from core.theme import LIGHT, DARK, resolve_mode
from core.tui import MenuScreen
from chaostictool import MAIN_ENTRIES


def luminance(value):
    channels = [int(value[i:i+2], 16) / 255 for i in (1, 3, 5)]
    channels = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return sum(a * b for a, b in zip(channels, (.2126, .7152, .0722)))


class VisualThemeTests(unittest.TestCase):
    def test_explicit_theme_overrides_background_and_unknown_falls_back(self):
        self.assertEqual(resolve_mode({'CHAOSTIC_THEME': 'light', 'COLORFGBG': '15;0'}), 'light')
        self.assertEqual(resolve_mode({'CHAOSTIC_THEME': 'dark', 'COLORFGBG': '0;15'}), 'dark')
        self.assertEqual(resolve_mode({'COLORFGBG': '0;15'}), 'light')
        self.assertEqual(resolve_mode({'COLORFGBG': '0;7'}), 'light')
        self.assertEqual(resolve_mode({'CHAOSTIC_THEME': 'invalid'}), 'dark')
        self.assertEqual(resolve_mode({}), 'dark')

    def test_text_and_selection_contrast_in_both_palettes(self):
        for palette in (LIGHT, DARK):
            for fg, bg in [('text','bg'), ('muted','bg'), ('faint','bg'), ('accent','bg'),
                           ('on_accent','accent_strong'), ('good','good_soft'),
                           ('danger','danger_soft'), ('warning','accent_soft')]:
                a, b = sorted((luminance(palette[fg]), luminance(palette[bg])))
                with self.subTest(palette=palette['bg'], foreground=fg):
                    self.assertGreaterEqual((b + .05) / (a + .05), 4.5)

    def test_home_keeps_numeric_phase_order_and_all_actions(self):
        screen = MenuScreen('Home', MAIN_ENTRIES, home=True, input=DummyInput(), output=DummyOutput())
        self.assertEqual([entry[0] for entry in screen.visible_entries], [str(n) for n in range(1, 11)])
        for width in (80, 116):
            rows, cursor = screen.render_body(width)
            text = '\n'.join(''.join(value for _, value in row) for row in rows)
            for action in ('Configure target', 'Search tools', 'Results & Session', 'Proxy / VPN / Tor', 'Quit'):
                self.assertIn(action, text)
            self.assertLess(cursor, len(rows))
            self.assertNotIn('RED OPS', ''.join(text for _, text in screen._masthead(width)))
            masthead_lines = ''.join(text for _, text in screen._masthead(width)).split('\n')
            self.assertEqual(len(masthead_lines), 9 if width >= 68 else 5)
            for m_line in masthead_lines:
                self.assertEqual(len(m_line), width)
                self.assertIn(m_line[1], ('╭', '│', '╰'))
                self.assertIn(m_line[width - 2], ('╮', '│', '╯'))
                self.assertEqual(m_line[width - 1], ' ')

    def test_keyboard_arrows_and_existing_aliases(self):
        async def choose(keys):
            with create_pipe_input() as pipe:
                screen = MenuScreen('Home', MAIN_ENTRIES, home=True, input=pipe, output=DummyOutput())
                pipe.send_text(keys)
                return await asyncio.wait_for(screen.app.run_async(), timeout=2)
        for keys, expected in [('\x1b[B\r', '2'), ('p', 'p'), ('r', '11'), ('g', '12'), ('/', '__search__'), ('q', '99')]:
            with self.subTest(keys=repr(keys)):
                self.assertEqual(asyncio.run(choose(keys)), expected)
