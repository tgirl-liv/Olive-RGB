"""Mouse-driven static scenes; capture and devices are simulated, never hardware."""
import tempfile
from pathlib import Path
from unittest.mock import patch,call
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from studio_ui.state import SCENES
from studio_qt.scene_transitions import SceneTransition
from studio_qt.preferences import PreferencesStore,validate
import test_screen_live as fixtures
import unittest


class SceneTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.ScreenWindowTests.setUpClass.__func__)
    setUp=fixtures.ScreenWindowTests.setUp
    tearDown=fixtures.ScreenWindowTests.tearDown
    wait=fixtures.ScreenWindowTests.wait
    def window(self,**kwargs):
        instant=kwargs.pop('instant',True)
        w=fixtures.ScreenWindowTests.window(self,**kwargs)
        if instant:w.c.set_transition(0,'Instant')  # Static-recall assertions use instant mode.
        return w
    # Reuse lifecycle fixtures, not the inherited Screen test cases.
    def click_scene(self,w,name):
        if w.c.state.page!='Studio':w.c.navigate('Studio')
        scroll=w.pages.widget(0);pad=next(p for p in w.scenes.cards if p.name==name)
        scroll.ensureWidgetVisible(pad);QTest.qWait(20)
        self.assertTrue(pad.isVisible())
        before=scroll.verticalScrollBar().value()
        geometry=w.master.mapTo(w,QPoint(0,0))
        QTest.mouseClick(pad,Qt.MouseButton.LeftButton);QTest.qWait(30)
        self.assertEqual(scroll.verticalScrollBar().value(),before)
        self.assertIs(w.focusWidget(),pad)
        self.assertEqual(w.master.mapTo(w,QPoint(0,0)),geometry)
        return pad

    def test_all_scene_pads_without_hardware_and_repeated_clicks(self):
        w=self.window();w.c.state.channels['Hue'].follow=True
        for hidden in (False,True):
            if w.workspace.inspector_collapsed!=hidden:
                QTest.mouseClick(w.inspector_toggle,Qt.MouseButton.LeftButton);QTest.qWait(20)
            self.assertEqual(w.inspector_scroll.isVisible(),not hidden)
            for name,colors in SCENES.items():
                self.click_scene(w,name);self.click_scene(w,name)
                self.assertTrue(w.c.scene_active);self.assertEqual(w.c.state.mode,'Manual')
                self.assertEqual(tuple(c.color for c in w.c.state.channels.values()),colors[:2])
                rgb=tuple(int(colors[0][i:i+2],16) for i in (1,3,5))
                self.assertEqual(w.scenes.preview.virtual_rgb,w.c.adapter.corner_music_rgb(rgb))
        self.assertFalse(self.f.f.corner.workers);self.assertFalse(w.c.adapter.hue.wanted)

    def test_music_screen_scene_and_back(self):
        w=self.window()
        for mode in ('Music','Screen'):
            QTest.mouseClick(w.master.modes[mode],Qt.MouseButton.LeftButton)
            self.wait(lambda:w.c.adapter.music_active if mode=='Music' else w.c.adapter.screen_active)
            self.click_scene(w,'Ocean Breeze')
            self.wait(lambda:w.c.scene_active)
            self.assertFalse(w.runtime.busy);self.assertFalse(w.screen_runtime.busy)
            self.assertFalse(w.c.adapter.music_active);self.assertFalse(w.c.adapter.screen_active)
            QTest.mouseClick(w.master.modes[mode],Qt.MouseButton.LeftButton)
            self.wait(lambda:w.c.adapter.music_active if mode=='Music' else w.c.adapter.screen_active)
            self.assertFalse(w.c.scene_active)
            QTest.mouseClick(w.master.modes['Manual'],Qt.MouseButton.LeftButton)
            self.wait(lambda:not w.runtime.busy and not w.screen_runtime.busy)

    def test_settings_favorites_restore_without_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'preferences-v1.json';w=self.window(preferences_path=path)
            w.c.state.channels['Corner'].brightness=.4;w.c.state.master_brightness=.5
            w.c.state.channels['Hue'].follow=False;old=w.c.state.channels['Hue'].color
            self.click_scene(w,'Neon Party');self.assertEqual(w.c.state.channels['Hue'].color,old)
            self.assertEqual(w.scenes.preview.virtual_rgb,(48,8,44))
            w.c.state.channels['Corner'].power=False;w.c.changed.emit();self.assertEqual(w.scenes.preview.virtual_rgb,(0,0,0))
            w.c.favorite('Ultraviolet');w.save_preferences()
            restored=self.window(preferences_path=path)
            self.assertEqual(restored.c.state.scene,'Neon Party');self.assertIn('Ultraviolet',restored.c.state.favorites)
            self.assertFalse(restored.c.scene_active);self.assertFalse(restored.runtime.busy)
            self.assertEqual(restored.c.state.channels['Corner'].brightness,.4)

    def test_invalid_scene_and_adapter_failure_visible(self):
        w=self.window();old=w.c.state.channels['Corner'].color
        with patch.dict(SCENES,{'Ocean Breeze':('bad','#123456','invalid')}):
            w.c.select_scene('Ocean Breeze')
        self.assertIn('failed',w.c.scene_status);self.assertEqual(w.c.state.channels['Corner'].color,old)
        def partial_failure(name):
            w.c.adapter.set_rgb('Corner','#112233')
            raise RuntimeError('test failure')
        with patch.object(w.c.adapter,'stage_scene_transition',side_effect=partial_failure):
            self.click_scene(w,'Ultraviolet')
        self.assertIn('test failure',w.scenes.status.text());self.assertFalse(w.c.scene_active)
        self.assertEqual(w.c.display_colors['Corner'],'#112233')
        self.assertEqual(w.c.state.mode,'Manual')
        with self.assertRaises(ValueError):validate({'scenes':{'selected':'missing'}},'live')


    def test_connected_devices_use_manual_adapter_routes_and_capabilities(self):
        w=self.window();a=w.c.adapter
        self.f.f.corner.connect(a);self.f.f.connect_hue(a)
        a.state.channels['Hue'].follow=True
        with patch.object(a,'set_rgb',wraps=a.set_rgb) as route:
            self.click_scene(w,'Sunset Chill')
            self.assertEqual([call.args for call in route.call_args_list],[('Corner','#FF995D'),('Hue','#C3338C')])
        self.f.f.wait(lambda:self.f.f.wrote('color',(195,51,140)))
        old=a.state.channels['Hue'].color;a.hue_caps['color']=False
        self.click_scene(w,'Ocean Breeze')
        self.assertEqual(a.state.channels['Hue'].color,old)
        self.assertIn('RGB unsupported',w.scenes.status.text())
        a.state.channels['Corner'].follow=False;old=a.state.channels['Corner'].color
        self.click_scene(w,'Neon Party');self.assertEqual(a.state.channels['Corner'].color,old)

    def test_scene_page_pad_mouse_and_pending_scene_cancelled_by_mode(self):
        from studio_qt.app import ScenePanel
        w=self.window();w.c.navigate('Scenes')
        panel=next(p for p in w.findChildren(ScenePanel) if p is not w.scenes)
        QTest.mouseClick(panel.cards[2],Qt.MouseButton.LeftButton)
        self.assertEqual(w.c.state.scene,'Cyber Night');self.assertTrue(w.c.scene_active)
        with patch.object(type(w.runtime),'busy',new_callable=__import__('unittest').mock.PropertyMock,return_value=True):
            w.c.select_scene('Ocean Breeze');self.assertEqual(w._pending_scene,'Ocean Breeze')
            w.request_mode('Music');self.assertIsNone(w._pending_scene)
        self.wait(lambda:w.c.adapter.music_active)
        self.assertFalse(w.c.scene_active)

    def test_smooth_live_transition_interrupt_and_final_color(self):
        w=self.window();a=w.c.adapter
        self.f.f.corner.connect(a)
        a.state.channels['Hue'].follow=False
        w.c.set_transition(.5,'Linear')
        self.click_scene(w,'Sunset Chill')
        self.assertIsNotNone(w._scene_fade)
        QTest.qWait(240)
        middle=a.state.channels['Corner'].color
        self.assertNotEqual(middle,'#FF995D')
        self.assertNotEqual(middle,'#F32E83')
        w.c.select_scene('Ocean Breeze')
        self.assertEqual(w._scene_fade.source['Corner'],tuple(int(middle[i:i+2],16) for i in (1,3,5)))
        self.wait(lambda:w._scene_fade is None)
        self.assertEqual(a.state.channels['Corner'].color,'#2365DD')
        self.assertTrue(w.c.scene_active)

    def test_mode_change_cancels_active_fade(self):
        w=self.window();w.c.set_transition(2.,'Smooth')
        self.f.f.corner.connect(w.c.adapter)
        w.c.select_scene('Cyber Night')
        self.assertIsNotNone(w._scene_fade)
        w.request_mode('Music')
        self.assertIsNone(w._scene_fade)
        self.assertFalse(w.scene_timer.isActive())
        self.assertFalse(w.c.scene_active)
        self.wait(lambda:w.c.adapter.music_active)

    def test_disconnected_preview_fades_without_device_io_or_opted_out_changes(self):
        w=self.window();w.c.set_transition(2.,'Smooth')
        w.c.state.channels['Hue'].follow=False
        previous=w.c.state.channels['Hue'].color
        w.c.select_scene('Neon Party')
        self.assertIsNotNone(w._scene_fade)
        self.assertEqual(w._scene_routes,set())
        self.assertEqual(w.c.state.channels['Corner'].color,'#EF27DA')
        self.assertEqual(w.c.state.channels['Hue'].color,previous)

    def test_manual_color_edit_interrupts_fade(self):
        w=self.window();a=w.c.adapter
        self.f.f.corner.connect(a)
        w.c.set_transition(2.,'Linear')
        w.c.select_scene('Cyber Night')
        self.assertIsNotNone(w._scene_fade)
        w.c.select_channel('Corner')
        w.c.apply_manual('color','#123456')
        self.assertIsNone(w._scene_fade)
        self.assertFalse(w.c.scene_active)
        QTest.qWait(150)
        self.assertEqual(a.state.channels['Corner'].color,'#123456')

    def test_live_transition_settings_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'preferences-v1.json'
            w=self.window(preferences_path=path)
            w.c.set_transition(2.5,'Linear')
            w.save_preferences()
            restored=self.window(preferences_path=path,instant=False)
            self.assertEqual(restored.c.state.transition_seconds,2.5)
            self.assertEqual(restored.c.state.transition_curve,'Linear')
            with self.assertRaises(ValueError):
                validate({'scenes':{'transition_seconds':6}},'live')
            with self.assertRaises(ValueError):
                validate({'scenes':{'transition_curve':'Blink'}},'live')


    def test_disconnected_live_preview_uses_engine_samples_and_scaled_output(self):
        from types import SimpleNamespace
        from studio_qt import scene_transitions
        from studio_qt.widgets.scene_pad import artwork
        w=self.window();a=w.c.adapter
        a.state.channels['Corner'].brightness=.4;a.state.master_brightness=.5
        for curve in ('Linear','Smooth'):
            with self.subTest(curve=curve):
                clock=[100.]
                a.state.channels['Corner'].color='#000000';w.c.display_colors['Corner']='#000000'
                w.c.set_transition(3,curve)
                thumbnail=artwork('Sunset Chill').copy()
                with patch.object(scene_transitions,'time',SimpleNamespace(monotonic=lambda:clock[0])), patch.object(a,'set_rgb',wraps=a.set_rgb) as route:
                    self.click_scene(w,'Sunset Chill');w.scene_timer.stop()
                    fade=w._scene_fade
                    self.assertEqual(w.scenes.preview.virtual_rgb,(0,0,0))
                    for elapsed in (.75,1.5,3):
                        clock[0]=100+elapsed;expected,progress=fade.sample()
                        w.step_scene()
                        self.assertEqual(w.c.display_colors['Corner'],expected['Corner'])
                        rgb=tuple(int(expected['Corner'][i:i+2],16) for i in (1,3,5))
                        self.assertEqual(w.scenes.preview.virtual_rgb,a.corner_music_rgb(rgb))
                        self.assertEqual(w.c.transition_progress,progress)
                    self.assertIsNone(w._scene_fade);self.assertFalse(w.scene_timer.isActive())
                    route.assert_not_called()
                self.assertEqual(thumbnail,artwork('Sunset Chill'))
        self.assertFalse(self.f.f.corner.workers);self.assertFalse(a.hue.wanted)
        self.assertIn('hardware unverified',w.scenes.preview.light_readout.text())

    def test_preview_interrupt_rapid_mouse_recalls_start_from_displayed_color(self):
        from types import SimpleNamespace
        from studio_qt import scene_transitions
        w=self.window();clock=[100.];w.c.set_transition(3,'Smooth')
        with patch.object(scene_transitions,'time',SimpleNamespace(monotonic=lambda:clock[0])):
            self.click_scene(w,'Sunset Chill');w.scene_timer.stop()
            clock[0]=101;w.step_scene();middle=dict(w.c.display_colors)
            for name in ('Ocean Breeze','Neon Party','Cyber Night'):
                self.click_scene(w,name);w.scene_timer.stop()
                self.assertEqual(w.c.display_colors,middle)
                self.assertEqual(w._scene_fade.source['Corner'],tuple(int(middle['Corner'][i:i+2],16) for i in (1,3,5)))
            clock[0]=104;w.step_scene()
            final=w.scenes.preview.virtual_rgb
            self.assertEqual(w.c.display_colors['Corner'],SCENES['Cyber Night'][0])
            self.assertIsNone(w._scene_fade);w.step_scene()
            self.assertEqual(w.scenes.preview.virtual_rgb,final)

    def test_connected_preview_samples_keep_existing_manual_routes(self):
        from types import SimpleNamespace
        from studio_qt import scene_transitions
        w=self.window();a=w.c.adapter;self.f.f.corner.connect(a)
        clock=[100.];w.c.set_transition(3,'Linear')
        with patch.object(scene_transitions,'time',SimpleNamespace(monotonic=lambda:clock[0])), patch.object(a,'set_rgb',wraps=a.set_rgb) as route:
            self.click_scene(w,'Ocean Breeze');w.scene_timer.stop();route.reset_mock()
            clock[0]=101;expected,_=w._scene_fade.sample();w.step_scene()
            self.assertEqual(route.call_args_list,[call('Corner',expected['Corner'])])
            rgb=tuple(int(expected['Corner'][i:i+2],16) for i in (1,3,5))
            self.assertEqual(w.scenes.preview.virtual_rgb,a.corner_music_rgb(rgb))
            w.step_scene();self.assertEqual(route.call_count,1)  # same sample never adds a write

    def test_close_cancels_preview_timer_and_callbacks(self):
        w=self.window();w.c.set_transition(3,'Linear');self.click_scene(w,'Ocean Breeze')
        self.assertTrue(w.scene_timer.isActive());w.close()
        self.wait(lambda:w._cleanup_done)
        self.assertFalse(w.scene_timer.isActive());self.assertIsNone(w._scene_fade)
        previous=w.scenes.preview.virtual_rgb;w.step_scene()
        self.assertEqual(w.scenes.preview.virtual_rgb,previous)

    def test_demo_mouse_scene_preview_uses_existing_controller_interpolation(self):
        from studio_qt.app import StudioWindow
        with tempfile.TemporaryDirectory() as directory:
            w=StudioWindow(workspace_path=Path(directory)/'workspace.json',preferences_path=Path(directory)/'prefs.json')
            try:
                w.show();QTest.qWait(20);w.timer.stop()
                w.c.state.motion=True;w.c.set_transition(3,'Smooth')
                pad=w.scenes.cards[0];w.pages.widget(0).ensureWidgetVisible(pad)
                QTest.mouseClick(pad,Qt.MouseButton.LeftButton);w.timer.stop()
                start=w.c.transition[0];w.c.advance(start+.75)
                rgb=tuple(int(w.c.display_colors['Corner'][i:i+2],16) for i in (1,3,5))
                channel=w.c.state.channels['Corner'];scale=channel.brightness*w.c.state.master_brightness
                self.assertEqual(w.scenes.preview.virtual_rgb,tuple(round(v*scale) for v in rgb))
                w.c.advance(start+3);self.assertIsNone(w.c.transition)
                self.assertEqual(w.c.display_colors['Corner'].upper(),SCENES[pad.name][0])
            finally:w.close();w.deleteLater()


class SceneTransitionMathTests(unittest.TestCase):
    def test_linear_midpoint_and_completion(self):
        t=SceneTransition({'Corner':'#000000'}, {'Corner':'#FFFFFF'},2,'Linear',started=0)
        self.assertEqual(t.sample(1),({'Corner':'#808080'},.5))
        self.assertEqual(t.sample(2),({'Corner':'#FFFFFF'},1.))

    def test_instant_and_invalid_inputs(self):
        t=SceneTransition({'Hue':'#112233'}, {'Hue':'#445566'},2,'Instant',started=0)
        self.assertEqual(t.sample(0)[0]['Hue'],'#445566')
        for seconds in (-1,6,float('nan')):
            with self.assertRaises(ValueError):
                SceneTransition({'Hue':'#112233'},{'Hue':'#445566'},seconds)
