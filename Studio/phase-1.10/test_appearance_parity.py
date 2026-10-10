"""Interface themes and logs remain separate from hardware and lighting palettes."""
import ast
import tempfile
import unittest
from pathlib import Path
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from studio_qt.app import StudioWindow
from studio_qt.appearance import THEMES,stylesheet
from studio_qt.theme import QSS
from studio_qt.preferences import PreferencesStore,defaults,validate


class AppearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'preferences-v1.json';self.windows=[]
    def tearDown(self):
        for w in self.windows:w.close();w.deleteLater()
        self.app.processEvents();self.tmp.cleanup()
    def window(self):
        w=StudioWindow(preferences_path=self.path);self.windows.append(w);w.show();return w
    def test_original_theme_constants_preserved(self):
        tree=ast.parse(Path(__file__).with_name('olive_rgb.py').read_text())
        n=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='THEMES' for t in n.targets))
        original={ast.literal_eval(k):{kw.arg:ast.literal_eval(kw.value) for kw in v.keywords} for k,v in zip(n.value.keys,n.value.values)}
        self.assertEqual(THEMES,original);self.assertEqual(stylesheet('Studio'),QSS)
    def test_all_themes_persist_and_restore_without_effects(self):
        w=self.window()
        for name in ('Tickets','Sakura','Blackout','Cyberpunk','Studio'):
            w.appearance_settings.theme.setCurrentText(name);w.save_preferences();other=self.window()
            self.assertEqual(other.appearance_settings.theme.currentText(),name);self.assertEqual(other.styleSheet(),stylesheet(name))
            self.assertEqual(other.c.state.mode,'Manual');self.assertFalse(other.c.state.playing)
    def test_interface_theme_never_changes_lighting_palette_or_state(self):
        w=self.window();before=(w.music_preferences(),[(c.color,c.power,c.brightness) for c in w.c.state.channels.values()])
        for name in THEMES:w.appearance_settings.theme.setCurrentText(name)
        self.assertEqual(before,(w.music_preferences(),[(c.color,c.power,c.brightness) for c in w.c.state.channels.values()]))
    def test_old_preferences_default_to_original_studio_appearance(self):
        values=defaults('demo');del values['appearance'];self.assertEqual(validate(values,'demo')['appearance'],{'theme':'Studio'})
        values['appearance']={'theme':'unknown'}
        with self.assertRaises(ValueError):validate(values,'demo')
    def test_readonly_bounded_plaintext_log_deduplicates_status(self):
        from PySide6.QtWidgets import QLabel
        w=self.window();p=w.appearance_settings;self.assertTrue(p.log.isReadOnly())
        w.music_status=QLabel('Audio error: test failure');p.collect();count=p.log.blockCount();p.collect()
        self.assertEqual(p.log.blockCount(),count);self.assertIn('Audio error: test failure',p.log.toPlainText())
        for i in range(600):p.append('test','event '+str(i))
        self.assertLessEqual(p.log.blockCount(),500)
        w.music_status.setText('LIVE · RMS 0.12 · RGB #FFFFFF');p.collect();count=p.log.blockCount()
        w.music_status.setText('LIVE · RMS 0.13 · RGB #FF0000');p.collect();self.assertEqual(p.log.blockCount(),count)
    def test_failure_to_save_preserves_preferences_and_reports_error(self):
        from unittest.mock import patch
        w=self.window();w.save_preferences();before=self.path.read_bytes()
        w.appearance_settings.theme.setCurrentText('Tickets')
        with patch('studio_qt.preferences.os.replace',side_effect=OSError('test disk unavailable')):w.save_preferences()
        self.assertEqual(self.path.read_bytes(),before);self.assertIn('test disk unavailable',w.preferences_notice.text())
        w.appearance_settings.collect();self.assertIn('test disk unavailable',w.appearance_settings.log.toPlainText())
    def test_demo_settings_and_navigation_operate_without_hardware(self):
        w=self.window();w.c.navigate('Settings');self.assertTrue(w.appearance_settings.isVisible())
        w.appearance_settings.theme.setCurrentText('Tickets');w.c.navigate('Studio')
        self.assertEqual(w.c.state.page,'Studio');self.assertTrue(all(status.simulated for status in w.c.adapter.statuses.values()))

    def test_live_theme_switch_keeps_music_capture_and_lighting_unchanged(self):
        import test_music_live as fixtures
        fixtures.MusicTests.setUpClass();f=fixtures.MusicTests();f.setUp()
        try:
            w=f.window();w.start_music();f.wait(lambda:w.c.adapter.last_frame is not None)
            engine=w.runtime.engine;thread=engine.thread;before=w.music_preferences()
            w.c.navigate('Settings');w.appearance_settings.theme.setCurrentText('Cyberpunk')
            QTest.qWait(100)
            self.assertIs(w.runtime.engine,engine);self.assertIs(engine.thread,thread)
            self.assertEqual(w.music_preferences(),before);self.assertTrue(w.c.adapter.music_active)
            w.c.navigate('Music');self.assertTrue(w.profile.isEnabled());self.assertTrue(w.palette.isEnabled())
            w.stop_music();f.wait(lambda:not w.runtime.busy)
        finally:f.tearDown()
