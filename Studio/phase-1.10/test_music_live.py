"""Production routing/capture contracts with fake audio and device I/O only."""
import ast,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import QThread
from PySide6.QtTest import QTest
import test_dual_live as fixtures
from music_coordination import MusicFrame
from studio_qt.music_adapter import MusicLightingAdapter
from studio_qt.music_runtime import MusicRuntime
from studio_qt.music_window import MusicLiveWindow


def frame(rgb=(255,0,0)):
    return MusicFrame(rgb,.6,.3,.1,.04,False,time.monotonic())


class FakeEngine:
    def __init__(self,log,options):
        self.log=log;self.options=options;self.running=False;self.thread=None;self.analysis_callback=None
    def set_profile(self,name):self.profile_name=name
    def start(self):
        self.running=True
        def run():
            try:
                while self.running:
                    if self.options.get('error'):
                        self.log('Audio error: '+self.options['error']);break
                    self.analysis_callback(frame());time.sleep(.01)
            finally:self.running=False
        self.thread=threading.Thread(target=run);self.thread.start()
    def stop(self):self.running=False


class MusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.DualTests.setUpClass();cls.app=fixtures.DualTests.app
    def setUp(self):
        self.f=fixtures.DualTests();self.f.setUp();self.engines=[];self.options={};self.windows=[];self.runtimes=[]
    def factory(self,rgb,meter,beat,log):
        if self.options.get('init_error'):raise RuntimeError('mock audio initialization failed')
        engine=FakeEngine(log,self.options);self.engines.append(engine);return engine
    def wait(self,predicate):self.f.wait(predicate)
    def adapter(self):
        a=MusicLightingAdapter(worker_factory=self.f.corner.factory,hue_factory=self.f.hue_factory,hue_identity={'name':'Tv lamp'})
        self.f.adapters.append(a);self.f.corner.adapters.append(a);return a
    def window(self):
        w=MusicLiveWindow(worker_factory=self.f.corner.factory,hue_factory=self.f.hue_factory,hue_identity={'name':'Tv lamp'},engine_factory=self.factory)
        self.windows.append(w);self.f.windows.append(w);self.f.corner.windows.append(w);self.f.adapters.append(w.c.adapter);self.f.corner.adapters.append(w.c.adapter)
        w.show();self.app.processEvents();return w
    def tearDown(self):
        for w in self.windows:w.close()
        for r in self.runtimes:r.stop()
        self.wait(lambda:all(not w.runtime.busy for w in self.windows) and all(not r.busy for r in self.runtimes))
        self.f.tearDown()
    def test_engine_class_and_helpers_preserved(self):
        root=Path(__file__).parent
        a=ast.parse((root/'olive_rgb.py').read_text(encoding='utf-8'));b=ast.parse((root/'studio_qt/music_engine.py').read_text(encoding='utf-8'))
        for name in ('MusicEngine','validated_music_colors','color_rgb'):
            self.assertEqual(ast.dump(next(n for n in a.body if getattr(n,'name',None)==name)),ast.dump(next(n for n in b.body if getattr(n,'name',None)==name)))
    def test_start_stop_one_engine_and_no_startup_capture(self):
        w=self.window();self.assertFalse(self.engines);w.start_music();w.start_music()
        self.wait(lambda:w.c.adapter.last_frame is not None);self.assertEqual(len(self.engines),1)
        w.stop_music();self.assertFalse(w.c.adapter.music_active);self.wait(lambda:not w.runtime.busy)
        self.wait(lambda:not w.music_timer.isActive())
        self.assertIsNone(w.reactor.live_frame)
    def test_audio_initialization_failure(self):
        self.options['init_error']=True;w=self.window();w.start_music()
        self.wait(lambda:'initialization failed' in w.music_status.text());self.assertFalse(w.c.adapter.music_active)
    def test_missing_device_and_capture_loss(self):
        w=self.window();w.start_music();self.wait(lambda:w.c.adapter.last_frame is not None)
        self.options['error']='default output disappeared';self.wait(lambda:'disappeared' in w.music_status.text())
        self.assertFalse(w.c.adapter.music_active);self.assertFalse(w.runtime.wanted)
    def test_corner_only_routes_real_frame(self):
        a=self.adapter();self.f.connect_corner(a);a.set_master(True,1);a.set_brightness('Corner',1);a.start_music();a.apply_frame(frame())
        self.wait(lambda:any(c[0]=='rgb' and c[2]==(255,0,0) for c in self.f.corner.lamps[0].calls));self.assertFalse(self.f.drivers)
    def test_hue_only_and_same_color(self):
        a=self.adapter();self.f.connect_hue(a);a.start_music('Same Color');a.apply_frame(frame((0,0,255)))
        self.wait(lambda:self.f.wrote('color',(0,0,255)));self.assertFalse(self.f.corner.workers)
    def test_white_only_hue_music_uses_supported_fields(self):
        self.f.options['caps']={'color':False};a=self.adapter();self.f.connect_hue(a);a.start_music();a.apply_frame(frame())
        self.wait(lambda:any(c[0]=='write' and c[2]=='brightness' for c in self.f.drivers[0].calls))
        self.assertNotIn('color',a.hue.pending)
    def test_dual_coordinated_colors(self):
        a=self.adapter();self.f.connect_corner(a);self.f.connect_hue(a);a.start_music();a.apply_frame(frame())
        self.assertNotEqual(a.music_colors['Corner'],a.music_colors['Hue'])
        self.wait(lambda:any(c[0]=='write' and c[2]=='color' for c in self.f.drivers[0].calls))
    def test_participation_preserves_manual_color(self):
        a=self.adapter();self.f.connect_hue(a);a.set_rgb('Hue','#0000FF');a.set_participation('Hue',False);a.start_music();a.apply_frame(frame())
        self.assertFalse(a.owns('Hue'));a.set_rgb('Hue','#00FF00');self.wait(lambda:self.f.wrote('color',(0,255,0)))
        a.set_participation('Hue',True);self.assertTrue(a.owns('Hue'))
        with self.assertRaises(ValueError):a.set_rgb('Hue','#FFFFFF')
        a.set_participation('Hue',False);self.assertEqual(a.state.channels['Hue'].color,'#00FF00')
    def test_follow_master_precedence_and_local_brightness(self):
        a=self.adapter();self.f.connect_hue(a);a.set_brightness('Hue',.5);a.start_music('Same Color');a.apply_frame(frame())
        a.set_master(False,.5);self.wait(lambda:self.f.wrote('brightness',127));self.assertTrue(a.hue.pending['power'])
        a.set_follow_master('Hue',True);self.assertFalse(a.hue.pending['power'])
        a.set_master(True,.5);self.assertEqual(a.hue.pending['brightness'],64)
    def test_rapid_frames_bounded_and_latest(self):
        a=self.adapter();self.f.connect_hue(a);a.start_music('Same Color')
        for n in range(1000):a.apply_frame(frame((0,0,n%256)))
        self.assertLessEqual(len(a.hue.pending),3);self.wait(lambda:self.f.wrote('color',(0,0,999%256)))
    def test_stop_discards_future_music_and_restores_manual(self):
        a=self.adapter();self.f.connect_hue(a);a.set_rgb('Hue','#00FF00');a.start_music('Same Color');a.apply_frame(frame())
        a.stop_music();a.apply_frame(frame((0,0,255)));self.assertEqual(a.hue.pending['color'],(0,255,0))
    def test_device_loss_does_not_stop_music_or_other_device(self):
        a=self.adapter();self.f.connect_hue(a);self.f.connect_corner(a);a.start_music();self.f.drivers[0].connected=False
        self.wait(lambda:a.hue_status=='error');a.apply_frame(frame());self.assertTrue(a.music_active);self.assertTrue(a.connected)
    def test_qt_thread_routing_and_no_synthetic_animation(self):
        w=self.window();threads=[];original=w.c.adapter.apply_frame
        def apply(value):threads.append(QThread.currentThread());original(value)
        w.c.adapter.apply_frame=apply;count=w.reactor.frames;w.start_music();self.wait(lambda:len(threads)>2)
        self.assertTrue(all(t==self.app.thread() for t in threads));self.assertEqual(count,w.reactor.frames)
    def test_close_releases_audio_and_bluetooth(self):
        w=self.window();self.f.connect_hue(w.c.adapter);w.start_music();self.wait(lambda:w.runtime.engine is not None)
        w.close();self.wait(lambda:w._cleanup_done and not w.runtime.busy and not w.isVisible());self.assertFalse(w.music_timer.isActive())
    def test_runtime_mailbox_bounded_and_stop_during_initialization(self):
        ready=threading.Event()
        def delayed(*args):ready.wait(.2);return self.factory(*args)
        r=MusicRuntime(delayed);self.runtimes.append(r);r.start();r.stop();ready.set();self.wait(lambda:not r.busy)
        self.assertFalse(self.engines[0].running);self.assertIsNone(r.take()[0])
    def test_demo_no_audio_access(self):
        from studio_qt.app import StudioWindow
        with patch('studio_qt.music_runtime.engine_factory',side_effect=AssertionError('DEMO capture')):
            w=StudioWindow();w.show();self.app.processEvents();w.close()
        self.assertFalse(self.engines)
    def test_four_window_sizes(self):
        from PySide6.QtCore import QPoint
        w=self.window()
        for size in [(1440,900),(1280,800),(1080,760),(800,600)]:
            w.resize(*size);w.c.navigate('Music');QTest.qWait(30);w.c.navigate('Studio');QTest.qWait(60);self.assertEqual((w.width(),w.height()),size)
            for b in (w.music_start,w.music_stop):self.assertTrue(b.parentWidget().rect().contains(b.geometry()))
            viewport=w.pages.widget(0).viewport()
            self.assertLessEqual(w.master.color.mapTo(viewport,QPoint()).x()+w.master.color.width(),viewport.width())
            self.assertLessEqual(w.reactor.mapTo(viewport,QPoint()).x()+w.reactor.width(),viewport.width())


