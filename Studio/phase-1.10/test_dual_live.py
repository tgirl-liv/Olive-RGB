"""No hardware: real Corner worker + fake lamp, fake Hue driver at its boundary."""
import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QCheckBox, QSpinBox, QLineEdit, QSlider, QComboBox
import test_corner_live as corner_tests
from studio_qt.dual_adapter import DualLightingAdapter
from studio_qt.dual_window import DualLiveWindow
from studio_qt.hue_session import HueEvent


class FakeHue:
    def __init__(self, identity, emit, options):
        self.identity = dict(identity, address_hint='MOCK-HUE', zigbee_address='mock-stable')
        self.emit = emit;self.options = options;self.connected = False
        self.capabilities = dict(power=True, brightness=True, color=True, temperature=True)
        self.capabilities.update(options.get('caps', {}))
        self.light = SimpleNamespace(poll_brightness=self.poll_brightness)
        self.calls = [];self.active = 0;self.max_active = 0;self.overlap = 0
    async def poll_brightness(self):return 128
    async def connect(self):
        self.calls.append(('connect', time.monotonic()))
        await asyncio.sleep(self.options.get('connect_delay', .01))
        if self.options.get('fail_connect'):raise OSError('mock Hue authentication failure')
        self.connected = not self.options.get('false_connected', False)
        self.emit('capabilities', dict(self.capabilities));self.emit('observed_power', True)
    async def write(self, key, value):
        self.active += 1;self.max_active = max(self.max_active, self.active)
        self.calls.append(('write', time.monotonic(), key, value))
        try:
            await asyncio.sleep(self.options.get('write_delay', .01))
            if self.options.get('fail_write'):raise OSError('mock Hue write failure')
        finally:self.active -= 1
    async def disconnect(self):
        self.overlap += bool(self.active)
        if self.options.get('fail_disconnect'):raise OSError('mock disconnect failed')
        self.connected = False;self.calls.append(('disconnect', time.monotonic()))


class DualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        corner_tests.LiveTests.setUpClass();cls.app = QApplication.instance()
    def setUp(self):
        self.corner = corner_tests.LiveTests();self.corner.setUp()
        self.options = {};self.drivers = [];self.adapters = [];self.windows = []
    def hue_factory(self, identity, emit):
        driver = FakeHue(identity, emit, self.options);self.drivers.append(driver);return driver
    def adapter(self):
        a = DualLightingAdapter(worker_factory=self.corner.factory, hue_factory=self.hue_factory, hue_identity={'name':'Tv lamp'})
        self.adapters.append(a);self.corner.adapters.append(a);return a
    def window(self):
        w = DualLiveWindow(worker_factory=self.corner.factory, hue_factory=self.hue_factory, hue_identity={'name':'Tv lamp'})
        self.windows.append(w);self.adapters.append(w.c.adapter);self.corner.adapters.append(w.c.adapter)
        self.corner.windows.append(w);w.show();self.app.processEvents();return w
    def wait(self, predicate, timeout=3500):self.corner.wait(predicate, timeout)
    def connect_hue(self, a):a.connect_hue();self.wait(lambda:a.hue_connected)
    def connect_corner(self, a):a.connect_corner();self.wait(lambda:a.connected)
    def wrote(self, key, value):return any(c[0]=='write' and c[2:]==(key,value) for d in self.drivers for c in d.calls)
    def tearDown(self):
        for w in self.windows:w.close()
        for a in self.adapters:a.close()
        self.wait(lambda:all(a.hue.thread is None or not a.hue.thread.is_alive() for a in self.adapters), 5000)
        self.corner.tearDown()
        for d in self.drivers:self.assertEqual(d.overlap, 0)
    def test_live_open_no_workers_no_connections(self):
        w = self.window();QTest.qWait(60)
        self.assertFalse(self.corner.workers);self.assertFalse(self.drivers)
        self.assertFalse(w.channels['Hue'].level.isEnabled())
    def test_hue_only_observed_state_and_no_initial_write(self):
        a = self.adapter();self.connect_hue(a);QTest.qWait(100)
        self.assertFalse(self.corner.workers);self.assertFalse(a.connected)
        self.assertEqual(a.hue_observed, {'power':True,'brightness':128})
        self.assertAlmostEqual(a.state.channels['Hue'].brightness, 128/254)
        self.assertEqual([c[0] for c in self.drivers[0].calls], ['connect'])
    def test_corner_only_does_not_start_hue(self):
        a = self.adapter();self.connect_corner(a);a.set_rgb('Corner','#FF0000')
        self.wait(lambda:any(x[0]=='rgb' for x in self.corner.lamps[0].calls));self.assertFalse(self.drivers)
    def test_both_connected_independent_rgb(self):
        a = self.adapter();self.connect_corner(a);self.connect_hue(a)
        a.set_rgb('Hue','#00FF00');self.wait(lambda:self.wrote('color',(0,255,0)))
        self.assertFalse(any(x[0]=='rgb' for x in self.corner.lamps[0].calls))
        n = len(self.drivers[0].calls);a.set_rgb('Corner','#FF0000')
        self.wait(lambda:any(x[0]=='rgb' for x in self.corner.lamps[0].calls));self.assertEqual(len(self.drivers[0].calls),n)
    def test_follow_master_no_double_scaling_and_independent_restore(self):
        a = self.adapter();self.connect_hue(a)
        a.set_brightness('Hue',.5);a.set_rgb('Hue','#800000');a.set_master(True,.5)
        self.wait(lambda:self.wrote('brightness',64))
        a.set_follow_master('Hue',True);self.wait(lambda:self.wrote('brightness',32))
        self.assertTrue(self.wrote('color',(128,0,0)))
        a.set_follow_master('Hue',False);self.wait(lambda:self.drivers[0].calls[-1][2:]==('brightness',64))
        n = len(self.drivers[0].calls);a.set_master(False,.1);QTest.qWait(300);self.assertEqual(len(self.drivers[0].calls),n)
        self.assertEqual(a.state.channels['Hue'].brightness,.5)
    def test_master_power_both_and_follow_off(self):
        a=self.adapter();self.connect_corner(a);self.connect_hue(a);a.set_follow_master('Hue',True)
        a.set_master(False,.5);self.wait(lambda:self.wrote('power',False))
        self.wait(lambda:any(x[0]=='rgb' and x[2]==(0,0,0) for x in self.corner.lamps[0].calls))
        a.set_master(True,.5);self.wait(lambda:self.wrote('power',True))
    def test_hue_disconnect_reconnect_no_corner_change(self):
        a=self.adapter();self.connect_corner(a);self.connect_hue(a);thread=a.hue.thread
        a.disconnect_hue();self.wait(lambda:a.hue_status=='disconnected');self.assertTrue(a.connected)
        self.connect_hue(a);self.assertIs(a.hue.thread,thread);self.assertEqual(len(self.corner.workers),1)
    def test_immediate_hue_disconnect_reconnect(self):
        a=self.adapter();self.connect_hue(a);a.disconnect_hue();a.connect_hue();self.wait(lambda:a.hue_connected)
        self.assertEqual(len(self.drivers),2);self.assertFalse(self.drivers[0].connected)
    def test_hue_failure_corner_still_works_no_retry(self):
        self.options['fail_connect']=True;a=self.adapter();self.connect_corner(a);a.connect_hue()
        self.wait(lambda:a.hue_status=='error');self.assertIn('authentication',a.hue_error)
        a.set_rgb('Corner','#FF0000');self.wait(lambda:any(x[0]=='rgb' for x in self.corner.lamps[0].calls))
        QTest.qWait(150);self.assertEqual(len(self.drivers),1);self.assertTrue(a.connected)
    def test_corner_failure_hue_still_works(self):
        self.corner.settings['failure']=True;a=self.adapter();self.connect_hue(a);a.connect_corner()
        self.wait(lambda:a.status=='error');a.set_rgb('Hue','#0000FF');self.wait(lambda:self.wrote('color',(0,0,255)));self.assertTrue(a.hue_connected)
    def test_hue_loss_no_reconnect_or_corner_interruption(self):
        a=self.adapter();self.connect_corner(a);self.connect_hue(a);self.drivers[0].connected=False
        self.wait(lambda:a.hue_status=='error');QTest.qWait(100);self.assertEqual(len(self.drivers),1);self.assertTrue(a.connected)
    def test_corner_loss_hue_unaffected(self):
        a=self.adapter();self.connect_corner(a);self.connect_hue(a);self.corner.lamps[0].client.is_connected=False
        self.wait(lambda:a.status=='error');a.set_power('Hue',False);self.wait(lambda:self.wrote('power',False))
    def test_capability_gates_and_no_fabricated_rgb(self):
        self.options['caps']={'color':False,'brightness':False};w=self.window();self.connect_hue(w.c.adapter);w.c.select_channel('Hue');self.app.processEvents()
        self.assertTrue(w.inspector.power.isEnabled());self.assertFalse(w.inspector.brightness.isEnabled());self.assertFalse(w.inspector.wheel.isEnabled())
        self.assertIn('RGB is requested',w.hue_note.text())
        with self.assertRaises(ValueError):w.c.adapter.set_rgb('Hue','#00FF00')
        with self.assertRaises(ValueError):w.c.adapter.set_brightness('Hue',.5)
        w.c.adapter.set_power('Hue',False);self.wait(lambda:self.wrote('power',False))
        self.assertFalse(any(c[0]=='write' and c[2]!='power' for c in self.drivers[0].calls))
    def test_rapid_changes_serialized_coalesced_4hz(self):
        self.options['write_delay']=.1;a=self.adapter();self.connect_hue(a)
        for n in range(200):a.set_rgb('Hue','#%02X0000'%(n+20));a.set_brightness('Hue',(n+1)/200)
        self.wait(lambda:self.wrote('color',(219,0,0)));self.wait(lambda:self.wrote('brightness',218))
        writes=[c for c in self.drivers[0].calls if c[0]=='write']
        self.assertLessEqual(len(writes),5);self.assertEqual(self.drivers[0].max_active,1)
        self.assertTrue(all(b[1]-a[1]>=.245 for a,b in zip(writes,writes[1:])))
    def test_stale_hue_status_and_capabilities_ignored(self):
        a=self.adapter();self.connect_hue(a);old=a.hue.generation;a.disconnect_hue()
        a._hue_incoming.emit(HueEvent(old,'status','connected'));a._hue_incoming.emit(HueEvent(old,'capabilities',{'color':True}))
        self.app.processEvents();self.assertFalse(a.hue_connected);self.assertFalse(a.hue_caps)
    def test_disconnect_during_write_drops_pending(self):
        self.options['write_delay']=2;a=self.adapter();self.connect_hue(a);a.set_rgb('Hue','#FF0000')
        self.wait(lambda:self.drivers[0].active>0);a.set_rgb('Hue','#00FF00');a.disconnect_hue()
        self.wait(lambda:a.hue_status=='disconnected');self.assertFalse(self.wrote('color',(0,255,0)))
        self.options['write_delay']=.01;self.connect_hue(a);QTest.qWait(80);self.assertFalse(self.wrote('color',(0,255,0)))
    def test_write_failure_not_simulated_success(self):
        self.options['fail_write']=True;a=self.adapter();self.connect_hue(a);a.set_power('Hue',False)
        self.wait(lambda:a.hue_status=='error');self.assertFalse(a.hue_connected);self.assertIn('write failure',a.hue_error)
    def test_disconnect_failure_is_terminal_and_corner_unaffected(self):
        a=self.adapter();self.connect_corner(a);self.connect_hue(a);self.options['fail_disconnect']=True
        a.disconnect_hue();self.wait(lambda:a.hue.closed);self.app.processEvents()
        self.assertEqual(a.hue_status,'error');self.assertIn('disconnect failed',a.hue_error)
        a.connect_hue();QTest.qWait(60);self.assertEqual(len(self.drivers),1);self.assertTrue(a.connected)
    def test_false_driver_success_rejected(self):
        self.options['false_connected']=True;a=self.adapter();a.connect_hue();self.wait(lambda:a.hue_status=='error');self.assertFalse(a.hue_connected)
    def test_close_while_connecting_gui_responsive(self):
        self.options['connect_delay']=2;self.corner.settings['connect_delay']=2;w=self.window()
        w.connect_hue();w.connect_corner();counter=[];timer=QTimer();timer.timeout.connect(lambda:counter.append(1));timer.start(10)
        QTest.qWait(300);self.assertGreater(len(counter),5)
        start=time.monotonic();w.close();self.assertLess(time.monotonic()-start,.1)
        self.wait(lambda:w._cleanup_done);timer.stop();self.assertFalse(w.timer.isActive())
    def test_close_during_hue_write_and_corner_pending(self):
        self.options['write_delay']=2;self.corner.settings['write_delay']=2;w=self.window();a=w.c.adapter;self.connect_hue(a);self.connect_corner(a)
        a.set_rgb('Hue','#FF0000');a.set_rgb('Corner','#FF0000');self.wait(lambda:self.drivers[0].active>0)
        a.set_rgb('Hue','#00FF00');w.close();self.wait(lambda:w._cleanup_done)
        self.assertFalse(self.wrote('color',(0,255,0)));self.assertFalse(self.drivers[0].connected)
    def test_close_without_connect_and_hue_only(self):
        w=self.window();w.close();self.wait(lambda:w._cleanup_done)
        w=self.window();self.connect_hue(w.c.adapter);w.close();self.wait(lambda:w._cleanup_done)
    def test_demo_isolation(self):
        from studio_qt.app import StudioWindow
        with patch('studio_qt.hue_session.driver_factory',side_effect=AssertionError('DEMO hardware')):
            w=StudioWindow();w.show();self.app.processEvents();w.close()
        self.assertFalse(self.drivers);self.assertFalse(self.corner.workers)
    def test_layout_and_controls_all_sizes(self):
        w=self.window();self.connect_hue(w.c.adapter);w.c.select_channel('Hue')
        for size in [(1440,900),(1280,800),(1080,760),(800,600)]:
            w.resize(*size);self.app.processEvents();self.assertEqual((w.width(),w.height()),size)
            self.assertTrue(w.inspector.wheel.isEnabled());self.assertTrue(w.master.level.isEnabled())
            for c in w.findChildren(QWidget):
                if c.isVisible() and isinstance(c,(QPushButton,QCheckBox,QSpinBox,QLineEdit,QSlider,QComboBox)):
                    self.assertTrue(c.parentWidget().rect().contains(c.geometry()),(size,c.accessibleName()))


class IdentityTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.folder=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.path=Path(self.folder.name)/'settings.json'
    def tearDown(self):self.folder.cleanup()
    def test_missing_identity_uses_existing_default_without_creating_settings(self):
        from studio_qt.hue_identity import load_hue_identity
        self.assertEqual(load_hue_identity(self.path),{'name':'Tv lamp'});self.assertFalse(self.path.exists())
    def test_saved_identity_read_only_and_unrelated_settings_ignored(self):
        import json
        from studio_qt.hue_identity import load_hue_identity
        identity={'name':'Tv lamp','address_hint':'SAVED','zigbee_address':'stable'}
        self.path.write_text(json.dumps({'hue':{'identity':identity,'power':False},'master':{'brightness':.2}}))
        before=self.path.read_bytes();self.assertEqual(load_hue_identity(self.path),identity);self.assertEqual(self.path.read_bytes(),before)
    def test_corrupt_or_invalid_identity_refuses_silent_default(self):
        from studio_qt.hue_identity import load_hue_identity
        for content in ['{','[]','{"hue":{"identity":{"zigbee_address":false}}}']:
            self.path.write_text(content)
            with self.assertRaises(ValueError):load_hue_identity(self.path)
            self.assertEqual(self.path.read_text(),content)

if __name__=='__main__':unittest.main()
