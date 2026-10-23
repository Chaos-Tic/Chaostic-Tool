"""Jetons visuels du bureau et thèmes clair/sombre commutables à chaud.

Toute l'app est stylée par ce QSS global construit à partir de jetons ; changer
de palette ici (ou via set_mode) restyle toute l'application. Surfaces Liquid Glass et accents bleu/lilas. Les widgets peints à la main lisent COLORS, mis à jour à chaque bascule.
"""
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication
from pathlib import Path

LIGHT = dict(
    BG="#f4f1fa", SURFACE="#ffffff", SURFACE2="#f0edf7", LINE="#d4d5e5", LINE_SOFT="#e7e5f0",
    TEXT="#151820", MUTED="#4a5060", FAINT="#62697b",
    ACCENT="#385cad", ACCENT_STRONG="#364d87", ACCENT_PRESSED="#293d70",
    ACCENT_SOFT="#e2eafa", ACCENT_LINE="#a5bce5",
    GOOD="#1f7657", INFO="#246387", WARNING="#895400", GOOD_SOFT="#e4f3eb", HOVER="#eef2fc", NAV_HOVER="#eaeef8",
    TERM_BG="#fafbff", TERM_TEXT="#24293a", SCROLL="#bec5d8", SCROLL_HOVER="#919db8",
    DISABLED_BG="#e9eaf1", DISABLED_TEXT="#6d7384",
    DANGER="#b3261e", DANGER_SOFT="#fbe9e8", DANGER_LINE="#e7b5b2",
    ENV_START="#fbefe8", ENV_MIDDLE="#eef0fb", ENV_END="#f1e8fa", RIM="#ffffff",
)
DARK = dict(
    BG="#191d30", SURFACE="#252b42", SURFACE2="#2c324b", LINE="#4d5671", LINE_SOFT="#353d57",
    TEXT="#f3f4f8", MUTED="#c0c7d9", FAINT="#a4aec5",
    ACCENT="#a8dafa", ACCENT_STRONG="#425c9c", ACCENT_PRESSED="#354a81",
    ACCENT_SOFT="#334766", ACCENT_LINE="#6e88b4",
    GOOD="#8fe0bf", INFO="#9fdcf8", WARNING="#ffcf7a", GOOD_SOFT="#263f3c", HOVER="#37415c", NAV_HOVER="#303b56",
    TERM_BG="#181d30", TERM_TEXT="#e3e8f4", SCROLL="#53617e", SCROLL_HOVER="#7285a5",
    DISABLED_BG="#252b3c", DISABLED_TEXT="#a4aec5",
    DANGER="#ffaaa8", DANGER_SOFT="#4b303c", DANGER_LINE="#99606d",
    ENV_START="#17182a", ENV_MIDDLE="#141a2a", ENV_END="#1d1630", RIM="#727e9b",
)

# Palette active + copie « à plat » pour les widgets peints (hud.py lit COLORS).
MODE = "light"
REDUCED_TRANSPARENCY = False
COLORS = dict(LIGHT)

DISPLAY = "Segoe UI"
MONO = "Consolas"
BODY = "Segoe UI"

