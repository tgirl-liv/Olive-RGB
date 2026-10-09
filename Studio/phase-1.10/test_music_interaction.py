"""Real Qt input during LIVE capture; media/audio/devices are simulated."""
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import Qt,QTimer,QPoint
from PySide6.QtTest import QTest
import test_album_lighting as fixtures
from studio_qt.music_runtime import preset_colors,validated_response,MusicRuntime


class MusicInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.AlbumUITests.setUpClass()
    def setUp(self):
        self.f=fixtures.AlbumUITests();self.f.setUp()
    def tearDown(self):self.f.tearDown()

    def select_last(self,w,combo):
        w.pages.widget(1).ensureWidgetVisible(combo)
        self.assertTrue(combo.isEnabled());combo.setFocus()
        QTest.mouseClick(combo,Qt.MouseButton.LeftButton,pos=QPoint(combo.width()-12,combo.height()//2))
        self.assertTrue(combo.view().isVisible())
        QTest.keyClick(combo.view(),Qt.Key.Key_End);QTest.keyClick(combo.view(),Qt.Key.Key_Return)
        self.assertEqual(combo.currentIndex(),combo.count()-1)

    def nudge(self,w,slider):
        w.pages.widget(1).ensureWidgetVisible(slider)
        self.assertTrue(slider.isEnabled());old=slider.value();slider.setFocus()
        QTest.keyClick(slider,Qt.Key.Key_Right);self.assertEqual(slider.value(),old+1)

    def exercise(self,source):
        w=self.f.window();w.c.navigate('Music')
        if source=='Album artwork':
            worker=self.f.select_album(w);worker.publish(colors=fixtures.COLORS);w.album.poll()
        w.music_start.click();self.f.f.wait(lambda:w.runtime.engine is not None and w.album.virtual_rgb is not None)
        engine=w.runtime.engine;thread=engine.thread;heartbeat=[]
        timer=QTimer(w);timer.setInterval(10);timer.timeout.connect(lambda:heartbeat.append(1));timer.start()
        self.select_last(w,w.profile);self.select_last(w,w.palette)
        self.nudge(w,w.sensitivity);self.nudge(w,w.smoothing)
        self.select_last(w,w.harmony);self.nudge(w,w.separation)
        self.f.f.wait(lambda:engine.profile_name=='MGK' and engine.user_sensitivity==1.01 and engine.user_smoothing==1.01)
        QTest.qWait(80);timer.stop();self.assertGreaterEqual(len(heartbeat),3)
        self.assertEqual(w.c.adapter.router.relationship,'Same Color');self.assertEqual(w.c.adapter.router.separation,.26)
        self.assertEqual(w.inspector.live_music.relationship.currentText(),'Same Color')
        self.assertEqual(w.inspector.live_music.separation.value(),26)
        self.assertTrue(w.inspector.live_music.relationship.isEnabled())
        self.assertEqual(len(self.f.f.engines),1);self.assertIs(w.runtime.engine,engine);self.assertIs(engine.thread,thread)
        if source=='Preset':self.assertEqual(engine.colors,preset_colors(w.palette.currentText()))
        else:
            self.assertEqual(engine.colors,fixtures.COLORS)
            worker.publish(kind='fallback');w.album.poll()
            self.assertEqual(engine.colors,preset_colors(w.palette.currentText()))
        w.stop_music();self.f.f.wait(lambda:not w.runtime.busy)

    def test_real_input_in_preset_mode_updates_existing_capture(self):self.exercise('Preset')
    def test_real_input_in_album_mode_updates_existing_capture_and_fallback(self):self.exercise('Album artwork')

    def test_pending_audio_read_does_not_block_gui_and_profile_reset_is_on_capture_thread(self):
        import numpy as np
        from studio_qt import music_engine as production
        from studio_qt.spectrum_engine import SpectrumMusicEngine
        w=self.f.window();w.c.navigate('Music');entered=threading.Event();release=threading.Event()
        profile_threads=[];recorders=[]
        class Engine(SpectrumMusicEngine):
            def set_profile(self,name):
                profile_threads.append(threading.get_ident());super().set_profile(name)
        w.runtime.factory=lambda *args:Engine(*args)
        class Recorder:
            def __enter__(self):recorders.append(self);return self
            def __exit__(self,*args):pass
            def record(self,numframes):
                entered.set();release.wait(2)
                mono=np.sin(np.arange(numframes)*2*np.pi*1000/48000)*.1
                return np.column_stack([mono,mono])
        audio=SimpleNamespace(default_speaker=lambda:SimpleNamespace(name='Mock output'),get_microphone=lambda *a,**k:SimpleNamespace(recorder=lambda **k:Recorder()))
        heartbeat=[];timer=QTimer(w);timer.setInterval(10);timer.timeout.connect(lambda:heartbeat.append(1))
        with patch.object(production,'sc',audio):
            w.start_music()
            try:
                self.assertTrue(entered.wait(1));engine=w.runtime.engine;thread=engine.thread
                timer.start();self.select_last(w,w.profile);self.nudge(w,w.sensitivity);self.nudge(w,w.smoothing)
                QTest.qWait(100);self.assertGreaterEqual(len(heartbeat),5)
                release.set();self.f.f.wait(lambda:(engine.profile_name,engine.user_sensitivity,engine.user_smoothing)==('MGK',1.01,1.01))
                self.assertEqual(profile_threads[-1],thread.ident);self.assertNotIn(threading.get_ident(),profile_threads)
                self.assertEqual(len(recorders),1);self.assertIs(w.runtime.engine,engine);self.assertIs(engine.thread,thread)
                self.assertEqual((engine.user_sensitivity,engine.user_smoothing),(1.01,1.01))
                self.f.f.wait(lambda:w.reactor.spectrum_frame is not None and w.album.virtual_rgb is not None)
            finally:
                release.set();timer.stop();w.stop_music();self.f.f.wait(lambda:not w.runtime.busy)

    def test_response_updates_during_initialization_are_latest_only(self):
        w=self.f.window();entered=threading.Event();release=threading.Event();factory=w.runtime.factory
        def opening(*args):entered.set();release.wait(2);return factory(*args)
        w.runtime.factory=opening;w.start_music()
        try:
            self.assertTrue(entered.wait(1))
            w.profile.setCurrentText('Smooth');w.sensitivity.setValue(75)
            w.profile.setCurrentText('Hyperpop');w.smoothing.setValue(110)
        finally:release.set()
        self.f.f.wait(lambda:w.runtime.engine is not None)
        self.assertEqual((w.runtime.engine.profile_name,w.runtime.engine.user_sensitivity,w.runtime.engine.user_smoothing),('Hyperpop',.75,1.1))

    def test_response_validation_preserves_pending_configuration(self):
        runtime=MusicRuntime();runtime.set_response('Reactive',1.,1.);original=runtime._response
        for profile,sensitivity,smoothing in (('Unknown',1,1),('Smooth',float('nan'),1),('Smooth',True,1),('Smooth',1,2)):
            with self.assertRaises(ValueError):runtime.set_response(profile,sensitivity,smoothing)
            self.assertEqual(runtime._response,original)
        self.assertEqual(validated_response('MGK',.25,1.4),('MGK',.25,1.4))


if __name__=='__main__':unittest.main()
