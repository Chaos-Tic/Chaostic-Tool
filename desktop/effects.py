"""Bounded interaction animations and readable status badges."""
from PySide6.QtCore import Qt,QVariantAnimation,QPropertyAnimation,QEasingCurve,QRectF
from PySide6.QtGui import QColor,QPainter,QPen
from PySide6.QtWidgets import QLabel,QPushButton,QGraphicsOpacityEffect,QSizePolicy

READY='#63e6b5';LINUX='#56d9ee';PENDING='#f2bf78';FAIL='#ff7c97';RUNNING='#b599ff';MUTED='#99a8c7'

def status_color(text):
    value=text.casefold()
    if any(w in value for w in ('échec','arrêté','interrompu','invalide')):return FAIL
    if 'en cours' in value:return RUNNING
    if any(w in value for w in ('inclus','détecté','prêt','terminé','active')):return LINUX if 'linux' in value else READY
    if any(w in value for w in ('installer','requis','configurer','à faire','passé')):return PENDING
    return MUTED

def status_pill(text,parent=None):
    pill=QLabel(str(text),parent);pill.setTextFormat(Qt.TextFormat.PlainText)
    c=QColor(status_color(text));pill.setFixedHeight(27)
    pill.setSizePolicy(QSizePolicy.Policy.Maximum,QSizePolicy.Policy.Fixed)
    pill.setStyleSheet(f'color:{c.name()}; background:rgba({c.red()},{c.green()},{c.blue()},22); border:1px solid rgba({c.red()},{c.green()},{c.blue()},85); border-radius:7px; padding:3px 10px; font-size:11px; font-weight:600;')
    pill.setToolTip(str(text));pill.setAccessibleName(str(text));pill.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True)
    return pill

def glow(*args,**kwargs):return None
def pulse(*args,**kwargs):return None

class GamingButton(QPushButton):
    def __init__(self,text,parent=None):
        super().__init__(text,parent);self.hover=0.
        self.hover_anim=QVariantAnimation(self);self.hover_anim.setDuration(170)
        self.hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hover_anim.valueChanged.connect(self._hover)
    def _hover(self,value):self.hover=float(value);self.update()
    def animate(self,value):
        from desktop.hud import clock
        self.hover_anim.stop()
        if not clock().enabled:self._hover(value);return
        self.hover_anim.setStartValue(self.hover);self.hover_anim.setEndValue(value);self.hover_anim.start()
    def enterEvent(self,event):super().enterEvent(event);self.animate(1.)
    def leaveEvent(self,event):super().leaveEvent(event);self.animate(0.)
    def hideEvent(self,event):self.hover_anim.stop();super().hideEvent(event)
    def paintEvent(self,event):
        super().paintEvent(event)
        if self.hover<=0 or not self.isEnabled():return
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c=QColor('#bb9eff' if self.objectName()=='primary' else '#6eddeb');c.setAlpha(int(170*self.hover))
        p.setPen(QPen(c,1));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),8,8)

def cancel(widget,name):
    animation=getattr(widget,name,None)
    if animation is not None:
        animation.stop();animation.deleteLater();setattr(widget,name,None)

def count_up(label,value,ms=420):
    from desktop.hud import clock
    cancel(label,'_count_anim')
    try:start=int(label.text())
    except ValueError:start=0
    if start==value or not clock().enabled:label.setText(str(value));return
    anim=QVariantAnimation(label);label._count_anim=anim
    anim.setStartValue(start);anim.setEndValue(int(value));anim.setDuration(ms);anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.valueChanged.connect(lambda v:label.setText(str(int(v))))
    def finish():
        label.setText(str(value));label._count_anim=None;anim.deleteLater()
    anim.finished.connect(finish);anim.start()

def fade_in(widget,ms=180):
    from desktop.hud import clock
    cancel(widget,'_fade_anim')
    if not clock().enabled:widget.setGraphicsEffect(None);return
    effect=QGraphicsOpacityEffect(widget);widget.setGraphicsEffect(effect)
    anim=QPropertyAnimation(effect,b'opacity',widget);widget._fade_anim=anim
    anim.setStartValue(.35);anim.setEndValue(1.);anim.setDuration(ms);anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    def finish():
        widget._fade_anim=None;widget.setGraphicsEffect(None);anim.deleteLater()
    anim.finished.connect(finish);anim.start()
