"""Jetons visuels du bureau et thèmes clair/sombre commutables à chaud.

Toute l'app est stylée par ce QSS global construit à partir de jetons ; changer
de palette ici (ou via set_mode) restyle toute l'application. Un seul accent
(orange). Les widgets peints à la main lisent COLORS, mis à jour à chaque bascule.
"""
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication
from pathlib import Path

LIGHT = dict(
    BG="#edf0f4", SURFACE="#ffffff", SURFACE2="#fbfcfe", LINE="#d9dee6", LINE_SOFT="#eef0f5",
    TEXT="#12141a", MUTED="#5b6472", FAINT="#7c8494",
    ACCENT="#ea580c", ACCENT_STRONG="#c2410c", ACCENT_PRESSED="#b23a09",
    ACCENT_SOFT="#fff1e6", ACCENT_LINE="#f6c9a8",
    GOOD="#16a34a", GOOD_SOFT="#e7f6ec", HOVER="#e9eef7", NAV_HOVER="#e7ecf5",
    TERM_BG="#ffffff", TERM_TEXT="#1f2937", SCROLL="#d3d8e2", SCROLL_HOVER="#b9c0cd",
    DISABLED_BG="#eef0f4", DISABLED_TEXT="#aab0ba",
    DANGER="#dc2626", DANGER_SOFT="#fdecec", DANGER_LINE="#f3c9c9",
)
DARK = dict(
    BG="#0f1216", SURFACE="#171b21", SURFACE2="#1b2027", LINE="#2a2f38", LINE_SOFT="#22272f",
    TEXT="#e7eaf0", MUTED="#98a1af", FAINT="#6b7280",
    ACCENT="#f97316", ACCENT_STRONG="#fb8c3c", ACCENT_PRESSED="#ea580c",
    ACCENT_SOFT="#2a1a10", ACCENT_LINE="#6b3d1c",
    GOOD="#34d399", GOOD_SOFT="#16261c", HOVER="#232a33", NAV_HOVER="#1d232b",
    TERM_BG="#0c1015", TERM_TEXT="#c9d3e0", SCROLL="#333a45", SCROLL_HOVER="#48505c",
    DISABLED_BG="#171b21", DISABLED_TEXT="#5a6270",
    DANGER="#f87171", DANGER_SOFT="#2a1618", DANGER_LINE="#5a2a2a",
)

# Palette active + copie « à plat » pour les widgets peints (hud.py lit COLORS).
MODE = "light"
COLORS = dict(LIGHT)

DISPLAY = "Segoe UI"
MONO = "Consolas"
BODY = "Segoe UI"
_FONT_DIR = Path(__file__).parent / "assets" / "fonts"

