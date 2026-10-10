"""Preserved screen math and Studio lifecycle with simulated screen/device I/O."""
import ast
import threading
import time
import tempfile
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from PySide6.QtCore import Qt
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
    def setUp(self):self.patch=patch('mss.MSS',Capture);self.patch.start();Capture.rgb=(200,50,25);Capture.delay=0;Capture.calls=[]
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
        self.patch=patch('mss.MSS',Capture);self.patch.start();self.runtimes=[]
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
        self.patch=patch('mss.MSS',Capture);self.patch.start()
    def tearDown(self):
        try:
            for w in self.windows:w.close()
            self.wait(lambda:all(not w.screen_runtime.busy and not w.screen_runtime.scanning for w in self.windows))
            self.f.tearDown()
        finally:self.patch.stop()
    def wait(self,predicate):self.f.wait(predicate)
    def window(self,**kwargs):
        w=ScreenLiveWindow(worker_factory=self.f.f.corner.factory,hue_factory=self.f.f.hue_factory,hue_identity={'name':'Tv lamp'},engine_factory=kwargs.pop('engine_factory',self.f.factory),**kwargs)
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
            values=PreferencesStore(path).load('live')['screen'];self.assertEqual(values,{'capture_mode':'Movie','monitor':2,'intensity':1.5,'saturation':2.})
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
        w=self.window();w.c.navigate('Screen')
        self.assertEqual(w.c.state.page,'Screen');self.assertFalse(w.screen_runtime.busy)
    def test_actual_selector_manual_music_screen_manual_releases_ownership(self):
        from PySide6.QtCore import Qt
        w=self.window();a=w.c.adapter
        self.f.f.corner.connect(a)
        # Exercise physical Qt clicks in the dashboard rather than calling slots.
        QTest.mouseClick(w.master.modes['Manual'],Qt.MouseButton.LeftButton)
        self.assertEqual(w.c.state.mode,'Manual');self.assertTrue(w.master.modes['Manual'].isChecked())
        QTest.mouseClick(w.master.modes['Music'],Qt.MouseButton.LeftButton)
        self.wait(lambda:a.last_frame is not None);self.assertTrue(a.owns('Corner'))
        QTest.mouseClick(w.master.modes['Screen'],Qt.MouseButton.LeftButton)
        self.assertEqual(w.c.state.page,'Screen');self.assertEqual(w.c.state.mode,'Manual')
        self.assertFalse(a.music_active)
        self.wait(lambda:a.screen_active and w.screen_preview.virtual_rgb is not None)
        self.assertTrue(a.owns('Corner'));self.assertIsNone(w._pending_screen_mode)
        self.assertTrue(w.movie_start.isVisible());self.assertTrue(w.gaming_start.isVisible())
        self.assertTrue(w.master.modes['Screen'].isChecked())
        self.assertFalse(w.master.modes['Music'].isChecked());self.assertFalse(w.master.modes['Manual'].isChecked())
        self.wait(lambda:not w.runtime.busy);w.c.changed.emit();w.live_controls()
        self.assertEqual(w.c.state.mode,'Movie');self.assertTrue(w.master.modes['Screen'].isChecked())
        # The bus is on the Studio page. Returning there must preserve selection.
        w.nav['Studio'].click();self.assertTrue(w.master.modes['Screen'].isChecked())
        QTest.mouseClick(w.master.modes['Manual'],Qt.MouseButton.LeftButton)
        self.assertEqual(w.c.state.mode,'Manual');self.assertTrue(w.master.modes['Manual'].isChecked())
        self.assertFalse(w.master.modes['Screen'].isChecked());self.assertFalse(a.owns('Corner'))
        self.assertEqual(len(self.f.f.corner.workers),1)

    def test_selector_styling_tracks_movie_gaming_and_reopens_active_screen(self):
        from PySide6.QtCore import Qt
        w=self.window()
        for mode in ('Movie','Gaming'):
            self.start(w,mode);w.c.changed.emit();w.live_controls()
            self.assertTrue(w.master.modes['Screen'].isChecked())
            self.assertFalse(w.master.modes['Manual'].isChecked());self.assertFalse(w.master.modes['Music'].isChecked())
            thread=w.screen_runtime.thread;w.nav['Studio'].click()
            QTest.mouseClick(w.master.modes['Screen'],Qt.MouseButton.LeftButton)
            self.assertEqual(w.c.state.page,'Screen');self.assertEqual(w.c.state.mode,mode)
            self.assertIs(w.screen_runtime.thread,thread);self.assertTrue(w.c.adapter.screen_active)
        w.nav['Studio'].click();QTest.mouseClick(w.master.modes['Manual'],Qt.MouseButton.LeftButton)
        self.wait(lambda:not w.screen_runtime.busy);self.assertTrue(w.master.modes['Manual'].isChecked())
        self.assertFalse(w.master.modes['Screen'].isChecked());self.assertFalse(w.c.adapter.screen_active)

    def test_screen_selector_starts_saved_capture_without_connections(self):
        w=self.window();w.master.modes['Screen'].click()
        self.wait(lambda:w.screen_preview.virtual_rgb is not None)
        self.assertEqual(w.c.state.mode,'Movie');self.assertEqual(w.c.state.page,'Screen')
        self.assertFalse(w.runtime.busy);self.assertFalse(self.f.f.corner.workers)
        self.assertIsNone(w.c.adapter.hue.thread)
        thread=w.screen_runtime.thread
        for _ in range(5):w.c.set('mode','Screen');w.poll_screen()
        self.assertIs(w.screen_runtime.thread,thread)
        self.assertTrue(w.master.modes['Screen'].isChecked())

    def test_latest_request_wins_and_manual_cancels_queued_capture(self):
        w=self.window();w.start_screen('Movie');w.c.set('mode','Music');w.c.set('mode','Screen')
        self.assertEqual(w._pending_screen_mode,'Movie');self.assertFalse(w._pending_music)
        w.c.set('mode','Manual');w.poll_screen()
        self.assertIsNone(w._pending_screen_mode);self.wait(lambda:not w.screen_runtime.busy)
        self.assertFalse(w.screen_runtime.wanted)
        self.assertEqual(w.c.state.mode,'Manual');self.assertTrue(w.master.modes['Manual'].isChecked())

    def test_stopped_music_error_does_not_cancel_screen_activation(self):
        w=self.window();w.master.modes['Screen'].click()
        w.runtime.error='Audio error: late stopped capture failure';w.poll_music()
        self.wait(lambda:w.screen_preview.virtual_rgb is not None)
        self.assertEqual(w.c.state.mode,'Movie');self.assertTrue(w.master.modes['Screen'].isChecked())
        self.assertFalse(w.c.adapter.music_active)

    def test_music_reselection_is_idempotent_and_manual_stops_capture(self):
        w=self.window();w.master.modes['Music'].click()
        self.wait(lambda:w.c.adapter.last_frame is not None)
        thread=w.runtime.thread;count=len(self.f.engines)
        for _ in range(5):w.master.modes['Music'].click();w.poll_screen()
        self.assertIs(w.runtime.thread,thread);self.assertEqual(len(self.f.engines),count)
        self.assertTrue(w.master.modes['Music'].isChecked())
        w.master.modes['Manual'].click();self.wait(lambda:not w.runtime.busy)
        self.assertFalse(w.c.adapter.music_active);self.assertTrue(w.master.modes['Manual'].isChecked())
        self.assertFalse(self.f.f.corner.workers)

    def test_music_activation_failure_restores_safe_selector(self):
        def fail(*args):raise OSError('audio unavailable')
        w=self.window();w.runtime.factory=fail;QTest.mouseClick(w.master.modes['Music'],Qt.MouseButton.LeftButton)
        self.wait(lambda:'audio unavailable' in w.music_status.text())
        self.assertEqual(w.c.state.mode,'Manual');self.assertTrue(w.master.modes['Manual'].isChecked())
        self.assertFalse(w.c.adapter.music_active);self.assertFalse(w.c.adapter.screen_active)
        self.assertIn('Error',w.mode_badge.text());self.assertIn('audio unavailable',w.mode_badge.toolTip())
        self.assertNotIn('Active',w.master.modes['Music'].text())

    def test_screen_activation_failure_restores_safe_selector(self):
        def fail(*args):raise OSError('screen denied')
        w=self.window(screen_factory=fail);QTest.mouseClick(w.master.modes['Screen'],Qt.MouseButton.LeftButton)
        self.wait(lambda:'screen denied' in w.screen_status.text())
        self.assertEqual(w.c.state.mode,'Manual');self.assertTrue(w.master.modes['Manual'].isChecked())
        self.assertFalse(w.master.modes['Screen'].isChecked());self.assertFalse(self.f.f.corner.workers)
        self.assertIn('Error',w.mode_badge.text());self.assertIn('screen denied',w.mode_badge.toolTip())
        self.assertNotIn('Active',w.master.modes['Screen'].text())

    def test_saved_gaming_selection_and_music_settings_activate(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'preferences-v1.json';w=self.window(preferences_path=path)
            self.start(w,'Gaming');w.stop_screen();w.profile.setCurrentText('MGK')
            w.sensitivity.setValue(125);w.smoothing.setValue(75);w.save_preferences()
            restored=self.window(preferences_path=path)
            self.assertFalse(restored.screen_runtime.busy);restored.master.modes['Screen'].click()
            self.wait(lambda:restored.screen_preview.virtual_rgb is not None)
            self.assertEqual(restored.c.state.mode,'Gaming')
            old=restored.screen_runtime.thread;restored.master.modes['Music'].click()
            self.wait(lambda:restored.c.adapter.last_frame is not None)
            self.assertFalse(old.is_alive());self.assertEqual(restored.runtime.engine.profile_name,'MGK')
            self.assertEqual(restored.runtime.engine.user_sensitivity,1.25)
            self.assertEqual(restored.runtime.engine.user_smoothing,.75)

    def test_synchronous_activation_failure_and_retry(self):
        w=self.window()
        with patch.object(w.runtime,'start',side_effect=RuntimeError('startup refused')):
            w.c.set('mode','Music');w.poll_screen()
        self.assertIn('startup refused',w.music_status.text())
        self.assertEqual(w.c.state.mode,'Manual');self.assertTrue(w.master.modes['Manual'].isChecked())
        w.c.set('mode','Music');self.wait(lambda:w.c.adapter.last_frame is not None)
        self.assertTrue(w.c.adapter.music_active)

    def test_no_monitor_failure_and_capture_mode_validation(self):
        w=self.window();w.monitor.clear();w.screen_runtime.scan_error='Monitor discovery denied'
        w.c.set('mode','Screen');w.poll_screen()
        self.assertIn('Monitor discovery denied',w.screen_status.text())
        self.assertEqual(w.c.state.mode,'Manual');self.assertTrue(w.master.modes['Manual'].isChecked())
        with self.assertRaises(ValueError):validate({'screen':{'capture_mode':'invalid'}},'live')
        self.assertEqual(validate({'screen':{}},'live')['screen']['capture_mode'],'Movie')

    def test_music_actions_are_on_music_page_not_main_header(self):
        w=self.window();page=w.pages.widget(1).widget()
        self.assertTrue(page.isAncestorOf(w.music_start));self.assertTrue(page.isAncestorOf(w.music_stop))
        self.assertFalse(w.music_start.isVisible());w.c.navigate('Music')
        self.assertTrue(w.music_start.isVisible());self.assertTrue(w.music_stop.isVisible())

    def test_selector_production_audio_opens_one_loopback_and_delivers_fft_and_preview(self):
        from studio_qt import music_engine as production
        from studio_qt.audio_capture import LoopbackAudio
        from studio_qt.music_runtime import engine_factory
        gate=threading.Event();entered=threading.Event();opens=[];closed=[];samples={'amplitude':.15}
        class Recorder:
            def __enter__(self):opens.append(threading.get_ident());entered.set();return self
            def __exit__(self,*args):closed.append(True)
            def record(self,numframes):
                gate.wait(2)
                mono=np.sin(np.arange(numframes)*2*np.pi*1000/48000)*samples['amplitude']
                return np.column_stack([mono,mono])
        loopback=SimpleNamespace(id='playback-id',name='Windows test output',isloopback=True,recorder=lambda **kwargs:Recorder())
        wrong=SimpleNamespace(id='mic-id',name='Windows test output',isloopback=False)
        backend=SimpleNamespace(default_speaker=lambda:SimpleNamespace(id='playback-id',name='Windows test output'),
            all_microphones=lambda **kwargs:[wrong,loopback],get_microphone=lambda *args,**kwargs:wrong)
        with patch.object(production,'sc',LoopbackAudio(backend)):
            w=self.window(engine_factory=engine_factory)
            try:
                QTest.mouseClick(w.master.modes['Music'],Qt.MouseButton.LeftButton);self.wait(entered.is_set)
                self.assertFalse(w.c.adapter.music_active);self.assertEqual(w.c.state.mode,'Manual')
                self.assertEqual(w.c.state.page,'Studio')
                self.assertTrue(w.music_timer.isActive())
                self.assertIn('Starting',w.master.modes['Music'].text())
                self.assertFalse(w.master.modes['Music'].isChecked())
                self.assertIsNone(w.c.adapter.last_frame)
                for _ in range(4):w.master.modes['Music'].click()
                gate.set();self.wait(lambda:w.reactor.spectrum_frame is not None and max(w.reactor.levels)>.1)
                self.assertTrue(w.c.adapter.music_active);self.assertEqual(w.c.state.mode,'Music')
                self.assertIn('Active',w.master.modes['Music'].text())
                self.assertEqual(len(w.reactor.spectrum_frame.magnitudes),72)
                self.assertIsNotNone(w.album.virtual_rgb);self.assertEqual(w.album.virtual_rgb,w.c.adapter.corner_music_rgb(w.c.adapter.music_colors['Corner']))
                self.assertEqual(len(opens),1);self.assertNotEqual(opens[0],threading.get_ident())
                self.assertIn('Windows test output',w.music_status.text())
                samples['amplitude']=0;self.wait(lambda:'capture running · silence' in w.music_status.text())
                self.assertTrue(w.c.adapter.music_active);self.assertEqual(w.c.adapter.last_frame.energy,0)
                audio_thread=w.runtime.thread;QTest.mouseClick(w.master.modes['Screen'],Qt.MouseButton.LeftButton)
                self.wait(lambda:w.screen_preview.virtual_rgb is not None)
                self.assertFalse(audio_thread.is_alive());self.assertEqual(closed,[True])
                screen_thread=w.screen_runtime.thread;samples['amplitude']=.15
                w.nav['Studio'].click();QTest.mouseClick(w.master.modes['Music'],Qt.MouseButton.LeftButton)
                self.wait(lambda:w.reactor.spectrum_frame is not None and w.c.adapter.music_active)
                self.assertFalse(screen_thread.is_alive());self.assertEqual(len(opens),2)
                w.master.modes['Manual'].click();self.wait(lambda:not w.runtime.busy)
                self.assertEqual(closed,[True,True]);self.assertFalse(self.f.f.corner.workers);self.assertIsNone(w.c.adapter.hue.thread)
            finally:gate.set();w.stop_music();self.wait(lambda:not w.runtime.busy)

    def test_selector_real_audio_reports_missing_default_device(self):
        from studio_qt import music_engine as production
        from studio_qt.audio_capture import LoopbackAudio
        from studio_qt.music_runtime import engine_factory
        backend=SimpleNamespace(default_speaker=lambda:None)
        with patch.object(production,'sc',LoopbackAudio(backend)):
            w=self.window(engine_factory=engine_factory);w.master.modes['Music'].click()
            self.wait(lambda:'No valid default audio output device' in w.music_status.text())
            self.assertFalse(w.c.adapter.music_active);self.assertEqual(w.c.state.mode,'Manual')
            self.assertTrue(w.master.modes['Manual'].isChecked());self.assertFalse(self.f.f.corner.workers)

    def test_selector_production_recorder_open_failure_reports_actual_error(self):
        from studio_qt import music_engine as production
        from studio_qt.audio_capture import LoopbackAudio
        from studio_qt.music_runtime import engine_factory
        class DeniedRecorder:
            def __enter__(self):raise OSError('WASAPI endpoint access denied')
            def __exit__(self,*args):pass
        loopback=SimpleNamespace(id='speaker-id',isloopback=True,recorder=lambda **kwargs:DeniedRecorder())
        backend=SimpleNamespace(default_speaker=lambda:SimpleNamespace(id='speaker-id',name='Default output'),
            all_microphones=lambda **kwargs:[loopback])
        with patch.object(production,'sc',LoopbackAudio(backend)):
            w=self.window(engine_factory=engine_factory);w.master.modes['Music'].click()
            self.wait(lambda:'WASAPI endpoint access denied' in w.music_status.text())
            self.assertFalse(w.c.adapter.music_active);self.assertEqual(w.c.state.mode,'Manual')
            self.assertTrue(w.master.modes['Manual'].isChecked());self.assertIsNone(w.album.virtual_rgb)

    def test_selector_production_screen_open_failure_reports_actual_error(self):
        w=self.window()
        with patch('mss.MSS',side_effect=PermissionError('Desktop capture denied')):
            w.master.modes['Screen'].click()
            self.wait(lambda:'Desktop capture denied' in w.screen_status.text())
            self.assertFalse(w.c.adapter.screen_active);self.assertEqual(w.c.state.mode,'Manual')
            self.assertTrue(w.master.modes['Manual'].isChecked());self.assertIsNone(w.screen_preview.virtual_rgb)

    def test_loopback_resolution_rejects_microphones_and_preserves_device_errors(self):
        from studio_qt.audio_capture import LoopbackAudio
        speaker=SimpleNamespace(name='Output',id='endpoint')
        backend=SimpleNamespace(default_speaker=lambda:speaker,all_microphones=lambda **kwargs:[],
            get_microphone=lambda *args,**kwargs:SimpleNamespace(isloopback=False))
        audio=LoopbackAudio(backend);audio.default_speaker()
        with patch('studio_qt.audio_capture.sys.platform','linux'):
            with self.assertRaisesRegex(RuntimeError,'physical microphone'):audio.get_microphone('Output',True)
            backend.get_microphone=lambda *args,**kwargs:(_ for _ in ()).throw(OSError('device unplugged'))
            with self.assertRaisesRegex(RuntimeError,'endpoint.*device unplugged'):audio.get_microphone('Output',True)
        with patch('studio_qt.audio_capture.sys.platform','win32'):
            with self.assertRaisesRegex(RuntimeError,'No enabled loopback matches.*endpoint'):audio.get_microphone('Output',True)

    def test_real_screen_selector_waits_for_capture_and_tracks_changed_pixels(self):
        Capture.delay=.2;w=self.window();QTest.mouseClick(w.master.modes['Screen'],Qt.MouseButton.LeftButton)
        self.wait(lambda:any(call[0]=='grab' for call in Capture.calls))
        self.assertFalse(w.c.adapter.screen_active);self.assertEqual(w.c.state.mode,'Manual')
        self.assertIn('Starting',w.master.modes['Screen'].text())
        self.assertFalse(w.master.modes['Screen'].isChecked());self.assertTrue(w.screen_timer.isActive())
        self.wait(lambda:w.screen_preview.virtual_rgb is not None)
        self.assertTrue(w.c.adapter.screen_active);self.assertEqual(w.c.state.mode,'Movie')
        self.assertIn('Active',w.master.modes['Screen'].text())
        old=w.screen_preview.virtual_rgb;Capture.rgb=(20,220,35)
        self.wait(lambda:w.screen_preview.virtual_rgb!=old)
        self.assertEqual(w.screen_preview.virtual_rgb,w.c.adapter.corner_music_rgb(w.c.adapter.screen_rgb))
        thread=w.screen_runtime.thread
        for _ in range(4):w.master.modes['Screen'].click();w.poll_screen()
        self.assertIs(w.screen_runtime.thread,thread)
        self.assertEqual(sum(call[0]=='open' for call in Capture.calls),2)  # discovery + one capture
        self.assertFalse(self.f.f.corner.workers);self.assertIsNone(w.c.adapter.hue.thread)
        w.master.modes['Manual'].click();self.wait(lambda:not w.screen_runtime.busy)
        self.assertFalse(w.c.adapter.screen_active)

    def test_audio_startup_timeout_stops_worker_and_restores_manual(self):
        gate=threading.Event();entered=threading.Event()
        original=self.f.factory
        def factory(*args):
            engine=original(*args)
            def start():
                engine.running=True
                def run():entered.set();gate.wait(2)
                engine.thread=threading.Thread(target=run);engine.thread.start()
            engine.start=start;return engine
        w=self.window(engine_factory=factory)
        try:
            w.master.modes['Music'].click();self.wait(entered.is_set)
            w.runtime.started_at=time.monotonic()-6;w.poll_music()
            self.assertIn('Audio startup timed out',w.music_status.text())
            self.assertFalse(w.runtime.wanted);self.assertFalse(w.c.adapter.music_active)
            self.assertEqual(w.c.state.mode,'Manual');self.assertTrue(w.master.modes['Manual'].isChecked())
        finally:gate.set();self.wait(lambda:not w.runtime.busy)

    def test_screen_startup_timeout_returns_manual_and_cancels_capture(self):
        Capture.delay=.25;w=self.window();w.master.modes['Screen'].click()
        self.wait(lambda:any(call[0]=='grab' for call in Capture.calls))
        w.screen_runtime.started_at=time.monotonic()-6;w.poll_screen()
        self.assertIn('Screen startup timed out',w.screen_status.text())
        self.assertFalse(w.screen_runtime.wanted);self.assertFalse(w.c.adapter.screen_active)
        self.assertEqual(w.c.state.mode,'Manual');self.assertTrue(w.master.modes['Manual'].isChecked())
        self.wait(lambda:not w.screen_runtime.busy)

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


class ScreenLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.MusicTests.setUpClass()

    def test_launched_master_buttons_start_production_capture_and_previews(self):
        """Click the launcher's real widgets; mock only native inputs, not runtimes."""
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication,QDialog,QRadioButton
        from studio_qt import app as launcher,music_engine as production
        from studio_qt.audio_capture import LoopbackAudio
        app=QApplication.instance();errors=[];windows=[];stage=0
        gate=threading.Event();entered=threading.Event();opens=[];closed=[]
        class Recorder:
            def __enter__(self):opens.append(threading.get_ident());entered.set();return self
            def __exit__(self,*args):closed.append(True)
            def record(self,numframes):
                gate.wait(2);time.sleep(.01)
                mono=.15*np.sin(np.arange(numframes)*2*np.pi*1000/48000)
                return np.column_stack([mono,mono])
        loopback=SimpleNamespace(id='test-output',name='Test playback',isloopback=True,recorder=lambda **kwargs:Recorder())
        backend=SimpleNamespace(default_speaker=lambda:loopback,all_microphones=lambda **kwargs:[loopback])
        def drive():
            nonlocal stage
            try:
                for dialog in app.topLevelWidgets():
                    if isinstance(dialog,QDialog) and 'startup mode' in dialog.windowTitle():
                        for radio in dialog.findChildren(QRadioButton):
                            if radio.text().startswith('LIVE'):radio.setChecked(True)
                        dialog.accept();return
                for w in app.topLevelWidgets():
                    if not isinstance(w,ScreenLiveWindow):continue
                    if w not in windows:windows.append(w)
                    if stage==0 and w.isVisible() and w.monitor.count():
                        self.assertEqual(w.c.state.page,'Studio')
                        self.assertTrue(w.master.modes['Music'].isVisible())
                        QTest.mouseClick(w.master.modes['Music'],Qt.MouseButton.LeftButton);stage=1
                    elif stage==1 and entered.is_set():
                        self.assertTrue(w.music_timer.isActive());self.assertFalse(w.c.adapter.music_active)
                        self.assertIn('Starting',w.master.modes['Music'].text())
                        self.assertEqual(w.c.state.mode,'Manual')
                        for _ in range(3):QTest.mouseClick(w.master.modes['Music'],Qt.MouseButton.LeftButton)
                        gate.set();stage=2
                    elif stage==2 and w.reactor.spectrum_frame is not None and w.album.virtual_rgb is not None:
                        self.assertEqual(len(opens),1);self.assertEqual(w.c.state.page,'Studio')
                        self.assertEqual(w.c.state.mode,'Music');self.assertGreater(w.c.adapter.last_frame.energy,0)
                        self.assertEqual(len(w.reactor.spectrum_frame.magnitudes),72)
                        self.assertEqual(w.album.virtual_rgb,w.c.adapter.corner_music_rgb(w.c.adapter.music_colors['Corner']))
                        self.assertIn('Active',w.master.modes['Music'].text())
                        QTest.mouseClick(w.master.modes['Screen'],Qt.MouseButton.LeftButton);stage=3
                    elif stage==3 and w.screen_preview.virtual_rgb is not None:
                        self.assertEqual(closed,[True]);self.assertFalse(w.runtime.busy)
                        self.assertEqual(w.c.state.mode,'Movie');self.assertIn('Active',w.master.modes['Screen'].text())
                        self.assertEqual(w.screen_preview.virtual_rgb,w.c.adapter.corner_music_rgb(w.c.adapter.screen_rgb))
                        self.assertIsNone(w.c.adapter.session.worker);self.assertIsNone(w.c.adapter.hue.thread)
                        w.nav['Studio'].click();QTest.mouseClick(w.master.modes['Manual'],Qt.MouseButton.LeftButton);stage=4
                    elif stage==4 and not w.screen_runtime.busy:
                        self.assertEqual(w.c.state.mode,'Manual');self.assertFalse(w.c.adapter.screen_active)
                        w.close();stage=5
                    elif stage==5 and w._cleanup_done and not w.isVisible():app.quit()
            except BaseException as error:errors.append(error);app.exit(1)
        timer=QTimer();timer.timeout.connect(drive);timer.start(25)
        watchdog=QTimer();watchdog.setSingleShot(True)
        watchdog.timeout.connect(lambda:(errors.append(AssertionError('Launched main mode buttons timed out')),app.exit(1)));watchdog.start(12000)
        Capture.calls=[];Capture.delay=0
        try:
            with tempfile.TemporaryDirectory() as directory,patch('mss.MSS',Capture),patch.object(production,'sc',LoopbackAudio(backend)),patch.object(launcher,'default_path',return_value=Path(directory)/'workspace.json'),patch.object(launcher,'preferences_path_default',return_value=Path(directory)/'preferences-v1.json'):
                result=launcher.main()
            self.assertFalse(errors,str(errors));self.assertEqual(result,0);self.assertEqual(stage,5)
            self.assertEqual(len(windows),1);self.assertNotEqual(opens[0],threading.get_ident())
        finally:
            gate.set();timer.stop();watchdog.stop()
            for w in windows:w.close()
            deadline=time.monotonic()+3
            while any(w.runtime.busy or w.screen_runtime.busy or not w._cleanup_done for w in windows) and time.monotonic()<deadline:app.processEvents();QTest.qWait(10)
            for w in windows:w.deleteLater()

    def test_actual_live_launcher_screen_navigation_exposes_controls(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication,QDialog,QRadioButton
        from studio_qt import app as launcher
        app=QApplication.instance();errors=[];windows=[];stage=0
        def drive():
            nonlocal stage
            try:
                for dialog in app.topLevelWidgets():
                    if isinstance(dialog,QDialog) and 'startup mode' in dialog.windowTitle():
                        for radio in dialog.findChildren(QRadioButton):
                            if radio.text().startswith('LIVE'):radio.setChecked(True)
                        dialog.accept();return
                for w in app.topLevelWidgets():
                    if not isinstance(w,ScreenLiveWindow):continue
                    if w not in windows:windows.append(w)
                    if stage==0 and w.isVisible() and w.monitor.count():
                        w.nav['Screen'].click();app.processEvents()
                        self.assertEqual(w.c.state.page,'Screen')
                        self.assertTrue(w.movie_start.isVisible())
                        self.assertTrue(w.gaming_start.isVisible())
                        self.assertTrue(w.screen_intensity.isVisible())
                        self.assertTrue(w.screen_saturation.isVisible())
                        self.assertTrue(w.screen_preview.isVisible())
                        self.assertIs(w.pages.currentWidget().widget(),w.movie_start.parentWidget().parentWidget())
                        self.assertFalse(w.screen_runtime.busy)
                        w.movie_start.click();stage=1
                    elif stage==1 and w.screen_preview.virtual_rgb is not None:
                        self.assertEqual(w.c.state.mode,'Movie');w.gaming_start.click();stage=2
                    elif stage==2 and w.screen_runtime.engine and w.screen_runtime.engine.mode=='Gaming' and w.screen_preview.virtual_rgb is not None:
                        self.assertEqual(w.c.state.mode,'Gaming')
                        self.assertIsNone(w.c.adapter.session.worker)
                        self.assertIsNone(w.c.adapter.hue.thread)
                        self.assertFalse(w.runtime.busy)
                        w.screen_stop.click();w.close();stage=3
                    elif stage==3 and w._cleanup_done and not w.screen_runtime.busy and not w.isVisible():app.quit()
            except BaseException as error:errors.append(error);app.exit(1)
        def timeout():errors.append(AssertionError('Launcher Screen navigation timed out'));app.exit(1)
        timer=QTimer();timer.timeout.connect(drive);timer.start(25)
        watchdog=QTimer();watchdog.setSingleShot(True);watchdog.timeout.connect(timeout);watchdog.start(10000)
        Capture.calls=[];Capture.delay=0
        try:
            with tempfile.TemporaryDirectory() as directory,patch('mss.MSS',Capture),patch.object(launcher,'default_path',return_value=Path(directory)/'workspace.json'),patch.object(launcher,'preferences_path_default',return_value=Path(directory)/'preferences-v1.json'):
                result=launcher.main()
            self.assertFalse(errors,str(errors));self.assertEqual(result,0);self.assertEqual(stage,3);self.assertEqual(len(windows),1)
        finally:
            timer.stop();watchdog.stop()
            for w in windows:w.close()
            deadline=time.monotonic()+3
            while any(w.screen_runtime.busy or not w._cleanup_done for w in windows) and time.monotonic()<deadline:app.processEvents();QTest.qWait(10)
            for w in windows:w.deleteLater()


if __name__=='__main__':unittest.main()
