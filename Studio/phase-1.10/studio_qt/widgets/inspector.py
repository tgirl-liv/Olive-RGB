from PySide6.QtCore import Slot, QSignalBlocker
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QTabWidget,QComboBox,QSpinBox,QLineEdit,QCheckBox,QSizePolicy
from PySide6.QtGui import QColor
from .common import Panel,text,button,slider,assign
from .color_wheel import ColorWheel


class Inspector(Panel):
    def __init__(self,c):
        super().__init__('DEVICE INSPECTOR');self.c=c
        self.device=QComboBox();self.device.setAccessibleName('Inspector device')
        for key,channel in c.state.channels.items():self.device.addItem(channel.name,key)
        self.device.currentIndexChanged.connect(lambda i:c.select_channel(self.device.itemData(i)))
        self.box.addWidget(self.device)
        self.statuses={};self.device_name=text('Philips Hue','heading');self.box.addWidget(self.device_name)
        self.status=text('DEMO · awaiting mock status','demo');self.box.addWidget(self.status)
        self.tabs=QTabWidget();self.tabs.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Maximum);self.tabs.tabBar().setExpanding(True);self.box.addWidget(self.tabs)
        color=QWidget();layout=QVBoxLayout(color);layout.setContentsMargins(2,14,2,12);layout.setSpacing(10)
        layout.addWidget(text('COLOR LAB','heading'));self.wheel=ColorWheel();self.wheel.setFixedHeight(204);layout.addWidget(self.wheel)
        self.wheel.hueChanged.connect(lambda h:c.set_hsv(h,*c.state.get_hsv()[1:]))
        layout.addWidget(text('HSV · COLOR BALANCE','muted'))
        grid=QGridLayout();grid.setVerticalSpacing(8);layout.addLayout(grid);self.hsv=[]
        for i,(name,maximum) in enumerate([('Hue',359),('Saturation',100),('Value',100)]):
            grid.addWidget(text(name),i,0);level=slider(0,high=maximum);level.setAccessibleName(name)
            value=QSpinBox();value.setRange(0,maximum);value.setSuffix('°' if i==0 else '%')
            grid.addWidget(level,i,1);grid.addWidget(value,i,2);self.hsv.append((level,value))
            level.valueChanged.connect(lambda n,i=i:self.edit_hsv(i,n));value.valueChanged.connect(lambda n,i=i:self.edit_hsv(i,n))
        row=QHBoxLayout();layout.addLayout(row);row.addWidget(text('HEX'))
        self.hex=QLineEdit();self.hex.setAccessibleName('HEX color');self.hex.setMaxLength(7);self.hex.editingFinished.connect(self.edit_hex);row.addWidget(self.hex)
        self.error=text('','muted');self.error.setWordWrap(True);self.error.hide();layout.addWidget(self.error)
        layout.addWidget(text('QUICK COLORS','muted'))
        swatches=QHBoxLayout();layout.addLayout(swatches)
        for col in ['#F52DCB','#AD64FA','#2857FF','#1DD9F0','#24EAB4','#FFAD21','#FF375E']:
            b=button('',lambda checked=False,col=col:c.set_hex(col));b.setAccessibleName('Color '+col);b.setToolTip(col)
            b.setFixedSize(25,25);b.setStyleSheet(f'background:{col};border-radius:12px;padding:0;');swatches.addWidget(b)
        self.advanced=button('Advanced · RGB values',lambda b:self.rgb_widget.setVisible(b),True);layout.addWidget(self.advanced)
        self.rgb_widget=QWidget();rgbrow=QHBoxLayout(self.rgb_widget);rgbrow.setContentsMargins(0,0,0,0);self.rgb=[]
        for name in ['R','G','B']:
            value=QSpinBox();value.setRange(0,255);value.setAccessibleName(name);rgbrow.addWidget(text(name));rgbrow.addWidget(value)
            value.valueChanged.connect(self.edit_rgb);self.rgb.append(value)
        layout.addWidget(self.rgb_widget);self.rgb_widget.hide();layout.addStretch()
        self.tabs.addTab(color,'Color')
        music=QWidget();ml=QVBoxLayout(music);ml.addWidget(text('Mock music routing','heading'))
        self.relationship=QComboBox();self.relationship.addItems(['Same Color','Coordinated Colors','Independent Devices'])
        self.relationship.currentTextChanged.connect(lambda v:c.set('relationship',v));ml.addWidget(self.relationship)
        ml.addWidget(text('Color separation'));self.separation=slider(25,lambda n:c.set('separation',n/100));ml.addWidget(self.separation)
        ml.addWidget(text('Sensitivity'));ml.addWidget(slider(60,lambda n:c.set('sensitivity',n/100)))
        note=text('Synthetic visualization only. No audio input or device connection.','muted');note.setWordWrap(True);ml.addWidget(note);ml.addStretch();self.tabs.addTab(music,'Music')
        setup=QWidget();sl=QVBoxLayout(setup);sl.addWidget(text('Preview preferences','heading'))
        self.reduced=QCheckBox('Reduced Motion');self.reduced.toggled.connect(lambda b:c.set('motion',not b));sl.addWidget(self.reduced)
        sl.addWidget(text('Transition duration'));self.duration=QComboBox();self.duration.addItems(['0','0.5','1','1.2','2','5'])
        self.duration.currentTextChanged.connect(lambda n:c.set_transition(float(n),c.state.transition_curve));sl.addWidget(self.duration)
        self.curve=QComboBox();self.curve.addItems(['Smooth','Linear','Instant']);self.curve.currentTextChanged.connect(lambda v:c.set_transition(c.state.transition_seconds,v));sl.addWidget(self.curve)
        note=text('All changes stay in memory. Restarting restores the demo defaults.','muted');note.setWordWrap(True);sl.addWidget(note);sl.addStretch();self.tabs.addTab(setup,'Setup')
        self.tabs.currentChanged.connect(lambda i:self.select_tab(i))
        self.box.addWidget(text('DEVICE CONTROLS','heading'))
        row=QHBoxLayout();self.box.addLayout(row)
        self.power=QCheckBox('Power');self.power.toggled.connect(lambda b:c.channel(c.state.selected_channel,'power',b));row.addWidget(self.power)
        self.follow=QCheckBox('Follow Master');self.follow.toggled.connect(lambda b:c.channel(c.state.selected_channel,'follow',b));row.addWidget(self.follow)
        self.box.addWidget(text('Local brightness','muted'));self.brightness=slider(80,lambda n:c.channel(c.state.selected_channel,'brightness',n/100));self.brightness.setAccessibleName('Selected device local brightness');self.box.addWidget(self.brightness)
        self.box.addStretch();c.changed.connect(self.sync);self.sync()
    @Slot(object)
    def receive_status(self,status):
        if self.c.adapter.closed:return
        self.statuses[status.device_id]=status;self.refresh_status()
    def refresh_status(self):
        if hasattr(self.c.adapter,'status_for'):
            self.status.setText('LIVE · '+self.c.adapter.status_for(self.c.state.selected_channel));return
        if getattr(self.c.adapter,'live',False):
            self.status.setText('LIVE · '+self.c.adapter.status if self.c.state.selected_channel=='Corner' else 'NOT INTEGRATED · no Hue hardware');return
        status=self.statuses.get(self.c.state.selected_channel)
        if status and not status.simulated:self.status.setText('LIVE · '+('connected' if status.connected else 'disconnected'))
        else:self.status.setText('DEMO · '+('connected (simulated)' if status and status.connected else 'offline (simulated)'))
    def select_tab(self,i):self.c.state.select_inspector(['Color','Music','Setup'][i]);self.c.changed.emit()
    def edit_hsv(self,i,n):
        values=list(self.c.state.get_hsv());values[i]=n/(360 if i==0 else 100);self.c.set_hsv(*values)
    def edit_hex(self):
        try:self.c.set_hex(self.hex.text());self.error.setText('');self.error.hide()
        except ValueError:self.error.setText('Use six hexadecimal digits, e.g. #A855FF.');self.error.show()
    def edit_rgb(self):self.c.set_hex(QColor(*(s.value() for s in self.rgb)).name())
    def sync(self):
        s=self.c.state
        block=QSignalBlocker(self.device);self.device.setCurrentIndex(self.device.findData(s.selected_channel));del block
        self.device_name.setText(s.channels[s.selected_channel].name);self.refresh_status()
        block=QSignalBlocker(self.tabs);self.tabs.setCurrentIndex(['Color','Music','Setup'].index(s.inspector));del block
        hsv=s.get_hsv();self.wheel.hsv=hsv;self.wheel.update()
        for i,(level,value) in enumerate(self.hsv):
            n=min(359,round(hsv[i]*360)) if i==0 else round(hsv[i]*100);assign(level,n);assign(value,n)
        assign(self.hex,s.channels[s.selected_channel].color)
        for spin,n in zip(self.rgb,QColor(s.channels[s.selected_channel].color).getRgb()[:3]):assign(spin,n)
        assign(self.relationship,s.relationship);assign(self.separation,round(s.separation*100));assign(self.reduced,not s.motion)
        assign(self.duration,f'{s.transition_seconds:g}');assign(self.curve,s.transition_curve)
        channel=s.channels[s.selected_channel];assign(self.power,channel.power);assign(self.follow,channel.follow);assign(self.brightness,round(channel.brightness*100))
