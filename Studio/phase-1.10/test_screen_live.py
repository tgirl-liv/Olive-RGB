"""Preserved screen math and Studio lifecycle with simulated screen/device I/O."""
import ast
import threading
import time
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from PySide6.QtTest import QTest
import test_music_live as fixtures
from studio_qt.screen_engine import ScreenEngine
from studio_qt.screen_runtime import ScreenRuntime
from studio_qt.screen_window import ScreenLiveWindow
from studio_qt.preferences import PreferencesStore,validate

MONITORS=[{'left':0,'top':0,'width':40,'height':40},
          {'left':-40,'top':0,'width':40,'height':40},
          {'left':0,'top':0,'width':40,'height':40}]


class Capture:
    monitors=MONITORS
    rgb=(200,50,25)
    delay=0
    calls=[]
    def __enter__(self):self.calls.append(('open',threading.get_ident()));return self
    def __exit__(self,*args):self.calls.append(('close',threading.get_ident()))
    def grab(self,region):
        self.calls.append(('grab',threading.get_ident(),dict(region)))
        if self.delay:time.sleep(self.delay)
        frame=np.zeros((40,40,4),dtype=np.uint8);frame[:,:,:3]=self.rgb[::-1];return frame


class ScreenAnalysisTests(unittest.TestCase):
    def setUp(self):self.patch=patch('studio_qt.screen_engine.mss.MSS',Capture);self.patch.start();Capture.rgb=(200,50,25);Capture.delay=0;Capture.calls=[]
    def tearDown(self):self.patch.stop()
    def render(self,mode,intensity=1.,saturation=1.25,count=1):
        colors=[];messages=[];previews=[]
        def output(*rgb):
            colors.append(rgb)
            if len(colors)>=count:engine.stop()
        engine=ScreenEngine(output,lambda *args:previews.append(args),messages.append)
        engine.running=True;engine.intensity=intensity;engine.saturation=saturation
        engine._run(0,mode,1)
        return colors,previews,messages
    def test_original_engine_is_exactly_preserved(self):
        root=Path(__file__).parent
        def node(path):return next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if getattr(n,'name',None)=='ScreenEngine')
        self.assertEqual(ast.dump(node(root/'olive_rgb.py')),ast.dump(node(root/'studio_qt/screen_engine.py')))
    def test_movie_original_average_luma_intensity_and_preview(self):
        rgb=np.array(Capture.rgb,dtype=float);gray=rgb@np.array([.2126,.7152,.0722]);target=np.clip(gray+(rgb-gray)*1.25,0,255)
        luma=target@np.array([.2126,.7152,.0722]);expected=tuple(int(v) for v in target*np.clip(.30+luma/255*.90,.25,1.))
        colors,previews,_=self.render('Movie');self.assertEqual(colors,[expected]);self.assertEqual(previews,[(expected,'Movie')])
        self.assertEqual(Capture.calls[1][2],MONITORS[1])
    def test_gaming_original_impact_and_smoothing(self):
        Capture.rgb=(255,255,255)
        colors,previews,_=self.render('Gaming',intensity=.5,count=2)
        self.assertEqual(colors[0],(165,165,165));self.assertEqual(colors[1],(140,140,140));self.assertEqual(previews[1],(colors[1],'Gaming'))
    def test_saturation_zero_grayscale_and_clipping(self):
        result=ScreenEngine._boost_saturation((255,0,0),0)
        self.assertTrue(np.allclose(result,(54.213,)*3))
        result=ScreenEngine._boost_saturation((255,0,0),2.5);self.assertEqual(tuple(result),(255.,0.,0.))
    def test_dark_screen_black_and_no_fabricated_output(self):
        Capture.rgb=(0,0,0);colors,_,_=self.render('Movie');self.assertEqual(colors,[(0,0,0)])
    def test_missing_monitor_reports_error_without_output(self):
        colors=[];logs=[];engine=ScreenEngine(lambda *rgb:colors.append(rgb),lambda *args:None,logs.append)
        engine.running=True;engine._run(0,'Movie',99)
        self.assertFalse(engine.running);self.assertFalse(colors);self.assertTrue(any('does not exist' in s for s in logs))


