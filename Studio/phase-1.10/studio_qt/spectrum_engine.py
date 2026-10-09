"""Optional observer extension; the production MusicEngine class stays verbatim."""
from .music_engine import MusicEngine,BASS_RANGE


class SpectrumMusicEngine(MusicEngine):
    def _band_mean(self,spectrum,frequencies,low,high):
        if (low,high)==BASS_RANGE:
            # The inherited capture loop creates these arrays once per block and
            # never mutates them. Retain references until its analysis callback.
            self._display_fft=(spectrum,frequencies)
        return MusicEngine._band_mean(spectrum,frequencies,low,high)

    def publish_spectrum(self,frame,mailbox,generation):
        value=getattr(self,'_display_fft',None)
        self._display_fft=None
        if value is not None:mailbox.publish(*value,frame,generation)
