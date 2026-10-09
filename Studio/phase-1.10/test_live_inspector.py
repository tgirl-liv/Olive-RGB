"""LIVE inspector routing with real sessions and simulated device/audio boundaries."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton
import test_music_live as fixtures
from studio_qt.music_window import MusicLiveWindow
from studio_qt.preferences import PreferencesStore


class LiveInspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.MusicTests.setUpClass();cls.app=fixtures.MusicTests.app

    def setUp(self):
        self.f=fixtures.MusicTests();self.f.setUp()
        self.qt_errors=[]
        self.hook=patch.object(sys,'excepthook',lambda *args:self.qt_errors.append(args[1]));self.hook.start()

    def tearDown(self):
        try:
            self.f.tearDown();self.assertEqual(self.qt_errors,[])
        finally:self.hook.stop()

    def window(self,preferences_path=None):
        if preferences_path is None:return self.f.window()
        f=self.f
        w=MusicLiveWindow(worker_factory=f.f.corner.factory,hue_factory=f.f.hue_factory,
                          hue_identity={'name':'Tv lamp'},engine_factory=f.factory,preferences_path=preferences_path)
        f.windows.append(w);f.f.windows.append(w);f.f.corner.windows.append(w)
        f.f.adapters.append(w.c.adapter);f.f.corner.adapters.append(w.c.adapter)
        w.show();self.app.processEvents();return w

    def test_tabs_available_disconnected_without_starting_services(self):
        w=self.window()
        self.assertTrue(w.open_tab('Music'));self.assertTrue(w.open_tab('Setup'))
        self.assertFalse(w.inspector.tabs.widget(0).isEnabled())
        self.assertFalse(self.f.engines);self.assertFalse(self.f.f.drivers);self.assertFalse(self.f.f.corner.workers)
        self.assertIs(w.inspector.live_music.window.c,w.c)
        self.assertIs(w.inspector.live_setup.window.c.adapter,w.c.adapter)
        for _,link in w.inspector_links.values():self.assertTrue(link.isEnabled())
        self.assertFalse(w.inspector.reduced.isEnabled());self.assertFalse(w.inspector.relationship.isEnabled())

    def test_setup_corner_uses_existing_connection_actions(self):
        w=self.window();setup=w.inspector.live_setup;w.open_tab('Setup')
        self.assertTrue(setup.connect_button.isEnabled());self.assertFalse(setup.disconnect_button.isEnabled())
        with patch.object(w.c.adapter,'connect_corner',wraps=w.c.adapter.connect_corner) as connect:
            setup.connect_button.click();connect.assert_called_once_with()
        self.assertFalse(setup.connect_button.isEnabled());self.assertTrue(setup.disconnect_button.isEnabled())
        self.f.wait(lambda:w.c.adapter.connected)
        self.assertIn('RGB color',setup.capabilities.text());self.assertIn('software power',setup.capabilities.text())
        with patch.object(w.c.adapter,'disconnect_corner',wraps=w.c.adapter.disconnect_corner) as disconnect:
            setup.disconnect_button.click();disconnect.assert_called_once_with()
        self.f.wait(lambda:w.c.adapter.status=='disconnected')
        self.assertTrue(setup.connect_button.isEnabled());self.assertFalse(setup.disconnect_button.isEnabled())
        self.assertFalse(self.f.f.drivers)

    def test_setup_hue_reports_caps_and_disables_unsupported_settings(self):
        self.f.f.options['caps']={'color':False}
        w=self.window();w.c.select_channel('Hue');setup=w.inspector.live_setup
        self.assertIn('unknown',setup.capabilities.text())
        setup.connect_button.click();self.f.wait(lambda:w.c.adapter.hue_connected)
        self.assertIn('brightness',setup.capabilities.text());self.assertIn('temperature',setup.capabilities.text())
        self.assertNotIn('power, brightness, color,',setup.capabilities.text())
        self.assertFalse(w.inspector.tabs.widget(0).isEnabled())
        self.assertTrue(w.open_tab('Music'));self.assertTrue(w.open_tab('Setup'))
        for control in setup.findChildren(QPushButton):
            if control.text() in ('Choose another device','Color temperature','Scene / transition settings'):
                self.assertFalse(control.isEnabled());self.assertIn('Unavailable',control.toolTip())
        setup.disconnect_button.click();self.f.wait(lambda:w.c.adapter.hue_status=='disconnected')
        self.assertIn('unknown',setup.capabilities.text());self.assertFalse(self.f.f.corner.workers)

    def test_setup_reports_connection_failure(self):
        self.f.f.options['fail_connect']=True
        w=self.window();w.c.select_channel('Hue');setup=w.inspector.live_setup
        setup.connect_button.click();self.f.wait(lambda:w.c.adapter.hue_status=='error')
        self.assertIn('authentication failure',setup.status.text())
        self.assertTrue(setup.connect_button.isEnabled());self.assertFalse(setup.disconnect_button.isEnabled())

    def test_participation_tracks_selected_device_and_existing_panel(self):
        w=self.window();music=w.inspector.live_music
        music.participation.setChecked(False)
        self.assertEqual(w.c.adapter.participation,{'Corner':False,'Hue':True})
        self.assertFalse(w.participate['Corner'].isChecked())
        w.c.select_channel('Hue');self.assertTrue(music.participation.isChecked())
        w.participate['Hue'].setChecked(False);self.assertFalse(music.participation.isChecked())
        music.participation.setChecked(True)
        self.assertEqual(w.c.adapter.participation,{'Corner':False,'Hue':True})
        self.assertFalse(self.f.engines);self.assertFalse(self.f.f.drivers)

    def test_shared_coordination_and_participation_persist_without_new_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'qt.json';w=self.window(path);music=w.inspector.live_music
            music.relationship.setCurrentText('Same Color');music.separation.setValue(73)
            self.assertEqual(w.harmony.currentText(),'Same Color');self.assertEqual(w.separation.value(),73)
            self.assertEqual([music.relationship.itemText(i) for i in range(music.relationship.count())],['Coordinated Colors','Same Color'])
            w.harmony.setCurrentText('Coordinated Colors');w.separation.setValue(42)
            self.assertEqual(music.relationship.currentText(),'Coordinated Colors');self.assertEqual(music.separation.value(),42)
            music.participation.setChecked(False);QTest.qWait(300)
            saved=PreferencesStore(path).load('live')['music']
            self.assertEqual(saved['separation'],.42);self.assertFalse(saved['participation']['Corner'])
            w.close();self.f.wait(lambda:w._cleanup_done)
            other=self.window(path)
            self.assertEqual(other.inspector.live_music.separation.value(),42)
            self.assertFalse(other.inspector.live_music.participation.isChecked())
            self.assertFalse(other.runtime.busy);self.assertFalse(other.c.adapter.session.wanted)
            other.close();self.f.wait(lambda:other._cleanup_done)

    def test_music_actions_preserve_ownership_and_busy_gates(self):
        w=self.window();self.f.f.connect_corner(w.c.adapter);self.f.f.connect_hue(w.c.adapter)
        w.c.select_channel('Hue');music=w.inspector.live_music
        music.start.click();self.f.wait(lambda:w.c.adapter.last_frame is not None)
        self.assertEqual(len(self.f.engines),1);self.assertTrue(w.c.adapter.owns('Hue'))
        self.assertFalse(w.inspector.tabs.widget(0).isEnabled())
        self.assertTrue(music.participation.isEnabled());self.assertFalse(music.relationship.isEnabled());self.assertFalse(music.separation.isEnabled())
        self.assertFalse(music.start.isEnabled());self.assertTrue(music.stop.isEnabled())
        self.assertIn('Music owns Hue',music.status.text())
        music.participation.setChecked(False)
        self.assertFalse(w.c.adapter.owns('Hue'));self.assertTrue(w.inspector.tabs.widget(0).isEnabled())
        self.assertTrue(w.c.adapter.owns('Corner'))
        music.stop.click();self.f.wait(lambda:not w.runtime.busy and music.relationship.isEnabled() and music.separation.isEnabled())
        self.assertFalse(w.c.adapter.music_active);self.assertEqual(w.c.state.mode,'Manual')
        self.assertTrue(music.relationship.isEnabled());self.assertTrue(music.separation.isEnabled())

    def test_closing_disables_inspector_actions_and_completes_workers(self):
        self.f.f.options['connect_delay']=.15
        w=self.window();w.c.select_channel('Hue');w.inspector.live_setup.connect_button.click()
        w.close()
        self.assertFalse(w.inspector.live_setup.connect_button.isEnabled())
        self.assertFalse(w.inspector.live_setup.disconnect_button.isEnabled())
        self.assertFalse(w.inspector.live_music.participation.isEnabled());self.assertFalse(w.inspector.live_music.start.isEnabled())
        self.f.wait(lambda:w._cleanup_done)


    def both(self,w):
        w.inspector.device.setCurrentIndex(w.inspector.device.findData('Both'))
        self.assertEqual(w.c.target_devices(),('Corner','Hue'))

    def connect_both(self,w):
        self.f.f.connect_corner(w.c.adapter);self.f.f.connect_hue(w.c.adapter)

    def test_target_selector_and_master_do_not_change_independent_values(self):
        w=self.window();ins=w.inspector
        self.assertEqual([ins.device.itemText(i) for i in range(ins.device.count())],['Both Lights','Corner Lamp','Philips Hue'])
        before={key:vars(ch).copy() for key,ch in w.c.state.channels.items()}
        w.master.color.click();self.assertEqual(w.c.manual_target,'Both')
        self.assertEqual(before,{key:vars(ch).copy() for key,ch in w.c.state.channels.items()})
        self.assertIn('Hue: disconnected',ins.target_notice.text());self.assertIn('Corner: disconnected',ins.target_notice.text())
        self.assertFalse(self.f.f.corner.workers);self.assertFalse(self.f.f.drivers)
        self.assertFalse(ins.follow.isEnabled())
        w.channels['Hue'].select.click();self.assertEqual(w.c.target_devices(),('Hue',))

    def test_both_hex_rgb_hsv_and_wheel_route_to_existing_adapters(self):
        w=self.window();self.connect_both(w);self.both(w);ins=w.inspector
        workers=list(self.f.f.corner.workers);drivers=list(self.f.f.drivers)
        with patch.object(w.c.adapter,'set_rgb',wraps=w.c.adapter.set_rgb) as write:
            ins.hex.setText('#123456');ins.hex.editingFinished.emit()
            self.assertEqual(write.call_args_list, [unittest.mock.call('Corner','#123456'),unittest.mock.call('Hue','#123456')])
        ins.rgb[0].setValue(255)
        self.assertTrue(all(ch.color=='#FF3456' for ch in w.c.state.channels.values()))
        w.c.set_hex('#FF0000');ins.hsv[0][1].setValue(180)
        self.assertTrue(all(ch.color=='#00FFFF' for ch in w.c.state.channels.values()))
        ins.wheel.hueChanged.emit(0.)
        self.assertTrue(all(ch.color=='#FF0000' for ch in w.c.state.channels.values()))
        self.f.wait(lambda:self.f.f.wrote('color',(255,0,0)))
        self.f.wait(lambda:any(call[0]=='rgb' and call[2][0]>0 and call[2][1:]==(0,0) for call in self.f.f.corner.lamps[0].calls))
        self.assertEqual(self.f.f.corner.workers,workers);self.assertEqual(self.f.f.drivers,drivers)
        before={key:ch.color for key,ch in w.c.state.channels.items()}
        with self.assertRaises(ValueError):w.c.set_hex('#broken')
        self.assertEqual(before,{key:ch.color for key,ch in w.c.state.channels.items()})

    def test_both_local_power_brightness_preserve_follow_and_master_settings(self):
        w=self.window();self.connect_both(w)
        w.c.channel('Corner','follow',True);w.c.channel('Hue','follow',False)
        master=(w.c.state.master_power,w.c.state.master_brightness)
        colors={key:ch.color for key,ch in w.c.state.channels.items()}
        self.both(w);w.inspector.brightness.setValue(31)
        self.assertTrue(all(ch.brightness==.31 for ch in w.c.state.channels.values()))
        w.inspector.power.click();self.assertTrue(all(not ch.power for ch in w.c.state.channels.values()))
        w.inspector.power.click();self.assertTrue(all(ch.power for ch in w.c.state.channels.values()))
        self.assertEqual((w.c.state.master_power,w.c.state.master_brightness),master)
        self.assertEqual({key:ch.color for key,ch in w.c.state.channels.items()},colors)
        self.assertTrue(w.c.state.channels['Corner'].follow);self.assertFalse(w.c.state.channels['Hue'].follow)
        w.inspector.device.setCurrentIndex(w.inspector.device.findData('Hue'))
        w.inspector.brightness.setValue(52)
        self.assertEqual(w.c.state.channels['Corner'].brightness,.31);self.assertEqual(w.c.state.channels['Hue'].brightness,.52)

    def test_both_disconnected_target_is_skipped_with_feedback(self):
        w=self.window();self.f.f.connect_corner(w.c.adapter);self.both(w)
        hue=vars(w.c.state.channels['Hue']).copy()
        self.assertTrue(w.inspector.tabs.widget(0).isEnabled())
        w.c.set_hex('#123456');w.inspector.brightness.setValue(29);w.inspector.power.click()
        self.assertEqual(vars(w.c.state.channels['Hue']),hue)
        self.assertEqual(w.c.state.channels['Corner'].color,'#123456')
        self.assertIn('Hue: disconnected',w.inspector.target_notice.text());self.assertFalse(self.f.f.drivers)

    def test_both_unsupported_hue_fields_are_skipped(self):
        self.f.f.options['caps']={'color':False,'brightness':False,'power':False}
        w=self.window();self.connect_both(w);self.both(w)
        hue=vars(w.c.state.channels['Hue']).copy()
        w.c.set_hex('#AABBCC');self.assertIn('Hue: color unsupported',w.inspector.target_notice.text())
        w.inspector.brightness.setValue(32);self.assertIn('Hue: brightness unsupported',w.inspector.target_notice.text())
        w.inspector.power.click();self.assertIn('Hue: power unsupported',w.inspector.target_notice.text())
        self.assertEqual(vars(w.c.state.channels['Hue']),hue)
        self.assertEqual(w.c.state.channels['Corner'].color,'#AABBCC')
        self.assertFalse(any(call[0]=='write' for call in self.f.f.drivers[0].calls))

    def test_both_music_owned_color_is_skipped_but_power_brightness_work(self):
        w=self.window();self.connect_both(w);w.participate['Hue'].setChecked(False)
        w.start_music();self.f.wait(lambda:w.c.adapter.last_frame is not None)
        corner=w.c.state.channels['Corner'].color;self.both(w)
        self.assertTrue(w.inspector.tabs.widget(0).isEnabled())
        w.c.set_hex('#00FF00')
        self.assertEqual(w.c.state.channels['Corner'].color,corner);self.assertEqual(w.c.state.channels['Hue'].color,'#00FF00')
        self.assertIn('Corner: Music owns color',w.inspector.target_notice.text())
        w.inspector.brightness.setValue(36);self.assertTrue(all(ch.brightness==.36 for ch in w.c.state.channels.values()))
        self.assertTrue(w.c.adapter.music_active);self.assertTrue(w.c.adapter.owns('Corner'))
        w.disconnect_hue();self.assertFalse(w.inspector.tabs.widget(0).isEnabled())
        self.assertIn('Hue: disconnected',w.inspector.target_notice.text())
        w.stop_music();self.f.wait(lambda:not w.runtime.busy)
        self.assertTrue(w.inspector.tabs.widget(0).isEnabled())

    def test_both_setup_participation_and_persistence_use_existing_state(self):
        from PySide6.QtCore import Qt
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'qt.json';w=self.window(path);self.both(w)
            w.inspector.live_setup.connect_button.click()
            self.f.wait(lambda:w.c.adapter.connected and w.c.adapter.hue_connected)
            self.assertEqual(len(self.f.f.corner.workers),1);self.assertEqual(len(self.f.f.drivers),1)
            w.participate['Hue'].setChecked(False)
            music=w.inspector.live_music
            self.assertEqual(music.participation.checkState(),Qt.CheckState.PartiallyChecked)
            music.participation.click();self.assertEqual(w.c.adapter.participation,{'Corner':True,'Hue':True})
            music.participation.setChecked(False);self.assertEqual(w.c.adapter.participation,{'Corner':False,'Hue':False})
            w.c.set_hex('#ABCDEF');w.inspector.brightness.setValue(61)
            w.c.select_channel('Corner');w.inspector.brightness.setValue(24);QTest.qWait(300)
            saved=PreferencesStore(path).load('live')
            self.assertEqual(saved['devices']['Corner']['brightness'],.24);self.assertEqual(saved['devices']['Hue']['brightness'],.61)
            self.assertTrue(all(ch['color']=='#ABCDEF' for ch in saved['devices'].values()))
            self.assertEqual(set(saved['devices']),{'Corner','Hue'})
            w.close();self.f.wait(lambda:w._cleanup_done)


if __name__=='__main__':unittest.main()
