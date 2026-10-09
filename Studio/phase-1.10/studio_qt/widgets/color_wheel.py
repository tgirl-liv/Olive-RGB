import math
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QConicalGradient
from PySide6.QtWidgets import QWidget


class ColorWheel(QWidget):
    hueChanged = Signal(float)

    def __init__(self):
        super().__init__()
        self.hsv = (.75, .8, .9)
        self.setMinimumSize(180, 180)
        self.setMaximumHeight(270)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('Hue wheel; use arrow keys to change hue')

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height()) - 18
        c = QPointF(self.width()/2, self.height()/2)
        r = side/2
        gradient = QConicalGradient(c, 0)
        for i in range(13): gradient.setColorAt(i/12, QColor.fromHsvF(i/12, 1, 1))
        p.setPen(QPen(gradient, r*.39)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, r*.78, r*.78)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor.fromHsvF(*self.hsv))
        p.drawEllipse(c, r*.43, r*.43)
        a = self.hsv[0]*math.tau
        pos = c + QPointF(math.cos(a)*r*.78, -math.sin(a)*r*.78)
        p.setPen(QPen(QColor('#FFFFFF'), 2)); p.setBrush(QColor.fromHsvF(self.hsv[0], 1, 1))
        p.drawEllipse(pos, 8, 8)
        if self.hasFocus():
            p.setPen(QPen(QColor('#C8ABFF'), 1, Qt.PenStyle.DotLine)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(2,2,-2,-2), 12,12)

    def mousePressEvent(self, event): self.mouseMoveEvent(event)
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            d = event.position()-QPointF(self.width()/2,self.height()/2)
            self.hueChanged.emit((math.atan2(-d.y(), d.x())/math.tau)%1)
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.hueChanged.emit((self.hsv[0]+(-1 if event.key()==Qt.Key.Key_Left else 1)/360)%1)
        else: super().keyPressEvent(event)
