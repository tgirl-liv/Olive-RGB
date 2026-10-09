"""Display-only FFT snapshots; producer never waits for the GUI consumer."""
from dataclasses import dataclass
import threading


@dataclass(frozen=True)
class SpectrumFrame:
    magnitudes: tuple
    rms: float
    timestamp: float


class SpectrumMailbox:
    def __init__(self):
        self.lock=threading.Lock();self.generation=None;self.latest=None

    def reset(self,generation=None):
        with self.lock:self.generation=generation;self.latest=None

    def publish(self,spectrum,frequencies,frame,generation):
        if not self.lock.acquire(blocking=False):return False
        try:
            if generation!=self.generation:return False
            # Only small copies on capture thread; no binning, Qt or consumer calls.
            self.latest=(spectrum.copy(),frequencies.copy(),frame.energy,frame.timestamp,generation)
            return True
        finally:self.lock.release()

    def take(self):
        with self.lock:
            value,self.latest=self.latest,None
        if value is None:return None
        spectrum,frequencies,rms,timestamp,_=value
        return SpectrumFrame(log_magnitudes(spectrum,frequencies),rms,timestamp)


def log_magnitudes(spectrum,frequencies):
    """72 log bands, 20 Hz..20 kHz, normalized Hann-window FFT amplitudes.

    This runs on the consumer, using the FFT already calculated by MusicEngine.
    Empty low-frequency bands interpolate measured bins at the band center;
    4096 samples at 48 kHz cannot resolve arbitrarily narrow low bands.
    """
    import numpy as np  # LIVE only; importing the mailbox never loads capture/FFT.
    spectrum=np.maximum(0,np.nan_to_num(spectrum,nan=0,posinf=0,neginf=0))
    samples=2*(len(spectrum)-1)
    amplitudes=spectrum*(4/max(1,samples-1))
    edges=np.geomspace(20.,min(20000.,float(frequencies[-1])),73)
    result=[]
    for low,high in zip(edges[:-1],edges[1:]):
        values=amplitudes[(frequencies>=low)&(frequencies<high)]
        result.append(float(np.max(values)) if len(values) else float(np.interp((low*high)**.5,frequencies,amplitudes)))
    return tuple(result)
