"""Canvas visuals and scroll containers. Animation is owned by the app."""
import colorsys
import math
import tkinter as tk
from tkinter import ttk

from .theme import (BG, PANEL, RAISED, LINE, TEXT, MUTED, PINK, PURPLE, CYAN,
                    WELL, SELECTED, HOVER, DISABLED, FOCUS, TYPE, RADIUS,
                    ATTACK_SECONDS, DECAY_SECONDS, PEAK_HOLD_SECONDS,
                    PEAK_DECAY_PER_SECOND)


def blend(a, b, amount):
    amount=max(0.,min(1.,amount))
    a, b = a.lstrip('#'), b.lstrip('#')
    return '#'+''.join(f'{round(int(a[i:i+2],16)*(1-amount)+int(b[i:i+2],16)*amount):02x}' for i in (0,2,4))


def rounded(canvas,x1,y1,x2,y2,r=8,**kw):
    return canvas.create_polygon(x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,
                                 x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1,
                                 smooth=True,splinesteps=12,**kw)


class NeonSlider(tk.Canvas):
    """Focusable Canvas slider: mouse/drag, arrows, Home/End, and Tk variable."""
    def __init__(self,parent,value=0,command=None,low=0,high=1,variable=None,vertical=False,color=PURPLE):
        super().__init__(parent,bg=parent.cget('bg'),highlightthickness=0,
                         width=28 if vertical else 100,height=190 if vertical else 25,takefocus=True)
        self.low=low;self.high=high;self.command=command;self.vertical=vertical;self.color=color;self.hover=False
        self.bind('<Enter>',lambda _:self.hovering(True));self.bind('<Leave>',lambda _:self.hovering(False))
        self._value=variable or tk.DoubleVar(value=value)
        self.trace=self._value.trace_add('write',lambda *_:self.draw())
        self.bind('<Configure>',lambda _:self.draw())
        self.bind('<FocusIn>',lambda _:self.draw());self.bind('<FocusOut>',lambda _:self.draw())
        self.bind('<Button-1>',self.pick);self.bind('<B1-Motion>',self.pick)
        for key,sign in (('Left',-1),('Down',-1),('Right',1),('Up',1)):
            self.bind('<'+key+'>',lambda _,s=sign:self.change(self._value.get()+s*(self.high-self.low)/100))
        self.bind('<Home>',lambda _:self.change(self.low));self.bind('<End>',lambda _:self.change(self.high))
        self.bind('<Destroy>',self.cleanup)

    def hovering(self,value):
        self.hover=value;self.draw()

    def cleanup(self,event):
        if event.widget is self:self._value.trace_remove('write',self.trace)

    def change(self,value):
        self._value.set(max(self.low,min(self.high,value)))
        if self.command:self.command(self._value.get())
        return 'break'

    def pick(self,event):
        self.focus_set()
        length=self.winfo_height() if self.vertical else self.winfo_width()
        t=((length-event.y-10) if self.vertical else (event.x-10))/max(1,length-20)
        self.change(self.low+max(0,min(1,t))*(self.high-self.low))

    def draw(self):
        if not self.winfo_exists():return
        self.delete('all');w=self.winfo_width();h=self.winfo_height()
        t=max(0,min(1,(self._value.get()-self.low)/max(.0001,self.high-self.low)))
        if self.vertical:
            rounded(self,w/2-6,9,w/2+6,h-9,6,fill=RAISED,outline=LINE)
            y=h-10-t*(h-20)
            for row in range(int(y),max(int(y)+1,h-10),2):
                self.create_line(w/2-5,row,w/2+5,row,fill=blend('#6635B5','#F6ECFF',(h-row)/max(1,h)),width=2)
            x=w/2
        else:
            rounded(self,9,h/2-5,w-9,h/2+5,5,fill=RAISED,outline=LINE)
            x=10+t*(w-20);y=h/2
            for col in range(10,max(11,int(x)),3):
                self.create_line(col,h/2-4,col,h/2+4,fill=blend('#7432E8',self.color,col/max(1,w)),width=3)
        self.create_oval(x-10,y-10,x+10,y+10,fill=blend(PANEL,self.color,.25),outline='')
        self.create_oval(x-6,y-6,x+6,y+6,fill=TEXT,outline=FOCUS if self.hover else self.color)
        if self.focus_get() is self:self.create_rectangle(1,1,w-2,h-2,outline=FOCUS,dash=(2,2))