_QSS = """
        QWidget { color: __TEXT__; }
        QMainWindow, QDialog { background: __BG__; }
        QWidget#sidebar { background: __GLASS__; border: 1px solid __RIM__; border-radius: 22px; }
        QFrame#card { background: transparent; border: none; }
        QFrame#cmdcard { background: __SURFACE2__; border: 1px solid __LINE__; border-radius: 12px; }
        QLabel { background: transparent; border: none; }
        QLabel#muted { color: __MUTED__; }
        QLabel#eyebrow { color: __FAINT__; font-family: '__DISPLAY__'; font-size: 11px; font-weight: 500; letter-spacing: 1.1px; }
        QLabel#pageTitle { font-family: '__DISPLAY__'; font-size: 21px; font-weight: 700; color: __TEXT__; }
        QLabel#sectionTitle { font-size: 15px; font-weight: 600; color: __TEXT__; }
        QLabel#number { font-family: '__DISPLAY__'; font-size: 28px; font-weight: 800; color: __TEXT__; }
        QLabel#badge { background: __GOOD_SOFT__; color: __GOOD__; border: 1px solid __GOOD__; border-radius: 12px; padding: 6px 12px; font-family: '__DISPLAY__'; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
        QLabel#cmdlabel { color: __ACCENT__; font-family: '__MONO__', 'Cascadia Code', Consolas, monospace; font-size: 13px; background: transparent; }
        QLabel#heroTag { color:__ACCENT__; font-family:'__DISPLAY__'; font-size:11px; font-weight:500; letter-spacing:1.1px; }
        QLabel#heroTitle { color:__TEXT__; font-family:'__DISPLAY__'; font-size:30px; font-weight:800; }
        QLabel#heroDesc { color:__MUTED__; font-size:14px; }

        QPushButton { background: __SURFACE__; color: __TEXT__; border: 1px solid __LINE__; border-radius: 12px; padding: 10px 15px; font-weight: 600; min-height: 18px; }
        QPushButton:hover { background: __HOVER__; border-color: __ACCENT_LINE__; }
        QPushButton:pressed { background: __LINE_SOFT__; }
        QPushButton:focus, QLineEdit:focus, QComboBox:focus, QTableWidget:focus { border: 1px solid __ACCENT__; }
        QPushButton:disabled { color: __DISABLED_TEXT__; background: __DISABLED_BG__; border-color: __LINE_SOFT__; }
        QPushButton#primary { background: __ACCENT_STRONG__; border: 1px solid __ACCENT_STRONG__; color: #ffffff; font-weight: 700; }
        QPushButton#primary:hover { background: __ACCENT_STRONG__; border-color: __ACCENT_STRONG__; }
        QPushButton#primary:pressed { background: __ACCENT_PRESSED__; }
        QPushButton#primary:disabled { background: __ACCENT_SOFT__; border-color: __ACCENT_SOFT__; color: __FAINT__; }
        QPushButton#danger { background: __SURFACE__; color: __DANGER__; border-color: __DANGER_LINE__; }
        QPushButton#danger:hover { background: __DANGER_SOFT__; border-color: __DANGER__; }
        QPushButton#danger:disabled { background: __DISABLED_BG__; color: __DISABLED_TEXT__; border-color: __LINE_SOFT__; }
        QPushButton#ghost { background: __SURFACE__; border: 1px solid __LINE__; color: __TEXT__; }
        QPushButton#ghost:hover { background: __HOVER__; border-color: __ACCENT_LINE__; }
        QPushButton#nav { text-align: left; border: 1px solid transparent; background: transparent; color: __MUTED__; padding: 11px 12px; font-weight: 600; border-radius: 12px; }
        QPushButton#nav:hover { background: __NAV_HOVER__; color: __TEXT__; }
        QPushButton#nav:checked { background: __ACCENT_SOFT__; color: __TEXT__; border: 1px solid __ACCENT__; font-weight: 700; }
        QPushButton#nav:focus { border: 1px solid __ACCENT__; }
        QPushButton#mission { text-align:left; background:__SURFACE__; border:1px solid __LINE__; border-radius:12px; padding:12px 16px; font-family:'__DISPLAY__'; font-size:13px; min-height:32px; color:__TEXT__; }
        QPushButton#mission:hover { background:__HOVER__; border-color:__ACCENT_LINE__; }
        QPushButton#mission:pressed { background:__LINE_SOFT__; }
        QDialogButtonBox QPushButton { min-width:88px; }

        QLineEdit, QComboBox { background: __SURFACE__; border: 1px solid __LINE__; border-radius: 12px; padding: 10px 12px; min-height: 18px; color: __TEXT__; selection-background-color: __ACCENT_LINE__; selection-color: __TEXT__; }
        QLineEdit:hover, QComboBox:hover { border-color: __ACCENT_LINE__; }
        QComboBox::drop-down { width: 26px; border: none; }
        QComboBox QAbstractItemView { background: __SURFACE__; selection-background-color: __ACCENT_SOFT__; selection-color: __TEXT__; padding: 5px; border: 1px solid __LINE__; outline: 0; }

        QListWidget { background: __SURFACE__; border: 1px solid __LINE__; border-radius: 12px; padding: 8px; outline: 0; }
        QListWidget::item { padding: 12px; border-radius: 12px; border: 1px solid transparent; color: __TEXT__; }
        QListWidget::item:hover { background: __HOVER__; }
        QListWidget::item:selected { background: __ACCENT_SOFT__; border: 1px solid __ACCENT_LINE__; color: __TEXT__; }
        QMenu { background: __SURFACE__; border: 1px solid __LINE__; padding: 6px; border-radius: 12px; color: __TEXT__; }
        QMenu::item { padding: 10px 16px; border-radius: 6px; }
        QMenu::item:selected { background: __ACCENT_SOFT__; }

        QTableWidget { background: __SURFACE__; alternate-background-color: __SURFACE2__; border: 1px solid __LINE__; border-radius: 12px; gridline-color: __LINE_SOFT__; outline: 0; }
        QTableWidget::item { padding: 11px 12px; border-bottom: 1px solid __LINE_SOFT__; color: __TEXT__; }
        QTableWidget::item:hover { background: __HOVER__; }
        QTableWidget::item:selected { background: __ACCENT_SOFT__; color: __TEXT__; }
        QHeaderView::section { background: __SURFACE2__; color: __FAINT__; padding: 12px; border: none; border-bottom: 1px solid __LINE__; font-size: 11px; font-weight: 700; letter-spacing: 0.6px; }
        QTableCornerButton::section { background: __SURFACE__; border: none; }

        QPlainTextEdit { background: __TERM_BG__; color: __TERM_TEXT__; border: 1px solid __LINE__; border-radius: 12px; padding: 15px; selection-background-color: __ACCENT_LINE__; selection-color: __TEXT__; font-family: '__MONO__', 'Cascadia Code', Consolas, monospace; font-size: 13px; }
        QScrollBar:vertical { background: transparent; width: 11px; margin: 2px; }
        QScrollBar::handle:vertical { background: __SCROLL__; border-radius: 12px; min-height: 34px; }
        QScrollBar::handle:vertical:hover { background: __SCROLL_HOVER__; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        QScrollBar:horizontal { background: transparent; height: 11px; margin: 2px; }
        QScrollBar::handle:horizontal { background: __SCROLL__; border-radius: 12px; min-width: 34px; }
        QScrollBar::handle:horizontal:hover { background: __SCROLL_HOVER__; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
        QScrollArea { background: transparent; border: none; }
        QCheckBox { spacing: 9px; color: __TEXT__; }
        QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid __SCROLL__; border-radius: 12px; background: __SURFACE__; }
        QCheckBox::indicator:checked { background: __ACCENT__; border-color: __ACCENT__; }
        QToolTip { background: __SURFACE__; color: __TEXT__; border: 1px solid __LINE__; padding: 6px; border-radius: 12px; }
        QProgressBar { background: __LINE_SOFT__; border: none; border-radius: 3px; max-height: 6px; }
        QProgressBar::chunk { background: __ACCENT__; border-radius: 3px; }
        QStatusBar { color: __MUTED__; background: __SURFACE__; border-top: 1px solid __LINE__; }
        QStatusBar::item { border: none; }
        QSplitter::handle { background: transparent; width: 12px; height: 12px; }
        QPlainTextEdit#operationConsole { border: none; padding: 10px; }
        QLabel#targetTitle { color: __TEXT__; font-size: 20px; font-weight: 700; }
        QLabel#metricLabel { color: __MUTED__; font-family: '__MONO__'; font-size: 12px; }
        QLabel#metricValue { color: __TEXT__; font-family: '__MONO__'; font-size: 23px; }
        QLabel#sidebarMeta { color: __MUTED__; font-family: '__MONO__'; font-size: 11px; }
        QLabel#brandCaption { color: __MUTED__; font-family: '__MONO__'; font-size: 12px; }
        QPushButton#brandAction { background: __GLASS__; border: 1px solid __LINE__; color: __TEXT__; }
        QPushButton#brandAction:hover { background: __HOVER__; border-color: __ACCENT__; }
        QLabel#heroHeading { font-size: 30px; font-weight: 700; color: __TEXT__; }
        QLabel#heroDescription { font-size: 13px; color: __MUTED__; }
        QScrollArea > QWidget > QWidget { background: transparent; }


"""