class ScreenRuntimeTests(unittest.TestCase):
    def setUp(self):
        Capture.calls=[];Capture.delay=0;Capture.rgb=(200,50,25)
        self.patch=patch('studio_qt.screen_engine.mss.MSS',Capture);self.patch.start();self.runtimes=[]
    def tearDown(self):
        for r in self.runtimes:r.close()
        for r in self.runtimes:
            if r.thread:r.thread.join(3)
            if r.scan_thread:r.scan_thread.join(3)
            self.assertFalse(r.busy);self.assertFalse(r.scanning)
        self.patch.stop()
    def runtime(self,**kwargs):r=ScreenRuntime(**kwargs);self.runtimes.append(r);return r
    def wait(self,predicate):
        deadline=time.monotonic()+3
        while not predicate() and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(predicate())
    def test_capture_thread_settings_latest_mailbox_and_stop(self):
        r=self.runtime();r.start('Gaming');self.wait(lambda:r.frame is not None);engine=r.engine;thread=r.thread
        r.configure(1,.25,.5);self.wait(lambda:engine.intensity==.25 and engine.saturation==.5)
        self.assertIs(r.thread,thread);self.assertFalse(r.start('Movie'));time.sleep(.15)
        frame,_,_,wanted=r.take();self.assertIsInstance(frame,tuple);self.assertTrue(wanted);self.assertIsNone(r.frame)
        r.stop();self.wait(lambda:not r.busy);self.assertIsNone(r.take()[0])
        self.assertTrue(all(c[1]!=threading.get_ident() for c in Capture.calls))
    def test_monitor_discovery_is_off_caller_thread(self):
        r=self.runtime();r.refresh_monitors();self.wait(lambda:not r.scanning)
        self.assertEqual(r.monitors,MONITORS[1:]);self.assertNotEqual(Capture.calls[0][1],threading.get_ident())
    def test_missing_dependencies_or_capture_failure_report_error(self):
        def fail(*args):raise ImportError('mss unavailable')
        r=self.runtime(factory=fail);r.start('Movie');self.wait(lambda:not r.busy)
        self.assertIn('mss unavailable',r.error);self.assertFalse(r.wanted);self.assertIsNone(r.frame)
    def test_validation_rejects_unsupported_controls(self):
        r=self.runtime()
        for values in ((0,1,1.25),(1,float('nan'),1.25),(1,1,3),(True,1,1)):
            with self.assertRaises(ValueError):r.configure(*values)
        with self.assertRaises(ValueError):r.start('Music')
    def test_close_during_capture_discards_late_result(self):
        Capture.delay=.15;r=self.runtime();r.start('Gaming');self.wait(lambda:any(c[0]=='grab' for c in Capture.calls))
        r.close();self.wait(lambda:not r.busy);self.assertIsNone(r.take()[0]);self.assertFalse(r.start('Movie'))
    def test_monitor_scan_failure_is_explicit(self):
        def fail():raise OSError('capture permission denied')
        r=self.runtime(scanner=fail);r.refresh_monitors();self.wait(lambda:not r.scanning)
        self.assertEqual(r.monitors,[]);self.assertIn('permission denied',r.scan_error)


class ScreenWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.MusicTests.setUpClass()
    def setUp(self):
        self.f=fixtures.MusicTests();self.f.setUp();self.windows=[];Capture.rgb=(200,50,25);Capture.delay=0;Capture.calls=[]
        self.patch=patch('studio_qt.screen_engine.mss.MSS',Capture);self.patch.start()
    def tearDown(self):
        try:
            for w in self.windows:w.close()
            self.wait(lambda:all(not w.screen_runtime.busy and not w.screen_runtime.scanning for w in self.windows))
            self.f.tearDown()
        finally:self.patch.stop()
    def wait(self,predicate):self.f.wait(predicate)
    def window(self,**kwargs):
        w=ScreenLiveWindow(worker_factory=self.f.f.corner.factory,hue_factory=self.f.f.hue_factory,hue_identity={'name':'Tv lamp'},engine_factory=self.f.factory,**kwargs)
        self.windows.append(w);self.f.windows.append(w);self.f.f.windows.append(w);self.f.f.corner.windows.append(w);self.f.f.adapters.append(w.c.adapter);self.f.f.corner.adapters.append(w.c.adapter)
        w.show();self.wait(lambda:w.monitor.count()>0);return w
    def start(self,w,mode='Movie'):w.start_screen(mode);self.wait(lambda:w.screen_preview.virtual_rgb is not None)
    def test_launch_idle_and_preview_without_hardware(self):
        w=self.window();self.assertFalse(w.screen_runtime.busy);self.assertIsNone(w.screen_runtime.engine);self.assertFalse(self.f.engines)
        self.start(w);self.assertFalse(self.f.f.corner.workers);self.assertFalse(w.c.adapter.hue_connected)
        self.assertEqual(w.screen_preview.virtual_rgb,w.c.adapter.corner_music_rgb(w.c.adapter.screen_rgb))
        self.assertTrue(all(c[1]!=threading.get_ident() for c in Capture.calls))
    def test_screen_settings_persist_and_restart_stays_idle(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'preferences-v1.json';w=self.window(preferences_path=path)
            w.monitor.setCurrentIndex(1);w.screen_intensity.setValue(150);w.screen_saturation.setValue(200);w.save_preferences()
            values=PreferencesStore(path).load('live')['screen'];self.assertEqual(values,{'monitor':2,'intensity':1.5,'saturation':2.})
            restored=self.window(preferences_path=path);self.assertEqual(restored.monitor.currentData(),2);self.assertEqual(restored.screen_intensity.value(),150);self.assertFalse(restored.screen_runtime.busy)
    def test_missing_saved_monitor_safe_fallback_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'preferences-v1.json';store=PreferencesStore(path);values=validate({},'live');values['screen']['monitor']=99;store.save('live',values)
            w=self.window(preferences_path=path);self.assertEqual(w.monitor.currentData(),1);self.assertIn('Saved monitor unavailable',w.screen_status.text());self.assertFalse(w.screen_runtime.busy)
        for values in ({'monitor':0},{'intensity':0},{'saturation':float('inf')}):
            with self.assertRaises(ValueError):validate({'screen':values},'live')
    def test_live_adjustments_remain_interactive_without_restart(self):
        w=self.window();self.start(w);engine=w.screen_runtime.engine;thread=w.screen_runtime.thread
        w.screen_intensity.setValue(175);w.screen_saturation.setValue(75)
        self.wait(lambda:engine.intensity==1.75 and engine.saturation==.75)
        self.assertIs(w.screen_runtime.engine,engine);self.assertIs(w.screen_runtime.thread,thread)
        self.assertTrue(w.screen_intensity.isEnabled());self.assertTrue(w.screen_saturation.isEnabled());self.assertTrue(w.palette.isEnabled())
    def test_monitor_switch_drains_old_capture_before_restart(self):
        w=self.window();self.start(w);old=w.screen_runtime.thread;w.monitor.setCurrentIndex(1)
        self.wait(lambda:w.screen_runtime.thread is not old and w.c.adapter.screen_rgb is not None)
        self.assertFalse(old.is_alive());self.assertEqual(w.screen_runtime.engine.monitor_number,2)
        self.assertTrue(any(c[0]=='grab' and c[2]==MONITORS[2] for c in Capture.calls))
    def test_music_screen_exclusive_and_capture_switching(self):
        w=self.window();w.start_music();self.wait(lambda:w.c.adapter.last_frame is not None);music_thread=w.runtime.thread
        self.start(w,'Gaming');self.assertFalse(music_thread.is_alive());self.assertFalse(w.c.adapter.music_active);self.assertTrue(w.c.adapter.screen_active)
        screen_thread=w.screen_runtime.thread;w.start_music();self.wait(lambda:w.c.adapter.last_frame is not None)
        self.assertFalse(screen_thread.is_alive());self.assertFalse(w.c.adapter.screen_active);self.assertTrue(w.c.adapter.music_active)
    def test_manual_ownership_scaling_and_restore(self):
        w=self.window();self.f.f.corner.connect(w.c.adapter);a=w.c.adapter
        a.set_rgb('Corner','#123456');a.set_master(True,.5);a.set_brightness('Corner',.5);self.start(w)
        self.assertTrue(a.owns('Corner'));self.assertIn('Screen owns',w.c.target_reason('Corner','color'))
        with self.assertRaises(ValueError):a.set_rgb('Corner','#FFFFFF')
        a.set_participation('Corner',False);self.assertTrue(a.owns('Corner'))
        self.assertEqual(w.screen_preview.virtual_rgb,a.corner_music_rgb(a.screen_rgb))
        w.stop_screen();self.assertFalse(a.owns('Corner'));self.assertEqual(a.state.channels['Corner'].color,'#123456')
        self.wait(lambda:any(c[0]=='rgb' and c[2]==(4,13,22) for c in a.session.worker.lamp.calls))
    def test_hue_reuses_session_and_follow_master_opt_out(self):
        w=self.window();a=w.c.adapter;self.f.f.connect_hue(a);a.set_follow_master('Hue',True);hue=a.hue;self.start(w)
        self.assertIs(a.hue,hue);self.assertTrue(a.owns('Hue'))
        a.set_follow_master('Hue',False);self.assertFalse(a.owns('Hue'));a.set_rgb('Hue','#123456')
        self.assertEqual(a.state.channels['Hue'].color,'#123456')
        a.set_follow_master('Hue',True);self.assertTrue(a.owns('Hue'));w.stop_screen();self.assertFalse(a.owns('Hue'))
    def test_shutdown_during_slow_capture_is_async_and_clean(self):
        Capture.delay=.25;w=self.window();w.start_screen('Movie');self.wait(lambda:any(c[0]=='grab' for c in Capture.calls))
        started=time.monotonic();w.close();self.assertLess(time.monotonic()-started,.15)
        self.wait(lambda:w._cleanup_done and not w.screen_runtime.busy and not w.isVisible())
    def test_capture_failure_restores_manual_without_connecting(self):
        def fail(*args):raise OSError('screen denied')
        w=self.window(screen_factory=fail);w.start_screen('Movie');self.wait(lambda:'screen denied' in w.screen_status.text())
        self.assertFalse(w.c.adapter.screen_active);self.assertEqual(w.c.state.mode,'Manual');self.assertFalse(self.f.f.corner.workers)
    def test_adapter_refuses_conflicting_owners(self):
        w=self.window();a=w.c.adapter;a.start_music()
        with self.assertRaises(RuntimeError):a.start_screen()
        a.stop_music();a.start_screen()
        with self.assertRaises(RuntimeError):a.start_music()
        a.stop_screen()
    def test_master_power_and_independent_device_scaling_match_preview(self):
        w=self.window();self.start(w);a=w.c.adapter
        a.set_master(False,.5);w.live_controls();self.assertEqual(w.screen_preview.virtual_rgb,(0,0,0))
        a.set_follow_master('Corner',False);a.set_brightness('Corner',.25);w.live_controls()
        self.assertEqual(w.screen_preview.virtual_rgb,tuple(round(c*.25) for c in a.screen_rgb))
    def test_screen_navigation_never_starts_capture(self):
        w=self.window();w.master.modes['Screen'].click()
        self.assertEqual(w.c.state.page,'Screen');self.assertFalse(w.screen_runtime.busy)
    def test_ledble_screen_uses_existing_selected_worker(self):
        from studio_qt import corner_worker
        from studio_qt.device_families import LEDBLE
        from test_corner_live import FakeLamp
        with patch.object(corner_worker,'LEDBLEDriver',FakeLamp):
            w=self.window();w.family_selector.setCurrentText(LEDBLE);self.f.f.corner.connect(w.c.adapter)
            worker=w.c.adapter.session.worker;self.start(w,'Gaming')
            self.wait(lambda:any(c[0]=='rgb' for c in worker.lamp.calls))
            self.assertIs(w.c.adapter.session.worker,worker);self.assertEqual(worker.device_family,LEDBLE)
            self.assertEqual(len(self.f.f.corner.workers),1)
            w.stop_screen();w.close();self.wait(lambda:w._cleanup_done and not w.screen_runtime.busy)
    def test_close_cancels_pending_transition_before_next_capture(self):
        w=self.window();w.start_music();self.wait(lambda:w.c.adapter.music_active)
        w.start_screen('Movie');w.close()
        self.wait(lambda:w._cleanup_done and not w.runtime.busy and not w.screen_runtime.busy)
        self.assertIsNone(w._pending_screen_mode);self.assertFalse(w.screen_runtime.wanted)

    def test_stale_output_cannot_hold_ownership(self):
        w=self.window();self.start(w);Capture.delay=.3
        # Drop the latest mailbox value and simulate an expired display snapshot.
        w.screen_runtime.take();w._last_screen_frame=(w.c.adapter.screen_rgb,'Movie',time.monotonic()-2)
        with w.screen_runtime.lock:w.screen_runtime.frame=None
        with patch.object(w.screen_runtime,'take',return_value=(None,'', '', True)):w.poll_screen()
        self.assertFalse(w.c.adapter.screen_active);self.assertIn('stale',w.screen_status.text());self.assertIsNone(w.screen_preview.virtual_rgb)


if __name__=='__main__':unittest.main()
