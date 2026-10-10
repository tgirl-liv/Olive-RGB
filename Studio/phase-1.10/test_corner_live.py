"""Actual isolated worker and actor, with only LotusLamp hardware replaced.
Run in the existing BLE Python environment with PySide6 installed/available.
No real BleakClient is constructed and no BLE scan is performed.
"""
import ast,asyncio,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QDialog,QRadioButton
from PySide6.QtTest import QTest
from studio_qt import corner_worker
from studio_qt.corner_adapter import CornerLampAdapter
from studio_qt.corner_session import CornerEvent,LAMP_ADDRESS
from studio_qt.live_window import LiveStudioWindow,choose_startup_mode


class FakeLamp:
    connect_delay=.01
    write_delay=.01
    failure=False
    wrong_address=False
    fail_write=False
    false_result=False
    def __init__(self,**kwargs):
        self.calls=[];self.active=0;self.max_active=0;self.disconnect_overlaps=0
        self.client=SimpleNamespace(is_connected=False,address='00:00:00:00:00:00' if self.wrong_address else LAMP_ADDRESS,disconnect=self.disconnect)
    async def connect(self):
        self.calls.append(('connect',time.monotonic()))
        await asyncio.sleep(self.connect_delay)
        if self.failure:raise OSError('mock connection failed')
        if self.false_result:return False
        self.client.is_connected=True
    async def disconnect(self):
        if self.active:self.disconnect_overlaps+=1
        self.client.is_connected=False;self.calls.append(('disconnect',time.monotonic()))
    async def set_rgb(self,*rgb):
        self.active+=1;self.max_active=max(self.active,self.max_active)
        self.calls.append(('rgb',time.monotonic(),rgb))
        try:
            await asyncio.sleep(self.write_delay)
            if self.fail_write:raise OSError('mock write failed')
        finally:self.active-=1


class LiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        self.lamps=[];self.workers=[];self.adapters=[];self.windows=[]
        self.thread_errors=[]
        def factory(status,log):
            worker=corner_worker.BluetoothWorker(status,log);self.workers.append(worker);return worker
        self.factory=factory
        self.patches=[patch.object(corner_worker,'LotusLamp',self.make_lamp),patch.object(corner_worker.BluetoothWorker,'_debug',lambda *args:None),
                      patch.object(threading,'excepthook',lambda error:self.thread_errors.append(error.exc_value))]
        for p in self.patches:p.start()
        self.settings={}
    def make_lamp(self,**kwargs):
        lamp=FakeLamp(**kwargs)
        for key,value in self.settings.items():setattr(lamp,key,value)
        if self.settings.get('wrong_address'):lamp.client.address='00:00:00:00:00:00'
        self.lamps.append(lamp);return lamp
    def adapter(self,**kwargs):
        a=CornerLampAdapter(worker_factory=self.factory,**kwargs);self.adapters.append(a);return a
    def wait(self,predicate,timeout=3500):
        deadline=time.monotonic()+timeout/1000
        while time.monotonic()<deadline:
            self.app.processEvents()
            if predicate():return
            QTest.qWait(10)
        self.fail('Timed out waiting for condition')
    def connect(self,a):a.connect_corner();self.wait(lambda:a.connected)
    def tearDown(self):
        try:
            for window in self.windows:window.close()
            for adapter in self.adapters:adapter.close()
            self.wait(lambda:all(not w.thread.is_alive() for w in self.workers)
                      and all(a.session.thread is None or not a.session.thread.is_alive() for a in self.adapters)
                      and all(w._cleanup_done for w in self.windows),timeout=5000)
            self.app.processEvents()
            for lamp in self.lamps:self.assertEqual(lamp.disconnect_overlaps,0)
            self.assertEqual(self.thread_errors,[], 'Uncaught lifecycle/worker exception')
            for window in self.windows:window.deleteLater()
        finally:
            for p in reversed(self.patches):p.stop()
    def test_worker_class_exactly_preserved(self):
        root=Path(__file__).parent
        def worker(path):return next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.ClassDef) and n.name=='BluetoothWorker')
        self.assertEqual(ast.dump(worker(root/'olive_rgb.py')),ast.dump(worker(root/'studio_qt/corner_worker.py')))
    def test_live_open_does_not_start_worker(self):
        a=self.adapter();a.discover_devices();QTest.qWait(60);self.assertEqual(self.workers,[]);self.assertFalse(a.connected)
    def test_connect_disconnect_and_same_worker_reused(self):
        a=self.adapter();self.connect(a);self.assertEqual(len(self.workers),1)
        self.assertEqual([x[0] for x in self.lamps[0].calls],['connect'])
        a.disconnect_corner();self.wait(lambda:a.status=='disconnected');self.connect(a)
        self.assertEqual(len(self.workers),1)
    def test_failed_connection_is_error_no_retry(self):
        self.settings['failure']=True;a=self.adapter();a.connect_corner();self.wait(lambda:a.status=='error')
        QTest.qWait(250);self.assertFalse(a.connected);self.assertFalse(a.session.wanted)
        self.assertEqual(sum(c[0]=='connect' for c in self.lamps[0].calls),1)
        self.assertIn('mock connection failed',a.message)
    def test_immediate_disconnect_reconnect_replaces_old_connection(self):
        a=self.adapter();self.connect(a)
        a.disconnect_corner();a.connect_corner();self.wait(lambda:a.connected)
        self.assertEqual(len(self.workers),1)
        self.assertEqual([x[0] for x in self.lamps[0].calls],['connect','disconnect','connect'])
    def test_wrong_address_rejected(self):
        self.settings['wrong_address']=True;a=self.adapter();a.connect_corner();self.wait(lambda:a.status=='error')
        self.assertFalse(a.connected);self.assertIn('does not match',a.message)
    def test_rapid_colors_coalesce_latest_and_limit_rate(self):
        self.settings['write_delay']=.15;a=self.adapter();self.connect(a)
        a.set_master(True,1);a.set_brightness('Corner',1)
        for color in ['#FF0000','#00FF00','#0000FF']*80:a.set_rgb('Corner',color)
        self.wait(lambda:any(x[0]=='rgb' and x[2]==(0,0,255) for x in self.lamps[0].calls))
        a.set_rgb('Corner','#FF0000');self.wait(lambda:any(x[0]=='rgb' and x[2]==(255,0,0) for x in self.lamps[0].calls))
        writes=[x for x in self.lamps[0].calls if x[0]=='rgb'];self.assertLess(len(writes),6)
        self.assertTrue(all(b[1]-a[1]>=.245 for a,b in zip(writes,writes[1:])))
        self.assertEqual(self.lamps[0].max_active,1)
    def test_brightness_and_follow_master(self):
        a=self.adapter();self.connect(a);a.set_rgb('Corner','#FF0000');a.set_brightness('Corner',.5);a.set_master(True,.5)
        self.wait(lambda:any(x[0]=='rgb' and x[2]==(64,0,0) for x in self.lamps[0].calls))
        a.set_follow_master('Corner',False)
        self.wait(lambda:any(x[0]=='rgb' and x[2]==(128,0,0) for x in self.lamps[0].calls))
    def test_software_power_off_and_restore(self):
        a=self.adapter();self.connect(a);a.set_rgb('Corner','#FF0000');a.set_brightness('Corner',1);a.set_master(True,1);a.set_power('Corner',False)
        self.wait(lambda:any(x[0]=='rgb' and x[2]==(0,0,0) for x in self.lamps[0].calls))
        a.set_power('Corner',True);self.wait(lambda:any(x[0]=='rgb' and x[2]==(255,0,0) for x in self.lamps[0].calls))
    def test_unsupported_power_rejected_without_hardware(self):
        a=self.adapter(software_power=False)
        with self.assertRaises(ValueError):a.set_power('Corner',False)
        self.assertEqual(self.workers,[])
    def test_connection_loss_no_reconnect(self):
        a=self.adapter();self.connect(a);self.lamps[0].client.is_connected=False
        self.wait(lambda:a.status=='error');QTest.qWait(100);self.assertFalse(a.connected)
        self.assertEqual(sum(c[0]=='connect' for c in self.lamps[0].calls),1)
    def test_write_failure_clears_connection(self):
        self.settings['fail_write']=True;a=self.adapter();self.connect(a);a.set_rgb('Corner','#FF0000')
        self.wait(lambda:a.status=='error');self.assertFalse(a.connected)
    def test_stale_status_ignored(self):
        a=self.adapter();self.connect(a);old=a.session.generation;a.disconnect_corner()
        a._incoming.emit(CornerEvent(old,'connected','stale'));self.app.processEvents();self.assertFalse(a.connected)
    def test_close_during_connect(self):
        self.settings['connect_delay']=2;a=self.adapter();a.connect_corner();self.wait(lambda:bool(self.lamps));start=time.monotonic();a.close()
        self.assertLess(time.monotonic()-start,.05);self.wait(lambda:not self.workers[0].thread.is_alive())
        self.assertFalse(a.connected);self.assertFalse(self.lamps[0].client.is_connected)
    def test_close_during_pending_write_no_new_writes(self):
        self.settings['write_delay']=2;a=self.adapter();self.connect(a);a.set_rgb('Corner','#FF0000')
        self.wait(lambda:self.lamps[0].active>0);a.set_rgb('Corner','#00FF00');a.close()
        before=sum(x[0]=='rgb' for x in self.lamps[0].calls)
        self.wait(lambda:not self.workers[0].thread.is_alive());self.assertEqual(sum(x[0]=='rgb' for x in self.lamps[0].calls),before)
    def test_disconnect_during_connect_then_manual_reconnect(self):
        self.settings['connect_delay']=1;a=self.adapter();a.connect_corner();self.wait(lambda:bool(self.lamps));a.disconnect_corner()
        self.wait(lambda:a.status=='disconnected');self.lamps[0].connect_delay=.01;self.connect(a)
        self.assertEqual(len(self.workers),1)
    def test_no_automatic_color_on_connection(self):
        a=self.adapter();a.set_rgb('Corner','#00FF00');self.connect(a);QTest.qWait(120)
        self.assertFalse(any(x[0]=='rgb' for x in self.lamps[0].calls))
    def test_scene_stages_offline_without_connecting_music_still_unsupported(self):
        a=self.adapter()
        a.apply_scene('Ocean Breeze')
        self.assertEqual(a.state.channels['Corner'].color,'#2365DD')
        with self.assertRaises(ValueError):a.apply_scene('missing')
        with self.assertRaises(ValueError):a.select_mode('Music')
        self.assertEqual(self.workers,[])
    def test_gui_remains_responsive_while_connecting_and_closing(self):
        self.settings['connect_delay']=2;w=LiveStudioWindow(worker_factory=self.factory);self.windows.append(w);self.adapters.append(w.c.adapter);w.show()
        self.assertEqual(self.workers,[]);self.app.processEvents();w.connect_button.click();counter=[];timer=QTimer();timer.timeout.connect(lambda:counter.append(1));timer.start(10)
        QTest.qWait(300);self.assertGreater(len(counter),5);self.assertFalse(w.c.adapter.connected)
        w.close();self.wait(lambda:w._cleanup_done);timer.stop();self.assertFalse(w.timer.isActive())
    def test_demo_default_startup_choice(self):
        def accept():
            for widget in self.app.topLevelWidgets():
                if isinstance(widget,QDialog):
                    checked=[x.text() for x in widget.findChildren(QRadioButton) if x.isChecked()]
                    self.assertTrue(checked[0].startswith('DEMO'));widget.accept()
        QTimer.singleShot(20,accept);self.assertEqual(choose_startup_mode(),'DEMO');self.assertEqual(self.workers,[])
    def test_live_widgets_receive_real_status_and_hue_stays_disabled(self):
        w=LiveStudioWindow(worker_factory=self.factory);self.windows.append(w);self.adapters.append(w.c.adapter);w.show();self.app.processEvents()
        w.connect_button.click();self.wait(lambda:w.c.adapter.connected);self.app.processEvents()
        self.assertIn('LIVE',w.inspector.status.text());self.assertNotIn('DEMO',w.mode_badge.text())
        self.assertTrue(w.channels['Corner'].level.isEnabled());self.assertFalse(w.channels['Hue'].level.isEnabled())
        self.assertFalse(w.master.modes['Music'].isEnabled());self.assertFalse(w.scenes.isEnabled())
        w.inspector.hex.setText('#00FF00');w.inspector.edit_hex()
        self.wait(lambda:any(x[0]=='rgb' and x[2][1]>0 and x[2][0]==0 for x in self.lamps[0].calls))
    def test_disconnect_invalidates_pending_colors(self):
        self.settings['write_delay']=1;a=self.adapter();self.connect(a);a.set_rgb('Corner','#FF0000')
        self.wait(lambda:self.lamps[0].active>0);a.set_rgb('Corner','#00FF00');a.disconnect_corner()
        self.wait(lambda:a.status=='disconnected')
        self.assertFalse(any(x[0]=='rgb' and x[2][1]>0 for x in self.lamps[0].calls))
        self.connect(a);QTest.qWait(100)
        self.assertFalse(any(x[0]=='rgb' and x[2][1]>0 for x in self.lamps[0].calls))
    def test_tiny_color_change_eventually_delivered(self):
        a=self.adapter();self.connect(a);a.set_master(True,1);a.set_brightness('Corner',1);a.set_rgb('Corner','#800000')
        self.wait(lambda:any(x[0]=='rgb' and x[2]==(128,0,0) for x in self.lamps[0].calls))
        a.set_rgb('Corner','#810000')
        self.wait(lambda:any(x[0]=='rgb' and x[2]==(129,0,0) for x in self.lamps[0].calls),timeout=2500)
    def test_missing_dependencies_are_live_error_not_demo(self):
        def missing(*args):raise ImportError('mock dependency missing')
        a=CornerLampAdapter(worker_factory=missing);self.adapters.append(a);a.connect_corner()
        self.wait(lambda:a.status=='error');self.assertTrue(a.live);self.assertIn('dependency missing',a.message)
    def test_connection_return_without_client_is_not_connected(self):
        self.settings['false_result']=True;a=self.adapter();a.connect_corner()
        self.wait(lambda:a.status=='error');self.assertFalse(a.connected)
    def test_live_controls_fit_all_target_sizes(self):
        from PySide6.QtWidgets import QWidget,QPushButton,QCheckBox,QSpinBox,QLineEdit,QSlider,QComboBox
        w=LiveStudioWindow(worker_factory=self.factory);self.windows.append(w);self.adapters.append(w.c.adapter);w.show()
        for size in [(1440,900),(1280,800),(1080,760),(800,600)]:
            w.resize(*size);self.app.processEvents();self.assertEqual((w.width(),w.height()),size)
            from studio_qt.app import ScenePanel
            for panel in w.findChildren(ScenePanel):self.assertIn('Unavailable in LIVE',panel.status.text())
            w.c.select_channel('Hue');self.app.processEvents();self.assertIn('NOT INTEGRATED',w.inspector.status.text())
            w.c.select_channel('Corner')
            for control in w.findChildren(QWidget):
                if isinstance(control,(QPushButton,QCheckBox,QSpinBox,QLineEdit,QSlider,QComboBox)) and control.isVisible():
                    self.assertTrue(control.parentWidget().rect().contains(control.geometry()),(size,control.accessibleName()))
    def test_demo_constructor_never_uses_live_factory(self):
        from studio_qt.app import StudioWindow
        w=StudioWindow();w.show();self.app.processEvents();w.close();self.assertEqual(self.workers,[])
    def test_close_before_connect_finishes_without_worker(self):
        w=LiveStudioWindow(worker_factory=self.factory);self.windows.append(w);self.adapters.append(w.c.adapter);w.show();w.close()
        self.wait(lambda:w._cleanup_done);self.assertEqual(self.workers,[])

if __name__=='__main__':unittest.main()
