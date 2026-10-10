"""Simulated Hue parity tests; no bridge, Bluetooth or physical bulb required."""
import tempfile
import unittest
from pathlib import Path
from PySide6.QtTest import QTest
import test_dual_live as fixtures
from studio_qt.dual_window import DualLiveWindow
from studio_qt.screen_adapter import ScreenLightingAdapter
from studio_qt.preferences import PreferencesStore,defaults,validate


class HueParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.DualTests.setUpClass()
    def setUp(self):
        self.f=fixtures.DualTests();self.f.setUp();self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'preferences-v1.json'
    def tearDown(self):self.f.tearDown();self.tmp.cleanup()
    def window(self):
        w=DualLiveWindow(worker_factory=self.f.corner.factory,hue_factory=self.f.hue_factory,preferences_path=self.path)
        self.f.windows.append(w);self.f.corner.windows.append(w);w.show();return w
    def test_identity_mode_temperature_persist_without_connecting(self):
        w=self.window();a=w.c.adapter
        a.set_hue_identity({'name':'Bedroom','address_hint':'saved','zigbee_address':'stable'})
        a.hue_mode='temperature';a.hue_temperature=420;w.save_preferences()
        restored=self.window();self.assertEqual(restored.c.adapter.hue.identity,a.hue_identity)
        self.assertEqual(restored.c.adapter.hue_temperature,420);self.assertEqual(restored.c.adapter.hue_mode,'temperature')
        self.assertFalse(self.f.drivers);self.assertFalse(self.f.corner.workers)
    def test_detected_identity_saved_and_restored(self):
        w=self.window();self.f.connect_hue(w.c.adapter);w.save_preferences()
        other=self.window();self.assertEqual(other.c.adapter.hue.identity['zigbee_address'],'mock-stable')
        self.assertEqual(len(self.f.drivers),1);self.assertFalse(other.c.adapter.hue.wanted)
    def test_color_white_color_switch_repeats_identical_color(self):
        a=self.f.adapter();self.f.connect_hue(a);a.set_rgb('Hue','#804020')
        self.f.wait(lambda:self.f.wrote('color',(128,64,32)))
        a.set_hue_mode('temperature',400);self.f.wait(lambda:self.f.wrote('temperature',400))
        self.assertNotIn('color',a.hue.pending)
        a.set_hue_mode('color');self.f.wait(lambda:len([c for c in self.f.drivers[0].calls if c[0]=='write' and c[2]=='color'])==2)
        self.assertNotIn('temperature',a.hue.pending)
    def test_white_does_not_use_rgb_intensity(self):
        a=self.f.adapter();self.f.connect_hue(a);a.set_rgb('Hue','#000000');a.set_hue_mode('temperature',300)
        self.f.wait(lambda:self.f.wrote('temperature',300));self.assertTrue(a.hue.pending['power'])
        self.assertEqual(a.hue.pending['brightness'],128)
    def test_capability_ui_and_unsupported_white_rejected(self):
        self.f.options['caps']={'temperature':False};w=self.window();self.f.connect_hue(w.c.adapter)
        w.live_controls();panel=w.hue_preferences_panel
        self.assertFalse(panel.temperature.isEnabled());self.assertFalse(panel.mode.model().item(1).isEnabled())
        with self.assertRaises(ValueError):w.c.adapter.set_hue_mode('temperature')
    def test_white_only_bulb_controls(self):
        self.f.options['caps']={'color':False};w=self.window();self.f.connect_hue(w.c.adapter)
        w.hue_preferences_panel.mode.setCurrentIndex(1)
        self.f.wait(lambda:self.f.wrote('temperature',300));self.assertTrue(w.hue_preferences_panel.temperature.isEnabled())
    def test_target_switch_disconnects_and_drops_commands_without_connect(self):
        a=self.f.adapter();self.f.connect_hue(a);a.set_rgb('Hue','#FF0000');old=a.hue.generation
        a.set_hue_identity({'name':'Another bulb'});self.assertGreater(a.hue.generation,old)
        self.assertFalse(a.hue.pending);self.f.wait(lambda:a.hue_status=='disconnected')
        QTest.qWait(100);self.assertEqual(len(self.f.drivers),1)
        self.f.connect_hue(a);self.assertEqual(self.f.drivers[-1].identity['name'],'Another bulb')
    def test_music_screen_restore_white_and_exclude_ownership(self):
        from music_coordination import MusicFrame
        import time
        a=ScreenLightingAdapter(worker_factory=self.f.corner.factory,hue_factory=self.f.hue_factory,hue_identity={'name':'Tv lamp'})
        self.f.adapters.append(a);self.f.corner.adapters.append(a);self.f.connect_hue(a)
        a.set_follow_master('Hue',True);a.set_hue_mode('temperature',350)
        self.f.wait(lambda:self.f.wrote('temperature',350));a.start_music()
        with self.assertRaises(ValueError):a.set_hue_mode('color')
        with self.assertRaises(RuntimeError):a.start_screen()
        # Screen takes over only after Music releases ownership.
        a.stop_music();a.start_screen();a.apply_screen((255,20,10))
        self.f.wait(lambda:self.f.wrote('color',(255,20,10)))
        with self.assertRaises(RuntimeError):a.start_music()
        with self.assertRaises(ValueError):a.set_hue_mode('temperature',400)
        a.stop_screen();self.f.wait(lambda:len([c for c in self.f.drivers[0].calls if c[0]=='write' and c[2]=='temperature'])==2)
        self.assertEqual(a.hue_mode,'temperature');self.assertEqual(a.hue_temperature,350)
    def test_invalid_preferences_safe_fallback(self):
        for value in ({'mode':'bad'},{'temperature':False},{'temperature':501},{'identity':{'name':''}},{'identity':{'name':42}}):
            data=defaults('live');data['hue'].update(value)
            with self.assertRaises(ValueError):validate(data,'live')
        self.path.write_text('{');self.assertEqual(PreferencesStore(self.path).load('live')['hue']['mode'],'color')
    def test_navigation_and_selection_no_hardware(self):
        w=self.window()
        for page in ('Settings','Devices','Studio','Music','Screen'):w.c.navigate(page)
        w.c.select_channel('Hue');w.live_controls()
        self.assertFalse(self.f.drivers);self.assertFalse(self.f.corner.workers)

    def test_measured_music_routes_rgb_then_restores_saved_white(self):
        from music_coordination import MusicFrame
        import time
        a=ScreenLightingAdapter(worker_factory=self.f.corner.factory,hue_factory=self.f.hue_factory,hue_identity={'name':'Tv lamp'})
        self.f.adapters.append(a);self.f.corner.adapters.append(a);self.f.connect_hue(a)
        a.set_hue_mode('temperature',370);self.f.wait(lambda:self.f.wrote('temperature',370))
        a.start_music('Same Color');a.apply_frame(MusicFrame((200,20,40),.6,.3,.1,.04,False,time.monotonic()))
        self.f.wait(lambda:self.f.wrote('color',(200,20,40)))
        a.stop_music();self.f.wait(lambda:len([c for c in self.f.drivers[0].calls if c[0]=='write' and c[2]=='temperature'])==2)
        self.assertEqual(a.hue_mode,'temperature');self.assertFalse(a.music_active)
    def test_reconnect_failure_is_bounded_until_explicit_retry(self):
        a=self.f.adapter();self.f.options['fail_connect']=True;a.connect_hue()
        self.f.wait(lambda:a.hue_status=='error');QTest.qWait(150)
        self.assertEqual(len(self.f.drivers),1);self.assertFalse(a.hue.wanted)
        self.f.options['fail_connect']=False;self.f.connect_hue(a)
        self.assertEqual(len(self.f.drivers),2);a.disconnect_hue()
        self.f.wait(lambda:a.hue_status=='disconnected');self.assertFalse(a.hue.pending)

    def test_screen_follow_optout_restores_white_without_stopping_capture(self):
        a=ScreenLightingAdapter(worker_factory=self.f.corner.factory,hue_factory=self.f.hue_factory,hue_identity={'name':'Tv lamp'})
        self.f.adapters.append(a);self.f.corner.adapters.append(a);self.f.connect_hue(a)
        a.set_follow_master('Hue',True);a.set_hue_mode('temperature',360)
        self.f.wait(lambda:self.f.wrote('temperature',360));a.start_screen();a.apply_screen((20,200,40))
        self.f.wait(lambda:self.f.wrote('color',(20,200,40)))
        a.set_follow_master('Hue',False)
        self.f.wait(lambda:len([c for c in self.f.drivers[0].calls if c[0]=='write' and c[2]=='temperature'])==2)
        self.assertTrue(a.screen_active);self.assertFalse(a.owns('Hue'));self.assertNotIn('color',a.hue.pending)

    def test_screen_follow_optout_restores_manual_rgb(self):
        a=ScreenLightingAdapter(worker_factory=self.f.corner.factory,hue_factory=self.f.hue_factory,hue_identity={'name':'Tv lamp'})
        self.f.adapters.append(a);self.f.corner.adapters.append(a);self.f.connect_hue(a)
        a.set_rgb('Hue','#804020');a.set_follow_master('Hue',True)
        self.f.wait(lambda:self.f.wrote('color',(128,64,32)));a.start_screen();a.apply_screen((20,200,40))
        self.f.wait(lambda:self.f.wrote('color',(20,200,40)));a.set_follow_master('Hue',False)
        self.f.wait(lambda:len([c for c in self.f.drivers[0].calls if c[0]=='write' and c[2:] == ('color',(128,64,32))])==2)
        self.assertTrue(a.screen_active);self.assertFalse(a.owns('Hue'))
    def test_invalid_rgb_does_not_change_white_preference(self):
        a=self.f.adapter();self.f.connect_hue(a);a.set_hue_mode('temperature',340)
        with self.assertRaises(ValueError):a.set_rgb('Hue','invalid')
        self.assertEqual(a.hue_mode,'temperature');self.assertEqual(a.hue_temperature,340)
