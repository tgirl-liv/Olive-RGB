from PySide6.QtWidgets import QHBoxLayout, QGridLayout, QCheckBox, QComboBox, QWidget, QLayout
from PySide6.QtCore import Qt,QSize
from .common import Panel, text, button, slider, assign


class MasterBus(Panel):
    def __init__(self, controller):
        super().__init__('MASTER BUS'); self.c=controller
        from PySide6.QtCore import QSize
        from .icons import icon
        self.power=button('',lambda on:controller.set('master_power',on),True)
        self.power.setIcon(icon('Power'));self.power.setIconSize(QSize(24,24));self.power.setFixedSize(46,46)
        self.power.setAccessibleName('Master power');self.power.setToolTip('Master power · Space to toggle');self.power.setObjectName('masterPower')
        self.color=button('',self.edit_output);self.color.setFixedSize(24,24);self.color.setAccessibleName('Edit output color');self.header.addWidget(self.color)
        self.grid=QGridLayout();self.grid.setSpacing(12);self.box.addLayout(self.grid)
        self.level=slider(80,lambda n:controller.set('master_brightness',n/100));self.level.setObjectName('masterLevel')
        self.level.setAccessibleName('Master brightness');self.level.setMinimumHeight(30)
        self.value=text('80%','heading');self.value.setMinimumWidth(37)
        self.modes={};self.mode_widget=QWidget()
        modes=QHBoxLayout(self.mode_widget);modes.setContentsMargins(0,0,0,0);modes.setSpacing(3)
        for name in ['Manual','Music','Screen']:
            b=button(name,lambda checked=False,name=name:controller.request_mode(name),True);b.setObjectName('modeSegment');b.setAccessibleName(name+' mode');modes.addWidget(b);self.modes[name]=b
        controller.changed.connect(self.sync);controller.output_changed.connect(self.output);self.reflow();self.sync()
    def edit_output(self):
        if getattr(self.c.adapter,'live',False):self.c.select_target('Both')
        else:self.c.select_channel('Corner')
        self.c.state.select_inspector('Color');self.c.changed.emit()
        if getattr(self.c.adapter,'live',False):self.c.parent().open_tab('Color')
    def resizeEvent(self,event):super().resizeEvent(event);self.reflow()
    def reflow(self):
        for w in [self.power,self.level,self.value,self.mode_widget]:self.grid.removeWidget(w)
        self.grid.addWidget(self.power,0,0);self.grid.addWidget(self.level,0,1);self.grid.addWidget(self.value,0,2)
        if self.width()<630:self.grid.addWidget(self.mode_widget,1,0,1,3)
        else:self.grid.addWidget(self.mode_widget,0,3)
        self.grid.setColumnStretch(1,1)
    def sync(self):
        s=self.c.state;assign(self.power,s.master_power);assign(self.level,round(s.master_brightness*100))
        self.value.setText(f'{s.master_brightness:.0%}')
        for name,b in self.modes.items():assign(b,name==s.mode)
        self.output()
    def output(self):
        color=self.c.display_colors['Corner'];self.color.setToolTip(('Edit Both Lights color · Corner '+color.upper()+' · Hue '+self.c.display_colors['Hue'].upper()) if getattr(self.c.adapter,'live',False) else 'Edit corner output color · '+color.upper())
        self.color.setStyleSheet('background:'+color+';border:2px solid #d9c5ef;border-radius:12px;padding:0;')


class DeviceChannel(Panel):
    def __init__(self,controller,key):
        super().__init__();self.c=controller;self.key=key;self.setObjectName('deviceChannel')
        self.grid=QGridLayout();self.box.addLayout(self.grid)
        self.select=button(controller.state.channels[key].name,lambda:controller.select_channel(key),True)
        self.dot=text('');self.dot.setFixedSize(12,12)
        self.power=QCheckBox('Power');self.power.toggled.connect(lambda b:controller.channel(key,'power',b))
        self.follow=QCheckBox('Follow Master');self.follow.toggled.connect(lambda b:controller.channel(key,'follow',b))
        self.level=slider(80,lambda n:controller.channel(key,'brightness',n/100));self.level.setAccessibleName(f'{key} local brightness')
        self.value=text('80%');self.value.setFixedWidth(42);self.value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        self.select.setFixedWidth(max(128,max(self.select.fontMetrics().horizontalAdvance(ch.name) for ch in controller.state.channels.values())+26))
        self.power.setFixedWidth(66);self.follow.setFixedWidth(112);self.select.setFixedHeight(34)
        self.grid.setHorizontalSpacing(8);self.grid.setVerticalSpacing(8)
        self.grid.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint);self.box.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        controller.changed.connect(self.sync);controller.output_changed.connect(self.output);self.reflow();self.sync()
    def resizeEvent(self,event):super().resizeEvent(event);self.reflow()
    def minimumSizeHint(self):return QSize(280,super().minimumSizeHint().height())
    def reflow(self):
        widgets=[self.select,self.dot,self.power,self.follow,self.level,self.value]
        for w in widgets:self.grid.removeWidget(w)
        for col in range(6):self.grid.setColumnStretch(col,0);self.grid.setColumnMinimumWidth(col,0)
        if self.width()>=620:
            for i,w in enumerate(widgets):self.grid.addWidget(w,0,i)
            self.grid.setColumnStretch(4,1)
        elif self.width()>=420:
            for i,w in enumerate(widgets[:4]):self.grid.addWidget(w,0,i)
            self.grid.addWidget(self.level,1,0,1,3);self.grid.addWidget(self.value,1,3,alignment=Qt.AlignmentFlag.AlignRight)
            self.grid.setColumnStretch(3,1)
        else:
            self.grid.addWidget(self.select,0,0);self.grid.addWidget(self.dot,0,1);self.grid.addWidget(self.power,0,2)
            self.grid.addWidget(self.follow,1,0);self.grid.addWidget(self.level,1,1,1,2);self.grid.addWidget(self.value,1,3)
            self.grid.setColumnStretch(2,1)
    def sync(self):
        s=self.c.state.channels[self.key]
        assign(self.select,self.c.state.selected_channel==self.key);assign(self.power,s.power);assign(self.follow,s.follow)
        assign(self.level,round(s.brightness*100));self.value.setText(f'{s.brightness:.0%}');self.output()
    def output(self):self.dot.setStyleSheet('background:'+self.c.display_colors[self.key]+';border-radius:6px;')
