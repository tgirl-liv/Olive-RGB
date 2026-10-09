"""Original Tkinter output adjustment math, independent of capture and Qt."""
import colorsys
import math
from dataclasses import replace


def adjust_music_rgb(rgb, brightness, saturation):
    h, s, v = colorsys.rgb_to_hsv(*(channel / 255.0 for channel in rgb))
    return tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(
        h, s * saturation, v * brightness))


def validated_adjustments(brightness, saturation):
    if any(type(value) not in (int, float) or not math.isfinite(value) or not 0<=value<=1
           for value in (brightness, saturation)):
        raise ValueError('Music brightness and saturation must be between 0 and 1')
    return float(brightness), float(saturation)


def adjusted_frame(frame, brightness, saturation):
    """Copy only RGB; retain the measured analysis and original frame."""
    return replace(frame, rgb=adjust_music_rgb(frame.rgb, brightness, saturation))
