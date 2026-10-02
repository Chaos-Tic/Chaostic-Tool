"""Procedural HUD artwork and a shared, visibility-aware animation clock."""
import math,weakref,time
from shiboken6 import isValid
from PySide6.QtCore import Qt,QTimer,QObject,QEvent,QPointF,QRectF
from PySide6.QtGui import QColor,QPainter,QPen,QLinearGradient,QRadialGradient,QFont,QPainterPath,QCursor
from PySide6.QtWidgets import QWidget,QApplication,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFrame
from desktop import theme
from pathlib import Path
from PySide6.QtSvg import QSvgRenderer

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
    """Quiet workspace; decoration stays inside the brand panel."""
    def paintEvent(self,event):
        # Uniform workspace; decorative grid is limited to the emblem.
        p=QPainter(self);p.fillRect(self.rect(),QColor(theme.COLORS['background']))

class Hero(MotionPanel):
    def __init__(self,parent=None,on_tools=None,on_flows=None):
        super().__init__(parent);self.motion_active=False;self.setMinimumHeight(230);self.parallax=QPointF()
        row=QHBoxLayout(self);row.setContentsMargins(24,20,24,20);row.setSpacing(18)
        box=QVBoxLayout();box.setSpacing(12);row.addLayout(box,1)
        from desktop.i18n import T
        tag=QLabel('RED OPS  /  CONTROL SURFACE');tag.setObjectName('heroTag');box.addWidget(tag)
        self.title=QLabel('CHAOSTIC TOOL');self.title.setObjectName('heroTitle');box.addWidget(self.title)
        desc=QLabel(T('Votre cible. Vos outils. Votre session.'));desc.setObjectName('heroDesc');desc.setWordWrap(True);box.addWidget(desc)
        phases=QLabel(T('RECONNAISSANCE / EXÉCUTION / RÉSULTATS'));phases.setObjectName('eyebrow');box.addWidget(phases)
        actions=QHBoxLayout()
        for text,fn,kind in [(T('Ouvrir l’arsenal'),on_tools,'primary'),(T('Attack flows'),on_flows,'ghost')]:
            from desktop.effects import GamingButton
            b=GamingButton(text);b.setObjectName(kind);b.setCursor(Qt.CursorShape.PointingHandCursor)
            if fn:b.clicked.connect(fn)
            actions.addWidget(b)
        actions.addStretch();box.addLayout(actions)
        self.emblem=BrandEmblem(self);row.addWidget(self.emblem)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.emblem.setVisible(self.width() >= 850)
        clock().sync()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=QRectF(1,1,self.width()-2,self.height()-2)
        path=QPainterPath();path.moveTo(r.left()+14,r.top());path.lineTo(r.right(),r.top())
        path.lineTo(r.right(),r.bottom()-14);path.lineTo(r.right()-14,r.bottom())
        path.lineTo(r.left(),r.bottom());path.lineTo(r.left(),r.top()+14);path.closeSubpath()
        p.fillPath(path,QColor(theme.COLORS['surface']))
        p.setPen(QPen(QColor(theme.COLORS['border']),1));p.drawPath(path)
        p.setPen(QPen(QColor(theme.COLORS['accent']),3))
        p.drawLine(16,2,105,2);p.drawLine(self.width()-105,self.height()-2,self.width()-16,self.height()-2)


class BrandEmblem(QWidget):
    """Static vector mark; no fake telemetry, background timers or raster scaling."""
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedSize(240,185)
        self.renderer=QSvgRenderer(str(Path(__file__).parent/'assets/icon.svg'),self)
        self.setAccessibleName('ChaosticTool Red Ops')
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(theme.COLORS['border']),1))
        for x in range(0,self.width(),20):p.drawLine(x,0,x,self.height())
        for y in range(0,self.height(),20):p.drawLine(0,y,self.width(),y)
        self.renderer.render(p,QRectF(50,12,152,152))
        p.setPen(QColor(theme.COLORS['muted']));p.setFont(QFont(theme.MONO,9))
        from desktop import VERSION
        p.drawText(QRectF(0,166,self.width(),18),Qt.AlignmentFlag.AlignCenter,'DESKTOP  /  '+VERSION)

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
    """Static panel corners; no perpetual animation or shared-clock registration."""
    def paintEvent(self,event):
        super().paintEvent(event)
        p=QPainter(self);p.setPen(QPen(QColor(theme.COLORS['accent_line']),1))
        for x,sign in ((10,1),(self.width()-10,-1)):
            p.drawLine(x,5,x+sign*16,5);p.drawLine(x,5,x,11)


class HUDRail(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedHeight(6)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    def paintEvent(self,event):
        p=QPainter(self);p.setPen(QPen(QColor(theme.COLORS['border']),1))
        p.drawLine(0,2,self.width(),2)
        p.setPen(QPen(QColor(theme.COLORS['accent']),2));p.drawLine(0,2,54,2)