class CaptureTests(unittest.TestCase):
    def test_actual_engine_missing_default_output_reports_error(self):
        from studio_qt import music_engine as module
        logs=[];engine=module.MusicEngine(lambda *a:None,lambda *a:None,lambda:None,logs.append)
        with patch.object(module,'sc',SimpleNamespace(default_speaker=lambda:None)):
            engine.start();engine.thread.join(2)
        self.assertFalse(engine.running);self.assertTrue(any('Audio error' in text for text in logs))
    def test_actual_engine_with_fake_recorder_and_device_loss(self):
        import numpy as np
        from studio_qt import music_engine as module
        frames=[];logs=[];closed=[]
        engine=module.MusicEngine(lambda *a:None,lambda *a:None,lambda:None,logs.append)
        engine.analysis_callback=frames.append
        class Recorder:
            count=0
            def __enter__(self):return self
            def __exit__(self,*args):closed.append(True)
            def record(self,numframes):
                self.count+=1
                if self.count>2:raise RuntimeError('mock recorder removed')
                x=np.sin(np.arange(numframes)*2*np.pi*100/48000)*.1
                return np.column_stack([x,x])
        audio=SimpleNamespace(default_speaker=lambda:SimpleNamespace(name='Mock output'),get_microphone=lambda *a,**k:SimpleNamespace(recorder=lambda **k:Recorder()))
        with patch.object(module,'sc',audio):engine.start();engine.thread.join(2)
        self.assertFalse(engine.thread.is_alive());self.assertTrue(closed);self.assertEqual(len(frames),2)
        self.assertGreater(frames[0].energy,0);self.assertTrue(any('removed' in x for x in logs))

if __name__=='__main__':unittest.main()
