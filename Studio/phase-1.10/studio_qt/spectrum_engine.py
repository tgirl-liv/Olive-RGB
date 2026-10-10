"""Optional observer extension; the production MusicEngine class stays verbatim."""
from .music_engine import MusicEngine,BASS_RANGE
from .native_capture import audio_apartment
from .capture_diagnostics import bind,emit


class SpectrumMusicEngine(MusicEngine):
    def _run(self):
        bind(getattr(self,'diagnostic_generation',0))
        try:
            with audio_apartment():return MusicEngine._run(self)
        except Exception as error:
            emit('music.native.failed.'+type(error).__name__)
            self.log_callback(f'Audio error: {type(error).__name__}: {error}')
            self.running=False

    def _band_mean(self,spectrum,frequencies,low,high):
        if (low,high)==BASS_RANGE:
            # The inherited capture loop creates these arrays once per block and
            # never mutates them. Retain references until its analysis callback.
            self._display_fft=(spectrum,frequencies)
        return MusicEngine._band_mean(spectrum,frequencies,low,high)

    def publish_spectrum(self,frame,mailbox,generation):
        value=getattr(self,'_display_fft',None)
        self._display_fft=None
        if value is not None:
            accepted=mailbox.publish(*value,frame,generation)
            emit('music.fft.mailbox',generation,interval=1,accepted=accepted)
