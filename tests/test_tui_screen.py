"""Full-screen dialog colours and the session-wide alternate screen.

Headless checks only: the captured Rich output keeps its ANSI colours, the
dialog still scrolls on the plain text, and the alternate screen is entered and
left exactly once per session on a recording Output. What a real terminal
shows (no flash between screens, actual colours) still needs a hands-on run.
"""
import unittest
from unittest.mock import patch

from core.terminal import ScreenConsole

try:
    from prompt_toolkit.formatted_text import to_formatted_text
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
except ImportError:  # pragma: no cover - the plain path has its own tests
    DummyOutput = None

from core import tui


class DrainTests(unittest.TestCase):
    def test_drain_keeps_ansi_colours_and_plain_text_stays_measurable(self):
        console = ScreenConsole()
        console.begin_screen("Demo")
        console.print("[bold #ff0000]ALERT[/bold #ff0000] secret-free body")
        drained = console._drain()
        self.assertIn("\x1b[1;38;2;255;0;0mALERT\x1b[0m", drained)
        self.assertEqual(tui.plain(drained), "ALERT secret-free body")

    def test_plain_console_path_is_unchanged(self):
        console = ScreenConsole()
        self.assertFalse(console._capturing)
        self.assertEqual(console._drain(), "")


@unittest.skipUnless(DummyOutput, "prompt_toolkit required")
class DialogTests(unittest.TestCase):
    def test_dialog_scrolls_on_plain_lines_and_renders_colours(self):
        content = "\n".join(f"\x1b[1;38;2;64;186;240mline {i}\x1b[0m" for i in range(30))
        with create_pipe_input() as pipe:
            screen = tui.DialogScreen("Prompt", content, "Title", input=pipe, output=DummyOutput())
            self.assertEqual(len(screen.lines), 30)
            self.assertEqual(screen.lines[0], "line 0")
            self.assertEqual(screen.scroll, 18)
            fragments = to_formatted_text(screen.body.content.text)
            self.assertIn("#40baf0", fragments[0][0])
            self.assertNotIn("\x1b", "".join(text for _, text in fragments))
            pipe.send_text("\r")
            self.assertEqual(screen.run(), "")

    def test_dialog_without_escapes_keeps_plain_body(self):
        with create_pipe_input() as pipe:
            screen = tui.DialogScreen("Prompt", "[bold]markup[/bold] body", input=pipe, output=DummyOutput())
            self.assertEqual(screen.body.content.text(), "markup body")


if DummyOutput:
    class _RecordingOutput(DummyOutput):
        """Counts the real enter/quit calls, like a terminal would see them."""
        def __init__(self):
            self.enters = self.quits = 0

        def enter_alternate_screen(self):
            self.enters += 1

        def quit_alternate_screen(self):
            self.quits += 1


@unittest.skipUnless(DummyOutput, "prompt_toolkit required")
class SessionScreenTests(unittest.TestCase):
    def setUp(self):
        self.output = _RecordingOutput()
        self.pipe = self.enterContext(create_pipe_input())
        for item in (patch.object(tui, "available", return_value=True),
                     patch.object(tui, "create_output", return_value=self.output),
                     patch.object(tui, "create_input", return_value=self.pipe)):
            self.enterContext(item)

    def _message(self, text):
        self.pipe.send_text("\r")
        tui.message(text, "Title")

    def test_alternate_screen_is_entered_and_left_once_for_several_screens(self):
        with tui.session_screen():
            self.assertEqual((self.output.enters, self.output.quits), (1, 0))
            self._message("first")
            self._message("second")
            self.assertEqual((self.output.enters, self.output.quits), (1, 0))
        self.assertEqual((self.output.enters, self.output.quits), (1, 1))
        self.assertIsNone(tui._SESSION_OUTPUT)

    def test_crash_and_interrupt_still_restore_the_normal_screen(self):
        for error in (RuntimeError, KeyboardInterrupt, SystemExit):
            self.output.enters = self.output.quits = 0
            with self.subTest(error=error.__name__), self.assertRaises(error), tui.session_screen():
                self._message("body")
                raise error()
            self.assertEqual((self.output.enters, self.output.quits), (1, 1))
            self.assertFalse("enter_alternate_screen" in vars(self.output))

    def test_suspend_gives_the_normal_screen_back_then_returns(self):
        with tui.session_screen():
            with tui.suspend_screen():
                self.assertEqual((self.output.enters, self.output.quits), (1, 1))
            self.assertEqual((self.output.enters, self.output.quits), (2, 1))
            self._message("after suspend")
        self.assertEqual((self.output.enters, self.output.quits), (2, 2))

    def test_plain_path_is_a_no_op(self):
        with patch.object(tui, "available", return_value=False), \
                patch.object(tui, "create_output", side_effect=AssertionError("must not create an output")):
            with tui.session_screen(), tui.suspend_screen():
                pass
            self.assertEqual((self.output.enters, self.output.quits), (0, 0))


if __name__ == "__main__":
    unittest.main()
