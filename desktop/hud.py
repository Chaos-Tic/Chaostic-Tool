"""Procedural HUD artwork and a shared, visibility-aware animation clock."""
import math,weakref,time
from shiboken6 import isValid
from PySide6.QtCore import Qt,QTimer,QObject,QEvent,QPointF,QRectF
from PySide6.QtGui import QColor,QPainter,QPen,QLinearGradient,QRadialGradient,QFont,QPainterPath,QCursor,QPixmap
from PySide6.QtWidgets import QWidget,QApplication,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFrame
from desktop import theme
from pathlib import Path
from desktop.identity import ARTWORK, panel, hatch

class MotionClock(QObject):
    def __init__(self,app):
        super().__init__(app);self.enabled=True;self.widgets=weakref.WeakSet();self.time=0.0
        self.last=time.monotonic()
        self.timer=QTimer(self);self.timer.setTimerType(Qt.TimerType.PreciseTimer);self.timer.setInterval(16);self.timer.timeout.connect(self.tick)
        app.installEventFilter(self)
    def eventFilter(self,obj,event):
        if event.type() in (QEvent.Type.Show,QEvent.Type.Hide,QEvent.Type.WindowStateChange):
            QTimer.singleShot(0,self.sync)
        return False
    def visible(self):
        return [w for w in self.widgets if isValid(w) and w.isVisible() and not w.window().isMinimized() and w.motion_active]
    def sync(self):
        if self.enabled and self.visible():
            if not self.timer.isActive():self.last=time.monotonic();self.timer.start()
        else:self.timer.stop()
    def tick(self):
        stamp=time.monotonic();dt=min(.1,stamp-self.last);self.last=stamp
        for w in self.visible():w.phase+=dt;w.update()
    def set_rate(self, fps):
        self.timer.setInterval(33 if fps == 30 else 16)

    def set_enabled(self,enabled):
        self.enabled=bool(enabled);self.sync()
        for w in self.widgets:
            if isValid(w):w.update()

def clock():
    app=QApplication.instance()
    if not hasattr(app,'_hud_motion'):app._hud_motion=MotionClock(app)
    return app._hud_motion

class MotionPanel(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.phase=0.;self.motion_active=True;clock().widgets.add(self)
    def set_active(self,active):self.motion_active=bool(active);clock().sync();self.update()

def tint(color,alpha):
    c=QColor(color);c.setAlpha(alpha);return c

class GridBackground(QWidget):
    """Paint the same peach, sky and lilac environment as Lorenz."""
    def paintEvent(self, event):
        p = QPainter(self)
        colors = theme.COLORS
        base = QLinearGradient(0, 0, self.width(), self.height())
        for stop, key in ((0, 'ENV_START'), (.5, 'ENV_MIDDLE'), (1, 'ENV_END')):
            base.setColorAt(stop, QColor(colors[key]))
        p.fillRect(self.rect(), base)
        if theme.REDUCED_TRANSPARENCY:
            return
        size = max(self.width(), self.height())
        for x, y, color in ((.08, .1, '#ffb48c'), (.95, .3, '#8fd0f6'), (.45, 1.02, '#c3a6f5')):
            field = QRadialGradient(self.width() * x, self.height() * y, size * .55)
            field.setColorAt(0, tint(color, 70 if theme.MODE == 'dark' else 150))
            field.setColorAt(1, tint(color, 0))
            p.fillRect(self.rect(), field)


class Hero(MotionPanel):
    """A calm welcome surface with real workspace actions."""
    def __init__(self, parent=None, on_tools=None, on_flows=None):
        super().__init__(parent)
        self.motion_active = False
        self.setAccessibleName('ChaosticTool Desktop')
        self.setMinimumHeight(218)
        box = QVBoxLayout(self)
        box.setContentsMargins(28, 24, 28, 24)
        box.setSpacing(12)
        from desktop.i18n import T
        kicker = QLabel(T('VOTRE ESPACE DE TRAVAIL'))
        kicker.setObjectName('heroTag')
        box.addWidget(kicker)
        self.title = QLabel(T('Votre prochaine opération,\nbien préparée.'))
        self.title.setObjectName('heroHeading')
        self.title.setWordWrap(True)
        box.addWidget(self.title)
        self.caption = QLabel(T('Cibles, outils et résultats, réunis dans un espace clair.'))
        self.caption.setObjectName('heroDescription')
        self.caption.setWordWrap(True)
        box.addWidget(self.caption)
        box.addStretch()
        dock = QHBoxLayout()
        dock.setSpacing(10)
        for text, fn, kind in [(T('Ouvrir l’arsenal'), on_tools, 'primary'), (T('Attack flows'), on_flows, 'brandAction')]:
            from desktop.effects import GamingButton
            button = GamingButton(text)
            button.setObjectName(kind)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if fn:
                button.clicked.connect(fn)
            dock.addWidget(button)
        dock.addStretch()
        box.addLayout(dock)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.caption.setVisible(self.width() >= 720)
        self.setMinimumHeight(218 if self.width() >= 720 else 198)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        panel(p, QRectF(self.rect()).adjusted(4, 4, -4, -4))
        # Decorative glass lenses never carry status or interfere with text.
        if self.width() < 860 or theme.REDUCED_TRANSPARENCY:
            return
        p.save()
        p.setClipRect(self.rect().adjusted(0, 6, -6, -6))
        cx, cy = self.width() - 136, self.height() / 2
        for dx, dy, side, color in ((-32, 22, 135, '#ffb48c'), (40, -18, 155, '#8fd0f6'), (2, 0, 110, '#c3a6f5')):
            r = QRectF(cx + dx - side/2, cy + dy - side/2, side, side)
            gradient = QLinearGradient(r.topLeft(), r.bottomRight())
            gradient.setColorAt(0, tint(color, 155))
            gradient.setColorAt(1, tint(color, 30))
            p.setBrush(gradient)
            p.setPen(QPen(QColor(theme.COLORS['RIM']), 1.5))
            p.drawEllipse(r)
        p.restore()

class ScanOverlay(MotionPanel):
    def __init__(self,parent=None):
        super().__init__(parent);self.motion_active=False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True)
    def paintEvent(self,event):
        if not self.motion_active:return
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # A stationary pulse indicates work, without a moving scanner.
        alpha=100+int(70*(.5+.5*math.sin(self.phase*2)))
        p.setPen(QPen(tint(theme.COLORS['accent'],alpha),2))
        p.drawLine(2,14,2,54)


class CircuitCard(QFrame):
    """Layered glass frame shared by every work panel."""
    def paintEvent(self,event):
        p=QPainter(self)
        panel(p,QRectF(self.rect()).adjusted(4,4,-4,-4),self.property('role')=='target')


class HUDRail(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedHeight(12)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    def paintEvent(self, event):
        p = QPainter(self)
        p.setPen(QPen(QColor(theme.COLORS['LINE']), 1))
        p.drawLine(0, 5, self.width(), 5)
