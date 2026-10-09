"""One production capture engine; bounded latest-frame mailbox, no Qt calls."""
import threading
import re
from .spectrum_data import SpectrumMailbox


def engine_factory(rgb, meter, beat, log):
    from .spectrum_engine import SpectrumMusicEngine
    return SpectrumMusicEngine(rgb, meter, beat, log)


def validated_palette(colors):
    keys=('bass','mids','treble','beat')
    if not isinstance(colors,dict) or set(colors)!=set(keys) or any(
        not isinstance(colors[key],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',colors[key]) for key in keys):
        raise ValueError('Music palette requires four RGB hex colors')
    return {key:colors[key].upper() for key in keys}


def preset_colors(name):
    from .music_engine import DEFAULT_MUSIC_COLORS,MUSIC_PRESETS
    return dict(DEFAULT_MUSIC_COLORS if name=='Default' else MUSIC_PRESETS[name])


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
        self._palette=None

    @property
    def busy(self):return self.thread is not None and self.thread.is_alive()

    def start(self, profile='Reactive', sensitivity=1., smoothing=1., palette='Default', colors=None):
        with self.lock:
            if self.busy:return False
            self._palette=validated_palette(colors if colors is not None else preset_colors(palette))
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
            engine.analysis_callback = frame
            with self.lock:
                self.engine = engine
                engine.colors=dict(self._palette)
                if not self.wanted:return
                engine.start()
            # Capture owns its original thread/context manager; joins never run in Qt.
            engine.thread.join()
        except Exception as error:log(f'Audio error: {type(error).__name__}: {error}')
        finally:
            with self.lock:self.wanted = False;self.engine = None

    def set_palette(self, colors):
        # Validate before locking; replace complete dictionaries, never mutate a
        # palette the unchanged audio engine may currently be reading.
        value=validated_palette(colors)
        with self.lock:
            self._palette=value
            if self.engine is not None:self.engine.colors=dict(value)

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
