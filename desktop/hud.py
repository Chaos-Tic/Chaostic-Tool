"""Procedural HUD artwork and a shared, visibility-aware animation clock."""
import math,weakref,time
from shiboken6 import isValid
from PySide6.QtCore import Qt,QTimer,QObject,QEvent,QPointF,QRectF
from PySide6.QtGui import QColor,QPainter,QPen,QLinearGradient,QRadialGradient,QFont,QPainterPath,QCursor
from PySide6.QtWidgets import QWidget,QApplication,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFrame
from desktop import theme

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
    """Fond clair et calme : une grille très discrète, sans accents néon."""
    def paintEvent(self,event):
        # Fond clair uni, sans grille : plus net, aucun artefact de lignes.
        p=QPainter(self);p.fillRect(self.rect(),QColor(theme.COLORS['background']))

class Hero(MotionPanel):
    def __init__(self,parent=None,on_tools=None,on_flows=None):
        super().__init__(parent);self.motion_active=False;self.setMinimumHeight(350);self.parallax=QPointF()
        from desktop.reactor import create_reactor
        self.reactor=create_reactor(self)
        box=QVBoxLayout(self);box.setContentsMargins(28,25,28,25);box.setSpacing(12)
        tag=QLabel('ChaosticTool');tag.setObjectName('heroTag');box.addWidget(tag)
        self.title=QLabel('Préparez votre\nprochaine opération.');self.title.setObjectName('heroTitle');box.addWidget(self.title)
        desc=QLabel('Votre cible, votre arsenal, vos décisions —\ntoutes vos opérations au même endroit.');desc.setObjectName('heroDesc');desc.setWordWrap(True);box.addWidget(desc)
        row=QHBoxLayout()
        for text,fn,kind in [('Ouvrir l’arsenal',on_tools,'primary'),('Attack flows',on_flows,'ghost')]:
            from desktop.effects import GamingButton
            b=GamingButton(text);b.setObjectName(kind);b.setCursor(Qt.CursorShape.PointingHandCursor)
            if fn:b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch();box.addLayout(row)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        # Le réacteur néon appartient à l'ancien thème sombre : on le masque.
        self.reactor.setVisible(False)
        clock().sync()

    def paintEvent(self,event):
        # Panneau blanc net, coins arrondis, bordure discrète. Aucun néon.
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=QRectF(1,1,self.width()-2,self.height()-2)
        path=QPainterPath();path.addRoundedRect(r,18,18)
        p.fillPath(path,QColor(theme.COLORS['surface']))
        p.setPen(QPen(QColor(theme.COLORS['border']),1));p.drawPath(path)

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