_QSS = """
        QWidget { color: __TEXT__; }
        QMainWindow, QDialog { background: __BG__; }
        QWidget#sidebar { background: __SURFACE__; border-right: 1px solid __LINE__; }
        QFrame#card { background: __SURFACE__; border: 1px solid __LINE__; border-radius: 14px; }
        QFrame#cmdcard { background: __SURFACE2__; border: 1px solid __LINE__; border-radius: 10px; }
        QLabel { background: transparent; border: none; }
        QLabel#muted { color: __MUTED__; }
        QLabel#eyebrow { color: __FAINT__; font-family: '__DISPLAY__'; font-size: 10px; font-weight: 800; letter-spacing: 1.4px; }
        QLabel#pageTitle { font-family: '__DISPLAY__'; font-size: 24px; font-weight: 800; color: __TEXT__; }
        QLabel#sectionTitle { font-size: 16px; font-weight: 700; color: __TEXT__; }
        QLabel#number { font-family: '__DISPLAY__'; font-size: 28px; font-weight: 800; color: __TEXT__; }
        QLabel#badge { background: __GOOD_SOFT__; color: __GOOD__; border: 1px solid __GOOD__; border-radius: 11px; padding: 6px 12px; font-family: '__DISPLAY__'; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
        QLabel#cmdlabel { color: __ACCENT__; font-family: '__MONO__', 'Cascadia Code', Consolas, monospace; font-size: 13px; background: transparent; }
        QLabel#heroTag { color:__ACCENT__; font-family:'__DISPLAY__'; font-size:10px; font-weight:800; letter-spacing:1.4px; }
        QLabel#heroTitle { color:__TEXT__; font-family:'__DISPLAY__'; font-size:28px; font-weight:800; }
        QLabel#heroDesc { color:__MUTED__; font-size:14px; }

        QPushButton { background: __SURFACE__; color: __TEXT__; border: 1px solid __LINE__; border-radius: 10px; padding: 10px 15px; font-weight: 600; min-height: 18px; }
        QPushButton:hover { background: __HOVER__; border-color: __ACCENT_LINE__; }
        QPushButton:pressed { background: __LINE_SOFT__; }
        QPushButton:focus, QLineEdit:focus, QComboBox:focus, QTableWidget:focus { border: 1px solid __ACCENT__; }
        QPushButton:disabled { color: __DISABLED_TEXT__; background: __DISABLED_BG__; border-color: __LINE_SOFT__; }
        QPushButton#primary { background: __ACCENT__; border: 1px solid __ACCENT__; color: #ffffff; font-weight: 700; }
        QPushButton#primary:hover { background: __ACCENT_STRONG__; border-color: __ACCENT_STRONG__; }
        QPushButton#primary:pressed { background: __ACCENT_PRESSED__; }
        QPushButton#primary:disabled { background: __ACCENT_SOFT__; border-color: __ACCENT_SOFT__; color: __FAINT__; }
        QPushButton#danger { background: __SURFACE__; color: __DANGER__; border-color: __DANGER_LINE__; }
        QPushButton#danger:hover { background: __DANGER_SOFT__; border-color: __DANGER__; }
        QPushButton#danger:disabled { background: __DISABLED_BG__; color: __DISABLED_TEXT__; border-color: __LINE_SOFT__; }
        QPushButton#ghost { background: __SURFACE__; border: 1px solid __LINE__; color: __TEXT__; }
        QPushButton#ghost:hover { background: __HOVER__; border-color: __ACCENT_LINE__; }
        QPushButton#nav { text-align: left; border: 1px solid transparent; background: transparent; color: __MUTED__; padding: 11px 12px; font-weight: 600; border-radius: 9px; }
        QPushButton#nav:hover { background: __NAV_HOVER__; color: __TEXT__; }
        QPushButton#nav:checked { background: __ACCENT_SOFT__; color: __ACCENT__; font-weight: 700; }
        QPushButton#nav:focus { border: 1px solid __ACCENT__; }
        QPushButton#mission { text-align:left; background:__SURFACE__; border:1px solid __LINE__; border-radius:14px; padding:20px; font-family:'__DISPLAY__'; font-size:13px; min-height:80px; color:__TEXT__; }
        QPushButton#mission:hover { background:__HOVER__; border-color:__ACCENT_LINE__; }
        QPushButton#mission:pressed { background:__LINE_SOFT__; }
        QDialogButtonBox QPushButton { min-width:88px; }

        QLineEdit, QComboBox { background: __SURFACE__; border: 1px solid __LINE__; border-radius: 10px; padding: 10px 12px; min-height: 18px; color: __TEXT__; selection-background-color: __ACCENT_LINE__; selection-color: __TEXT__; }
        QLineEdit:hover, QComboBox:hover { border-color: __ACCENT_LINE__; }
        QComboBox::drop-down { width: 26px; border: none; }
        QComboBox QAbstractItemView { background: __SURFACE__; selection-background-color: __ACCENT_SOFT__; selection-color: __TEXT__; padding: 5px; border: 1px solid __LINE__; outline: 0; }

        QListWidget { background: __SURFACE__; border: 1px solid __LINE__; border-radius: 12px; padding: 8px; outline: 0; }
        QListWidget::item { padding: 12px; border-radius: 8px; border: 1px solid transparent; color: __TEXT__; }
        QListWidget::item:hover { background: __HOVER__; }
        QListWidget::item:selected { background: __ACCENT_SOFT__; border: 1px solid __ACCENT_LINE__; color: __TEXT__; }
        QMenu { background: __SURFACE__; border: 1px solid __LINE__; padding: 6px; border-radius: 10px; color: __TEXT__; }
        QMenu::item { padding: 10px 16px; border-radius: 6px; }
        QMenu::item:selected { background: __ACCENT_SOFT__; }

        QTableWidget { background: __SURFACE__; alternate-background-color: __SURFACE2__; border: 1px solid __LINE__; border-radius: 12px; gridline-color: __LINE_SOFT__; outline: 0; }
        QTableWidget::item { padding: 11px 12px; border-bottom: 1px solid __LINE_SOFT__; color: __TEXT__; }
        QTableWidget::item:hover { background: __HOVER__; }
        QTableWidget::item:selected { background: __ACCENT_SOFT__; color: __TEXT__; }
        QHeaderView::section { background: __SURFACE__; color: __FAINT__; padding: 12px; border: none; border-bottom: 1px solid __LINE__; font-size: 11px; font-weight: 700; letter-spacing: 0.6px; }
        QTableCornerButton::section { background: __SURFACE__; border: none; }

        QPlainTextEdit { background: __TERM_BG__; color: __TERM_TEXT__; border: 1px solid __LINE__; border-radius: 12px; padding: 15px; selection-background-color: __ACCENT_LINE__; selection-color: __TEXT__; font-family: '__MONO__', 'Cascadia Code', Consolas, monospace; font-size: 13px; }
        QScrollBar:vertical { background: transparent; width: 11px; margin: 2px; }
        QScrollBar::handle:vertical { background: __SCROLL__; border-radius: 5px; min-height: 34px; }
        QScrollBar::handle:vertical:hover { background: __SCROLL_HOVER__; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        QScrollBar:horizontal { background: transparent; height: 11px; margin: 2px; }
        QScrollBar::handle:horizontal { background: __SCROLL__; border-radius: 5px; min-width: 34px; }
        QScrollBar::handle:horizontal:hover { background: __SCROLL_HOVER__; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
        QScrollArea { background: transparent; border: none; }
        QCheckBox { spacing: 9px; color: __TEXT__; }
        QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid __SCROLL__; border-radius: 5px; background: __SURFACE__; }
        QCheckBox::indicator:checked { background: __ACCENT__; border-color: __ACCENT__; }
        QToolTip { background: __SURFACE__; color: __TEXT__; border: 1px solid __LINE__; padding: 6px; border-radius: 8px; }
        QProgressBar { background: __LINE_SOFT__; border: none; border-radius: 3px; max-height: 6px; }
        QProgressBar::chunk { background: __ACCENT__; border-radius: 3px; }
        QStatusBar { color: __MUTED__; background: __SURFACE__; border-top: 1px solid __LINE__; }
        QStatusBar::item { border: none; }
        QSplitter::handle { background: transparent; width: 12px; height: 12px; }
"""


