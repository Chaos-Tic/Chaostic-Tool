"""Static industrial framing and the repository's original README artwork.

The PNG is used unchanged. Source rectangles select the original mascot and
wordmark when painting the sidebar; no alternate logo or generated texture.
"""
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget, QPushButton

from desktop import theme

ARTWORK = Path(__file__).parent / "assets" / "red-ops-banner.png"


def cut_path(rect, cut=12):
    path = QPainterPath()
    path.moveTo(rect.left() + cut, rect.top())
    path.lineTo(rect.right() - cut, rect.top())
    path.lineTo(rect.right(), rect.top() + cut)
    path.lineTo(rect.right(), rect.bottom() - cut)
    path.lineTo(rect.right() - cut, rect.bottom())
    path.lineTo(rect.left() + cut, rect.bottom())
    path.lineTo(rect.left(), rect.bottom() - cut)
    path.lineTo(rect.left(), rect.top() + cut)
    path.closeSubpath()
    return path


def hatch(painter, x, y, count=4, color=None):
    painter.setPen(QPen(QColor(color or theme.COLORS["ACCENT"]), 3))
    for i in range(count):
        painter.drawLine(int(x + i * 10), int(y + 5), int(x + i * 10 + 5), int(y))


def panel(painter, rect, active=False):
    """Double cut frame; decoration stays away from text and controls."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    colors = theme.COLORS
    path = cut_path(rect, 12)
    painter.fillPath(path, QColor(colors["SURFACE"]))
    painter.setPen(QPen(QColor(colors["LINE"]), 1))
    painter.drawPath(path)
    painter.setPen(QPen(QColor(colors["LINE_SOFT"]), 1))
    painter.drawPath(cut_path(rect.adjusted(4, 4, -4, -4), 10))
    painter.setPen(QPen(QColor(colors["ACCENT"] if active else colors["ACCENT_LINE"]), 2))
    painter.drawLine(int(rect.left()+14), int(rect.top()), int(rect.left()+70), int(rect.top()))
    painter.drawLine(int(rect.right()-45), int(rect.bottom()), int(rect.right()-14), int(rect.bottom()))
    hatch(painter, rect.right()-57, rect.top()+9, 3, colors["ACCENT_LINE"])


class BrandPanel(QWidget):
    """Original mascot and original wordmark, retained on every workspace."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.art = QPixmap(str(ARTWORK))
        self.compact = False
        self.setFixedHeight(157)
        self.setAccessibleName("ChaosticTool â€” Red Ops Control Surface")

    def set_compact(self, compact):
        if compact != self.compact:
            self.compact = compact
            self.setFixedHeight(88 if compact else 157)
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        side = 47 if self.compact else 105
        p.drawPixmap(QRectF((self.width()-side)/2, 0, side, side), self.art,
                     QRectF(130, 100, 250, 250))
        width = self.width()-4
        height = width*190/1265
        p.drawPixmap(QRectF(2, side+2, width, height), self.art,
                     QRectF(410, 115, 1265, 190))
        if not self.compact:
            p.setPen(QColor("#a79a9a"))
            font = QFont(theme.MONO, 8)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.1)
            p.setFont(font)
            p.drawText(QRectF(0, self.height()-16, self.width(), 14),
                       Qt.AlignmentFlag.AlignCenter, "RED OPS / DESKTOP")


class RailButton(QPushButton):
    """Numbered navigation with a keyboard-visible, cut-corner selection."""
    def __init__(self, text, number, parent=None):
        super().__init__(text, parent)
        self.number = number
        self.setFixedHeight(42)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("nav")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self.isChecked()
        hover = self.underMouse()
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if active or hover or self.hasFocus():
            path = cut_path(rect, 8)
            p.fillPath(path, QColor("#251012" if active else "#181414"))
            p.setPen(QPen(QColor("#ff3131" if active or self.hasFocus() else "#574040"), 1))
            p.drawPath(path)
        if active:
            p.fillRect(QRectF(1, 12, 3, self.height()-24), QColor("#ff3131"))
        p.setFont(QFont(theme.MONO, 11))
        p.setPen(QColor("#ff6464" if active else "#887d7d"))
        p.drawText(QRectF(12, 0, 29, self.height()), Qt.AlignmentFlag.AlignVCenter, self.number)
        p.setPen(QColor("#f4eeee" if active else "#bdb3b3"))
        p.drawText(QRectF(45, 0, self.width()-53, self.height()),
                   Qt.AlignmentFlag.AlignVCenter, self.text())

    def sizeHint(self):
        return QSize(210, 42)
