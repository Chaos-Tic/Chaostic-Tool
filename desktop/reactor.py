"""Projected 3D geometry, depth-sorted and drawn with Qt. Decorative, not telemetry."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient, QLinearGradient, QPolygonF, QCursor
from PySide6.QtWidgets import QWidget

from desktop.hud import clock, tint


def project(x, y, z, phase, scale):
    """Rotate model space, then project with a finite camera distance."""
    a = phase * .23
    x, z = x * math.cos(a) + z * math.sin(a), z * math.cos(a) - x * math.sin(a)
    b = -.35 + .12 * math.sin(phase * .2)
    y, z = y * math.cos(b) - z * math.sin(b), y * math.sin(b) + z * math.cos(b)
    perspective = 4 / (4 - z)
    return QPointF(x * scale * perspective, y * scale * perspective), z


def draw_reactor(widget, painter):
    p = painter
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    w, h, t = widget.width(), widget.height(), widget.phase
    parent = widget.parentWidget()
    background = QLinearGradient(-widget.x(), -widget.y(), parent.width()-widget.x(), parent.height()-widget.y())
    background.setColorAt(0, QColor('#151d38')); background.setColorAt(.55, QColor('#1b1940')); background.setColorAt(1, QColor('#291855'))
    p.fillRect(widget.rect(), background)
    cursor = widget.mapFromGlobal(QCursor.pos())
    goal = QPointF((cursor.x() / max(1, w) - .5) * 14,
                   (cursor.y() / max(1, h) - .5) * 10) if widget.underMouse() and clock().enabled else QPointF()
    widget.parallax += (goal - widget.parallax) * .09
    cx, cy = w * .5 + widget.parallax.x(), h * .48 + widget.parallax.y()
    scale = min(w, h) * .27
    haze = QRadialGradient(cx, cy, scale * 1.6)
    haze.setColorAt(0, QColor(104, 63, 214, 130))
    haze.setColorAt(.6, QColor(32, 78, 114, 55))
    haze.setColorAt(1, QColor(17, 23, 47, 0))
    p.fillRect(widget.rect(), haze)
    p.translate(cx, cy)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for radius, speed, color in ((1.35, 12, '#a586ff'), (1.55, -8, '#64e7eb')):
        r = scale * radius
        p.setPen(QPen(tint(color, 45), 1))
        p.drawEllipse(QRectF(-r, -r * .76, r * 2, r * 1.52))
        p.setPen(QPen(tint(color, 210), 2))
        for i in range(3):
            p.drawArc(QRectF(-r, -r * .76, r * 2, r * 1.52), int((t * speed + i * 120) * 16), 36 * 16)
    # Depth-sorted triangular shell: back edges dim, front faces luminous.
    rings, segments = 9, 20
    vertices = []
    for j in range(rings + 1):
        latitude = math.pi * j / rings
        vertices.append([project(math.sin(latitude) * math.cos(i * math.tau / segments),
                                 math.cos(latitude), math.sin(latitude) * math.sin(i * math.tau / segments),
                                 t, scale) for i in range(segments)])
    faces = []
    for j in range(rings):
        for i in range(segments):
            n = (i + 1) % segments
            for indices in (((j, i), (j + 1, i), (j, n)), ((j, n), (j + 1, i), (j + 1, n))):
                pts = [vertices[a][b] for a, b in indices]
                faces.append((sum(v[1] for v in pts) / 3, QPolygonF([v[0] for v in pts])))
    for depth, polygon in sorted(faces, key=lambda v: v[0]):
        alpha = int(28 + (depth + 1) * 49)
        p.setPen(QPen(tint('#83efff' if depth > .15 else '#9f78ff', alpha), .8))
        p.setBrush(tint('#6655d9', 5 if depth < 0 else 13))
        p.drawPolygon(polygon)
    for i in range(28):
        a = i * 2.39996 + t * (.09 + i % 3 * .03)
        r = scale * (1.2 + (i % 7) / 10)
        point = QPointF(math.cos(a) * r, math.sin(a) * r * .8)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(tint('#b8f6ff', 150))
        p.drawEllipse(point, 1.6, 1.6)
    p.resetTransform()
    p.setPen(QPen(tint('#70dfeb', 110), 1))
    for sign in (-1, 1):
        x = cx + sign * scale * 1.75
        p.drawLine(QPointF(x, cy - 20), QPointF(x, cy + 20))
        p.drawLine(QPointF(x, cy), QPointF(x - sign * 10, cy))


class RasterReactor(QWidget):
    renderer = 'Qt logiciel'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.phase = 0.; self.motion_active = True; self.parallax = QPointF()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        clock().widgets.add(self)

    def paintEvent(self, event):
        p = QPainter(self)
        draw_reactor(self, p)
        p.end()


def create_reactor(parent):
    # Native OpenGL was evaluated, but produced driver-dependent artifacts on
    # the Windows validation machine. Keep one tested renderer for this release.
    return RasterReactor(parent)
