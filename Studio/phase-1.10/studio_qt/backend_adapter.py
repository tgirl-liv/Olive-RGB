"""Mock-only intent boundary. No backend imports, I/O, packets or worker loops."""
from collections import deque
from dataclasses import dataclass
from typing import Protocol
from PySide6.QtCore import QObject, Signal
from studio_ui.state import StudioState


@dataclass(frozen=True)
class DeviceStatus:
    device_id: str
    name: str
    connected: bool
    simulated: bool = True


@dataclass(frozen=True)
class AudioMeters:
    bass: float
    mids: float
    treble: float
    level: float


class LightingAdapter(Protocol):
    """Intent contract; completion/status arrive through Qt-compatible signals.

    Device IDs are opaque UI identifiers, not addresses. RGB is a #RRGGBB
    color, not a device command. Brightness values are normalized 0..1.
    Audio meters flow from the adapter to the UI, never widget-to-worker.
    """
    device_status: object
    audio_meters: object
    closed: bool
    def discover_devices(self) -> None: ...
    def request_status(self) -> None: ...
    def set_power(self, device_id: str, enabled: bool) -> None: ...
    def set_rgb(self, device_id: str, color: str) -> None: ...
    def set_brightness(self, device_id: str, brightness: float) -> None: ...
    def set_follow_master(self, device_id: str, enabled: bool) -> None: ...
    def set_master(self, power: bool, brightness: float) -> None: ...
    def select_mode(self, mode: str) -> None: ...
    def apply_scene(self, scene: str) -> None: ...
    def close(self) -> None: ...


class MockLightingAdapter(QObject):
    device_status = Signal(object)
    audio_meters = Signal(object)

    def __init__(self, state=None, parent=None):
        super().__init__(parent)
        self.state = state or StudioState()
        self.commands = deque(maxlen=256)
        self.closed = False
        self.statuses = {key: DeviceStatus(key, channel.name, True)
                         for key, channel in self.state.channels.items()}

    def _record(self, name, *args):
        if self.closed: raise RuntimeError('Adapter is closed')
        self.commands.append((name, *args))

    @staticmethod
    def _brightness(value):
        value = float(value)
        if not 0 <= value <= 1: raise ValueError('Brightness must be 0..1')
        return value

    def discover_devices(self):
        self._record('discover_devices'); self.request_status()

    def request_status(self):
        self._record('request_status')
        for status in self.statuses.values(): self.device_status.emit(status)

    def simulate_status(self, device_id, connected):
        """Test/demo injection only; never opens a connection."""
        status = DeviceStatus(device_id, self.state.channels[device_id].name, bool(connected))
        self._record('simulate_status', device_id, bool(connected))
        self.statuses[device_id] = status; self.device_status.emit(status)

    def set_power(self, device_id, enabled):
        channel = self.state.channels[device_id]
        self._record('set_power', device_id, bool(enabled)); channel.power = bool(enabled)

    def set_rgb(self, device_id, color):
        channel = self.state.channels[device_id]
        # Reuse the model's validation without altering the selected channel.
        candidate = StudioState(); candidate.set_hex(color)
        color = candidate.channels[candidate.selected_channel].color
        self._record('set_rgb', device_id, color); channel.color = color

    def set_brightness(self, device_id, brightness):
        channel = self.state.channels[device_id]; brightness = self._brightness(brightness)
        self._record('set_brightness', device_id, brightness); channel.brightness = brightness

    def set_follow_master(self, device_id, enabled):
        channel = self.state.channels[device_id]
        self._record('set_follow_master', device_id, bool(enabled)); channel.follow = bool(enabled)

    def set_master(self, power, brightness):
        brightness = self._brightness(brightness)
        self._record('set_master', bool(power), brightness)
        self.state.master_power = bool(power); self.state.master_brightness = brightness

    def select_mode(self, mode):
        if mode not in ('Manual', 'Music', 'Screen'): raise ValueError('Unknown mode')
        self._record('select_mode', mode); self.state.mode = mode

    def apply_scene(self, scene):
        from studio_ui.state import SCENES
        if scene not in SCENES: raise ValueError('Unknown scene')
        self._record('apply_scene', scene); self.state.select_scene(scene)

    def publish_demo_meters(self, meters: AudioMeters):
        """Synthetic test source. A future backend publishes its existing analysis."""
        if self.closed: return
        if any(not 0 <= v <= 1 for v in (meters.bass, meters.mids, meters.treble, meters.level)):
            raise ValueError('Meters must be 0..1')
        self.audio_meters.emit(meters)

    def close(self):
        if not self.closed:
            self.commands.append(('close',)); self.closed = True
