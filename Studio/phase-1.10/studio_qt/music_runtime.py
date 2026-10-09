"""One production capture engine; bounded latest-frame mailbox, no Qt calls."""
import threading
from .spectrum_data import SpectrumMailbox


def engine_factory(rgb, meter, beat, log):
    from .spectrum_engine import SpectrumMusicEngine
    return SpectrumMusicEngine(rgb, meter, beat, log)


class MusicRuntime:
    def __init__(self, factory=None):
        self.factory = factory or engine_factory
        self.lock = threading.RLock()
        self.thread = self.engine = None
        self.wanted = False
        self.generation = 0
        self.frame = None
        self.message = 'Stopped'
        self.error = ''
        self.spectrum=SpectrumMailbox()

    @property
    def busy(self):return self.thread is not None and self.thread.is_alive()

    def start(self, profile='Reactive', sensitivity=1., smoothing=1., palette='Default'):
        with self.lock:
            if self.busy:return False
            self.generation += 1;generation = self.generation
            self.spectrum.reset(generation)
            self.wanted = True;self.frame = None;self.error = '';self.message = 'Opening default output loopback…'
            self.thread = threading.Thread(target=self._run, args=(generation,profile,sensitivity,smoothing,palette), name='Music lifecycle', daemon=True)
            self.thread.start();return True

    def _run(self, generation, profile, sensitivity, smoothing, palette):
        def log(message):
            with self.lock:
                if generation != self.generation:return
                self.message = str(message)
                if 'error' in str(message).lower():self.error = str(message)
        def frame(value):
            with self.lock:
                accepted=self.wanted and generation == self.generation
                if accepted:self.frame = value
            if accepted and hasattr(engine,'publish_spectrum'):engine.publish_spectrum(value,self.spectrum,generation)
        try:
            engine = self.factory(lambda *a:None,lambda *a:None,lambda:None,log)
            engine.set_profile(profile);engine.user_sensitivity = sensitivity;engine.user_smoothing = smoothing
            if palette != 'Default':
                from .music_engine import MUSIC_PRESETS
                engine.colors = dict(MUSIC_PRESETS[palette])
            engine.analysis_callback = frame
            with self.lock:
                self.engine = engine
                if not self.wanted:return
                engine.start()
            # Capture owns its original thread/context manager; joins never run in Qt.
            engine.thread.join()
        except Exception as error:log(f'Audio error: {type(error).__name__}: {error}')
        finally:
            with self.lock:self.wanted = False;self.engine = None

    def stop(self):
        with self.lock:
            self.wanted = False;self.frame = None
            self.spectrum.reset()
            if self.engine is not None:self.engine.stop()

    def take(self):
        with self.lock:
            frame,self.frame = self.frame,None
            return frame,self.message,self.error,self.wanted

    def take_spectrum(self):
        # Reduction happens on the GUI caller, outside the lighting mailbox lock.
        return self.spectrum.take()
