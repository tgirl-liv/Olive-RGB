"""DPR-independent cached QPainter artwork. No external image loading."""
import math
import random
from functools import lru_cache
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QPainter, QPainterPath, QColor, QImage, QLinearGradient, QRadialGradient, QPen, QFont
from PySide6.QtWidgets import QAbstractButton, QToolButton, QScrollArea
from studio_ui.state import SCENES
from ..theme import TEXT, PINK, PURPLE


@lru_cache(maxsize=8)
def artwork(name):
    image=QImage(720,400,QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor('#080b19'));p=QPainter(image);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    a,b,_=SCENES[name];rng=random.Random(name)
    sky=QLinearGradient(0,0,600,400);sky.setColorAt(0,QColor(a).darker(180));sky.setColorAt(.55,QColor(b));sky.setColorAt(1,QColor('#060a1c'))
    p.fillRect(image.rect(),sky)
    p.setPen(Qt.PenStyle.NoPen)
    for i in range(85):
        p.setBrush(QColor(235,222,255,rng.randrange(25,170)));r=rng.uniform(.5,1.6)
        p.drawEllipse(QPointF(rng.randrange(720),rng.randrange(240)),r,r)
    if name in ('MGK After Dark','Ultraviolet','BRAT Energy'):
        # Soft radial cloud banks, rendered once at high resolution.
        for layer in range(3):
            for i in range(22):
                x=rng.randrange(-50,770);y=120+layer*75+rng.randrange(-30,65);radius=rng.randrange(40,120)
                cloud=QRadialGradient(x,y,radius)
                c=QColor(a if layer%2==0 else b);c.setAlpha(150 if layer<2 else 230)
                cloud.setColorAt(0,c);edge=QColor(c);edge.setAlpha(0);cloud.setColorAt(1,edge)
                p.setBrush(cloud);p.drawEllipse(QPointF(x,y),radius,radius*.8)
        p.setPen(QPen(QColor('#F5B8FF' if name!='BRAT Energy' else '#E1FF94'),3))
        if name=='MGK After Dark':
            heart=QPainterPath();heart.moveTo(360,200);heart.cubicTo(240,125,300,40,360,110);heart.cubicTo(420,40,480,125,360,200)
            p.setBrush(QColor(255,85,210,80));p.drawPath(heart)
        else:
            path=QPainterPath(QPointF(60,210))
            for i in range(1,12):path.lineTo(60+i*52,180+rng.randrange(-75,70))
            p.drawPath(path)
    elif name=='Cyber Night':
        for i in range(23):
            x=i*33;y=rng.randrange(20,200);width=rng.randrange(22,36)
            p.fillRect(QRectF(x,y,width,330-y),QColor('#0b1730'))
            p.setPen(QPen(QColor(a if i%2 else b),2));p.drawLine(QPointF(x,y),QPointF(x,330))
            for yy in range(y+10,300,16):
                for xx in range(x+5,x+width-3,9):p.fillRect(QRectF(xx,yy,3,5),QColor(a if rng.random()>.3 else b))
        road=QPainterPath();road.moveTo(350,180);road.lineTo(250,400);road.lineTo(520,400);road.closeSubpath()
        p.fillPath(road,QColor('#171330'));p.setPen(QPen(QColor('#F74EC2'),3));p.drawLine(350,180,265,400);p.drawLine(360,180,510,400)
    elif name in ('Sunset Chill','Ocean Breeze'):
        sun=QRadialGradient(420,120,90);sun.setColorAt(0,QColor('#FFF5D4'));sun.setColorAt(.5,QColor('#FFC597'));sun.setColorAt(1,QColor(255,143,169,0))
        p.setBrush(sun);p.setPen(Qt.PenStyle.NoPen);p.drawEllipse(QPointF(420,120),90,90)
        for layer in range(7):
            path=QPainterPath(QPointF(0,400));base=165+layer*29
            for x in range(0,725,8):path.lineTo(x,base+math.sin(x*.014+layer)*23+math.sin(x*.031+layer)*9)
            path.lineTo(720,400);path.closeSubpath()
            c=QColor(b).darker(100+layer*27);p.fillPath(path,c)
            if name=='Ocean Breeze':p.setPen(QPen(QColor(115,230,255,130),2));p.drawPath(path);p.setPen(Qt.PenStyle.NoPen)
    elif name=='Neon Party':
        for i in range(8):
            color=QColor(a if i%2==0 else '#45DDFF');color.setAlpha(210-i*14)
            path=QPainterPath(QPointF(80+i*18,335));path.lineTo(355,30+i*18);path.lineTo(650-i*18,335);path.closeSubpath()
            for thickness,alpha in ((14,20),(6,60),(2,230)):
                c=QColor(color);c.setAlpha(alpha);p.setPen(QPen(c,thickness));p.setBrush(Qt.BrushStyle.NoBrush);p.drawPath(path)
    else:
        for x in range(0,170,18):p.fillRect(QRectF(x,0,7,340),QColor('#8C5528'))
        p.fillRect(QRectF(180,35,475,255),QColor('#080a15'))
        for i in range(5):
            p.setPen(QPen(QColor('#497FF4'),2));p.drawEllipse(QRectF(330-i*16,75-i*7,180+i*32,130+i*14))
        p.fillRect(QRectF(160,298,510,10),QColor('#DC8E3E'));p.fillRect(QRectF(250,330,300,50),QColor('#181928'))
    fade=QLinearGradient(0,180,0,400);fade.setColorAt(0,QColor(8,10,22,0));fade.setColorAt(1,QColor(8,10,22,245));p.fillRect(image.rect(),fade)
    p.end();return image


