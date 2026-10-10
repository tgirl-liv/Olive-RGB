"""Hue controls backed by the existing adapter; never owns a connection."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox,QLineEdit,QSpinBox
from .common import Panel,text,button,assign


class HuePreferences(Panel):
    def __init__(self,window):
        super().__init__('PHILIPS HUE · BLE TARGET');self.window=window;a=window.c.adapter
        self.name=QLineEdit(a.hue_identity.get('name','Tv lamp'));self.name.setMaxLength(256)
        self.address=QLineEdit(a.hue_identity.get('address_hint',''));self.address.setMaxLength(256)
        for label,control in (('Advertised bulb name',self.name),('Optional BLE address hint',self.address)):
            self.box.addWidget(text(label));self.box.addWidget(control)
        self.apply=button('Save target (disconnect; no automatic connect)',self.select_identity);self.box.addWidget(self.apply)
        self.mode=QComboBox();self.mode.addItem('RGB / color','color');self.mode.addItem('White temperature','temperature')
        self.temperature=QSpinBox();self.temperature.setRange(153,500);self.temperature.setSuffix(' mired')
        self.box.addWidget(self.mode);self.box.addWidget(self.temperature)
        self.status=text('','muted');self.status.setTextFormat(Qt.TextFormat.PlainText);self.status.setWordWrap(True);self.box.addWidget(self.status)
        self.mode.currentIndexChanged.connect(self.set_mode);self.temperature.valueChanged.connect(self.set_mode)
        self.refresh()

    def select_identity(self):
        a=self.window.c.adapter
        try:
            identity={'name':self.name.text()}
            if self.address.text().strip():identity['address_hint']=self.address.text()
            # A changed target must not inherit the previous bulb's stable ID.
            if identity=={k:v for k,v in a.hue_identity.items() if k!='zigbee_address'}:identity=dict(a.hue_identity)
            a.set_hue_identity(identity);self.window.queue_preferences();self.window.hue_update(None)
        except ValueError as error:self.status.setText(str(error))

    def set_mode(self,*args):
        try:
            self.window.c.adapter.set_hue_mode(self.mode.currentData(),self.temperature.value())
            self.window.queue_preferences();self.refresh()
        except (ValueError,RuntimeError) as error:self.status.setText(str(error));self.refresh_controls()

    def refresh_controls(self):
        w=self.window;a=w.c.adapter
        idle=not w._closing and not (hasattr(a,'owns') and a.owns('Hue'))
        assign(self.mode,'White temperature' if a.hue_mode=='temperature' else 'RGB / color')
        assign(self.temperature,a.hue_temperature)
        for i,key in enumerate(('color','temperature')):self.mode.model().item(i).setEnabled(idle and a.hue_connected and bool(a.hue_caps.get(key)))
        self.mode.setEnabled(idle and a.hue_connected and any(a.hue_caps.get(k) for k in ('color','temperature')))
        self.temperature.setEnabled(idle and a.hue_connected and a.hue_caps.get('temperature',False) and a.hue_mode=='temperature')
        for control in (self.name,self.address,self.apply):control.setEnabled(not w._closing)

    def refresh(self):
        self.refresh_controls();a=self.window.c.adapter
        owner=' · effect owns output; manual mode locked' if hasattr(a,'owns') and a.owns('Hue') else ''
        caps=', '.join(k for k,v in a.hue_caps.items() if v) or 'unknown until connected'
        unsupported=' · saved manual mode unsupported by this bulb' if a.hue_connected and not a.hue_caps.get(a.hue_mode) else ''
        self.status.setText(f'{a.hue_status}{owner}{unsupported}\nManual preference: {a.hue_mode}. Stable bulb ID: {a.hue_identity.get("zigbee_address","not detected")}.\nCapabilities: {caps}. White range 153–500 mired; driver clamps to bulb limits.\n'+a.hue_error+'\nBLE bulb only; bridge discovery/pairing is not implemented. Connect explicitly after saving a target.')