class NeonButton(tk.Canvas):
    """Canvas action retaining Tab, Space, Return and visible focus."""
    def __init__(self,parent,text='',command=None,width=96,height=32,accent=False):
        super().__init__(parent,width=width,height=height,bg=parent.cget('bg'),highlightthickness=0,takefocus=True,cursor='hand2')
        self.text=text;self.command=command;self.accent=accent;self.hover=False;self.pressed=False;self.disabled=False
        self.bind('<Configure>',lambda _:self.draw())
        self.bind('<Enter>',lambda _:self.hovering(True));self.bind('<Leave>',lambda _:self.hovering(False))
        self.bind('<ButtonPress-1>',self.press);self.bind('<ButtonRelease-1>',self.release)
        self.bind('<Return>',lambda _:self.invoke());self.bind('<space>',lambda _:self.invoke())
        self.bind('<FocusIn>',lambda _:self.draw());self.bind('<FocusOut>',lambda _:self.draw())

    def configure(self,cnf=None,**kw):
        if 'text' in kw:self.text=kw.pop('text')
        if 'accent' in kw:self.accent=kw.pop('accent')
        if 'state' in kw:self.disabled=kw['state']=='disabled'
        super().configure(cnf,**kw);self.draw()

    def hovering(self,value):self.hover=value;self.draw()
    def press(self,event):self.focus_set();self.pressed=True;self.draw()
    def release(self,event):
        pressed=self.pressed;self.pressed=False;self.draw()
        if pressed and 0<=event.x<self.winfo_width() and 0<=event.y<self.winfo_height():self.invoke()
    def invoke(self):
        if self.command and not self.disabled:self.command()
        return 'break'
    def draw(self):
        if not self.winfo_exists():return
        self.delete('all');w=self.winfo_width();h=self.winfo_height()
        fill=SELECTED if self.accent else RAISED
        if self.hover and not self.disabled:fill=HOVER if not self.accent else blend(SELECTED,PURPLE,.25)
        if self.pressed:fill=blend(fill,'#000000',.2)
        rounded(self,1,1,w-2,h-2,RADIUS['control'],fill=fill,outline=PURPLE if self.accent or self.focus_get() is self else LINE)
        self.create_text(w/2,h/2,text=self.text,fill=DISABLED if self.disabled else TEXT,font=TYPE['control'])


class ScrollArea(ttk.Frame):
    def __init__(self, parent, background=BG):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=background, highlightthickness=0, width=100)
        bar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right',fill='y')
        self.canvas.pack(side='left',fill='both',expand=True)
        self.body = tk.Frame(self.canvas, bg=background)
        self.window = self.canvas.create_window(0,0,window=self.body,anchor='nw')
        self.body.bind('<Configure>',lambda _:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.window,width=e.width))


class Reactor(tk.Canvas):
    """Retained Canvas geometry: no per-frame creation of hundreds of objects."""
    def __init__(self,parent):
        super().__init__(parent,bg=WELL,highlightthickness=1,highlightbackground=LINE,height=235)
        self.levels=[.05]*60;self.peaks=[.05]*60;self.peak_age=[0.]*60
        self.last_phase=None;self.last_enabled=None;self.last_key=None;self.geometry_size=None
        self.summary=(0.,0.,0.,0.);self.bars=[];self.markers=[];self.waves=[]

    def _build(self,w,h):
        self.delete('all');self.bars=[];self.markers=[];self.waves=[]
        for y in range(1,h,4):self.create_rectangle(1,y,w-1,y+4,fill=blend('#121426',WELL,y/h),outline='')
        for y in range(24,h,32):self.create_line(0,y,w,y,fill='#25263A',dash=(1,5))
        for x in range(24,w,48):self.create_line(x,0,x,h,fill='#29273E',dash=(1,5))
        anchors=((0.,'#8242EB'),(.25,PURPLE),(.48,PINK),(.64,'#D947C7'),(.80,CYAN),(1.,'#388EE8'))
        for i in range(60):
            t=i/59
            for (lo,a),(hi,b) in zip(anchors,anchors[1:]):
                if lo<=t<=hi:color=blend(a,b,(t-lo)/(hi-lo));break
            parts=[]
            for part in range(5):
                parts.append(self.create_rectangle(0,0,0,0,fill=blend('#151728',color,.42+.58*part/4),outline=''))
            self.bars.append(parts)
            self.markers.append(self.create_line(0,0,0,0,fill=blend(color,TEXT,.45),width=1))
        for width,color in ((7,'#332039'),(4,'#773156'),(1.6,'#FF8AD2')):
            self.waves.append(self.create_line(0,0,1,1,fill=color,width=width,smooth=True))
        self.geometry_size=(w,h)

    def draw(self,phase,enabled,intensity=1.):
        w=max(100,self.winfo_width());h=max(80,self.winfo_height())
        key=(phase,enabled,intensity,w,h)
        if key==self.last_key:return
        previous=self.last_phase;dt=.034 if previous is None else max(0,min(.1,phase-previous))
        changed=phase!=previous or enabled!=self.last_enabled
        if self.geometry_size!=(w,h):self._build(w,h)
        first=previous is None
        for i in range(60):
            target=(.12+.82*abs(math.sin(phase*1.6+i*.16))**2*abs(math.cos(i*.063-phase*.7)))*intensity if enabled else .015
            if changed or self.last_key is None or intensity!=self.last_key[2]:
                duration=ATTACK_SECONDS if target>self.levels[i] else DECAY_SECONDS
                alpha=1. if first or dt==0 else 1.-math.exp(-dt/duration)
                self.levels[i]+=(target-self.levels[i])*alpha
                self.peak_age[i]+=dt
                if self.levels[i]>=self.peaks[i]:self.peaks[i]=self.levels[i];self.peak_age[i]=0
                elif self.peak_age[i]>PEAK_HOLD_SECONDS:self.peaks[i]=max(self.levels[i],self.peaks[i]-dt*PEAK_DECAY_PER_SECOND)
        self.last_phase=phase;self.last_enabled=enabled;self.last_key=key
        base=h-9;step=(w-16)/60;bw=max(1,step*.68)
        for i in range(60):
            x=8+i*step;height=self.levels[i]*(h-30)
            for part,item in enumerate(self.bars[i]):self.coords(item,x,base-height*(part+1)/5,x+bw,base-height*part/5+1)
            peak=base-self.peaks[i]*(h-30)-4;self.coords(self.markers[i],x,peak,x+bw,peak)
        points=[]
        for x in range(0,w+2,4):
            sample=self.levels[min(59,int(x/max(1,w)*59))]
            wave=math.sin(x/w*math.tau*2.5+phase*2)*(.10+sample*.26)+.03*math.sin(x/w*math.tau*7-phase)
            points.extend((x,h*.48-wave*h*.7 if enabled else h*.6))
        for item in self.waves:self.coords(item,*points)
        bands=tuple(sum(self.levels[i:i+20])/20 for i in (0,20,40));self.summary=(*bands,sum(bands)/3)


