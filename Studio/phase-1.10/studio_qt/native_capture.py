"""Thread-scoped COM ownership and content-free native capture observations."""
from contextlib import contextmanager
import ctypes
import sys
import time
from .capture_diagnostics import emit


@contextmanager
def audio_apartment(ole=None):
    if ole is None and sys.platform!='win32':yield;return
    if ole is None:
        ole=ctypes.WinDLL('ole32')
        ole.CoInitializeEx.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
        ole.CoInitializeEx.restype=ctypes.c_long
        ole.CoUninitialize.restype=None
    result=ole.CoInitializeEx(None,0)  # MTA, on the actual WASAPI capture thread.
    code=result & 0xffffffff
    if code not in (0,1,0x80010106):
        emit('music.com.failed',hresult=code)
        raise OSError(f'WASAPI COM initialization failed (HRESULT 0x{code:08X})')
    emit('music.com.ready',owned=code in (0,1))
    try:yield
    finally:
        if code in (0,1):ole.CoUninitialize();emit('music.com.released')


class Recorder:
    def __init__(self,inner):self.inner=inner
    def __enter__(self):
        emit('music.recorder.enter.begin');self.inner.__enter__();emit('music.recorder.enter.ready');return self
    def __exit__(self,*args):
        try:return self.inner.__exit__(*args)
        finally:emit('music.recorder.closed')
    def record(self,**kwargs):
        emit('music.record.begin',interval=1);start=time.monotonic()
        result=self.inner.record(**kwargs)
        emit('music.record.return',interval=1,frames=len(result),duration_ms=round((time.monotonic()-start)*1000))
        return result


class Loopback:
    def __init__(self,inner):self.inner=inner
    def __getattr__(self,key):return getattr(self.inner,key)
    def recorder(self,**kwargs):
        emit('music.recorder.create.begin')
        recorder=self.inner.recorder(**kwargs);emit('music.recorder.create.ready')
        return Recorder(recorder)


class Capture:
    def __init__(self,inner):self.inner=inner
    def __enter__(self):
        emit('screen.capture.enter.begin');self.inner.__enter__();emit('screen.capture.enter.ready');return self
    def __exit__(self,*args):
        try:return self.inner.__exit__(*args)
        finally:emit('screen.capture.closed')
    @property
    def monitors(self):
        emit('screen.monitors.begin');value=self.inner.monitors
        emit('screen.monitors.ready',count=max(0,len(value)-1));return value
    def grab(self,region):
        emit('screen.grab.begin',interval=1);start=time.monotonic();value=self.inner.grab(region)
        emit('screen.grab.return',interval=1,duration_ms=round((time.monotonic()-start)*1000));return value


def MSS(*args,**kwargs):
    import mss
    emit('screen.capture.create.begin');value=Capture(mss.MSS(*args,**kwargs));emit('screen.capture.create.ready');return value
