"""Local vector icons, drawn at the requested Qt device scale."""
import math
from PySide6.QtCore import QRect, QRectF, QPointF, Qt, QSize
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPixmap, QPainterPath, QPen, QColor


class VectorIcon(QIconEngine):
    def __init__(self, name):super().__init__();self.name=name
    def clone(self):return VectorIcon(self.name)
    def pixmap(self,size,mode,state):
        result=QPixmap(size);result.fill(Qt.GlobalColor.transparent)
        painter=QPainter(result);self.paint(painter,QRect(0,0,size.width(),size.height()),mode,state);painter.end()
        return result
    def scaledPixmap(self,size,mode,state,scale):
        result=self.pixmap(QSize(round(size.width()*scale),round(size.height()*scale)),mode,state)
        result.setDevicePixelRatio(scale)
        return result
    def paint(self,p,rect,mode,state):
        p.save();p.setRenderHint(p.RenderHint.Antialiasing)
        size=min(rect.width(),rect.height());p.translate(rect.x()+(rect.width()-size)/2,rect.y()+(rect.height()-size)/2);p.scale(size/24,size/24)
        color=QColor('#68677c' if mode==QIcon.Mode.Disabled else '#ffffff' if mode==QIcon.Mode.Active else '#edb7ff' if state==QIcon.State.On else '#d4cce8')
        p.setPen(QPen(color,1.75,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin));p.setBrush(Qt.BrushStyle.NoBrush)
        n=self.name
        if n=='Studio':
            path=QPainterPath(QPointF(3,11));path.lineTo(12,3);path.lineTo(21,11);path.moveTo(5,10);path.lineTo(5,21);path.lineTo(10,21);path.lineTo(10,15);path.lineTo(14,15);path.lineTo(14,21);path.lineTo(19,21);path.lineTo(19,10);p.drawPath(path)
        elif n=='Music':
            p.drawLine(9,17,9,5);p.drawLine(9,5,20,3);p.drawLine(20,3,20,15);p.drawEllipse(QRectF(3,16,6,5));p.drawEllipse(QRectF(14,14,6,5))
        elif n=='Devices':
            path=QPainterPath(QPointF(9,17));path.lineTo(9,15);path.cubicTo(2,9,7,3,12,3);path.cubicTo(17,3,22,9,15,15);path.lineTo(15,17);path.closeSubpath();p.drawPath(path)
            p.drawLine(9,20,15,20);p.drawLine(11,22,13,22)
        elif n=='Screen':
            p.drawRoundedRect(QRectF(3,4,18,13),2,2);p.drawLine(12,17,12,21);p.drawLine(8,21,16,21)
        elif n=='Scenes':
            for x in (3,14):
                for y in (3,14):p.drawRoundedRect(QRectF(x,y,7,7),1.5,1.5)
        elif n=='Settings':
            path=QPainterPath()
            for i in range(48):
                angle=i*math.tau/48;radius=9 if i%6 in (1,2,3) else 7.3
                point=QPointF(12+radius*math.cos(angle),12+radius*math.sin(angle))
                if i==0:path.moveTo(point)
                else:path.lineTo(point)
            path.closeSubpath();p.drawPath(path);p.drawEllipse(QPointF(12,12),3,3)
        elif n=='Power':
            p.drawArc(QRectF(4,4,16,16),135*16,270*16);p.drawLine(12,3,12,11)
        elif n=='Favorite':
            path=QPainterPath(QPointF(12,20));path.cubicTo(10,18,3,13,3,8);path.cubicTo(3,3,9,2,12,7);path.cubicTo(15,2,21,3,21,8);path.cubicTo(21,13,14,18,12,20)
            if state==QIcon.State.On:p.setBrush(color)
            p.drawPath(path)
        elif n=='Logo':
            for x,y in [(4,9),(8,5),(12,2),(16,7),(20,10)]:p.drawLine(x,y,x,24-y)
        p.restore()


def icon(name):return QIcon(VectorIcon(name))