class ColorWheel(tk.Canvas):
    def __init__(self,parent,command):
        super().__init__(parent,width=235,height=228,bg=PANEL,highlightthickness=0,cursor='crosshair',takefocus=True)
        self.command=command;self.hsv=(0.,1.,1.)
        self.bind('<Configure>',lambda _:self.draw())
        self.bind('<Button-1>',self.pick);self.bind('<B1-Motion>',self.pick)
        self.bind('<Left>',lambda _:self.command((self.hsv[0]-.01)%1,*self.hsv[1:]))
        self.bind('<Right>',lambda _:self.command((self.hsv[0]+.01)%1,*self.hsv[1:]))
        self.bind('<FocusIn>',lambda _:self.draw());self.bind('<FocusOut>',lambda _:self.draw())

    def draw(self):
        self.delete('all');cx=self.winfo_width()/2;cy=self.winfo_height()/2;r=min(cx-6,cy-6)
        for ring in range(8,0,-1):
            rr=r*(.59+ring*.05125)
            for i in range(180):
                rgb=colorsys.hsv_to_rgb(i/180,.65+ring*.04375,1)
                color='#'+''.join(f'{round(c*255):02x}' for c in rgb)
                self.create_arc(cx-rr,cy-rr,cx+rr,cy+rr,start=i*2,extent=2.2,fill=color,outline='',style='pieslice')
        self.create_oval(cx-r*.59,cy-r*.59,cx+r*.59,cy+r*.59,fill=BG,outline=BG)
        color='#'+''.join(f'{round(c*255):02x}' for c in colorsys.hsv_to_rgb(*self.hsv))
        self.create_oval(cx-r*.46,cy-r*.46,cx+r*.46,cy+r*.46,fill=color,outline='')
        h,_,_=self.hsv;x=cx+r*.81*math.cos(h*math.tau);y=cy-r*.81*math.sin(h*math.tau)
        self.create_oval(x-10,y-10,x+10,y+10,outline=WELL,width=3)
        self.create_oval(x-8,y-8,x+8,y+8,outline=TEXT,width=2)
        if self.focus_get() is self:self.create_rectangle(1,1,self.winfo_width()-2,self.winfo_height()-2,outline=FOCUS,dash=(2,2))

    def pick(self,event):
        self.focus_set();dx=event.x-self.winfo_width()/2;dy=self.winfo_height()/2-event.y
        h=math.atan2(dy,dx)/math.tau%1
        self.command(h,self.hsv[1],self.hsv[2])