class ScenePad(QAbstractButton):
    def __init__(self,name,controller,parent=None):
        super().__init__(parent);self.name=name;self.controller=controller;self.hover=False
        self.setMinimumSize(125,96);self.setFixedHeight(100);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(name+' scene');self.setToolTip(name+' · Enter/Space to recall · F to favorite')
        self.favorite=QToolButton(self);self.favorite.setCheckable(True);self.favorite.setFixedSize(27,27)
        from .icons import icon
        from PySide6.QtCore import QSize
        self.favorite.setIcon(icon('Favorite'));self.favorite.setIconSize(QSize(17,17))
        self.favorite.setStyleSheet('QToolButton {background:rgba(12,12,25,190);border:1px solid transparent;border-radius:13px;} QToolButton:hover {background:#493052;border-color:#bb81da;} QToolButton:checked {background:#5b2453;} QToolButton:focus {border:2px solid white;} QToolButton:disabled {background:#242330;}')
        self.favorite.setAccessibleName('Favorite '+name);self.favorite.setToolTip('Favorite '+name)
        self.favorite.clicked.connect(lambda:self.controller.favorite(name));self.clicked.connect(lambda:self.controller.select_scene(name))
        controller.changed.connect(self.sync);self.sync()

    def sync(self):
        from .common import assign
        assign(self.favorite,self.name in self.controller.state.favorites)
        self.favorite.setText('');self.update()

    def mouseReleaseEvent(self,event):
        # Clicking a scene changes the active card and emits a panel refresh.
        # Qt may subsequently scroll its QScrollArea to the focused button,
        # even though the mouse click did not request navigation. Preserve
        # the user's viewport for mouse activation; keyboard focus still uses
        # Qt's normal ensure-visible behavior.
        area=self.parentWidget()
        while area is not None and not isinstance(area,QScrollArea):
            area=area.parentWidget()
        bar=area.verticalScrollBar() if area is not None else None
        position=bar.value() if bar is not None else None
        super().mouseReleaseEvent(event)
        if bar is not None and position is not None:
            QTimer.singleShot(0,lambda b=bar,p=position:b.setValue(p))

    def resizeEvent(self,event):self.favorite.move(self.width()-35,7);super().resizeEvent(event)
    def enterEvent(self,event):self.hover=True;self.update();super().enterEvent(event)
    def leaveEvent(self,event):self.hover=False;self.update();super().leaveEvent(event)
    def focusInEvent(self,event):self.update();super().focusInEvent(event)
    def focusOutEvent(self,event):self.update();super().focusOutEvent(event)
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_F:self.controller.favorite(self.name);event.accept()
        elif event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.click();event.accept()
        else:super().keyPressEvent(event)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect=QRectF(self.rect()).adjusted(2,2,-2,-2);path=QPainterPath();path.addRoundedRect(rect,10,10)
        p.setClipPath(path)
        art=artwork(self.name);ratio=rect.width()/rect.height();source=QRectF(art.rect())
        if source.width()/source.height()>ratio:
            width=source.height()*ratio;source.adjust((source.width()-width)/2,0,-(source.width()-width)/2,0)
        else:
            height=source.width()/ratio;source.adjust(0,(source.height()-height)/2,0,-(source.height()-height)/2)
        p.drawImage(rect,art,source)
        shade=QLinearGradient(0,self.height()-53,0,self.height());shade.setColorAt(0,QColor(10,10,23,0));shade.setColorAt(.45,QColor(10,10,23,195));shade.setColorAt(1,QColor(10,10,23,240));p.fillRect(rect,shade)
        if self.hover:p.fillPath(path,QColor(181,122,255,20))
        if self.isDown():p.fillPath(path,QColor(0,0,0,65))
        p.setClipping(False)
        active=self.controller.state.scene==self.name and self.controller.state.mode=='Manual' and self.controller.scene_active
        p.setPen(QPen(QColor(PINK if active else '#E2C8FF' if self.hasFocus() else PURPLE if self.hover else '#403653'),2 if active or self.hasFocus() else 1))
        p.setBrush(Qt.BrushStyle.NoBrush);p.drawPath(path)
        if active:
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(PINK));p.drawRoundedRect(QRectF(3,self.height()-46,3,35),1.5,1.5)
        p.setPen(QColor(TEXT));font=QFont('Segoe UI');font.setPixelSize(13);font.setWeight(QFont.Weight.DemiBold);p.setFont(font)
        p.drawText(self.label_rect(),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter|Qt.TextFlag.TextWordWrap,self.name)
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(10,10,23,205));p.drawRoundedRect(QRectF(9,9,36,20),5,5)
        font.setPixelSize(11);p.setFont(font);p.setPen(QColor('#eee3ff'))
        p.drawText(QRectF(9,9,36,20),Qt.AlignmentFlag.AlignCenter,'LIVE' if getattr(self.controller.adapter,'live',False) else f'{self.controller.state.transition_seconds:g}s')

    def label_rect(self):return QRectF(12,self.height()-43,self.width()-24,37)
