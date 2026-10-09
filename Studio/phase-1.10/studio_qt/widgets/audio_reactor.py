"""Synthetic data only. Painting and sampling are driven by the window timer."""
import math
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPainterPath, QColor, QLinearGradient, QPen, QFont
from PySide6.QtWidgets import QWidget, QSizePolicy
from ..theme import PURPLE, PINK, CYAN, MUTED


class AudioReactor(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setMinimumHeight(185);self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.setAccessibleName('Synthetic audio reactor; not live audio')
        self.levels=[.1]*72;self.peaks=[.1]*72;self.hold=[0.]*72
        self.phase=0.;self.frames=0;self.gradients=[];self.cache_height=0
        self.meter_values=None
        self.setToolTip('Synthetic spectrum and waveform. No audio capture.')

    def advance(self,dt,playing=True,intensity=.8):
        if not playing:return
        dt=max(0.,min(.1,dt));self.phase+=dt;self.frames+=1
        for i in range(72):
            target=(.10+.83*abs(math.sin(self.phase*1.6+i*.14))**2*abs(math.cos(i*.06-self.phase*.7)))*intensity
            alpha=1-math.exp(-dt/(.045 if target>self.levels[i] else .28))
            self.levels[i]+=(target-self.levels[i])*alpha
            self.hold[i]+=dt
            if self.levels[i]>=self.peaks[i]:self.peaks[i]=self.levels[i];self.hold[i]=0
            elif self.hold[i]>.25:self.peaks[i]=max(self.levels[i],self.peaks[i]-dt*.27)
        self.update()

    def _cache(self,height):
        if self.cache_height==height:return
        self.cache_height=height;self.gradients=[]
        for i in range(72):
            t=i/71
            left,right,amount=(QColor(PURPLE),QColor(PINK),t*2) if t<.5 else (QColor(PINK),QColor(CYAN),(t-.5)*2)
            color=QColor(*(round(a+(b-a)*amount) for a,b in zip(left.getRgb()[:3],right.getRgb()[:3])))
            gradient=QLinearGradient(0,height,0,10)
            gradient.setColorAt(0,color.darker(230));gradient.setColorAt(.6,color);gradient.setColorAt(1,color.lighter(125))
            self.gradients.append((gradient,color))

    def paintEvent(self,event):
        if getattr(self,'live',False):return self.paint_live()
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h=self.width(),self.height();bottom=h-42;self._cache(bottom)
        bg=QLinearGradient(0,0,w,bottom);bg.setColorAt(0,QColor('#101124'));bg.setColorAt(1,QColor('#090e1a'))
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(bg);p.drawRoundedRect(QRectF(0,0,w,bottom+3),9,9)
        p.setPen(QPen(QColor('#22263a'),.65,Qt.PenStyle.DashLine))
        for x in range(14,w,48):p.drawLine(x,8,x,bottom)
        for y in range(22,bottom,32):p.drawLine(8,y,w-8,y)
        step=(w-18)/72;bar=max(1,step-min(3,step*.30))
        for i,(gradient,color) in enumerate(self.gradients):
            x=9+i*step;height=self.levels[i]*(bottom-20)
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(gradient)
            p.drawRoundedRect(QRectF(x,bottom-height,bar,height),min(3,bar/2),min(3,bar/2))
            p.setPen(QPen(color.lighter(130),1));y=bottom-self.peaks[i]*(bottom-20)-4
            p.drawLine(QPointF(x,y),QPointF(x+bar,y))
        path=QPainterPath()
        for x in range(0,w+3,3):
            position=min(71,x/max(1,w)*71);index=int(position)
            sample=self.levels[index]*(1-(position-index))+self.levels[min(71,index+1)]*(position-index)
            wave=math.sin(x/max(1,w)*math.tau*2.8+self.phase*2)*(.10+sample*.25)
            y=bottom*.47-wave*bottom*.75
            if x==0:path.moveTo(x,y)
            else:path.lineTo(x,y)
        for width,color in ((9,QColor(243,75,172,18)),(5,QColor(243,75,172,40)),(1.8,QColor('#FF9ADD'))):
            p.setPen(QPen(color,width,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin));p.setBrush(Qt.BrushStyle.NoBrush);p.drawPath(path)
        values=[sum(self.levels[i:i+24])/24 for i in (0,24,48)];values.append(sum(values)/3)
        if self.meter_values is not None:values=self.meter_values
        font=QFont('Segoe UI');font.setPixelSize(11);p.setFont(font)
        for i,(name,color,value) in enumerate(zip(('BASS','MIDS','TREBLE','LEVEL'),(PURPLE,PINK,CYAN,'#D4C4FF'),values)):
            x=i*w/4+5;bw=w/4-14
            p.setPen(QColor(color));p.drawText(QRectF(x,h-34,bw,15),Qt.AlignmentFlag.AlignLeft,name)
            p.drawText(QRectF(x,h-34,bw,15),Qt.AlignmentFlag.AlignRight,f'{value:.0%}')
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#25283c'));p.drawRoundedRect(QRectF(x,h-13,bw,7),3,3)
            p.setBrush(QColor(color));p.drawRoundedRect(QRectF(x,h-13,bw*value,7),3,3)

    def paint_live(self):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h=self.width(),self.height();p.fillRect(self.rect(),QColor('#101124'))
        frame=getattr(self,'live_frame',None)
        values=(frame.bass,frame.mids,frame.treble) if frame else (0,0,0)
        for i,(name,value,color) in enumerate(zip(('BASS','MIDS','TREBLE'),values,(PURPLE,PINK,CYAN))):
            x=i*w/3+12;bw=w/3-24;height=max(0,min(1,value))*(h-60)
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(color));p.drawRoundedRect(QRectF(x,h-35-height,bw,height),5,5)
            p.setPen(QColor('#eeeeff'));p.drawText(QRectF(x,h-28,bw,20),Qt.AlignmentFlag.AlignCenter,f'{name} {value:.0%}')
        p.setPen(QColor('#eeeeff'));p.drawText(12,20,f'RMS {frame.energy:.4f}'+(' · BEAT' if frame.beat else '') if frame else 'Audio stopped / waiting for measured data')