class ScenePad(tk.Canvas):
    def __init__(self,parent,name,colors,select,favorite):
        super().__init__(parent,height=116,bg=PANEL,highlightthickness=0,cursor='hand2',width=100,takefocus=True)
        self.name=name;self.colors=colors;self.active=False;self.favorite=False
        self.duration=1.2;self.hover=False;self.pressed=False
        self.select=select;self.fav_command=favorite
        self.bind('<Configure>',lambda _:self.draw())
        self.bind('<ButtonPress-1>',self.press);self.bind('<ButtonRelease-1>',self.click)
        self.bind('<Enter>',lambda _:self.hovering(True));self.bind('<Leave>',lambda _:self.hovering(False))
        self.bind('<Return>',lambda _:self.select(self.name));self.bind('<space>',lambda _:self.select(self.name))
        self.bind('<Key-f>',lambda _:self.fav_command(self.name))
        self.bind('<FocusIn>',lambda _:self.draw());self.bind('<FocusOut>',lambda _:self.draw())

    def hovering(self,value):self.hover=value;self.draw()
    def press(self,event):self.focus_set();self.pressed=True;self.draw()
    def click(self,event):
        pressed=self.pressed;self.pressed=False
        if pressed and 0<=event.x<self.winfo_width() and 0<=event.y<self.winfo_height():
            if event.x>self.winfo_width()-32 and event.y<32:self.fav_command(self.name)
            else:self.select(self.name)
        self.draw()

    def draw(self):
        self.delete('all');w=max(30,self.winfo_width());h=self.winfo_height()
        a,b,_=self.colors
        for y in range(3,h-3,3):
            self.create_rectangle(3,y,w-3,y+3,fill=blend(a,blend(b,'#060617',.65),y/h),outline='')
        # Bundled vector-like artwork: mountains, moon, skyline, waves or lasers.
        if self.name in ('MGK After Dark','Sunset Chill'):
            self.create_oval(w*.35,14,w*.64,14+w*.29,fill=blend(a,'#FFF9DB',.65),outline='')
            for layer in range(3):
                pts=[3,h]
                for x in range(3,int(w),8):pts.extend((x,38+layer*12+14*math.sin(x*.07+layer*2)))
                pts.extend((w-3,h))
                self.create_polygon(*pts,fill=blend(b,'#0A0917',.2+layer*.2),outline='')
        elif self.name=='Cyber Night':
            for i in range(12):
                x=4+i*w/12;height=22+(i*17%47)
                self.create_rectangle(x,75-height,x+w/15,80,fill=blend('#070A21',b,.27),outline=blend(a,'#111123',.4))
                for y in range(int(78-height),75,7):self.create_line(x+3,y,x+w/18,y,fill=a if i%2 else b,width=1)
            self.create_line(w/2,40,w*.27,h,w*.75,h,w/2,40,fill=PINK,width=2)
        elif self.name=='Ocean Breeze':
            for layer in range(7):
                points=[]
                for x in range(3,int(w)-2,4):points.extend((x,25+layer*9+8*math.sin(x*.04+layer)))
                self.create_line(*points,fill=blend(a,'#D9FFFF',layer/9),width=2,smooth=True)
        elif self.name=='Movie Mode':
            self.create_rectangle(12,12,w-12,76,fill='#0B1427',outline=a,width=3)
            self.create_polygon(w*.35,64,w*.55,25,w*.72,64,fill=b,outline=CYAN)
            self.create_line(10,80,w-10,80,fill=a,width=4)
        elif self.name=='Neon Party':
            for inset,color in ((0,PINK),(18,CYAN),(34,PURPLE)):
                self.create_line(12+inset,77,w*.5,11+inset/3,w-12-inset,77,12+inset,77,fill=color,width=2)
        else:
            for i in range(14):
                x=(i*37)%max(1,int(w));y=12+(i*29)%60;r=10+i%5*4
                self.create_oval(x-r,y-r,x+r,y+r,fill=blend(b,a,(i%5)/6),outline=blend(a,'#CFFFFF',.2))
            self.create_line(5,65,w*.28,37,w*.52,60,w*.72,23,w-7,49,fill=blend(a,TEXT,.7),width=2,smooth=True)
        for i in range(35):
            y=h-39+i
            self.create_line(3,y,w-3,y,fill=blend(blend(b,'#0A0917',.4),'#0C0D18',i/38))
        border=PINK if self.active else PURPLE if self.hover or self.focus_get() is self else LINE
        rounded(self,2,2,w-3,h-3,8,fill='',outline=border,width=3 if self.active else 1)
        if self.pressed:rounded(self,5,5,w-6,h-6,6,fill='',outline=TEXT,width=2)
        self.create_text(w-17,17,text='★' if self.favorite else '☆',fill=TEXT,font=('Segoe UI',15))
        rounded(self,4,h-31,w-5,h-4,4,fill=WELL,outline='')
        self.create_text(12,h-18,text=self.name,anchor='w',fill=TEXT,font=('Segoe UI',10,'bold'))
        if self.active:self.create_line(5,9,5,h-9,fill=PINK,width=3)
        rounded(self,9,9,43,26,6,fill=blend(WELL,self.colors[1],.12),outline='')
        self.create_text(26,17,text=f'{self.duration:g}s',fill=TEXT,font=TYPE['caption'])
