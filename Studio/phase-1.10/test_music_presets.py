"""MGK-inspired presets use the existing Music path; no real audio/devices."""
import ast
from pathlib import Path
import tempfile
import unittest
from studio_qt.music_presets import MGK_PALETTES
from studio_qt.music_runtime import preset_colors
from studio_qt.preferences import PALETTES,PreferencesStore
from studio_qt.music_themes import ThemeStore,ThemeJobs
from studio_qt.music_window import MusicLiveWindow
import test_album_lighting as fixtures

EXPECTED={
    'Tickets to My Downfall': ('#FF4FA3','#FF92C8','#FFFFFF','#FF1744'),
    'Mainstream Sellout': ('#FF69B4','#F5F5F5','#F44336','#FF1493'),
    'Hotel Diablo': ('#50146C','#A020F0','#E63232','#16101E'),
    'Lost Americana': ('#1677C8','#F5E6CE','#C84D43','#86C8EA'),
    'Lace Up': ('#D71920','#282828','#E5E5E5','#FF5638'),
    'General Admission': ('#191919','#626262','#E0D6C8','#B21E35'),
    'Bloom': ('#E84983','#AF5AC7','#FFCA71','#FF4070'),
    'Binge': ('#C3F000','#151515','#F2F2F2','#FF482E'),
    'Rap Devil': ('#B30021','#FF3030','#F2F2F2','#FF6500'),
}


class PresetTests(unittest.TestCase):
    def test_builtin_identifiers_are_stable_unique_names(self):
        self.assertEqual(len(MGK_PALETTES),9)
        self.assertEqual(len(PALETTES),len(set(PALETTES)))
        self.assertEqual(PALETTES[:6],('Default','The Weeknd — After Hours','The Weeknd — Dawn FM',
                                     'The Weeknd — Starboy','Charli xcx — BRAT','Charli xcx — Crash'))
        self.assertEqual(PALETTES[6:],('Tickets to My Downfall','Mainstream Sellout','Hotel Diablo','Lost Americana',
                                     'Lace Up','General Admission','Bloom','Binge','Rap Devil'))

    def test_exact_colors_resolution_and_immutable_copied_palettes(self):
        self.assertEqual(set(MGK_PALETTES),set(EXPECTED))
        for name,values in EXPECTED.items():
            self.assertIn(name,PALETTES);colors=dict(zip(('bass','mids','treble','beat'),values))
            self.assertEqual(preset_colors(name),colors)
            with self.assertRaises(TypeError):MGK_PALETTES[name]['bass']='#000000'
            resolved=preset_colors(name);resolved['bass']='#000000';self.assertEqual(preset_colors(name),colors)
        with self.assertRaises(TypeError):MGK_PALETTES['Other']={}

    def test_original_palettes_and_mgk_profile_preserved(self):
        from studio_qt.music_engine import MUSIC_PRESETS,MusicEngine
        source=ast.parse((Path(__file__).parent/'olive_rgb.py').read_text())
        # Parse dict(...) keyword definitions without importing Tkinter/transport.
        node=next(node.value for node in source.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MUSIC_PRESETS' for t in node.targets))
        original={ast.literal_eval(name):{kw.arg:ast.literal_eval(kw.value) for kw in colors.keywords} for name,colors in zip(node.keys,node.values)}
        self.assertEqual(MUSIC_PRESETS,original)
        for name,colors in original.items():self.assertEqual(preset_colors(name),colors)
        engine=next(node for node in source.body if isinstance(node,ast.ClassDef) and node.name=='MusicEngine')
        profiles=ast.literal_eval(next(node.value for node in engine.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PROFILES' for t in node.targets)))
        self.assertEqual(MusicEngine.PROFILES['MGK'],profiles['MGK'])


class PresetUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.AlbumUITests.setUpClass()
    def setUp(self):self.f=fixtures.AlbumUITests();self.f.setUp()
    def tearDown(self):self.f.tearDown()
    def wait(self,predicate):self.f.f.wait(predicate)

    def test_live_switching_all_presets_without_restart_or_adjustment_reset(self):
        w=self.f.window();w.profile.setCurrentText('MGK');w.output_brightness.setValue(50);w.output_saturation.setValue(60)
        w.start_music();self.wait(lambda:w.runtime.engine is not None)
        engine=w.runtime.engine;thread=engine.thread
        for name in EXPECTED:
            w.palette.setCurrentText(name)
            self.assertEqual(engine.colors,preset_colors(name));self.assertIsNone(w.palette.currentData())
            self.assertEqual(w.c.adapter.adjustments,(.5,.6));self.assertEqual(w.profile.currentText(),'MGK')
            self.assertFalse(w.theme_buttons['Edit'].isEnabled());self.assertFalse(w.theme_buttons['Delete'].isEnabled())
        self.assertEqual(len(self.f.f.engines),1);self.assertIs(w.runtime.engine,engine);self.assertIs(engine.thread,thread)
        self.assertEqual(w.inspector.static_colors['MGK'].toolTip().split(' · ')[1],'#FF0046')

    def test_palette_selection_persists_across_restart_without_capture(self):
        w=self.f.window()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'preferences-v1.json';w.preferences_store=PreferencesStore(path)
            for name in EXPECTED:
                w.palette.setCurrentText(name);w.save_preferences()
                restored=MusicLiveWindow(preferences_path=path)
                try:
                    self.assertEqual(restored.palette.currentText(),name);self.assertEqual(restored.album.current_palette,preset_colors(name))
                    self.assertFalse(restored.runtime.busy);self.assertFalse(restored.c.adapter.session.wanted);self.assertFalse(restored.c.adapter.hue.wanted)
                finally:restored.close()

    def test_duplicate_builtin_into_persistent_custom_theme_then_delete_fallback(self):
        w=self.f.window()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'custom-music-themes-v1.json';w.themes=ThemeStore(path);w.theme_jobs=ThemeJobs(w.themes)
            for name in EXPECTED:
                w.palette.setCurrentText(name);dialog=w.open_theme_editor('duplicate')
                self.assertEqual({key:row.hex.text() for key,row in dialog.colors.items()},preset_colors(name))
                dialog.colors['bass'].hex.setText('#010203');dialog.select_button.click();self.wait(lambda:not w.theme_jobs.busy)
                identifier=w.palette.currentData();theme=ThemeStore(path).get(identifier)
                self.assertEqual(theme['name'],name+' copy');self.assertEqual(theme['colors']['bass'],'#010203')
                self.assertEqual(preset_colors(name)['bass'],EXPECTED[name][0])
                self.assertTrue(w.submit_theme_job('delete',(identifier,)));self.wait(lambda:not w.theme_jobs.busy)
                self.assertEqual(w.palette.currentText(),name);self.assertEqual(w.album.current_palette,preset_colors(name))

    def test_album_ownership_and_each_builtin_fallback_without_restart(self):
        w=self.f.window();worker=self.f.select_album(w);worker.publish(colors=fixtures.COLORS);w.album.poll()
        w.start_music();self.wait(lambda:w.runtime.engine is not None);engine=w.runtime.engine;thread=engine.thread
        for name in EXPECTED:
            w.palette.setCurrentText(name);self.assertEqual(engine.colors,fixtures.COLORS)
            worker.publish(kind='fallback');w.album.poll();self.assertEqual(engine.colors,preset_colors(name))
            worker.publish(colors=fixtures.COLORS);w.album.poll();self.assertEqual(engine.colors,fixtures.COLORS)
        self.assertIs(w.runtime.engine,engine);self.assertIs(engine.thread,thread);self.assertEqual(len(self.f.f.engines),1)


if __name__=='__main__':unittest.main()
