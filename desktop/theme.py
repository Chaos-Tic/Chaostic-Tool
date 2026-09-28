"""Shared desktop visual tokens and component states."""
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication
from pathlib import Path

COLORS = dict(background="#080d10", sidebar="#0b1115", surface="#132126", raised="#1b3035",
              border="#365055", text="#e9f1eb", muted="#a6babd", red="#e5ee36", green="#63e6b5")

# Bundled display / mono families (loaded from assets/fonts). Fall back to system
# fonts if a file is missing so the app still runs.
DISPLAY = "Segoe UI"
MONO = "Consolas"
BODY = "Segoe UI"
_FONT_DIR = Path(__file__).parent / "assets" / "fonts"


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


def apply_theme(app: QApplication):
    app.setStyle("Fusion")
    load_fonts()
    font = QFont("Segoe UI", 10)
    # Ship Exo 2 as a fallback so text never tofus on a machine without Segoe UI;
    # Windows still resolves Segoe UI first.
    if BODY != "Segoe UI":
        font.setFamilies(["Segoe UI", BODY])
    app.setFont(font)
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, COLORS["background"]),
                        (QPalette.ColorRole.WindowText, COLORS["text"]),
                        (QPalette.ColorRole.Base, COLORS["sidebar"]),
                        (QPalette.ColorRole.AlternateBase, COLORS["surface"]),
                        (QPalette.ColorRole.Text, COLORS["text"]),
                        (QPalette.ColorRole.Button, COLORS["raised"]),
                        (QPalette.ColorRole.ButtonText, COLORS["text"]),
                        (QPalette.ColorRole.Highlight, QColor("#643044")),
                        (QPalette.ColorRole.HighlightedText, COLORS["text"])):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(("""
        QWidget { color: #edf2ff; }
        QMainWindow, QDialog { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #080b19, stop:0.6 #0c1024, stop:1 #16102e); }
        QWidget#sidebar { background: #0b1022; border-right: 1px solid #20293a; }
        QFrame#card { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #192442, stop:1 #10192e); border: 1px solid #2b3550; border-radius: 14px; }
        QFrame#cmdcard { background: #080e20; border: 1px solid #2b3550; border-radius: 10px; }
        QLabel { background: transparent; border: none; }
        QLabel#muted { color: #a7b6d2; }
        QLabel#eyebrow { color: #7f8ba3; font-family: '__DISPLAY__'; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
        QLabel#pageTitle { font-family: '__DISPLAY__'; font-size: 23px; font-weight: 800; letter-spacing: 1px; }
        QLabel#sectionTitle { font-size: 17px; font-weight: 700; }
        QLabel#number { font-family: '__DISPLAY__'; font-size: 34px; font-weight: 900; color: #ffffff; letter-spacing: 1px; }
        QLabel#badge { background: #142a24; color: #63e6b5; border: 1px solid #2c5b4b; border-radius: 11px; padding: 6px 12px; font-family: '__DISPLAY__'; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
        QLabel#cmdlabel { color: #8de6ef; font-family: '__MONO__', 'Cascadia Code', Consolas, monospace; font-size: 13px; background: transparent; }
        QPushButton { background: #17203a; border: 1px solid #344367; border-radius: 8px; padding: 9px 15px; font-weight: 600; min-height: 18px; }
        QPushButton:hover { background: #253248; border-color: #5f6f8c; }
        QPushButton:pressed { background: #121824; }
        QPushButton:focus, QLineEdit:focus, QComboBox:focus, QTableWidget:focus { border: 1px solid #b69bff; }
        QPushButton:disabled { color: #697589; background: #131a25; border-color: #253043; }
        QPushButton#primary { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9870f6, stop:1 #6441d1); border: 1px solid #b397ff; color: #ffffff; font-weight: 700; }
        QPushButton#primary:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #af8aff, stop:1 #7a51e5); border-color: #d0bcff; }
        QPushButton#primary:pressed { background: #5c36c3; }
        QPushButton#primary:disabled { background: #30274d; border-color: #30274d; color: #9488b0; }
        QPushButton#danger { background: #3a2029; color: #ff9aa8; border-color: #7c4253; }
        QPushButton#danger:hover { background: #4a2733; border-color: #a3556b; }
        QPushButton#danger:disabled { background: #121a30; color: #697589; border-color: #253043; }
        QPushButton#ghost { background: transparent; border: 1px solid #344367; color: #c6d0e0; }
        QPushButton#ghost:hover { background: #1a2230; border-color: #5f6f8c; }
        QListWidget { background: #0c1327; border: 1px solid #293755; border-radius: 10px; padding: 8px; }
        QListWidget::item { padding: 12px; border-radius: 8px; border: 1px solid transparent; }
        QListWidget::item:hover { background: #141d2a; }
        QListWidget::item:selected { background: #242342; border: 1px solid #675594; color: #edf2ff; }
        QMenu { background: #101930; border: 1px solid #344367; padding: 6px; border-radius: 8px; }
        QMenu::item { padding: 10px 16px; border-radius: 6px; }
        QMenu::item:selected { background: #29244b; }
        QPushButton#nav { text-align: left; border: 1px solid transparent; border-left: 3px solid transparent; background: transparent; color: #97a3b8; padding: 11px 12px; font-weight: 600; border-radius: 9px; }
        QPushButton#nav:hover { background: #151d2a; color: #edf2ff; }
        QPushButton#nav:checked { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #35275a, stop:1 #151933); border-left: 3px solid #9b75ff; color: #c8b5ff; }
        QPushButton#nav:focus { border: 1px solid #b69bff; border-left: 3px solid #9b75ff; }
        QLineEdit, QComboBox { background: #0c1327; border: 1px solid #344367; border-radius: 8px; padding: 10px 12px; min-height: 18px; selection-background-color: #554382; }
        QLineEdit:hover, QComboBox:hover { border-color: #4c5a76; }
        QComboBox::drop-down { width: 26px; border: none; }
        QComboBox QAbstractItemView { background: #101930; selection-background-color: #554382; padding: 5px; border: 1px solid #344367; }
        QTableWidget { background: #0c1327; alternate-background-color: #121926; border: 1px solid #293755; border-radius: 10px; gridline-color: #253043; outline: 0; }
        QTableWidget::item { padding: 11px 12px; border-bottom: 1px solid #1c2534; }
        QTableWidget::item:hover { background: #16202e; }
        QTableWidget::item:selected { background: #242442; color: #ffffff; }
        QHeaderView::section { background: #101825; color: #7f8ba3; padding: 12px; border: none; border-bottom: 1px solid #26314a; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
        QPlainTextEdit { background: #070d1d; color: #c7e4f5; border: 1px solid #35456d; border-radius: 10px; padding: 15px; selection-background-color: #554382; font-family: '__MONO__', 'Cascadia Code', Consolas, monospace; font-size: 13px; }
        QScrollBar:vertical { background: transparent; width: 11px; margin: 2px; }
        QScrollBar::handle:vertical { background: #344367; border-radius: 5px; min-height: 34px; }
        QScrollBar::handle:vertical:hover { background: #55647e; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar:horizontal { background: transparent; height: 11px; margin: 2px; }
        QScrollBar::handle:horizontal { background: #344367; border-radius: 5px; min-width: 34px; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        QScrollArea { background: transparent; border: none; }
        QCheckBox { spacing: 9px; color: #b7c2d5; }
        QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #4c5a76; border-radius: 5px; background: #0c1327; }
        QCheckBox::indicator:checked { background: #9b75ff; border-color: #9b75ff; }
        QToolTip { background: #16202e; color: #edf2ff; border: 1px solid #52627c; padding: 6px; border-radius: 6px; }
        QProgressBar { background: #121a30; border: none; border-radius: 3px; max-height: 6px; }
        QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9b75ff, stop:1 #56d9ee); border-radius: 3px; }
        QStatusBar { color: #a7b6d2; background: #0b1022; border-top: 1px solid #20293a; }
        QSplitter::handle { background: transparent; width: 12px; height: 12px; }

        QLabel#heroTag { color:#88d9ec; font-family:'__DISPLAY__'; font-size:10px; letter-spacing:2px; }
        QLabel#heroTitle { color:#f1f3ff; font-family:'__DISPLAY__'; font-size:29px; font-weight:800; }
        QLabel#heroDesc { color:#b2c0e1; font-size:13px; }
        QPushButton#primary { min-height:22px; padding:10px 16px; }
        QLabel#eyebrow { color:#a1b1d1; }
        QTableWidget::item { padding:9px 12px; }
        QPushButton#nav { padding:12px 10px; }
        QDialogButtonBox QPushButton { min-width:85px; }

        /* OPERATION DECK: quiet industrial surfaces, high-contrast actions. */
        QMainWindow, QDialog { background:#080d10; }
        QWidget#sidebar { background:#0b1115; border-right:1px solid #304347; }
        QFrame#card { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #15242a,stop:1 #101b20); border:1px solid #30474d; border-radius:2px; }
        QFrame#cmdcard { background:#0a1317; border:1px solid #30474d; border-radius:2px; }
        QLabel#pageTitle { font-size:24px; color:#ecf1e5; letter-spacing:1px; }
        QLabel#heroTitle { font-size:27px; color:#e5ee36; font-weight:900; }
        QLabel#heroTag { color:#6ee5df; letter-spacing:2px; }
        QLabel#heroDesc { color:#b2c8c8; font-size:14px; }
        QLabel#eyebrow { color:#94b6b9; }
        QLabel#muted { color:#a6babd; }
        QLabel#number { font-size:28px; }
        QPushButton { background:#14252b; color:#e8f1ed; border:1px solid #3d5c61; border-radius:2px; padding:10px 15px; }
        QPushButton:hover { background:#20363d; border-color:#69d7d4; }
        QPushButton:pressed { background:#0b171c; }
        QPushButton#primary { background:#e5ee36; color:#111a1c; border:1px solid #eef66b; border-radius:2px; font-weight:800; }
        QPushButton#primary:hover { background:#f3fa85; color:#0b1115; border-color:#f3fa85; }
        QPushButton#primary:pressed { background:#bbc62e; }
        QPushButton#primary:disabled { background:#333b23; color:#899167; border-color:#444d30; }
        QPushButton#danger { background:#301b21; color:#ff9994; border-color:#b25357; }
        QPushButton#ghost { background:#101e24; color:#8be9e1; border:1px solid #477b7c; border-radius:2px; }
        QPushButton#ghost:hover { background:#20363d; border-color:#8be9e1; }
        QPushButton#nav { border-radius:0; color:#8fabad; padding:14px 10px; border-left:3px solid transparent; }
        QPushButton#nav:hover { background:#16282d; color:#dcebe9; }
        QPushButton#nav:checked { background:#202b20; color:#e5ee36; border:1px solid #4c5730; border-left:3px solid #e5ee36; }
        QPushButton#nav:focus { border:1px solid #a6bd63; border-left:3px solid #e5ee36; }
        QPushButton#mission { text-align:left; background:#142329; border:1px solid #416369; border-radius:0; padding:20px; font-family:'__DISPLAY__'; font-size:13px; min-height:85px; }
        QPushButton#mission:hover { background:#23372e; border-color:#d0dc56; color:#f0f791; }
        QPushButton#mission:pressed { background:#101e22; }
        QLineEdit, QComboBox { background:#0c191f; border:1px solid #3c5b62; border-radius:2px; color:#e6efeb; selection-background-color:#35565a; }
        QComboBox QAbstractItemView { background:#102128; selection-background-color:#35565a; border:1px solid #3c5b62; }
        QPushButton:focus, QLineEdit:focus, QComboBox:focus, QTableWidget:focus { border:1px solid #e5ee36; }
        QTableWidget { background:#0e191e; alternate-background-color:#132329; border:1px solid #30474d; border-radius:0; gridline-color:#233c40; }
        QTableWidget::item { border-bottom:1px solid #23383d; }
        QTableWidget::item:hover { background:#1a3036; }
        QTableWidget::item:selected { background:#2c443d; color:#f3f8db; }
        QHeaderView::section { background:#17272d; color:#95b7bb; border-bottom:1px solid #476064; }
        QPlainTextEdit { background:#091216; border:1px solid #3b5c65; border-radius:0; color:#c7e7e1; selection-background-color:#35565a; }
        QListWidget { background:#0e191e; border:1px solid #30474d; border-radius:0; }
        QListWidget::item { border-radius:0; }
        QListWidget::item:selected { background:#2c443d; border-color:#9faa54; }
        QMenu { background:#102128; border:1px solid #3c5b62; border-radius:0; }
        QMenu::item:selected { background:#304a43; }
        QCheckBox::indicator { background:#0c191f; border:1px solid #547176; border-radius:2px; }
        QCheckBox::indicator:checked { background:#e5ee36; border-color:#e5ee36; }
        QProgressBar::chunk { background:#61d9d2; border-radius:0; }
        QStatusBar { background:#0b1115; color:#92aeb2; border-top:1px solid #304347; }
        QToolTip { background:#152b30; color:#e7efdc; border:1px solid #6d9294; border-radius:0; }
    """ + 'QComboBox::down-arrow { width: 12px; height: 8px; image: url("' + (Path(__file__).parent/'assets/chevron-down.svg').as_posix() + '"); }').replace("__DISPLAY__", DISPLAY).replace("__MONO__", MONO))
