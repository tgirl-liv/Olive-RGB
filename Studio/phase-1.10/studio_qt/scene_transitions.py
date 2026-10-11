"""Pure, transport-agnostic RGB interpolation for LIVE scene recall.

The Qt window owns the clock and sends sampled colors through the existing
manual adapters. This module must not access BLE, Hue, or Qt.
"""
import math
import time


def _rgb(value):
    if not isinstance(value, str) or len(value) != 7 or value[0] != '#':
        raise ValueError('Scene transition requires #RRGGBB colors')
    try:
        return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))
    except ValueError as error:
        raise ValueError('Scene transition requires #RRGGBB colors') from error


class SceneTransition:
    """Immutable endpoints; sample from the last *commanded* RGB on interruption."""

    def __init__(self, source, target, seconds, curve='Smooth', started=None):
        if not isinstance(source, dict) or set(source) != set(target) or not source:
            raise ValueError('Scene transition requires matching device keys')
        if type(seconds) not in (float, int) or not math.isfinite(seconds) or not 0 <= seconds <= 5:
            raise ValueError('Invalid scene transition duration')
        if curve not in ('Smooth', 'Linear', 'Instant'):
            raise ValueError('Invalid scene transition curve')
        self.source = {key: _rgb(value) for key, value in source.items()}
        self.target = {key: _rgb(value) for key, value in target.items()}
        self.seconds = float(seconds)
        self.curve = curve
        self.started = time.monotonic() if started is None else started

    def sample(self, now=None):
        now = time.monotonic() if now is None else now
        fraction = (1. if self.seconds == 0 or self.curve == 'Instant'
                    else max(0., min(1., (now - self.started) / self.seconds)))
        amount = fraction * fraction * (3 - 2 * fraction) if self.curve == 'Smooth' else fraction
        colors = {
            key: '#' + ''.join(f'{round(a + (b-a)*amount):02X}' for a, b in zip(self.source[key], self.target[key]))
            for key in self.target
        }
        return colors, fraction
