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

class GridBackground(MotionPanel):
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#080b19'))
        glow=QRadialGradient(self.width()*.9,0,self.width()*.9)
        glow.setColorAt(0,QColor('#221541'));glow.setColorAt(1,QColor('#080b19'));p.fillRect(self.rect(),glow)
        p.setPen(QPen(QColor(80,105,175,18),1))
        for x in range(0,self.width(),48):p.drawLine(x,0,x,self.height())
        for y in range(0,self.height(),48):p.drawLine(0,y,self.width(),y)
        # Deterministic, slow particles: no random state and no changing data labels.
        # Perspective flight grid, confined to the background.
        horizon=self.height()*.30;center=self.width()*.65
        # Aurora ribbons and traveling lights give every page an ambient scene.
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for ribbon in range(4):
            path=QPainterPath();path.moveTo(0,70+ribbon*30)
            path.cubicTo(self.width()*.3,150+math.sin(self.phase*.2+ribbon)*60,
                         self.width()*.65,-80+ribbon*30,self.width(),120+ribbon*20)
            p.setPen(QPen(tint('#7a60e8' if ribbon%2 else '#59cadc',17),18-ribbon*3));p.drawPath(path)
        for side in (0,self.width()-1):
            p.setPen(QPen(tint('#9d78ff',35),2));p.drawLine(side,0,side,self.height())
            y=(self.phase*44)%max(1,self.height()+100)-100
            p.setPen(QPen(tint('#77e6f6',145),2));p.drawLine(QPointF(side,y),QPointF(side,y+70))
        p.setPen(QPen(QColor(135,100,245,25),1))
        for i in range(-10,11):
            p.drawLine(QPointF(center+i*16,horizon),QPointF(center+i*180,self.height()))
        for i in range(14):
            depth=((i/14+self.phase*.055)%1)**2
            y=horizon+depth*(self.height()-horizon)
            p.drawLine(QPointF(0,y),QPointF(self.width(),y))
        for i in range(32):
            x=(i*127.3+self.phase*(3+i%4))%max(1,self.width())
            y=(i*79.7-self.phase*(4+i%3))%max(1,self.height())
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(tint('#74dfed',35+int(20*math.sin(self.phase+i))))
            p.drawEllipse(QPointF(x,y),1.3,1.3)
            if i%4==0:
                p.setPen(QPen(tint('#a186ff',28),1));p.drawLine(QPointF(x,y),QPointF(x-16,y+24))

class Hero(MotionPanel):
    def __init__(self,parent=None,on_tools=None,on_flows=None):
        super().__init__(parent);self.setMinimumHeight(320);self.parallax=QPointF()
        from desktop.reactor import create_reactor
        self.reactor=create_reactor(self)
        box=QVBoxLayout(self);box.setContentsMargins(28,25,28,25);box.setSpacing(12)
        tag=QLabel('CHAOSTICTOOL  /  NEXUS');tag.setObjectName('heroTag');box.addWidget(tag)
        self.title=QLabel('VOTRE CENTRE\nD’OPÉRATIONS.');self.title.setObjectName('heroTitle');box.addWidget(self.title)
        desc=QLabel('Choisissez votre cible. Préparez vos outils.\nGardez le contrôle de chaque opération.');desc.setObjectName('heroDesc');desc.setWordWrap(True);box.addWidget(desc)
        row=QHBoxLayout()
        for text,fn,kind in [('OUVRIR L’ARSENAL',on_tools,'primary'),('ATTACK FLOWS',on_flows,'ghost')]:
            from desktop.effects import GamingButton
            b=GamingButton(text);b.setObjectName(kind);b.setCursor(Qt.CursorShape.PointingHandCursor)
            if fn:b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch();box.addLayout(row)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.reactor.setGeometry(self.width()-350, 12, 330, self.height()-40)
        self.reactor.setVisible(self.width()>790)
        clock().sync()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(self.rect()).adjusted(1,1,-1,-1)
        path=QPainterPath();path.addRoundedRect(rect,18,18);p.setClipPath(path)
        g=QLinearGradient(0,0,self.width(),self.height());g.setColorAt(0,QColor('#151d38'));g.setColorAt(.55,QColor('#1b1940'));g.setColorAt(1,QColor('#291855'))
        p.fillPath(path,g)
        if self.width() > 790:
            p.setPen(QPen(tint('#8d78d8', 35), 1))
            for y in range(22, self.height()-20, 18):
                p.drawLine(self.width()-370, y, self.width()-350, y)
        # HUD rails and corner identifiers.
        p.setClipping(False);p.setPen(QPen(QColor('#493b77'),1));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRoundedRect(rect,18,18)
        p.setPen(QPen(QColor('#8b5cf6'),3));p.drawLine(28,self.height()-2,140,self.height()-2)
        p.setPen(QPen(QColor('#40d9e6'),3));p.drawLine(145,self.height()-2,185,self.height()-2)

class ScanOverlay(MotionPanel):
    def __init__(self,parent=None):
        super().__init__(parent);self.motion_active=False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True)
    def paintEvent(self,event):
        if not self.motion_active:return
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Activity stays on the edge; it never sweeps over the output text.
        y=12+(math.sin(self.phase*1.4)+1)*.5*max(1,self.height()-70)
        p.setPen(QPen(QColor('#53dcec'),2));p.drawLine(QPointF(self.width()-3,y),QPointF(self.width()-3,y+42))


class CircuitCard(QFrame):
    """Edge-only animated ornament; contents retain their normal Qt semantics."""
    def __init__(self,parent=None):
        super().__init__(parent);self.phase=0.;self.motion_active=True;clock().widgets.add(self)
    def paintEvent(self,event):
        super().paintEvent(event)
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(tint('#70e2ee',125 if self.underMouse() else 65),1))
        for x,sign in ((12,1),(self.width()-12,-1)):
            p.drawLine(x,7,x+sign*20,7);p.drawLine(x,7,x,13)
        x=20+(math.sin(self.phase*.65)+1)*.5*max(0,self.width()-95)
        glow=QLinearGradient(x,0,x+55,0)
        glow.setColorAt(0,tint('#8b70ef',0));glow.setColorAt(.5,tint('#9adfea',150));glow.setColorAt(1,tint('#8b70ef',0))
        p.setPen(QPen(glow,2));p.drawLine(QPointF(x,self.height()-2),QPointF(x+55,self.height()-2))

class HUDRail(MotionPanel):
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedHeight(12)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    def paintEvent(self,event):
        p=QPainter(self);w=self.width()
        p.setPen(QPen(tint('#89a6d5',45),1));p.drawLine(0,6,w,6)
        for i in range(18):
            a=int(35+65*(.5+.5*math.sin(self.phase*1.6-i*.5)))
            p.fillRect(i*7,3,3,6,tint('#89c7f0',a))
        x=140+(self.phase*65)%max(1,w-210)
        p.setPen(QPen(tint('#b595ff',180),2));p.drawLine(QPointF(x,6),QPointF(min(w,x+36),6))