def load_fonts():
    """Register the shipped OFL fonts. Safe to call more than once."""
    global DISPLAY, MONO, BODY
    targets = (("Orbitron.ttf", "Orbitron"), ("ShareTechMono-Regular.ttf", "Share Tech Mono"), ("Exo2.ttf", "Exo 2"))
    for filename, want in targets:
        path = _FONT_DIR / filename
        if not path.exists():
            continue
        index = QFontDatabase.addApplicationFont(str(path))
        families = QFontDatabase.applicationFontFamilies(index) if index != -1 else []
        if want in families:
            if want == "Orbitron":
                DISPLAY = want
            elif want == "Share Tech Mono":
                MONO = want
            else:
                BODY = want
    return DISPLAY, MONO, BODY


def _stylesheet(tokens):
    heading = BODY  # titres en Exo 2 (pas d'Orbitron « jeu »)
    css = _QSS
    for key, value in tokens.items():
        css = css.replace("__" + key + "__", value)
    css = css.replace("__DISPLAY__", heading).replace("__MONO__", MONO)
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


def set_mode(app, mode):
    """Bascule clair/sombre à chaud : palette, feuille de style et COLORS."""
    global MODE, COLORS
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
    font = QFont("Segoe UI", 10)
    if BODY != "Segoe UI":
        font.setFamilies(["Segoe UI", BODY])
    app.setFont(font)
    set_mode(app, mode)
