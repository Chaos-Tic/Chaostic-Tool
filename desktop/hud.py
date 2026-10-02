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
    """Quiet workspace; decoration stays inside the brand panel."""
    def paintEvent(self,event):
        # Uniform workspace; decorative grid is limited to the emblem.
        p=QPainter(self);p.fillRect(self.rect(),QColor(theme.COLORS['background']))

class Hero(MotionPanel):
    """Original CLI artwork with a functional action dock; no ambient animation."""
    def __init__(self,parent=None,on_tools=None,on_flows=None):
        super().__init__(parent);self.motion_active=False
        self.art=QPixmap(str(ARTWORK));self.banner_height=240
        self.setAccessibleName('ChaosticTool — Red Ops Control Surface')
        self.setMinimumHeight(250)
        box=QVBoxLayout(self);box.setContentsMargins(18,0,18,12)
        box.addStretch()
        dock=QHBoxLayout();dock.setSpacing(10)
        from desktop.i18n import T
        self.caption=QLabel(T('VOTRE CIBLE. VOS OUTILS. VOTRE SESSION.'))
        self.caption.setObjectName('brandCaption');dock.addWidget(self.caption)
        dock.addStretch()
        for text,fn,kind in [(T('Ouvrir l’arsenal'),on_tools,'primary'),(T('Attack flows'),on_flows,'brandAction')]:
            from desktop.effects import GamingButton
            button=GamingButton(text);button.setObjectName(kind)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if fn:button.clicked.connect(fn)
            dock.addWidget(button)
        box.addLayout(dock)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.banner_height=min(242,int(self.width()/4))
        self.setFixedHeight(self.banner_height+64)
        self.caption.setVisible(self.width()>=850)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(),QColor('#030303'))
        width=self.banner_height*4
        p.drawPixmap(QRectF((self.width()-width)/2,0,width,self.banner_height),self.art,QRectF(self.art.rect()))
        p.setPen(QPen(QColor('#413030'),1))
        p.drawLine(18,self.banner_height+2,self.width()-18,self.banner_height+2)
        hatch(p,19,self.height()-4,3,'#a7232a')

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
    """Double industrial frame shared by every work panel."""
    def paintEvent(self,event):
        p=QPainter(self)
        panel(p,QRectF(self.rect()).adjusted(1,1,-1,-1),self.property('role')=='target')


class HUDRail(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedHeight(12)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    def paintEvent(self,event):
        p=QPainter(self);p.setPen(QPen(QColor(theme.COLORS['border']),1))
        p.drawLine(0,5,self.width(),5)
        p.setPen(QPen(QColor(theme.COLORS['accent']),2));p.drawLine(0,5,90,5);hatch(p,self.width()-46,3,4)
