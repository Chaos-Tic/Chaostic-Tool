"""Decorative city silhouette with a slow light cycle; no moving scan lines."""
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QLinearGradient, QRadialGradient, QPainterPath, QFont
from PySide6.QtWidgets import QWidget
from desktop.hud import clock, tint
from desktop import theme


def draw_reactor(widget,p):
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    parent=widget.parentWidget();w,h=widget.width(),widget.height()
    bg=QLinearGradient(-widget.x(),-widget.y(),parent.width()-widget.x(),parent.height()-widget.y())
    bg.setColorAt(0,QColor('#19272c'));bg.setColorAt(1,QColor('#0c1519'))
    p.fillRect(widget.rect(),bg)
    light=60+int(20*math.sin(widget.phase*.65))
    glow=QRadialGradient(w*.55,h*.45,h*.45)
    glow.setColorAt(0,QColor(88,179,163,light));glow.setColorAt(1,QColor(88,179,163,0))
    p.fillRect(widget.rect(),glow)
    # Fixed architectural silhouette: the light changes, buildings never drift.
    for layer in range(2):
        ground=h*(.82+layer*.08)
        for i in range(9):
            x=8+i*42-layer*13;bw=24+(i*7)%19;bh=45+(i*53+layer*37)%125
            path=QPainterPath();path.moveTo(x,ground);path.lineTo(x,ground-bh)
            path.lineTo(x+bw-7,ground-bh);path.lineTo(x+bw,ground-bh+7);path.lineTo(x+bw,ground);path.closeSubpath()
            p.fillPath(path,QColor('#142b31' if layer==0 else '#0c191f'))
            p.setPen(QPen(tint('#4d888b',65 if layer==0 else 135),1));p.drawPath(path)
            for row in range(3,int(bh/9)-1):
                if (row+i)%3==0:continue
                p.fillRect(QRectF(x+5,ground-bh+row*9,bw-11,2),tint('#75cbc7',light if layer==0 else light+20))
            if i in (2,6) and layer==0:
                p.setPen(QPen(tint('#e5ee36',170),2));p.drawLine(QPointF(x+4,ground-bh-17),QPointF(x+4,ground-bh))
    p.setPen(QPen(tint('#6cbebf',110),1));p.drawLine(8,int(h*.9),w-8,int(h*.9))
    # Large editorial mark anchors the composition without fictitious telemetry.
    p.setFont(QFont(theme.DISPLAY,38,QFont.Weight.Black));p.setPen(QColor('#e5ee36'))
    p.drawText(QRectF(8,8,w-16,74),Qt.AlignmentFlag.AlignRight,'CT')
    p.setFont(QFont(theme.MONO,9));p.setPen(QColor('#8dc3c5'))
    p.drawText(QRectF(8,76,w-16,22),Qt.AlignmentFlag.AlignRight,'OPERATION DECK')
    p.setPen(QPen(QColor('#f06465'),2));p.drawLine(w-80,102,w-10,102)


class RasterReactor(QWidget):
    renderer='Qt logiciel'
    def __init__(self,parent=None):
        super().__init__(parent);self.phase=0.;self.motion_active=True
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        clock().widgets.add(self)
    def paintEvent(self,event):
        p=QPainter(self);draw_reactor(self,p);p.end()


def create_reactor(parent):
    return RasterReactor(parent)
