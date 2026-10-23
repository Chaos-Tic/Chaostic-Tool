"""Layered glass surfaces and keyboard-accessible workspace navigation."""
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QLinearGradient
from PySide6.QtWidgets import QWidget, QPushButton

from desktop import theme

ARTWORK = Path(__file__).parent / "assets" / "red-ops-banner.png"


def cut_path(rect, cut=12):
    """Compatibility geometry for panels: a soft, rounded glass outline."""
    path = QPainterPath()
    path.addRoundedRect(rect, cut, cut)
    return path


def hatch(painter, x, y, count=4, color=None):
    """Small alignment marks retained for legacy HUD callers."""
    painter.setPen(QPen(QColor(color or theme.COLORS["ACCENT"]), 1))
    for i in range(count):
        painter.drawPoint(int(x + i * 5), int(y))


def panel(painter, rect, active=False):
    """A diffuse shadow, tinted body, luminous rim and inner reflection."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    colors = theme.COLORS
    radius = 20
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if not theme.REDUCED_TRANSPARENCY:
        for spread in range(6, 0, -1):
            shadow = QColor("#050b21" if theme.MODE == "dark" else "#5b4f85")
            shadow.setAlpha(3)
            painter.setPen(QPen(shadow, spread * 2))
            painter.drawRoundedRect(rect.adjusted(3, 5, -3, -1), radius, radius)
    fill = QColor(colors["SURFACE"])
    if not theme.REDUCED_TRANSPARENCY:
        fill.setAlpha(180 if theme.MODE == "dark" else 150)
    painter.setPen(QPen(QColor(colors["ACCENT_LINE"] if active else colors["RIM"]), 1))
    painter.setBrush(fill)
    painter.drawRoundedRect(rect, radius, radius)
    if not theme.REDUCED_TRANSPARENCY:
        sheen = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        sheen.setColorAt(0, QColor(255, 255, 255, 34 if theme.MODE == "dark" else 115))
        sheen.setColorAt(.55, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(sheen)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(colors["LINE_SOFT"]), 1))
    painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), radius - 3, radius - 3)


class BrandPanel(QWidget):
    """Use the application icon consistently, with a readable text wordmark."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon = QIcon(str(Path(__file__).parent / "assets" / "icon.png"))
        self.compact = False
        self.setFixedHeight(115)
        self.setAccessibleName("ChaosticTool Desktop")

    def set_compact(self, compact):
        if compact != self.compact:
            self.compact = compact
            self.setFixedHeight(78 if compact else 115)
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = 32 if self.compact else 42
        self.icon.paint(p, int((self.width() - side) / 2), 4, side, side)
        font = QFont(theme.BODY, 15)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(QColor(theme.COLORS["TEXT"]))
        p.drawText(QRectF(0, side + 10, self.width(), 27), Qt.AlignmentFlag.AlignCenter, "ChaosticTool")
        if not self.compact:
            p.setFont(QFont(theme.BODY, 9))
            p.setPen(QColor(theme.COLORS["MUTED"]))
            p.drawText(QRectF(0, 87, self.width(), 20), Qt.AlignmentFlag.AlignCenter, "D E S K T O P")


class RailButton(QPushButton):
    """Numbered glass capsules retain standard keyboard button behavior."""
    def __init__(self, text, number, parent=None):
        super().__init__(text, parent)
        self.number = number
        self.setFixedHeight(46)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("nav")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self.isChecked()
        colors = theme.COLORS
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        if active or self.underMouse() or self.hasFocus():
            p.setBrush(QColor(colors["ACCENT_SOFT"] if active else colors["NAV_HOVER"]))
            p.setPen(QPen(QColor(colors["ACCENT"] if self.hasFocus() else colors["ACCENT_LINE"]), 2 if self.hasFocus() else 1))
            p.drawRoundedRect(rect, 14, 14)
        p.setFont(QFont(theme.MONO, 9))
        p.setPen(QColor(colors["ACCENT"] if active else colors["MUTED"]))
        p.drawText(QRectF(14, 0, 28, self.height()), Qt.AlignmentFlag.AlignVCenter, self.number)
        font = QFont(theme.BODY, 10)
        font.setWeight(QFont.Weight.DemiBold if active else QFont.Weight.Normal)
        p.setFont(font)
        p.setPen(QColor(colors["TEXT"] if active else colors["MUTED"]))
        p.drawText(QRectF(46, 0, self.width() - 55, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text())
        if active:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colors["ACCENT"]))
            p.drawEllipse(QRectF(6, self.height() / 2 - 2, 4, 4))

    def sizeHint(self):
        return QSize(224, 46)
