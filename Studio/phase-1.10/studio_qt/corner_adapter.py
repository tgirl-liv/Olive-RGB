"""LIVE manual Corner Lamp adapter. Hue/scenes/audio are not integrated."""
from PySide6.QtCore import QObject,Signal,Slot,Qt
from studio_ui.state import StudioState
from .backend_adapter import MockLightingAdapter,DeviceStatus
from .corner_session import CornerSession


class CornerLampAdapter(QObject):
    live=True
    device_status=Signal(object)
    audio_meters=Signal(object)
    connection_changed=Signal(object)
    finished=Signal()
    _incoming=Signal(object)
    _stopped=Signal()

    def __init__(self,state=None,parent=None,worker_factory=None,software_power=True):
        super().__init__(parent)
        self.state=state or StudioState();self.state.mode='Manual';self.state.playing=False
        self.state.selected_channel='Corner'
        self.closed=False;self.connected=False;self.software_power=software_power
        self.status='disconnected';self.message='Disconnected · press Connect Corner Lamp'
        self._model=MockLightingAdapter(self.state,self);self.commands=self._model.commands
        self._last_nonzero=self.state.channels['Corner'].color
        self.session=CornerSession(self._incoming.emit,self._stopped.emit,worker_factory)
        self._incoming.connect(self._receive,Qt.ConnectionType.QueuedConnection)
        self._stopped.connect(self.finished,Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _receive(self,event):
        if self.closed or event.generation!=self.session.generation:return
        self.status=event.state;self.message=event.message;self.connected=event.state=='connected'
        self.connection_changed.emit(event)
        self.request_status()

    def discover_devices(self):self.request_status()  # No scan on opening LIVE.
    def request_status(self):
        if self.closed:return
        self.device_status.emit(DeviceStatus('Corner','Corner Lamp',self.connected,False))
        self.device_status.emit(DeviceStatus('Hue','Philips Hue',False,True))
    def connect_corner(self):
        if self.closed or self.session.closed:return
        self.session.connect()
    def disconnect_corner(self):
        if self.closed:return
        self.connected=False;self.status='disconnecting';self.session.disconnect();self.request_status()
    def _queue(self):
        if self.closed:return
        channel=self.state.channels['Corner']
        color=tuple(int(channel.color[i:i+2],16) for i in (1,3,5))
        scale=channel.brightness*(self.state.master_brightness if channel.follow else 1.)
        on=channel.power and (self.state.master_power or not channel.follow)
        self.session.color(tuple(round(c*scale) for c in color) if on else (0,0,0))
    def set_rgb(self,device_id,color):
        self._model.set_rgb(device_id,color)
        if device_id=='Corner':
            if self.state.channels['Corner'].color!='#000000':self._last_nonzero=self.state.channels['Corner'].color
            self._queue()
    def set_brightness(self,device_id,brightness):
        self._model.set_brightness(device_id,brightness)
        if device_id=='Corner':self._queue()
    def set_power(self,device_id,enabled):
        if device_id=='Corner' and not self.software_power:raise ValueError('Corner Lamp power is unsupported')
        self._model.set_power(device_id,enabled)
        if device_id=='Corner':
            if enabled and self.state.channels['Corner'].color=='#000000':self.state.channels['Corner'].color=self._last_nonzero
            self._queue()
    def set_follow_master(self,device_id,enabled):
        self._model.set_follow_master(device_id,enabled)
        if device_id=='Corner':self._queue()
    def set_master(self,power,brightness):
        if not self.software_power and bool(power)!=self.state.master_power:raise ValueError('Corner Lamp power is unsupported')
        self._model.set_master(power,brightness)
        if power and self.state.channels['Corner'].color=='#000000':self.state.channels['Corner'].color=self._last_nonzero
        if self.state.channels['Corner'].follow:self._queue()
    def select_mode(self,mode):
        if mode!='Manual':raise ValueError('Only manual control is supported in LIVE')
        self._model.select_mode(mode)
    def apply_scene(self,scene):raise ValueError('Scenes are unavailable in LIVE Phase 1.8')
    def publish_demo_meters(self,meters):pass
    def close(self):
        if self.closed:return
        self.closed=True;self.connected=False;self._model.close();self.session.close()
