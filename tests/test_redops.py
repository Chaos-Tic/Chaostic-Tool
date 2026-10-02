"""User-facing contracts for the Red Ops refresh."""
import tempfile
import unittest
from pathlib import Path
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from test_desktop import APP
from desktop import theme
from desktop.storage import Store
from desktop.window import Window


def luminance(value):
    channels=[int(value[i:i+2],16)/255 for i in (1,3,5)]
    channels=[c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4 for c in channels]
    return sum(c*w for c,w in zip(channels,(0.2126,0.7152,0.0722)))


class RedOpsTests(unittest.TestCase):
    def test_readable_text_and_primary_button_in_both_themes(self):
        for palette in (theme.LIGHT,theme.DARK):
            for foreground,background in [('TEXT','SURFACE'),('MUTED','SURFACE'),('FAINT','SURFACE'),('ACCENT','SURFACE'),('GOOD','SURFACE'),('WARNING','SURFACE')]:
                with self.subTest(foreground=foreground,background=background,palette=palette['BG']):
                    a,b=sorted((luminance(palette[foreground]),luminance(palette[background])))
                    self.assertGreaterEqual((b+.05)/(a+.05),4.5)
            self.assertGreaterEqual(1.05/(luminance(palette['ACCENT_STRONG'])+.05),4.5)

    def test_first_launch_dark_and_existing_light_preference_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory));window=Window(store)
            try:
                self.assertEqual(theme.MODE,'dark')
                window.toggle_theme()
                self.assertEqual(Store(store.root).settings['theme'],'light')
            finally:window.close();window.deleteLater();APP.processEvents()

            restored=Window(Store(store.root))
            try:self.assertEqual(theme.MODE,'light')
            finally:restored.close();restored.deleteLater();APP.processEvents()

    def test_french_compact_navigation_works_with_keyboard(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory))
            store.settings.update(language='fr',animations=False)
            window=Window(store);window.resize(900,600);window.show();QTest.qWait(50)
            try:
                self.assertEqual(window.width(),900)
                self.assertEqual(window.height(),600)
                # Custom-painted controls retain ordinary keyboard activation.
                window.nav[2].setFocus()
                QTest.keyClick(window.nav[2],Qt.Key.Key_Space)
                self.assertEqual(window.stack.currentIndex(),2)
                self.assertTrue(window.nav[2].isChecked())
                self.assertTrue(window.nav[2].hasFocus())
                window.navigate(0)
                self.assertEqual(window.stack.widget(0).horizontalScrollBar().maximum(),0)
            finally:window.close();window.deleteLater();APP.processEvents()

    def test_compact_home_keeps_session_and_actions_accessible(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory));store.settings['animations']=False
            store.add_target('https://example.com:8443','Assessment environment')
            window=Window(store);window.resize(900,600);window.show();QTest.qWait(50)
            try:
                self.assertLessEqual(window.width(),900)
                self.assertFalse(window.hero.caption.isVisible())
                self.assertTrue(window.brand_panel.compact)
                self.assertFalse(window.hero.art.isNull())
                self.assertEqual(window.stack.widget(0).horizontalScrollBar().maximum(),0)
                self.assertEqual(window.active_host.text(),'https://example.com:8443/')
                window.toggle_theme();APP.processEvents()
                self.assertEqual(window.active_host.text(),'https://example.com:8443/')
                self.assertFalse(window.runner.active)
            finally:window.close();window.deleteLater();APP.processEvents()
