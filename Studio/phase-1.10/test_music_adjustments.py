"""Output parity and Qt interaction; all audio and devices are simulated."""
import ast
import copy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton
import test_album_lighting as fixtures
from music_coordination import MusicFrame
from studio_qt.music_adjustments import adjust_music_rgb,adjusted_frame,validated_adjustments
from studio_qt.music_themes import ThemeStore
from studio_qt.music_runtime import engine_factory
from studio_qt.music_window import MusicLiveWindow
from studio_qt.preferences import defaults,validate,PreferencesStore


class AdjustmentMathTests(unittest.TestCase):
    def test_original_tkinter_math_is_preserved(self):
        def function(path):
            return next(node for node in ast.parse(path.read_text()).body if isinstance(node,ast.FunctionDef) and node.name=='adjust_music_rgb')
        source=Path(__file__).parent
        self.assertEqual(ast.dump(function(source/'olive_rgb.py')),ast.dump(function(source/'studio_qt/music_adjustments.py')))

    def test_identity_grayscale_black_and_original_rounding(self):
        for rgb in ((0,0,0),(255,0,70),(100,50,25),(1,2,3),(255,255,255),(42,179,244)):
            self.assertEqual(adjust_music_rgb(rgb,1,1),rgb)
            self.assertEqual(adjust_music_rgb(rgb,1,0),(max(rgb),)*3)
            self.assertEqual(adjust_music_rgb(rgb,0,.7),(0,0,0))
        self.assertEqual(adjust_music_rgb((100,50,25),.5,.5),(50,38,31))

    def test_copy_retains_all_analysis_fields_and_original(self):
        frame=MusicFrame((100,50,25),.6,.3,.1,.04,True,time.monotonic())
        adjusted=adjusted_frame(frame,.5,0)
        self.assertIsNot(adjusted,frame);self.assertEqual(adjusted.rgb,(50,50,50))
        self.assertEqual(replace(adjusted,rgb=frame.rgb),frame);self.assertEqual(frame.rgb,(100,50,25))

    def test_validation(self):
        for value in (-.1,1.1,True,None,'1',float('nan'),float('inf')):
            for pair in ((value,1),(1,value)):
                with self.assertRaises(ValueError):validated_adjustments(*pair)
        self.assertEqual(validated_adjustments(0,1),(0.,1.))

    def test_backward_compatible_persistence_and_invalid_preferences(self):
        music=defaults('live');del music['music']['output_brightness'];del music['music']['output_saturation']
        self.assertEqual(validate(music,'live')['music']['output_brightness'],1.)
        self.assertEqual(validate(music,'live')['music']['output_saturation'],1.)
        self.assertNotIn('output_brightness',defaults('demo')['music'])
        for field in ('output_brightness','output_saturation'):
            for value in (-1,1.01,True,float('nan')):
                data=defaults('live');data['music'][field]=value
                with self.assertRaises(ValueError):validate(data,'live')


class AdjustmentUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.AlbumUITests.setUpClass()
    def setUp(self):self.f=fixtures.AlbumUITests();self.f.setUp()
    def tearDown(self):self.f.tearDown()
    def wait(self,predicate):self.f.f.wait(predicate)

    def test_live_input_reset_and_no_capture_restart(self):
        w=self.f.window();w.c.navigate('Music');w.start_music()
        self.wait(lambda:w.runtime.engine is not None and w.album.virtual_rgb is not None)
        engine=w.runtime.engine;thread=engine.thread
        for widget in (w.output_brightness,w.output_saturation):
            w.pages.widget(1).ensureWidgetVisible(widget);self.assertTrue(widget.isEnabled())
            widget.setFocus();QTest.keyClick(widget,Qt.Key.Key_Home);self.assertEqual(widget.value(),0)
        self.wait(lambda:w.album.virtual_rgb==(0,0,0))
        w.output_brightness.setValue(50)
        self.wait(lambda:w.c.adapter.music_colors['Corner']==(128,128,128))
        self.assertEqual(w.album.virtual_rgb,w.c.adapter.corner_music_rgb((128,128,128)))
        w.adjustment_reset.click();self.assertEqual(w.c.adapter.adjustments,(1.,1.))
        self.wait(lambda:w.c.adapter.music_colors['Corner']==(255,0,0))
        self.assertIs(w.runtime.engine,engine);self.assertIs(engine.thread,thread);self.assertEqual(len(self.f.f.engines),1)

    def test_restart_restores_preferences_but_never_capture_or_connections(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'preferences-v1.json';w=self.f.window();w.preferences_store=PreferencesStore(path)
            w.output_brightness.setValue(37);w.output_saturation.setValue(62);w.save_preferences()
            restored=MusicLiveWindow(preferences_path=path)
            try:
                self.assertEqual((restored.output_brightness.value(),restored.output_saturation.value()),(37,62))
                self.assertEqual(restored.c.adapter.adjustments,(.37,.62));self.assertFalse(restored.runtime.busy)
                self.assertFalse(restored.c.adapter.session.wanted);self.assertFalse(restored.c.adapter.hue.wanted)
                restored.adjustment_reset.click();restored.save_preferences()
                self.assertEqual(PreferencesStore(path).load('live')['music']['output_brightness'],1.)
                self.assertEqual(PreferencesStore(path).load('live')['music']['output_saturation'],1.)
            finally:restored.close()

    def test_adjust_before_coordination_then_scale_power_and_restore_manual(self):
        a=self.f.f.adapter();self.f.f.f.connect_corner(a);self.f.f.f.connect_hue(a)
        a.set_rgb('Corner','#123456');a.set_rgb('Hue','#654321');manual={k:c.color for k,c in a.state.channels.items()}
        a.set_adjustments(.5,0);a.set_master(True,.5);a.set_brightness('Corner',.5);a.set_brightness('Hue',.5);a.set_follow_master('Hue',True)
        a.start_music('Same Color');frame=MusicFrame((200,100,50),.7,.2,.1,.02,True,time.monotonic());a.apply_frame(frame)
        self.assertIs(a.last_frame,frame);self.assertEqual(a.music_colors,{'Corner':(100,100,100),'Hue':(100,100,100)})
        self.assertEqual(a.corner_music_rgb(a.music_colors['Corner']),(25,25,25));self.assertEqual(a.hue.pending['brightness'],25)
        a.set_master(False,.5);self.assertFalse(a.hue.pending['power']);self.assertEqual(a.corner_music_rgb((100,100,100)),(0,0,0))
        a.set_master(True,1);a.set_participation('Hue',False);self.assertFalse(a.owns('Hue'))
        self.assertEqual(a.hue.pending['color'],(101,67,33))
        with self.assertRaises(ValueError):a.set_rgb('Corner','#FFFFFF')
        a.stop_music();self.assertEqual({k:c.color for k,c in a.state.channels.items()},manual)
        self.assertEqual(a.session.pending[1],a.corner_music_rgb((18,52,86)))

    def test_real_engine_album_and_custom_palette_preview_and_reactor(self):
        import numpy as np
        from studio_qt import music_engine as production
        w=self.f.window();w.runtime.factory=engine_factory
        class Recorder:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def record(self,numframes):
                mono=np.sin(np.arange(numframes)*2*np.pi*100/48000)*.1
                return np.column_stack([mono,mono])
        audio=SimpleNamespace(default_speaker=lambda:SimpleNamespace(name='Mock output'),get_microphone=lambda *a,**k:SimpleNamespace(recorder=lambda **k:Recorder()))
        w.output_brightness.setValue(50);w.output_saturation.setValue(0)
        with tempfile.TemporaryDirectory() as directory,patch.object(production,'sc',audio):
            w.themes=ThemeStore(Path(directory)/'custom-music-themes-v1.json')
            identifier=w.themes.save(None,'Night',fixtures.COLORS);w.palette.addItem('Custom · Night',identifier);w.palette.setCurrentIndex(w.palette.findData(identifier))
            for source in ('Preset','Album artwork'):
                if source=='Album artwork':
                    worker=self.f.select_album(w);worker.publish(colors=dict(fixtures.COLORS,bass='#00FF00'));w.album.poll()
                colors=copy.deepcopy(w.album.current_palette);w.start_music()
                try:
                    self.wait(lambda:w.album.virtual_rgb is not None and w.reactor.live_frame is not None)
                    self.assertEqual(w.runtime.engine.colors,colors)
                    frame=w.c.adapter.last_frame;rgb=adjust_music_rgb(frame.rgb,.5,0)
                    self.assertEqual(w.c.adapter.music_colors['Corner'],rgb)
                    self.assertEqual(w.album.virtual_rgb,w.c.adapter.corner_music_rgb(rgb))
                    self.assertEqual(w.reactor.live_frame,frame);self.assertEqual(len(set(rgb)),1)
                    self.assertFalse(self.f.f.f.corner.workers);self.assertFalse(self.f.f.f.drivers)
                finally:w.stop_music();self.wait(lambda:not w.runtime.busy)
            worker.publish(kind='fallback');w.album.poll();self.assertEqual(w.album.current_palette,fixtures.COLORS)

    def test_original_shortcuts_exact_colors_both_targets_and_ownership(self):
        w=self.f.window();a=w.c.adapter;self.f.f.f.connect_corner(a);self.f.f.f.connect_hue(a)
        w.c.select_target('Both');w.c.state.select_inspector('Color');w.c.changed.emit()
        for name,rgb in (('PINK',(255,20,120)),('PURPLE',(150,30,255)),('CYAN',(0,200,255)),('RED',(255,0,0)),
                         ('WARM',(255,90,20)),('WHITE',(255,255,255)),('MGK',(255,0,70)),('OFF',(0,0,0))):
            w.inspector.static_colors[name].click();color='#'+''.join(f'{c:02X}' for c in rgb)
            self.assertEqual([c.color for c in a.state.channels.values()],[color,color])
        shortcuts={b.accessibleName():b for b in w.inspector.findChildren(QPushButton)}
        for color in ('#F52DCB','#AD64FA','#2857FF','#1DD9F0','#24EAB4','#FFAD21','#FF375E'):
            self.assertIn('Color '+color,shortcuts)
        w.start_music();self.wait(lambda:a.last_frame is not None)
        before={k:c.color for k,c in a.state.channels.items()};w.inspector.static_colors['WHITE'].click()
        self.assertEqual({k:c.color for k,c in a.state.channels.items()},before);self.assertTrue(a.music_active)
        a.set_participation('Hue',False);w.live_controls();w.inspector.static_colors['WHITE'].click()
        self.assertEqual(a.state.channels['Corner'].color,before['Corner']);self.assertEqual(a.state.channels['Hue'].color,'#FFFFFF')
        self.assertTrue(a.music_active);w.stop_music()


if __name__=='__main__':unittest.main()
