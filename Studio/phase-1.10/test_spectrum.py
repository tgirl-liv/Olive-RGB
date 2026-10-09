"""Real FFT observer compatibility and display tests; all capture is simulated."""
import math
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from PySide6.QtTest import QTest
import test_audio_reactor as gui
import test_music_live as fixtures
from studio_qt import music_engine as production
from studio_qt.spectrum_engine import SpectrumMusicEngine
from studio_qt.spectrum_data import SpectrumMailbox,SpectrumFrame,log_magnitudes
from studio_qt.music_runtime import MusicRuntime,engine_factory
from studio_qt.widgets.audio_reactor import AudioReactor
from studio_qt.music_window import MusicLiveWindow
import sys
from music_coordination import MusicFrame


def fft_tone(frequency=1000,amplitude=.1):
    mono=np.sin(np.arange(4096)*2*np.pi*frequency/48000)*amplitude
    return np.abs(np.fft.rfft(mono*np.hanning(len(mono)))),np.fft.rfftfreq(len(mono),1/48000)


def frame(rms=.04):return MusicFrame((100,20,30),.6,.3,.1,rms,False,time.monotonic())


class SpectrumTests(unittest.TestCase):
    def test_log_bands_resolve_distinct_frequency_peaks(self):
        centers=np.geomspace(20,20000,73);centers=(centers[:-1]*centers[1:])**.5
        peaks=[]
        for hz in (100,1000,8000):
            values=log_magnitudes(*fft_tone(hz))
            self.assertEqual(len(values),72);self.assertTrue(all(math.isfinite(v) and v>=0 for v in values))
            peak=int(np.argmax(values));peaks.append(peak)
            self.assertLess(abs(math.log(centers[peak]/hz)),.15)
            self.assertGreater(max(values),.075)
            self.assertLess(sum(v>max(values)*.5 for v in values),12)
        self.assertEqual(peaks,sorted(set(peaks)))

    def test_binning_silence_and_amplitude_scaling(self):
        fft,freq=fft_tone();values=log_magnitudes(fft,freq)
        self.assertEqual(log_magnitudes(np.zeros_like(fft),freq),(0.,)*72)
        self.assertTrue(np.allclose(log_magnitudes(fft*.1,freq),np.array(values)*.1))

    def test_latest_only_snapshot_and_generation_isolation(self):
        mailbox=SpectrumMailbox();mailbox.reset(1);fft,freq=fft_tone()
        for n in range(200):self.assertTrue(mailbox.publish(fft*n,freq,frame(),1))
        result=mailbox.take();self.assertTrue(np.allclose(result.magnitudes,np.array(log_magnitudes(fft,freq))*199))
        self.assertIsNone(mailbox.take())
        self.assertFalse(mailbox.publish(fft,freq,frame(),0))
        mailbox.reset();self.assertFalse(mailbox.publish(fft,freq,frame(),1))
        mailbox.reset(2);self.assertTrue(mailbox.publish(fft,freq,frame(),2))
        fft[:]=0;self.assertGreater(max(mailbox.take().magnitudes),0)

    def test_busy_consumer_never_blocks_audio_producer(self):
        mailbox=SpectrumMailbox();mailbox.reset(1);fft,freq=fft_tone();result=[]
        with mailbox.lock:
            worker=threading.Thread(target=lambda:result.append(mailbox.publish(fft,freq,frame(),1)))
            worker.start();worker.join(.5)
            self.assertFalse(worker.is_alive());self.assertEqual(result,[False])
        self.assertIsNone(mailbox.take())

    def test_producer_does_not_perform_log_binning(self):
        mailbox=SpectrumMailbox();mailbox.reset(1)
        with patch('studio_qt.spectrum_data.log_magnitudes',side_effect=AssertionError('audio thread binning')):
            self.assertTrue(mailbox.publish(*fft_tone(),frame(),1))
        self.assertEqual(len(mailbox.take().magnitudes),72)

    def run_engine(self,cls):
        output=[];meters=[];fft_calls=[];recorders=[];mailbox=SpectrumMailbox();mailbox.reset(1)
        engine=cls(lambda *a:None,lambda *args:meters.append(args),lambda:None,lambda *args:None)
        def analysis(value):
            output.append(value)
            if hasattr(engine,'publish_spectrum'):engine.publish_spectrum(value,mailbox,1)
        engine.analysis_callback=analysis
        class Recorder:
            def __enter__(self):recorders.append(self);return self
            def __exit__(self,*args):pass
            def record(self,numframes):
                self.calls=getattr(self,'calls',0)+1
                if self.calls>2:raise RuntimeError('simulated device removed')
                mono=np.sin(np.arange(numframes)*2*np.pi*1000/48000)*.1
                return np.column_stack([mono,mono])
        audio=SimpleNamespace(default_speaker=lambda:SimpleNamespace(name='Mock output'),get_microphone=lambda *a,**k:SimpleNamespace(recorder=lambda **k:Recorder()))
        original=np.fft.rfft
        def fft(*args):fft_calls.append(1);return original(*args)
        with patch.object(production,'sc',audio),patch.object(np.fft,'rfft',fft):
            engine.start();engine.thread.join(2)
        self.assertFalse(engine.thread.is_alive());self.assertEqual(len(recorders),1);self.assertEqual(len(fft_calls),2)
        return output,meters,mailbox.take()

    def test_inherited_capture_and_lighting_are_identical(self):
        self.assertIs(SpectrumMusicEngine._run,production.MusicEngine._run)
        self.assertIs(SpectrumMusicEngine.start,production.MusicEngine.start)
        self.assertIs(SpectrumMusicEngine.stop,production.MusicEngine.stop)
        original,meters,_=self.run_engine(production.MusicEngine)
        observed,other_meters,spectrum=self.run_engine(SpectrumMusicEngine)
        self.assertEqual(len(original),2);self.assertEqual(len(observed),2)
        for a,b in zip(original,observed):
            self.assertEqual((a.rgb,a.bass,a.mids,a.treble,a.energy,a.beat),(b.rgb,b.bass,b.mids,b.treble,b.energy,b.beat))
        for a,b in zip(meters,other_meters):
            self.assertTrue(np.allclose(a[:4],b[:4]));self.assertTrue(np.array_equal(a[4],b[4]));self.assertEqual(a[5],b[5])
        self.assertEqual(len(spectrum.magnitudes),72);self.assertGreater(max(spectrum.magnitudes),.075)
        self.assertEqual(spectrum.rms,observed[-1].energy)
        self.assertEqual(spectrum.timestamp,observed[-1].timestamp)

    def test_runtime_factory_is_extension_and_stop_invalidates_visual_data(self):
        engine=engine_factory(lambda *a:None,lambda *a:None,lambda:None,lambda *a:None)
        self.assertIsInstance(engine,SpectrumMusicEngine)
        runtime=MusicRuntime();runtime.spectrum.reset(1)
        runtime.spectrum.publish(*fft_tone(),frame(),1);runtime.stop()
        self.assertIsNone(runtime.take_spectrum())


class SpectrumGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):gui.ReactorTests.setUpClass()
    def setUp(self):
        self.w=AudioReactor();self.w.enable_live();self.errors=[]
        self.hook=patch.object(sys,'excepthook',lambda *exc:self.errors.append(exc[1]));self.hook.start()
    def tearDown(self):
        try:self.w.reset_live();self.w.close();self.w.deleteLater();self.assertEqual(self.errors,[])
        finally:self.hook.stop()
    def visual(self,hz=1000,amplitude=.1):
        return SpectrumFrame(log_magnitudes(*fft_tone(hz,amplitude)),amplitude/math.sqrt(2),time.monotonic())

    def test_real_peaks_and_independent_curve_smoothing(self):
        w=self.w;value=self.visual();w.set_live_frame(frame(value.rms));w.set_spectrum_frame(value)
        w.advance_live(.034,value.timestamp)
        peak=max(w.levels);self.assertGreater(peak,.4)
        self.assertLess(sum(v>peak*.5 for v in w.levels),12)
        self.assertGreater(max(w.curve_levels)-min(w.curve_levels),.1)
        self.assertNotEqual(w.curve_levels,w.levels)
        self.assertEqual(w.frames,0);self.assertEqual(w.phase,0)

    def test_curve_is_positioned_above_even_full_height_bars(self):
        from studio_qt.widgets import audio_reactor as module
        w=self.w;w.resize(720,240);w.levels=[1.]*72;w.peaks=[1.]*72
        w.curve_levels=[i/71 for i in range(72)]
        bars=[];curves=[];original=module.QPainter
        class Painter:
            RenderHint=original.RenderHint
            def __init__(self,widget):self.real=original(widget)
            def __getattr__(self,name):return getattr(self.real,name)
            def drawRoundedRect(self,rect,*args):
                if rect.width()<10 and rect.height()>7:bars.append(rect)
                self.real.drawRoundedRect(rect,*args)
            def drawPath(self,path):curves.append(path.boundingRect());self.real.drawPath(path)
        with patch.object(module,'QPainter',Painter):w.grab()
        self.assertEqual(len(bars),72);self.assertEqual(len(curves),3)
        self.assertLess(max(rect.bottom() for rect in curves)+5,min(rect.top() for rect in bars))

    def test_adaptive_gain_handles_volume_drop_without_flicker_or_silence_boost(self):
        w=self.w;first=self.visual(amplitude=.2);w.set_spectrum_frame(first)
        w.advance_live(.1,first.timestamp);reference=w._spectrum_reference
        quiet=self.visual(amplitude=.01);w.set_spectrum_frame(quiet)
        w.advance_live(.1,quiet.timestamp)
        self.assertLess(w._spectrum_reference,reference)
        # Gain reference releases gradually rather than instantly normalizing noise.
        self.assertGreater(w._spectrum_reference,max(quiet.magnitudes))
        zero=SpectrumFrame((0.,)*72,0.,quiet.timestamp);w.set_spectrum_frame(zero)
        self.assertEqual(w.spectrum_targets(.1,zero.timestamp),[0.]*72)
        before=w.levels[:];w.advance_live(.1,zero.timestamp)
        self.assertTrue(all(a<=b for a,b in zip(w.levels,before)))

    def test_fft_stale_or_missing_never_falls_back_to_uniform_three_band_bars(self):
        w=self.w;value=self.visual();w.set_spectrum_frame(value);w.advance_live(.1,value.timestamp)
        w.set_live_frame(frame());w.clear_live_frame();w.set_live_frame(frame())
        self.assertTrue(w._fft_received)
        before=w.levels[:];w.advance_live(.1,value.timestamp+1.1)
        self.assertTrue(all(a<=b for a,b in zip(w.levels,before)))
        for n in range(100):w.advance_live(.1,value.timestamp+1.2+n*.1)
        self.assertEqual(w.levels+w.curve_levels,[0.]*144);self.assertFalse(w._live_timer.isActive())


class SpectrumWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.MusicTests.setUpClass()
    def setUp(self):
        self.f=fixtures.MusicTests();self.f.setUp();self.errors=[]
        self.hook=patch.object(sys,'excepthook',lambda *exc:self.errors.append(exc[1]));self.hook.start()
    def tearDown(self):
        try:self.f.tearDown();self.assertEqual(self.errors,[])
        finally:self.hook.stop()

    def test_production_runtime_uses_one_recorder_and_delivers_real_fft_to_widget(self):
        f=self.f;recorders=[];closed=[]
        class Recorder:
            def __enter__(self):recorders.append(self);return self
            def __exit__(self,*args):closed.append(True)
            def record(self,numframes):
                mono=np.sin(np.arange(numframes)*2*np.pi*1000/48000)*.1
                return np.column_stack([mono,mono])
        audio=SimpleNamespace(default_speaker=lambda:SimpleNamespace(name='Mock output'),get_microphone=lambda *a,**k:SimpleNamespace(recorder=lambda **k:Recorder()))
        w=MusicLiveWindow(worker_factory=f.f.corner.factory,hue_factory=f.f.hue_factory)
        f.windows.append(w);f.f.windows.append(w);f.f.corner.windows.append(w)
        f.f.adapters.append(w.c.adapter);f.f.corner.adapters.append(w.c.adapter)
        w.show()
        with patch.object(production,'sc',audio):
            w.start_music();f.wait(lambda:w.reactor.spectrum_frame is not None and max(w.reactor.levels)>.3)
            self.assertIsInstance(w.runtime.engine,SpectrumMusicEngine)
            self.assertEqual(len(recorders),1)
            self.assertEqual(len(w.reactor.spectrum_frame.magnitudes),72)
            self.assertGreater(max(w.reactor.curve_levels)-min(w.reactor.curve_levels),.1)
            self.assertFalse(f.f.corner.workers);self.assertFalse(f.f.drivers)
            w.stop_music();f.wait(lambda:not w.runtime.busy)
        self.assertEqual(closed,[True]);self.assertFalse(w.reactor._live_timer.isActive())
    def test_independent_visual_mailbox_delivery_does_not_route_extra_lighting_frames(self):
        w=self.f.window();w.start_music();self.f.wait(lambda:w.runtime.engine is not None)
        w.music_timer.stop();w.reactor.reset_live()
        w.runtime.take()  # consume lighting first, then simulate later FFT publication
        visual=SpectrumFrame(log_magnitudes(*fft_tone()),.04,time.monotonic())
        with patch.object(w.runtime,'take',return_value=(None,'', '',True)),patch.object(w.runtime,'take_spectrum',return_value=visual),patch.object(w.c.adapter,'apply_frame') as lighting:
            w.poll_music();lighting.assert_not_called()
        self.assertIs(w.reactor.spectrum_frame,visual);self.assertTrue(w.reactor._live_timer.isActive())
        QTest.qWait(60);self.assertTrue(any(w.reactor.levels))
        w.stop_music();self.assertIsNone(w.reactor.spectrum_frame)


if __name__=='__main__':unittest.main()
