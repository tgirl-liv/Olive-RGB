"""Manual two-device adapter; Corner implementation stays unchanged."""
from PySide6.QtCore import Signal, Slot, Qt
from .corner_adapter import CornerLampAdapter
from .backend_adapter import DeviceStatus
from .hue_session import HueSession


class DualLightingAdapter(CornerLampAdapter):
    hue_changed = Signal(object)
    state_observed = Signal()
    _hue_incoming = Signal(object)
    _hue_stopped = Signal()

    def __init__(self, state=None, parent=None, worker_factory=None, hue_factory=None, hue_identity=None):
        super().__init__(state, parent, worker_factory)
        self.hue_status = 'disconnected'
        self.hue_error = ''
        self.hue_connected = False
        self.hue_caps = {}
        self.hue_identity = dict(hue_identity or {'name': 'Tv lamp'})
        self.hue_observed = {}
        self._hue_color_set = False
        self._corner_done = self._hue_done = False
        self.state.channels['Hue'].follow = False
        self.hue = HueSession(self._hue_incoming.emit, self._hue_stopped.emit, hue_factory, hue_identity)
        self._hue_incoming.connect(self._receive_hue, Qt.ConnectionType.QueuedConnection)
        # Completion is aggregate, including a device that was never started.
        self._stopped.disconnect(self.finished)
        self._stopped.connect(self._corner_finished, Qt.ConnectionType.QueuedConnection)
        self._hue_stopped.connect(self._hue_finished, Qt.ConnectionType.QueuedConnection)

    def _corner_finished(self):self._corner_done = True;self._finish()
    def _hue_finished(self):
        self._hue_done = True
        if not self.closed:self.hue_changed.emit(None)
        self._finish()
    def _finish(self):
        if self.closed and self._corner_done and self._hue_done:self.finished.emit()

    @Slot(object)
    def _receive_hue(self, event):
        if self.closed or event.generation != self.hue.generation:return
        kind, value = event.kind, event.value
        if kind == 'status':
            self.hue_status = value;self.hue_connected = value == 'connected'
            if not self.hue_connected:self.hue_caps = {}
        elif kind == 'error':
            self.hue_status = 'error';self.hue_error = str(value);self.hue_connected = False;self.hue_caps = {}
        elif kind == 'capabilities':self.hue_caps = dict(value)
        elif kind == 'identity':self.hue_identity = dict(value)
        elif kind == 'observed_power':
            self.hue_observed['power'] = bool(value);self.state.channels['Hue'].power = bool(value)
        elif kind == 'observed_brightness':
            self.hue_observed['brightness'] = int(value);self.state.channels['Hue'].brightness = int(value) / 254
        elif kind == 'log':self.hue_error = str(value)
        self.hue_changed.emit(event)
        self.state_observed.emit()
        self.request_status()

    def connect_hue(self):
        if self.closed or self.hue.closed or self.hue.wanted:return
        self.hue_error = '';self.hue_observed = {};self._hue_color_set = False
        self.hue.connect()

    def disconnect_hue(self):
        if self.closed:return
        self.hue_connected = False;self.hue_caps = {};self.hue.disconnect();self.request_status()

    def request_status(self):
        if self.closed:return
        self.device_status.emit(DeviceStatus('Corner', 'Corner Lamp', self.connected, False))
        self.device_status.emit(DeviceStatus('Hue', 'Philips Hue', self.hue_connected, False))

    def status_for(self, device_id):return self.hue_status if device_id == 'Hue' else self.status

    def _require(self, capability):
        if self.closed:raise RuntimeError('Adapter is closed')
        if not self.hue_connected or not self.hue_caps.get(capability):raise ValueError(f'Hue {capability} unavailable: connect and verify bulb capability')

    def _queue_hue(self, color=False):
        if self.closed or not self.hue_connected:return
        channel = self.state.channels['Hue']
        rgb = tuple(int(channel.color[i:i+2], 16) for i in (1,3,5))
        intensity = max(rgb) / 255 if self._hue_color_set else 1.
        brightness = channel.brightness * (self.state.master_brightness if channel.follow else 1.) * intensity
        power = channel.power and (self.state.master_power or not channel.follow) and brightness > 0
        values = dict(power=bool(power), brightness=max(1, min(254, round(brightness * 254))))
        if color:values['color'] = rgb  # Unscaled chromaticity; intensity applied once above.
        self.hue.update(values)

    def set_rgb(self, device_id, color):
        if device_id != 'Hue':return super().set_rgb(device_id, color)
        self._require('color');self._model.set_rgb(device_id, color);self._hue_color_set = True;self._queue_hue(color=True)

    def set_brightness(self, device_id, brightness):
        if device_id != 'Hue':return super().set_brightness(device_id, brightness)
        self._require('brightness');self._model.set_brightness(device_id, brightness);self._queue_hue()

    def set_power(self, device_id, enabled):
        if device_id != 'Hue':return super().set_power(device_id, enabled)
        self._require('power');self._model.set_power(device_id, enabled);self._queue_hue()

    def set_follow_master(self, device_id, enabled):
        if device_id != 'Hue':return super().set_follow_master(device_id, enabled)
        self._require('power');self._model.set_follow_master(device_id, enabled);self._queue_hue()

    def set_master(self, power, brightness):
        super().set_master(power, brightness)
        if self.state.channels['Hue'].follow:self._queue_hue()

    def close(self):
        if self.closed:return
        super().close()
        self.hue_connected = False;self.hue.close();self._finish()
