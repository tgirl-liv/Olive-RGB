"""Family routing uses the real preserved worker with simulated controller I/O."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtTest import QTest
import test_music_live as fixtures
from test_corner_live import FakeLamp
from studio_qt import corner_worker
from studio_qt.device_families import LOTUS,LEDBLE,identity_for
from studio_qt.preferences import PreferencesStore,defaults,validate
from studio_qt.music_window import MusicLiveWindow


class FamilyPreferencesTests(unittest.TestCase):
    def test_old_preferences_default_lotus_and_validate_exact_identities(self):
        self.assertEqual(validate({},'live')['controller'],{'family':LOTUS,'identity':identity_for(LOTUS)})
        self.assertNotIn('controller',defaults('demo'))
        data=defaults('live');data['controller']={'family':LEDBLE}
        self.assertEqual(validate(data,'live')['controller']['identity'],{'name':'LEDBLE-00-0806'})
        for controller in ({'family':'Other'},{'family':LEDBLE,'identity':identity_for(LOTUS)},None):
            data['controller']=controller
            with self.assertRaises(ValueError):validate(data,'live')
        from ledble_driver import LEDBLEDriver
        self.assertEqual(identity_for(LEDBLE)['name'],LEDBLEDriver.DEVICE_NAME)


class FamilySessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.MusicTests.setUpClass()
    def setUp(self):
        self.f=fixtures.MusicTests();self.f.setUp();self.strips=[];self.options={}
        def strip():
            lamp=FakeLamp();lamp.client.address='Windows-strip-device-UUID'
            for key,value in self.options.items():setattr(lamp,key,value)
            self.strips.append(lamp);return lamp
        self.patch=patch.object(corner_worker,'LEDBLEDriver',side_effect=strip);self.patch.start()
    def tearDown(self):
        try:
            self.f.tearDown()
            for strip in self.strips:self.assertEqual(strip.disconnect_overlaps,0)
        finally:self.patch.stop()
    def wait(self,predicate):self.f.wait(predicate)
    def connect(self,a):a.connect_corner();self.wait(lambda:a.connected)

    def test_selection_never_connects_and_reconnect_reuses_worker_loop(self):
        a=self.f.adapter();a.select_family(LEDBLE);QTest.qWait(60)
        self.assertFalse(a.session.wanted);self.assertFalse(self.strips);self.assertFalse(self.f.f.corner.workers)
        self.connect(a);w=a.session.worker;loop=w.loop
        self.assertIs(w.lamp,self.strips[0]);self.assertEqual(w.device_family,LEDBLE)
        a.disconnect_corner();self.wait(lambda:a.status=='disconnected');self.connect(a)
        self.assertIs(a.session.worker,w);self.assertIs(w.loop,loop);self.assertEqual(len(self.strips),1)
        self.assertFalse(any(c[0]=='rgb' for c in self.strips[0].calls))

    def test_switch_disconnects_then_requires_explicit_connect_and_returns_lotus(self):
        a=self.f.adapter();self.connect(a);w=a.session.worker;lotus=w.lamp
        a.set_rgb('Corner','#FF0000');a.select_family(LEDBLE)
        self.wait(lambda:not lotus.client.is_connected);self.assertIsNone(a.session.pending)
        QTest.qWait(100);self.assertFalse(self.strips);self.assertFalse(a.session.wanted)
        self.connect(a);self.assertIs(w.lamp,self.strips[0]);self.assertFalse(any(c[0]=='rgb' for c in self.strips[0].calls))
        a.select_family(LOTUS);self.connect(a);self.assertIs(w.lamp,lotus)
        self.assertFalse(self.strips[0].client.is_connected);self.assertEqual(len(self.f.f.corner.workers),1)

    def test_switch_during_write_discards_pending_and_cancels_before_disconnect(self):
        a=self.f.adapter();a.select_family(LEDBLE);self.options['write_delay']=1;self.connect(a)
        old=self.strips[0];a.set_rgb('Corner','#FF0000');self.wait(lambda:old.active>0)
        a.set_rgb('Corner','#00FF00');a.select_family(LOTUS);self.connect(a)
        self.assertEqual(old.disconnect_overlaps,0)
        self.assertFalse(any(c[0]=='rgb' and c[2][1]>0 for c in old.calls))
        self.assertFalse(any(c[0]=='rgb' for c in a.session.worker.lamp.calls))

    def test_switch_during_connect_invalidates_old_completion(self):
        self.options['connect_delay']=1;a=self.f.adapter();a.select_family(LEDBLE);a.connect_corner()
        self.wait(lambda:bool(self.strips));a.select_family(LOTUS);self.connect(a)
        self.assertEqual(a.session.worker.device_family,LOTUS);self.assertFalse(self.strips[0].client.is_connected)
        self.assertEqual(a.session.worker.lamp.client.address,identity_for(LOTUS)['address'])

    def test_strip_connect_and_write_failure_allow_only_explicit_retry(self):
        a=self.f.adapter();a.select_family(LEDBLE);self.options['failure']=True;a.connect_corner()
        self.wait(lambda:a.status=='error');self.assertFalse(a.connected);QTest.qWait(100)
        self.assertEqual(len([c for c in self.strips[0].calls if c[0]=='connect']),1)
        self.strips[0].failure=False;self.connect(a);self.strips[0].fail_write=True
        a.set_rgb('Corner','#FF0000');self.wait(lambda:a.status=='error');self.assertFalse(a.connected)
        self.assertFalse(a.session.wanted)

    def test_uncertain_cleanup_prevents_replacement_connection(self):
        a=self.f.adapter();a.select_family(LEDBLE);self.connect(a)
        async def fail():raise OSError('uncertain disconnect')
        self.strips[0].disconnect=fail;self.strips[0].client.disconnect=fail
        a.select_family(LOTUS);a.connect_corner()
        self.wait(lambda:a.session.closed)
        self.assertFalse(a.session.wanted);self.assertEqual(a.session.worker.device_family,LEDBLE)
        self.assertFalse(any(c[0]=='connect' for c in self.f.f.corner.lamps[0].calls))
        # Restore simulated cleanup so teardown does not retain a fake link.
        self.strips[0].client.is_connected=False

    def test_close_during_strip_connect_drains_worker_and_lifecycle(self):
        self.options['connect_delay']=1;w=self.f.window();w.family_selector.setCurrentText(LEDBLE)
        w.connect_corner();self.wait(lambda:bool(self.strips));w.close()
        self.wait(lambda:w._cleanup_done and not w.c.adapter.session.thread.is_alive())
        self.assertFalse(w.c.adapter.session.worker.thread.is_alive())
        self.assertFalse(self.strips[0].client.is_connected)

    def test_close_during_strip_write_discards_pending_and_drains_io(self):
        self.options['write_delay']=1;w=self.f.window();w.family_selector.setCurrentText(LEDBLE)
        self.connect(w.c.adapter);w.c.adapter.set_rgb('Corner','#FF0000')
        self.wait(lambda:self.strips[0].active>0);w.c.adapter.set_rgb('Corner','#00FF00');w.close()
        self.wait(lambda:w._cleanup_done and not w.c.adapter.session.thread.is_alive())
        self.assertEqual(self.strips[0].active,0);self.assertFalse(self.strips[0].client.is_connected)
        self.assertFalse(any(c[0]=='rgb' and c[2][1]>0 for c in self.strips[0].calls))

    def test_ui_family_and_identity_persist_without_starting_hardware(self):
        w=self.f.window();w.family_selector.setCurrentText(LEDBLE)
        self.assertEqual(w.c.state.channels['Corner'].name,'LEDBLE Strip')
        self.assertEqual(w.inspector.device.itemText(w.inspector.device.findData('Corner')),'LEDBLE Strip')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'preferences-v1.json';w.preferences_store=PreferencesStore(path);w.save_preferences()
            self.assertEqual(PreferencesStore(path).load('live')['controller'],{'family':LEDBLE,'identity':identity_for(LEDBLE)})
            restored=MusicLiveWindow(preferences_path=path)
            try:
                self.assertEqual(restored.family_selector.currentText(),LEDBLE);self.assertEqual(restored.c.adapter.session.family,LEDBLE)
                self.assertFalse(restored.runtime.busy);self.assertFalse(restored.c.adapter.session.wanted);self.assertIsNone(restored.c.adapter.session.worker)
            finally:restored.close()

    def test_music_ownership_hue_and_device_controls_survive_family_switch(self):
        w=self.f.window();w.family_selector.setCurrentText(LEDBLE);self.connect(w.c.adapter)
        self.f.f.connect_hue(w.c.adapter);w.start_music();self.wait(lambda:w.c.adapter.last_frame is not None)
        engine=w.runtime.engine;worker=w.c.adapter.session.worker
        self.assertTrue(w.c.adapter.owns('Corner'));self.assertTrue(w.c.adapter.owns('Hue'))
        with self.assertRaises(ValueError):w.c.adapter.set_rgb('Corner','#FFFFFF')
        w.c.adapter.set_power('Corner',False);self.wait(lambda:any(c[0]=='rgb' and c[2]==(0,0,0) for c in self.strips[0].calls))
        w.family_selector.setCurrentText(LOTUS);self.connect(w.c.adapter)
        self.assertIs(w.runtime.engine,engine);self.assertIs(w.c.adapter.session.worker,worker)
        self.assertTrue(w.c.adapter.hue_connected);self.assertTrue(w.c.adapter.owns('Corner'))
        w.stop_music();self.assertFalse(w.c.adapter.owns('Corner'))

    def test_demo_never_creates_family_selector_or_live_workers(self):
        from studio_qt.app import StudioWindow
        w=StudioWindow()
        try:
            self.assertFalse(hasattr(w,'family_selector'));self.assertFalse(self.strips);self.assertFalse(self.f.f.corner.workers)
        finally:w.close()

    def test_ledble_writes_use_existing_cadence_and_software_power_only(self):
        a=self.f.adapter();a.select_family(LEDBLE);self.connect(a)
        worker=a.session.worker;accepted=[];original=worker.set_rgb
        def record(*rgb,**kwargs):
            previous=worker.last_send_time;original(*rgb,**kwargs)
            if worker.last_send_time!=previous:accepted.append(worker.last_send_time)
        worker.set_rgb=record
        a.set_master(True,1);a.set_brightness('Corner',1)
        for n in range(50):a.set_rgb('Corner',f'#{n:02X}0000')
        self.wait(lambda:any(c[0]=='rgb' and c[2]==(49,0,0) for c in self.strips[0].calls))
        a.set_power('Corner',False);self.wait(lambda:any(c[0]=='rgb' and c[2]==(0,0,0) for c in self.strips[0].calls))
        # Measure the limiter's accepted timestamps, not task scheduling jitter.
        self.assertGreaterEqual(len(accepted),2)
        self.assertTrue(all(b-a>=.25 for a,b in zip(accepted,accepted[1:])))
        self.assertEqual(self.strips[0].max_active,1)


if __name__=='__main__':unittest.main()
