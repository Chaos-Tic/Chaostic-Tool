"""Bounded interaction animations and readable status badges."""
from PySide6.QtCore import Qt,QVariantAnimation,QPropertyAnimation,QEasingCurve,QRectF,QPointF,QObject,QEvent
from PySide6.QtGui import QColor,QPainter,QPen
from PySide6.QtWidgets import QLabel,QPushButton,QGraphicsOpacityEffect,QGraphicsDropShadowEffect,QSizePolicy

READY='#16a34a';LINUX='#0891b2';PENDING='#b45309';FAIL='#dc2626';RUNNING='#ea580c';MUTED='#5b6472'

def status_color(text):
    value=text.casefold()
    if any(w in value for w in ('échec','arrêté','interrompu','invalide')):return FAIL
    if 'en cours' in value:return RUNNING
    if any(w in value for w in ('inclus','détecté','prêt','terminé','active')):return LINUX if 'linux' in value else READY
    if any(w in value for w in ('installer','requis','configurer','à faire','passé')):return PENDING
    return MUTED

def status_pill(text,parent=None):
    pill=QLabel(str(text),parent);pill.setTextFormat(Qt.TextFormat.PlainText)
    c=QColor(status_color(text))
    pill.setSizePolicy(QSizePolicy.Policy.Maximum,QSizePolicy.Policy.Fixed)
    pill.setStyleSheet(f'color:{c.name()}; background:rgba({c.red()},{c.green()},{c.blue()},22); border:1px solid rgba({c.red()},{c.green()},{c.blue()},85); border-radius:8px; padding:5px 12px; font-size:11px; font-weight:600;')
    pill.setToolTip(str(text));pill.setAccessibleName(str(text));pill.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True)
    return pill

def glow(*args,**kwargs):return None
def pulse(*args,**kwargs):return None


class _CardHover(QObject):
    """Ombre douce + légère élévation animée au survol : donne du relief aux cartes
    sur fond clair et un retour tactile discret."""
    def __init__(self,widget,base,up):
        super().__init__(widget)
        self.eff=QGraphicsDropShadowEffect(widget)
        self.eff.setColor(QColor(23,29,46,34));self.eff.setBlurRadius(base);self.eff.setOffset(0,3)
        widget.setGraphicsEffect(self.eff)
        self.anim=QVariantAnimation(self);self.anim.setDuration(160)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(lambda v:self.eff.setBlurRadius(float(v)))
        self.base=base;self.up=up
        widget.setAttribute(Qt.WidgetAttribute.WA_Hover,True)
        widget.installEventFilter(self)
    def _to(self,target,offset):
        from desktop.hud import clock
        self.eff.setOffset(0,offset)
        if not clock().enabled:self.eff.setBlurRadius(target);return
        self.anim.stop();self.anim.setStartValue(self.eff.blurRadius());self.anim.setEndValue(target);self.anim.start()
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.Enter:self._to(self.up,8)
        elif event.type()==QEvent.Type.Leave:self._to(self.base,3)
        return False


def card_shadow(widget,base=16,up=30):
    """Attache une ombre portée + survol animé à une carte."""
    return _CardHover(widget,base,up)

class GamingButton(QPushButton):
    def __init__(self,text,parent=None):
        super().__init__(text,parent);self.hover=0.
        self.hover_anim=QVariantAnimation(self);self.hover_anim.setDuration(170)
        self.hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hover_anim.valueChanged.connect(self._hover)
        self.ripple=1.;self.ripple_center=QPointF()
        self.click_anim=QVariantAnimation(self);self.click_anim.setDuration(450)
        self.click_anim.setStartValue(0.);self.click_anim.setEndValue(1.)
        self.click_anim.valueChanged.connect(self._ripple)
    def _ripple(self,value):self.ripple=float(value);self.update()
    def mousePressEvent(self,event):
        from desktop.hud import clock
        if clock().enabled:
            self.ripple_center=event.position();self.click_anim.stop();self.click_anim.start()
        super().mousePressEvent(event)
    def _hover(self,value):self.hover=float(value);self.update()
    def animate(self,value):
        from desktop.hud import clock
        self.hover_anim.stop()
        if not clock().enabled:self._hover(value);return
        self.hover_anim.setStartValue(self.hover);self.hover_anim.setEndValue(value);self.hover_anim.start()
    def enterEvent(self,event):super().enterEvent(event);self.animate(1.)
    def leaveEvent(self,event):super().leaveEvent(event);self.animate(0.)
    def hideEvent(self,event):self.hover_anim.stop();self.click_anim.stop();self.ripple=1.;super().hideEvent(event)
    def paintEvent(self,event):
        super().paintEvent(event)
        if not self.isEnabled():return
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        from PySide6.QtGui import QPainterPath
        path=QPainterPath();path.addRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),10,10);p.setClipPath(path)
        primary=self.objectName() in ('primary','mission')
        if self.ripple<1:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255,255,255,int(60*(1-self.ripple))) if primary else QColor(234,88,12,int(40*(1-self.ripple))))
            radius=self.width()*self.ripple;p.drawEllipse(self.ripple_center,radius,radius)
        if self.hover<=0:return
        c=QColor('#ffffff' if primary else '#ea580c');c.setAlpha(int(130*self.hover))
        p.setPen(QPen(c,1));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),10,10)

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

def fade_in(widget,ms=240):
    from desktop.hud import clock
    cancel(widget,'_fade_anim')
    if not clock().enabled:widget.setGraphicsEffect(None);return
    effect=QGraphicsOpacityEffect(widget);widget.setGraphicsEffect(effect)
    anim=QPropertyAnimation(effect,b'opacity',widget);widget._fade_anim=anim
    anim.setStartValue(.12);anim.setEndValue(1.);anim.setDuration(ms);anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    def finish():
        widget._fade_anim=None;widget.setGraphicsEffect(None);anim.deleteLater()
    anim.finished.connect(finish);anim.start()
