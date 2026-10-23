"""Check Qt UI in an isolated X server; never connects to targets or updates.

Run with xvfb-run -a -s '-screen 0 1600x1000x24 -nolisten tcp' python scripts/check-native-ui.py
Requires Xvfb and xdotool. A temporary demo profile is used. No scan, installer or network check is started.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from desktop import theme
from desktop.storage import Store
from desktop.window import Window


def main():
    app = QApplication([])
    theme.apply_theme(app)
    if font := os.environ.get("CHAOSTIC_TEST_FONT"):
        theme.BODY = theme.DISPLAY = font
        app.setFont(QFont(font, 10))
    assert app.platformName() == 'xcb', app.platformName()
    results = []
    overflows = []
    with tempfile.TemporaryDirectory(prefix='chaostic-native-') as directory:
        for language in ('en', 'fr'):
            store = Store(Path(directory) / language)
            store.settings.update(language=language, animations=False, check_updates=False)
            store.add_target('https://staging.example.com', 'Demo target')
            window = Window(store)
            window._on_update_result(True, "9.0.0", "https://github.com/Chaos-Tic/Chaostic-Tool/releases", False)
            try:
                for mode in ('light', 'dark'):
                    theme.set_mode(app, mode)
                    for width, height in ((1360, 860), (900, 600)):
                        window.resize(width, height)
                        window.show()
                        app.processEvents()
                        subprocess.run(["xdotool", "windowfocus", str(int(window.winId()))], check=True)
                        QTest.qWait(40)
                        assert window.width() == width and window.height() == height
                        for page in range(7):
                            window.navigate(page)
                            app.processEvents()
                            assert window.stack.currentIndex() == page
                            widget = window.stack.widget(page)
                            # Scroll areas must fit horizontally at the supported minimum.
                            if hasattr(widget, 'horizontalScrollBar'):
                                if widget.horizontalScrollBar().maximum():
                                    overflows.append([language, mode, width, page, widget.horizontalScrollBar().maximum()])
                        window.nav[2].setFocus()
                        QTest.keyClick(window.nav[2], Qt.Key.Key_Space)
                        assert window.stack.currentIndex() == 2
                        assert window.nav[2].hasFocus()
                        results.append([language, mode, width, height])
                window.transparency_toggle.setChecked(True)
                assert theme.REDUCED_TRANSPARENCY
                assert not window.runner.active
            finally:
                window.close()
                window.deleteLater()
                app.processEvents()
    assert not overflows, overflows
    print(json.dumps({'platform': app.platformName(), 'checked': results, 'result': 'OK'}))


if __name__ == '__main__':
    main()
