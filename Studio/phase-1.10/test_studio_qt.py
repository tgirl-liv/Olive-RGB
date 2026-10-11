"""Hardware-free Qt regression tests. Run separately from the Tk test suite."""
import subprocess,sys,time,unittest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from studio_qt.app import StudioWindow
from studio_ui.state import SCENES,NAVIGATION


class QtStudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle('Fusion');cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):self.w=StudioWindow();self.w.show();self.app.processEvents();self.c=self.w.c
    def tearDown(self):self.w.close();self.w.deleteLater();self.app.processEvents()
    def test_startup_isolation(self):
        self.assertTrue(self.w.timer.isActive())
        # Other unittest modules load production backends during collection.
        # Test DEMO startup in a fresh interpreter instead of inspecting the
        # shared sys.modules cache from the entire regression suite.
        script = """
import sys
from PySide6.QtWidgets import QApplication
from studio_qt.app import StudioWindow
app = QApplication([])
window = StudioWindow()
assert window.timer.isActive()
for name in ('tkinter','olive_rgb','hue_driver','music_coordination','bleak','soundcard'):
    assert name not in sys.modules, name
window.close()
"""
        result = subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+'\\n'+result.stderr)
    def test_navigation(self):
        for i,page in enumerate(NAVIGATION):
            self.w.nav[page].click();self.assertEqual(self.c.state.page,page);self.assertEqual(self.w.pages.currentIndex(),i)
    def test_scene_selection_and_follow(self):
        self.c.channel('Hue','follow',False);original=self.c.state.channels['Hue'].color
        for card in self.w.scenes.cards:
            card.click();self.assertEqual(self.c.state.scene,card.name)
        self.assertEqual(self.c.state.channels['Hue'].color,original)
        self.assertEqual(len(self.w.scenes.cards),8)
    def test_favorites(self):
        card=self.w.scenes.cards[2];before=card.name in self.c.state.favorites;card.favorite.click()
        self.assertNotEqual(card.name in self.c.state.favorites,before)
        self.w.scenes.favorite.click()
        self.assertEqual(sum(not x.isHidden() for x in self.w.scenes.cards),len(self.c.state.favorites))
    def test_hex_validation_and_sync(self):
        ins=self.w.inspector;ins.hex.setText('#FF0000');ins.edit_hex()
        self.assertEqual(self.c.state.channels['Hue'].color,'#FF0000');self.assertEqual(ins.rgb[0].value(),255)
        ins.hex.setText('invalid');ins.edit_hex();self.assertTrue(ins.error.text());self.assertEqual(self.c.state.channels['Hue'].color,'#FF0000')
    def test_hsv_rgb_and_keyboard(self):
        ins=self.w.inspector;ins.hsv[0][1].setValue(120)
        self.assertAlmostEqual(self.c.state.get_hsv()[0],1/3,places=2)
        self.c.set_hex('#000000');ins.rgb[2].setValue(255);self.assertEqual(self.c.state.channels['Hue'].color,'#0000FF')
        h=self.c.state.get_hsv()[0];QTest.keyClick(ins.wheel,Qt.Key.Key_Right);self.assertNotEqual(self.c.state.get_hsv()[0],h)
    def test_channels_and_master(self):
        self.w.channels['Corner'].select.click();self.assertEqual(self.c.state.selected_channel,'Corner')
        self.w.channels['Corner'].level.setValue(32);self.assertEqual(self.c.state.channels['Corner'].brightness,.32)
        self.w.channels['Corner'].power.click();self.assertFalse(self.c.state.channels['Corner'].power)
        self.w.master.level.setValue(44);self.assertEqual(self.c.state.master_brightness,.44)
    def test_transitions_cancel_and_finish(self):
        self.c.set_transition(2);self.c.select_scene('Ocean Breeze',now=0);self.c.advance(1)
        mid=dict(self.c.display_colors);self.assertEqual(self.c.transition_progress,.5)
        self.c.select_scene('BRAT Energy',now=1);self.assertEqual(self.c.display_colors,mid)
        self.c.advance(3);self.assertIsNone(self.c.transition)
        self.assertEqual(self.c.display_colors['Corner'].upper(),SCENES['BRAT Energy'][0])
        self.c.select_scene('Neon Party');self.c.set_hex('#123456');self.assertIsNone(self.c.transition)
    def test_reduced_motion(self):
        self.w.inspector.reduced.setChecked(True);frames=self.w.reactor.frames;QTest.qWait(120)
        self.assertEqual(self.w.reactor.frames,frames)
        self.c.select_scene('Ocean Breeze');self.assertIsNone(self.c.transition)
    def test_follow_off_during_transition(self):
        self.c.set_transition(2);self.c.select_scene('Ocean Breeze',now=0);self.c.advance(1)
        original=self.c.display_colors['Hue'];self.c.channel('Hue','follow',False);self.c.advance(2)
        self.assertEqual(self.c.display_colors['Hue'],original)
    def test_hidden_and_paused_reactor(self):
        self.c.navigate('Scenes');frames=self.w.reactor.frames;QTest.qWait(120);self.assertEqual(self.w.reactor.frames,frames)
        self.c.navigate('Studio');self.c.set('playing',False);QTest.qWait(100);self.assertEqual(self.w.reactor.frames,frames)
    def test_tabs_and_transition_settings(self):
        ins=self.w.inspector;ins.tabs.setCurrentIndex(2);self.assertEqual(self.c.state.inspector,'Setup')
        ins.duration.setCurrentText('5');ins.curve.setCurrentText('Linear');self.assertEqual(self.c.state.transition_seconds,5);self.assertEqual(self.c.state.transition_curve,'Linear')
    def test_resize(self):
        for width,height in [(1440,900),(1280,800),(1080,760),(800,600)]:
            self.w.resize(width,height);self.app.processEvents();self.assertEqual((self.w.width(),self.w.height()),(width,height))
            for i in range(self.w.pages.count()):
                area=self.w.pages.widget(i);self.assertEqual(area.horizontalScrollBar().maximum(),0)
            self.assertEqual(self.w.inspector_scroll.horizontalScrollBar().maximum(),0)
            self.assertGreaterEqual(self.w.inspector.width(),260)
    def test_shutdown(self):
        self.c.select_scene('Ocean Breeze');self.w.close();self.assertFalse(self.w.timer.isActive());self.assertIsNone(self.c.transition)
        self.assertTrue(self.c.adapter.closed)
    def test_master_segmented_modes_and_keyboard(self):
        for mode,b in self.w.master.modes.items():
            b.click();self.assertEqual(self.c.state.mode,mode)
            self.assertEqual(sum(x.isChecked() for x in self.w.master.modes.values()),1)
            self.assertIn(('select_mode',mode),self.c.adapter.commands)
        before=self.c.state.master_power;QTest.keyClick(self.w.master.power,Qt.Key.Key_Space)
        self.assertNotEqual(self.c.state.master_power,before)
        self.w.master.level.setValue(28)
        self.assertEqual(self.c.adapter.commands[-1],('set_master',not before,.28))
    def test_compact_vector_navigation(self):
        self.w.resize(800,600);self.app.processEvents()
        for page,b in self.w.nav.items():
            self.assertEqual(b.text(),'');self.assertFalse(b.icon().isNull());self.assertEqual(b.toolTip(),page)
            QTest.keyClick(b,Qt.Key.Key_Space);self.assertEqual(self.c.state.page,page)
        self.w.resize(1440,900);self.app.processEvents();self.assertEqual(self.w.nav['Scenes'].text(),'Scenes')
    def test_inspector_status_and_advanced(self):
        ins=self.w.inspector;self.assertEqual(ins.device.currentText(),'Philips Hue')
        ins.advanced.click();self.assertFalse(ins.rgb_widget.isHidden());ins.advanced.click();self.assertTrue(ins.rgb_widget.isHidden())
        self.c.adapter.simulate_status('Hue',False);self.app.processEvents();self.assertIn('offline',ins.status.text())
        self.c.select_channel('Corner');self.assertEqual(ins.device.currentText(),'Corner Lamp');self.assertIn('connected',ins.status.text())
        self.w.master.color.click();self.assertEqual(self.c.state.inspector,'Color')
    def test_adapter_receives_manual_commands(self):
        adapter=self.c.adapter;self.c.set_hex('#00FF00');self.c.channel('Hue','power',False);self.c.channel('Hue','brightness',.2)
        self.c.select_scene('Neon Party')
        for command in [('set_rgb','Hue','#00FF00'),('set_power','Hue',False),('set_brightness','Hue',.2),('apply_scene','Neon Party')]:
            self.assertIn(command,adapter.commands)
    def test_queued_audio_meter_delivery(self):
        from studio_qt.backend_adapter import AudioMeters
        values=AudioMeters(.1,.2,.3,.2);self.w.last_meters=None
        self.c.adapter.publish_demo_meters(values);self.assertIsNone(self.w.last_meters)
        self.app.processEvents();self.assertEqual(self.w.last_meters,values)
        self.assertEqual(self.w.reactor.meter_values,[.1,.2,.3,.2])
    def test_control_bounds_at_all_sizes(self):
        from PySide6.QtWidgets import QWidget,QPushButton,QCheckBox,QSpinBox,QLineEdit,QSlider,QComboBox
        self.w.inspector.advanced.click()
        for size in [(1440,900),(1280,800),(1080,760),(800,600)]:
            self.w.resize(*size);self.app.processEvents()
            for child in self.w.findChildren(QWidget):
                if isinstance(child,(QPushButton,QCheckBox,QSpinBox,QLineEdit,QSlider,QComboBox)) and child.isVisible():
                    self.assertTrue(child.parentWidget().rect().contains(child.geometry()),(size,child.accessibleName(),child.geometry()))
    def test_idle_scheduler_stops_and_resumes(self):
        self.c.set('playing',False);QTest.qWait(80)
        frames=self.w.reactor.frames;self.assertFalse(self.w.timer.isActive());QTest.qWait(100)
        self.assertEqual(self.w.reactor.frames,frames)
        self.c.set('playing',True);QTest.qWait(120);self.assertGreater(self.w.reactor.frames,frames)
        self.c.navigate('Scenes');QTest.qWait(50);self.assertFalse(self.w.timer.isActive())
        self.c.navigate('Studio');QTest.qWait(120);self.assertTrue(self.w.timer.isActive())
        self.c.set('motion',False);self.assertFalse(self.w.timer.isActive())
    def test_paused_scene_transition_still_finishes(self):
        self.c.set('playing',False);self.c.set_transition(.05);self.c.select_scene('Ocean Breeze')
        QTest.qWait(150);self.assertIsNone(self.c.transition);self.assertFalse(self.w.timer.isActive())
    def test_scene_labels_fit(self):
        from PySide6.QtGui import QFont,QFontMetricsF
        font=QFont('Segoe UI');font.setPixelSize(13);font.setWeight(QFont.Weight.DemiBold);metrics=QFontMetricsF(font)
        for size in [(1440,900),(1280,800),(1080,760),(800,600)]:
            self.w.resize(*size);self.app.processEvents()
            for card in self.w.scenes.cards:
                rect=card.label_rect();bounds=metrics.boundingRect(rect,Qt.TextFlag.TextWordWrap|Qt.AlignmentFlag.AlignLeft,card.name)
                self.assertLessEqual(bounds.height(),rect.height(),card.name)
                self.assertLessEqual(bounds.width(),rect.width(),card.name)
                self.assertFalse(card.favorite.icon().isNull());self.assertEqual(card.favorite.text(),'')
    def test_vector_icons_at_all_scales(self):
        from PySide6.QtGui import QIcon
        from PySide6.QtCore import QSize
        from studio_qt.widgets.icons import VectorIcon
        for name in ['Studio','Music','Devices','Screen','Scenes','Settings','Power','Favorite','Logo']:
            engine=VectorIcon(name)
            for scale in [1,1.25,1.5]:
                for mode in [QIcon.Mode.Normal,QIcon.Mode.Active,QIcon.Mode.Disabled]:
                    pix=engine.scaledPixmap(QSize(24,24),mode,QIcon.State.On,scale);im=pix.toImage()
                    self.assertEqual(pix.devicePixelRatioF(),scale)
                    self.assertTrue(any(im.pixelColor(x,y).alpha()>0 for x in range(im.width()) for y in range(im.height())),name)
                    self.assertEqual(im.pixelColor(0,0).alpha(),0)
    def test_scroll_out_of_view_stops_timer(self):
        self.w.resize(800,600);self.app.processEvents();bar=self.w.pages.widget(0).verticalScrollBar()
        bar.setValue(bar.maximum());QTest.qWait(80);self.assertFalse(self.w.timer.isActive())
        bar.setValue(0);QTest.qWait(120);self.assertTrue(self.w.timer.isActive())

if __name__=='__main__':unittest.main()