def load_fonts():
    """Choose installed sans-serif families without loading decorative fonts."""
    global DISPLAY, MONO, BODY
    available = set(QFontDatabase.families())
    BODY = next((name for name in ("Geist", "Segoe UI Variable Text", "Segoe UI", "Inter", "Cantarell", "Noto Sans") if name in available), QApplication.font().family())
    DISPLAY = BODY
    MONO = next((name for name in ("Cascadia Code", "Consolas", "DejaVu Sans Mono") if name in available), "monospace")
    return DISPLAY, MONO, BODY


def _stylesheet(tokens):
    heading = BODY
    css = _QSS.replace("__GLASS__", glass_css())
    for key, value in tokens.items():
        css = css.replace("__" + key + "__", value)
    css = css.replace("__DISPLAY__", heading).replace("__MONO__", MONO)
    css += "QWidget#hbadge { background: " + tokens['GOOD_SOFT'] + "; border: 1px solid " + tokens['GOOD'] + "; border-radius: 12px; }"
    css += "QLabel#statusDot { background: " + tokens['GOOD'] + "; border-radius: 4px; } QLabel#statusCaption { color: " + tokens['GOOD'] + "; font-size: 11px; }"
    css += "QLabel#pageTitle { font-family: '" + DISPLAY + "'; }"
    css += "QLabel#sessionHost { font-family: '" + MONO + "'; }"
    css += "QLabel#sessionHost { color: " + tokens['TEXT'] + "; font-size: 14px; }"
    css += ('QComboBox::down-arrow { width: 12px; height: 8px; image: url("'
            + (Path(__file__).parent / 'assets/chevron-down.svg').as_posix() + '"); }')
    return css


