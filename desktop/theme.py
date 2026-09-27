"""Shared desktop visual tokens and component states."""
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

COLORS = dict(background="#0c1017", sidebar="#10151e", surface="#141b26", raised="#1b2432",
              border="#293344", text="#f0f3f9", muted="#a4afc2", red="#ff4d64", green="#73deb0")


def apply_theme(app: QApplication):
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 10)
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
    app.setStyleSheet("""
        QWidget { color: #f0f3f9; }
        QMainWindow, QDialog { background: #0c1017; }
        QWidget#sidebar { background: #10151e; border-right: 1px solid #293344; }
        QFrame#card { background: #141b26; border: 1px solid #293344; border-radius: 12px; }
        QLabel { background: transparent; border: none; }
        QLabel#muted { color: #a4afc2; }
        QLabel#eyebrow { color: #b4bed0; font-size: 11px; font-weight: 600; letter-spacing: 2px; }
        QLabel#pageTitle { font-size: 29px; font-weight: 700; }
        QLabel#sectionTitle { font-size: 17px; font-weight: 600; }
        QLabel#number { font-size: 32px; font-weight: 700; }
        QLabel#badge { background: #172f2a; color: #73deb0; border: 1px solid #285044; border-radius: 10px; padding: 5px 10px; font-size: 11px; font-weight: 600; }
        QPushButton { background: #1b2432; border: 1px solid #344156; border-radius: 7px; padding: 9px 15px; font-weight: 600; min-height: 18px; }
        QPushButton:hover { background: #253145; border-color: #56647a; }
        QPushButton:pressed { background: #141b26; }
        QPushButton:focus, QLineEdit:focus, QComboBox:focus, QTableWidget:focus { border: 2px solid #ff7e8e; }
        QPushButton:disabled { color: #697589; background: #141b26; border-color: #253043; }
        QPushButton#primary { background: #ed3b55; border-color: #ed3b55; color: #ffffff; }
        QPushButton#primary:hover { background: #ff4d64; border-color: #ff4d64; }
        QPushButton#primary:disabled { background: #512b39; border-color: #512b39; color: #aa8590; }
        QPushButton#danger { background: #38202b; color: #ff9aa8; border-color: #764052; }
        QPushButton#nav { text-align: left; border: 1px solid transparent; background: transparent; color: #a4afc2; padding: 12px 14px; font-weight: 500; }
        QPushButton#nav:hover { background: #1a2230; color: #f0f3f9; }
        QPushButton#nav:checked { background: #30212d; border-color: #643044; color: #ff8798; font-weight: 600; }
        QPushButton#nav:focus { border: 2px solid #ff7e8e; }
        QLineEdit, QComboBox { background: #101720; border: 1px solid #344156; border-radius: 7px; padding: 10px 12px; min-height: 18px; selection-background-color: #643044; }
        QComboBox::drop-down { width: 24px; border: none; }
        QComboBox QAbstractItemView { background: #17202d; selection-background-color: #643044; padding: 5px; }
        QTableWidget { background: #101720; alternate-background-color: #141b26; border: 1px solid #293344; border-radius: 9px; gridline-color: #253043; outline: 0; }
        QTableWidget::item { padding: 11px 12px; border-bottom: 1px solid #222c3c; }
        QTableWidget::item:selected { background: #2e293b; color: #ffffff; }
        QHeaderView::section { background: #161e2a; color: #a4afc2; padding: 12px; border: none; border-bottom: 1px solid #293344; font-size: 11px; font-weight: 600; }
        QPlainTextEdit { background: #090e15; color: #c8d7e8; border: 1px solid #293344; border-radius: 8px; padding: 15px; selection-background-color: #643044; font-family: 'Cascadia Code', Consolas; font-size: 12px; }
        QScrollBar:vertical { background: #10151e; width: 10px; margin: 0; }
        QScrollBar::handle:vertical { background: #344156; border-radius: 4px; min-height: 30px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollArea { background: transparent; border: none; }
        QCheckBox { spacing: 9px; color: #b7c2d5; }
        QToolTip { background: #243044; color: #f0f3f9; border: 1px solid #52627c; padding: 6px; }
        QProgressBar { background: #1b2432; border: none; border-radius: 3px; max-height: 5px; }
        QProgressBar::chunk { background: #ff4d64; border-radius: 3px; }
        QStatusBar { color: #a4afc2; background: #10151e; border-top: 1px solid #293344; }
        QSplitter::handle { background: #0c1017; width: 12px; height: 12px; }
    """)
