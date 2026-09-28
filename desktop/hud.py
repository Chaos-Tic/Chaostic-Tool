"""Procedural HUD artwork and a shared, visibility-aware animation clock."""
import math,weakref
from shiboken6 import isValid
from PySide6.QtCore import Qt,QTimer,QObject,QEvent,QPointF,QRectF
from PySide6.QtGui import QColor,QPainter,QPen,QLinearGradient,QRadialGradient,QFont,QPainterPath
from PySide6.QtWidgets import QWidget,QApplication,QVBoxLayout,QHBoxLayout,QLabel,QPushButton
from desktop import theme

class MotionClock(QObject):
    def __init__(self,app):
        super().__init__(app);self.enabled=True;self.widgets=weakref.WeakSet();self.time=0.0
        self.timer=QTimer(self);self.timer.setInterval(33);self.timer.timeout.connect(self.tick)
        app.installEventFilter(self)
    def eventFilter(self,obj,event):
        if event.type() in (QEvent.Type.Show,QEvent.Type.Hide,QEvent.Type.WindowStateChange):
            QTimer.singleShot(0,self.sync)
        return False
    def visible(self):
        return [w for w in self.widgets if isValid(w) and w.isVisible() and not w.window().isMinimized() and w.motion_active]
    def sync(self):
        if self.enabled and self.visible():
            if not self.timer.isActive():self.timer.start()
        else:self.timer.stop()
    def tick(self):
        for w in self.visible():w.phase+=.033;w.update()
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
        for i in range(18):
            x=(i*127.3+self.phase*(3+i%4))%max(1,self.width())
            y=(i*79.7-self.phase*(4+i%3))%max(1,self.height())
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(tint('#74dfed',35+int(20*math.sin(self.phase+i))))
            p.drawEllipse(QPointF(x,y),1.3,1.3)

class Hero(MotionPanel):
    def __init__(self,parent=None,on_tools=None,on_flows=None):
        super().__init__(parent);self.setMinimumHeight(276)
        box=QVBoxLayout(self);box.setContentsMargins(28,25,28,25);box.setSpacing(12)
        tag=QLabel('CHAOSTICTOOL  /  NEXUS');tag.setObjectName('heroTag');box.addWidget(tag)
        self.title=QLabel('VOTRE CENTRE\nD’OPÉRATIONS.');self.title.setObjectName('heroTitle');box.addWidget(self.title)
        desc=QLabel('Choisissez votre cible. Préparez vos outils.\nGardez le contrôle de chaque opération.');desc.setObjectName('heroDesc');desc.setWordWrap(True);box.addWidget(desc)
        row=QHBoxLayout()
        for text,fn,kind in [('OUVRIR L’ARSENAL',on_tools,'primary'),('ATTACK FLOWS',on_flows,'ghost')]:
            b=QPushButton(text);b.setObjectName(kind);b.setCursor(Qt.CursorShape.PointingHandCursor)
            if fn:b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch();box.addLayout(row)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(self.rect()).adjusted(1,1,-1,-1)
        path=QPainterPath();path.addRoundedRect(rect,18,18);p.setClipPath(path)
        g=QLinearGradient(0,0,self.width(),self.height());g.setColorAt(0,QColor('#151d38'));g.setColorAt(.55,QColor('#1b1940'));g.setColorAt(1,QColor('#291855'))
        p.fillPath(path,g)
        if self.width()>790:
            cx,cy=self.width()-175,self.height()/2
            haze=QRadialGradient(cx,cy,190);haze.setColorAt(0,QColor(133,84,255,65));haze.setColorAt(1,QColor(85,70,210,0));p.fillRect(self.rect(),haze)
            p.save();p.translate(cx,cy)
            for radius,direction,color in [(112,1,'#9974ff'),(94,-1,'#52e2ef'),(73,.65,'#635593')]:
                p.save();p.rotate(self.phase*direction*18)
                p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(tint(color,100),1));p.drawEllipse(QPointF(0,0),radius,radius)
                p.setPen(QPen(QColor(color),3))
                for start in [0,130,240]:p.drawArc(QRectF(-radius,-radius,2*radius,2*radius),start*16,48*16)
                p.restore()
            for i in range(48):
                a=i*math.tau/48;p.setPen(QPen(tint('#b4c8ff',100 if i%4==0 else 40),1))
                p.drawLine(QPointF(math.cos(a)*125,math.sin(a)*125),QPointF(math.cos(a)*(133 if i%4==0 else 129),math.sin(a)*(133 if i%4==0 else 129)))
            p.rotate(-self.phase*6);poly=QPainterPath()
            for i in range(7):
                a=i*math.tau/6-math.pi/2;pt=QPointF(math.cos(a)*48,math.sin(a)*48)
                if i==0:poly.moveTo(pt)
                else:poly.lineTo(pt)
            p.fillPath(poly,QColor(118,79,223,45));p.setPen(QPen(QColor('#b69bff'),2));p.drawPath(poly);p.restore()
            p.setFont(QFont(theme.DISPLAY,16,QFont.Weight.Bold));p.setPen(QColor('#ecf2ff'));p.drawText(QRectF(cx-45,cy-22,90,44),Qt.AlignmentFlag.AlignCenter,'CT')
            p.setFont(QFont(theme.MONO,8));p.setPen(QColor('#80cadb'));p.drawText(QRectF(cx-100,cy+138,200,18),Qt.AlignmentFlag.AlignCenter,'LOCAL / OPERATOR CONSOLE')
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