def _apply_palette(app, t):
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, t["BG"]),
                        (QPalette.ColorRole.WindowText, t["TEXT"]),
                        (QPalette.ColorRole.Base, t["SURFACE"]),
                        (QPalette.ColorRole.AlternateBase, t["SURFACE2"]),
                        (QPalette.ColorRole.Text, t["TEXT"]),
                        (QPalette.ColorRole.Button, t["SURFACE"]),
                        (QPalette.ColorRole.ButtonText, t["TEXT"]),
                        (QPalette.ColorRole.Highlight, t["ACCENT_SOFT"]),
                        (QPalette.ColorRole.HighlightedText, t["TEXT"]),
                        (QPalette.ColorRole.ToolTipBase, t["SURFACE"]),
                        (QPalette.ColorRole.ToolTipText, t["TEXT"]),
                        (QPalette.ColorRole.PlaceholderText, t["FAINT"])):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)


def glass_css():
    if REDUCED_TRANSPARENCY:
        return COLORS["SURFACE"]
    return "rgba(36, 42, 65, 205)" if MODE == "dark" else "rgba(255, 255, 255, 155)"


def set_mode(app, mode, reduced_transparency=None):
    """Bascule clair/sombre à chaud : palette, feuille de style et COLORS."""
    global MODE, COLORS, REDUCED_TRANSPARENCY
    if reduced_transparency is not None:
        REDUCED_TRANSPARENCY = bool(reduced_transparency)
    MODE = "dark" if str(mode).lower() == "dark" else "light"
    tokens = DARK if MODE == "dark" else LIGHT
    COLORS.clear()
    COLORS.update(tokens)
    # Alias pratiques pour les widgets peints à la main.
    COLORS["background"] = tokens["BG"]; COLORS["sidebar"] = tokens["SURFACE"]
    COLORS["surface"] = tokens["SURFACE"]; COLORS["border"] = tokens["LINE"]
    COLORS["text"] = tokens["TEXT"]; COLORS["muted"] = tokens["MUTED"]
    COLORS["accent"] = tokens["ACCENT"]; COLORS["accent_line"] = tokens["ACCENT_LINE"]
    COLORS["good"] = tokens["GOOD"]
    _apply_palette(app, tokens)
    app.setStyleSheet(_stylesheet(tokens))
    for widget in app.topLevelWidgets():
        widget.update()
    return MODE


def apply_theme(app: QApplication, mode="light"):
    app.setStyle("Fusion")
    load_fonts()
    font = QFont(BODY, 10)
    app.setFont(font)
    set_mode(app, mode)
