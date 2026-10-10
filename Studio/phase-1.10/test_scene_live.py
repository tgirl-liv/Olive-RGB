"""Mouse-driven static scenes; capture and devices are simulated, never hardware."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from studio_ui.state import SCENES
from studio_qt.preferences import PreferencesStore,validate
import test_screen_live as fixtures
import unittest


class SceneTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.ScreenWindowTests.setUpClass.__func__)
    setUp=fixtures.ScreenWindowTests.setUp
    tearDown=fixtures.ScreenWindowTests.tearDown
    wait=fixtures.ScreenWindowTests.wait
    window=fixtures.ScreenWindowTests.window
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
        with patch.object(w.c.adapter,'apply_scene',side_effect=partial_failure):
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
