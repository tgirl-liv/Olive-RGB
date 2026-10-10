"""Background MSS capture using the preserved engine and latest-only RGB mailbox."""
import threading
import time
import math


def validate_settings(monitor,intensity,saturation):
    if type(monitor) is not int or not 1<=monitor<=128:raise ValueError('Invalid monitor')
    for value,low,high in ((intensity,.25,2.),(saturation,.5,2.5)):
        if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise ValueError('Invalid screen adjustment')
    return monitor,float(intensity),float(saturation)


def engine_factory(rgb,preview,log,controls):
    from .screen_engine import ScreenEngine
    class CaptureEngine(ScreenEngine):
        def _still_active(self,generation):
            active=super()._still_active(generation)
            if active:self.intensity,self.saturation=controls()
            return active
    return CaptureEngine(rgb,preview,log)


def scan_monitors():
    import mss
    with mss.MSS() as capture:return [dict(m) for m in capture.monitors[1:]]


class ScreenRuntime:
    def __init__(self,factory=None,scanner=None):
        self.factory=factory or engine_factory;self.scanner=scanner or scan_monitors
        self.lock=threading.RLock();self.thread=None;self.engine=None;self.scan_thread=None
        self.generation=0;self.wanted=False;self.closed=False;self.frame=None
        self.message='Screen stopped';self.error='';self.monitors=None;self.scan_error=''
        self.settings=(1,1.,1.25)

    @property
    def busy(self):return self.thread is not None and self.thread.is_alive()
    @property
    def scanning(self):return self.scan_thread is not None and self.scan_thread.is_alive()

    def configure(self,monitor,intensity,saturation):
        settings=validate_settings(monitor,intensity,saturation)
        with self.lock:self.settings=settings

    def controls(self):
        with self.lock:return self.settings[1:]

    def refresh_monitors(self):
        if self.closed or self.scanning or self.busy:return False
        def scan():
            try:
                monitors=self.scanner()
                if not monitors:raise RuntimeError('No capturable monitors found')
                with self.lock:self.monitors=monitors;self.scan_error=''
            except Exception as error:
                with self.lock:self.monitors=[];self.scan_error=f'Monitor discovery failed: {type(error).__name__}: {error}'
        self.scan_thread=threading.Thread(target=scan,name='Screen monitor discovery',daemon=True);self.scan_thread.start();return True

    def start(self,mode):
        if mode not in ('Movie','Gaming'):raise ValueError('Unsupported screen mode')
        with self.lock:
            if self.closed or self.busy:return False
            self.generation+=1;generation=self.generation;monitor=self.settings[0]
            self.wanted=True;self.frame=None;self.error='';self.message='Opening screen capture…'
            self.thread=threading.Thread(target=self._run,args=(generation,mode,monitor),name='Screen lifecycle',daemon=True)
            self.thread.start();return True

    def _run(self,generation,mode,monitor):
        def log(message):
            with self.lock:
                if generation!=self.generation:return
                self.message=str(message)
                if 'error' in self.message.lower():self.error=self.message
        def output(*rgb):
            with self.lock:
                if self.wanted and generation==self.generation:self.frame=(tuple(rgb),mode,time.monotonic())
        try:
            engine=self.factory(output,lambda *args:None,log,self.controls)
            # Only the lifecycle thread starts or joins capture. Qt never waits.
            with self.lock:
                self.engine=engine
                if not self.wanted or generation!=self.generation:return
                engine.intensity,engine.saturation=self.settings[1:]
                engine.start(mode,monitor)
            engine.thread.join()
        except Exception as error:log(f'Screen capture error: {type(error).__name__}: {error}')
        finally:
            with self.lock:
                self.engine=None
                if generation==self.generation:self.wanted=False

    def stop(self):
        with self.lock:
            self.generation+=1;self.wanted=False;self.frame=None
            if self.engine is not None:self.engine.stop()

    def close(self):
        self.closed=True;self.stop()

    def take(self):
        with self.lock:
            value=self.frame;self.frame=None
            return value,self.message,self.error,self.wanted
