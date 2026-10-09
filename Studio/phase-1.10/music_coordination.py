"""Audio-frame harmony and application routing; no Bluetooth or capture code."""
import colorsys
import math
from dataclasses import dataclass
from hue_driver import LightingRouter

RELATIONSHIPS = ('Same Color', 'Coordinated Colors', 'Independent Devices')


@dataclass(frozen=True)
class MusicFrame:
    rgb: tuple
    bass: float
    mids: float
    treble: float
    energy: float
    beat: bool
    timestamp: float


def separation_value(value):
    try:
        value = float(value)
        return max(0., min(1., value)) if math.isfinite(value) else .25
    except (ValueError, TypeError):
        return .25


class AccentGenerator:
    def __init__(self):
        self.reset()

    def reset(self):
        self.hue = None
        self.value = 0.
        self.last_time = None
        self.beat_until = float('-inf')

    def color(self, frame, separation):
        h, s, v = colorsys.rgb_to_hsv(*(c / 255. for c in frame.rgb))
        dt = max(0., min(.25, frame.timestamp - self.last_time)) if self.last_time is not None else .05
        self.last_time = frame.timestamp
        # 20..180 degrees: analogous accents through complementary colors.
        offset = (20. + 160. * separation_value(separation)) / 360.
        target = (h + offset) % 1.
        if self.hue is None:
            self.hue = target
        elif s > .12:  # Keep hue stable through white beat flashes.
            delta = (target - self.hue + .5) % 1. - .5
            alpha = 1. - math.exp(-dt / (.35 if frame.energy > .015 else .9))
            self.hue = (self.hue + delta * alpha) % 1.
        if frame.beat:
            # Immediate attack with a short envelope, not a playback delay.
            # It survives mailbox coalescing at the existing Hue write cadence.
            self.beat_until = frame.timestamp + .65
        pulse = max(0., min(1., (self.beat_until-frame.timestamp)/.65))
        activity = max(0., min(1., frame.mids + frame.treble))
        target_value = min(1., v * (.72 + .08*activity + .5*pulse))
        alpha = 1. if frame.beat else 1.-math.exp(-dt/.3)
        self.value += (target_value-self.value)*alpha
        # A zero primary means darkness (also respects the Music brightness slider).
        if v == 0.: self.value = 0.
        saturation = min(1., s * 1.12)
        return tuple(round(c*255) for c in colorsys.hsv_to_rgb(self.hue, saturation, self.value))


class MusicLightingRouter(LightingRouter):
    """Music-only extension of the existing application router."""
    def __init__(self, *args, **kwargs):
        self.music_active = False
        self.relationship = 'Coordinated Colors'
        self.separation = .25
        self.accent = AccentGenerator()
        self.accent_rgb = None
        self.manual_rgb = None
        super().__init__(*args, **kwargs)

    def configure_music(self, relationship, separation):
        with self.lock:
            self.relationship = relationship if relationship in RELATIONSHIPS else 'Coordinated Colors'
            self.separation = separation_value(separation)
            self.accent.reset()
            if self.music_active and self.relationship == 'Independent Devices':
                self.rgb = self.manual_rgb
                self.accent_rgb = None
                self._send(force=True)

    def start_music(self):
        with self.lock:
            self.manual_rgb = self.rgb
            self.music_active = True
            self.accent_rgb = None
            self.accent.reset()
            self._send()

    def stop_music(self):
        with self.lock:
            if not self.music_active: return
            self.music_active = False
            self.accent_rgb = None
            self.rgb = self.manual_rgb
            self._send(force=True)

    def set_music_frame(self, frame):
        with self.lock:
            if not self.music_active or self.relationship == 'Independent Devices': return
            self.rgb = frame.rgb
            if max(self.rgb): self.last_nonzero = self.rgb
            self.accent_rgb = self.accent.color(frame, self.separation) if self.relationship == 'Coordinated Colors' else self.rgb
            self._send()

    def _send(self, force=False):
        if not self.music_active:
            return super()._send(force)
        rgb = tuple(round(c*self.brightness) for c in self.rgb) if self.power else (0,0,0)
        self.corner.set_rgb(*rgb, force=force)
        self.hue.update(master=dict(power=self.power, brightness=self.brightness,
                                   rgb=self.accent_rgb if self.accent_rgb is not None else self.rgb,
                                   music_independent=self.relationship == 'Independent Devices'))
