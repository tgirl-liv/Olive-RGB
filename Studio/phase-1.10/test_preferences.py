"""Qt preferences contracts: no real device I/O or audio capture."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from studio_qt.preferences import PreferencesStore, defaults, validate, restore, snapshot
from studio_ui.state import StudioState


class PreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'qt.json';self.store=PreferencesStore(self.path)

    def test_missing_fields_and_roundtrip_modes(self):
        demo=defaults('demo');demo['master']['brightness']=.42
        live=defaults('live');live['music']['palette']='Charli xcx — BRAT'
        self.assertTrue(self.store.save('demo',demo));self.assertTrue(self.store.save('live',live))
        self.assertEqual(self.store.load('demo'),demo);self.assertEqual(self.store.load('live'),live)
        self.assertEqual(validate({},'live'),defaults('live'))

    def test_invalid_fields_rejected(self):
        cases=[('master','power',1),('master','brightness',True),('master','brightness',float('nan')),
               ('master','brightness',float('inf')),('master','brightness',1.01),
               ('music','profile','Unknown'),('music','palette',[]),('music','relationship','Unknown'),
               ('music','sensitivity',0),('music','smoothing',2),('music','separation',-.1)]
        for section,key,value in cases:
            with self.subTest(key=key,value=value):
                values=defaults('live');values[section][key]=value
                with self.assertRaises(ValueError):validate(values,'live')
        for value in ('red','#FFF','#GGFFFF',None):
            values=defaults('demo');values['devices']['Corner']['color']=value
            with self.assertRaises(ValueError):validate(values,'demo')
        values=defaults('live');values['music']['participation']['Hue']='yes'
        with self.assertRaises(ValueError):validate(values,'live')

    def test_corruption_safe_fallback_then_repair(self):
        for raw in ('{broken','[]','{"version":1,"live":{"master":{"power":"yes"}}}', '\xff'):
            self.path.write_bytes(raw.encode('latin1'))
            self.assertEqual(self.store.load('live'),defaults('live'));self.assertTrue(self.store.error)
            self.assertTrue(self.store.save('live',defaults('live')))
            self.assertEqual(self.store.load('live'),defaults('live'))

    def test_future_version_preserved(self):
        original='{"version":2,"live":{"future":true}}';self.path.write_text(original)
        self.assertEqual(self.store.load('live'),defaults('live'))
        self.assertFalse(self.store.save('live',defaults('live')))
        self.assertEqual(self.path.read_text(),original)

    def test_atomic_failure_preserves_previous_file_and_cleans_temp(self):
        self.store.save('live',defaults('live'));original=self.path.read_bytes()
        values=defaults('live');values['master']['power']=False
        with patch('studio_qt.preferences.os.replace',side_effect=OSError('disk failure')):
            self.assertFalse(self.store.save('live',values))
        self.assertEqual(self.path.read_bytes(),original)
        self.assertEqual(list(self.path.parent.iterdir()),[self.path])

    def test_tkinter_settings_refused(self):
        path=self.path.parent/'OliveRGB'/'settings.json';path.parent.mkdir();path.write_text('production')
        with self.assertRaises(ValueError):PreferencesStore(path)
        self.assertEqual(path.read_text(),'production')

    def test_restore_is_idle_and_snapshot_excludes_runtime(self):
        state=StudioState();values=defaults('demo');values['devices']['Corner']['color']='#123456'
        restore(state,values)
        self.assertEqual(state.mode,'Manual');self.assertFalse(state.playing)
        self.assertEqual(state.channels['Corner'].color,'#123456')
        result=snapshot(state,values['music']);self.assertEqual(result,values)
        self.assertNotIn('mode',result);self.assertNotIn('playing',result)


class PreferencesUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'qt.json'
        self.windows=[]

    def tearDown(self):
        from PySide6.QtTest import QTest
        for w in self.windows:w.close()
        for _ in range(100):
            self.app.processEvents();QTest.qWait(10)
            if all(not getattr(w,'_closing',False) or w._cleanup_done for w in self.windows):break
        self.assertTrue(all(not getattr(w,'_closing',False) or w._cleanup_done for w in self.windows))
        self.temp.cleanup()

    def demo(self):
        from studio_qt.app import StudioWindow
        w=StudioWindow(preferences_path=self.path);self.windows.append(w);return w

    def test_demo_restores_master_devices_and_music(self):
        w=self.demo();w.c.set('master_brightness',.37);w.c.set('master_power',False)
        w.c.channel('Corner','brightness',.22);w.c.channel('Corner','power',False)
        w.c.channel('Hue','follow',False);w.c.set_hex('#123456')
        for key,value in [('sensitivity',.72),('smoothing',.41),('relationship','Same Color'),('separation',.83)]:w.c.set(key,value)
        w.close();other=self.demo()
        self.assertEqual(other.c.state.master_brightness,.37);self.assertFalse(other.c.state.master_power)
        self.assertEqual(other.c.state.channels['Corner'].brightness,.22);self.assertFalse(other.c.state.channels['Corner'].power)
        self.assertEqual(other.c.state.channels['Hue'].color,'#123456');self.assertFalse(other.c.state.channels['Hue'].follow)
        self.assertEqual(other.c.state.sensitivity,.72);self.assertEqual(other.c.state.smoothing,.41)
        self.assertEqual(other.c.state.relationship,'Same Color');self.assertEqual(other.c.state.separation,.83)
        self.assertEqual(other.c.state.mode,'Manual');self.assertFalse(other.c.state.playing)

    def test_debounce_and_hidden_inspector_link(self):
        from PySide6.QtTest import QTest
        w=self.demo();w.c.set('master_brightness',.31)
        QTest.qWait(300);self.assertEqual(PreferencesStore(self.path).load('demo')['master']['brightness'],.31)
        w.toggle_inspector();self.assertTrue(w.workspace.inspector_collapsed)
        self.assertTrue(w.open_tab('Music'));self.assertFalse(w.workspace.inspector_collapsed)

    def test_live_restore_does_not_invoke_factories_and_links_are_gated(self):
        from studio_qt.music_window import MusicLiveWindow
        from unittest.mock import Mock
        values=defaults('live');values['music'].update(profile='MGK',palette='Charli xcx — BRAT',sensitivity=2.31,smoothing=.77,relationship='Same Color',separation=.64,participation={'Corner':False,'Hue':True})
        PreferencesStore(self.path).save('live',values)
        worker=Mock(side_effect=AssertionError('Unexpected Bluetooth startup'))
        hue=Mock(side_effect=AssertionError('Unexpected Hue startup'))
        engine=Mock(side_effect=AssertionError('Unexpected audio startup'))
        w=MusicLiveWindow(preferences_path=self.path,worker_factory=worker,hue_factory=hue,engine_factory=engine)
        self.windows.append(w)
        self.assertEqual(w.music_preferences(),values['music'])
        self.assertEqual(w.c.adapter.participation,values['music']['participation'])
        worker.assert_not_called();hue.assert_not_called();engine.assert_not_called()
        self.assertFalse(w.runtime.busy);self.assertFalse(w.c.adapter.music_active)
        self.assertFalse(w.c.adapter.session.wanted);self.assertFalse(w.c.adapter.hue.wanted)
        self.assertEqual(w.c.state.mode,'Manual');self.assertTrue(w.open_tab('Setup'));self.assertTrue(w.open_tab('Music'))
        for _,link in w.inspector_links.values():self.assertTrue(link.isEnabled())
        self.assertIn('unavailable',w.page_notes['Screen'].text())
        with patch.object(w.runtime,'start',return_value=True) as start, patch.object(w.c.adapter,'start_music') as route:
            w.start_music();start.assert_called_once_with('MGK',2.31,.77,'Charli xcx — BRAT')
            route.assert_called_once_with('Same Color',.64)
        w.stop_music();w.close()
        self.assertEqual(PreferencesStore(self.path).load('live')['music'],values['music'])


if __name__=='__main__':unittest.main()
