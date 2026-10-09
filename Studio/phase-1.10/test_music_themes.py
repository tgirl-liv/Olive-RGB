"""Custom palette transactions and Qt integration; audio/devices are simulated."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox
from shiboken6 import isValid
import test_album_lighting as fixtures
from studio_qt.music_themes import ThemeStore,ThemeJobs,validated_library,MAX_BYTES
from studio_qt.music_runtime import preset_colors
from studio_qt.preferences import PreferencesStore,defaults,validate
from studio_qt.music_window import MusicLiveWindow
from studio_qt.widgets.music_theme_editor import MusicThemeEditor

COLORS=fixtures.COLORS


class ThemeStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'custom-music-themes-v1.json';self.store=ThemeStore(self.path)

    def test_crud_duplicate_and_restart(self):
        first=self.store.save(None,'  Night  ',COLORS)
        self.assertEqual(str(uuid.UUID(first)),first)
        self.store.save(first,'Night',dict(COLORS,beat='#FFFFFF'))
        second=self.store.save(None,'Night copy',self.store.get(first)['colors'])
        self.store.rename(first,'Renamed')
        restored=ThemeStore(self.path)
        self.assertEqual(restored.get(first)['name'],'Renamed');self.assertEqual(restored.get(first)['id'],first)
        self.assertEqual(restored.get(first)['colors'],restored.get(second)['colors'])
        restored.delete(first);self.assertIsNone(ThemeStore(self.path).get(first));self.assertIsNotNone(ThemeStore(self.path).get(second))

    def test_validation_keeps_existing_bytes_and_state(self):
        identifier=self.store.save(None,'Valid',COLORS);before=self.path.read_bytes();records=copy.deepcopy(self.store.themes)
        for name,colors in (('',COLORS),('A'*65,COLORS),('Line\nBreak',COLORS),('Other',{}),('Other',dict(COLORS,bass='#GGGGGG'))):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):self.store.save(None,name,colors)
        with self.assertRaises(ValueError):self.store.save(None,'valid',COLORS)
        with self.assertRaises(ValueError):self.store.save('missing','Other',COLORS)
        with self.assertRaises(ValueError):self.store.rename('Default','Other')
        with self.assertRaises(ValueError):self.store.delete('Default')
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.store.themes,records)
        returned=self.store.get(identifier);returned['colors']['bass']='#FFFFFF'
        self.assertEqual(self.store.get(identifier)['colors'],COLORS)

    def test_atomic_replace_and_fsync_failures_preserve_file_and_cleanup(self):
        identifier=self.store.save(None,'Original',COLORS);before=self.path.read_bytes()
        for operation in ('os.replace','os.fsync'):
            with patch('studio_qt.music_themes.'+operation,side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):self.store.save(identifier,'Changed',COLORS)
            self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.store.get(identifier)['name'],'Original')
            self.assertEqual(list(self.path.parent.iterdir()),[self.path])

    def test_corrupt_oversized_and_unsupported_files_are_preserved(self):
        for raw in (b'{broken',b'\xff',b'[]',b'{"version":2,"themes":[]}',b'x'*(MAX_BYTES+1)):
            with self.subTest(raw=raw[:25]):
                self.path.write_bytes(raw);store=ThemeStore(self.path)
                self.assertTrue(store.blocked);self.assertTrue(store.error)
                self.assertEqual(store.resolve(None,'Default'),preset_colors('Default'))
                with self.assertRaises(ValueError):store.save(None,'New',COLORS)
                self.assertEqual(self.path.read_bytes(),raw)

    def test_missing_file_and_missing_id_use_builtin(self):
        self.assertFalse(self.path.exists());self.assertFalse(self.store.blocked)
        self.assertEqual(self.store.resolve(str(uuid.uuid4()),'Charli xcx — BRAT'),preset_colors('Charli xcx — BRAT'))

    def test_external_file_changes_are_not_overwritten(self):
        self.store.save(None,'Original',COLORS)
        external=b'{"version":1,"themes":[]}';self.path.write_bytes(external)
        with self.assertRaises(ValueError):self.store.save(None,'Other',COLORS)
        self.assertEqual(self.path.read_bytes(),external)

    def test_library_schema_ids_duplicates_and_bounds(self):
        record={'id':str(uuid.uuid4()),'name':'One','colors':COLORS}
        for value in ({'version':True,'themes':[]},{'version':1,'themes':{}},
                      {'version':1,'themes':[dict(record,id='bad')]},
                      {'version':1,'themes':[record,record]},
                      {'version':1,'themes':[record]*129}):
            with self.assertRaises(ValueError):validated_library(value)

    def test_paths_inside_git_and_settings_are_rejected(self):
        repository=Path(self.temp.name)/'repo';(repository/'.git').mkdir(parents=True);(repository/'.git'/'HEAD').write_text('ref: refs/heads/main')
        for path in (repository/'themes.json',Path(self.temp.name)/'settings.json',Path(self.temp.name)/'preferences-v1.json'):
            with self.assertRaises(ValueError):ThemeStore(path)

    def test_preferences_backward_compatible_and_id_validation(self):
        values=defaults('live');del values['music']['custom_theme_id']
        self.assertIsNone(validate(values,'live')['music']['custom_theme_id'])
        identifier=str(uuid.uuid4());values['music']['custom_theme_id']=identifier
        path=Path(self.temp.name)/'qt.json';store=PreferencesStore(path)
        self.assertTrue(store.save('live',values));self.assertEqual(store.load('live')['music']['custom_theme_id'],identifier)
        for bad in ('Default',42,{},'BAD-ID'):
            values['music']['custom_theme_id']=bad
            with self.assertRaises(ValueError):validate(values,'live')
        self.assertNotIn('custom_theme_id',defaults('demo')['music'])


class ThemeUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.AlbumUITests.setUpClass()
    def setUp(self):
        self.f=fixtures.AlbumUITests();self.f.setUp();self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'custom-music-themes-v1.json';self.dialogs=[]
    def tearDown(self):
        for dialog in self.dialogs:
            if isValid(dialog):dialog.close()
        try:self.f.tearDown()
        finally:self.temp.cleanup()
    def window(self):
        w=self.f.window();w.themes=ThemeStore(self.path);w.theme_jobs=ThemeJobs(w.themes);return w
    def wait(self,predicate):self.f.f.wait(predicate)
    def save(self,w,name='Night',colors=COLORS,select=True,identifier=None):
        self.assertTrue(w.save_theme(identifier,name,colors,select))
        self.wait(lambda:not w.theme_jobs.busy)
        self.assertIn('saved.',w.theme_notice.text())
        return next(t['id'] for t in w.themes.list() if t['name']==name)

    def test_editor_hex_rgb_picker_swatches_and_invalid_input(self):
        dialog=MusicThemeEditor('New',COLORS);self.dialogs.append(dialog);requests=[]
        dialog.save_requested.connect(lambda *args:requests.append(args));dialog.show()
        row=dialog.colors['bass'];row.hex.setText('#ff0000')
        self.assertEqual([spin.value() for spin in row.rgb],[255,0,0]);self.assertIn('#ff0000',row.swatch.styleSheet())
        row.rgb[1].setValue(12);self.assertEqual(row.hex.text(),'#FF0C00')
        with patch('studio_qt.widgets.music_theme_editor.QColorDialog.getColor',return_value=QColor('#123456')):row.swatch.click()
        self.assertEqual(row.hex.text(),'#123456')
        row.hex.setText('invalid');dialog.save_button.click();self.assertTrue(dialog.error.text());self.assertFalse(requests)
        row.hex.setText('#123456');dialog.name.setText('  Edited  ');dialog.select_button.click()
        self.assertEqual(requests[0],(None,'Edited',COLORS,True))

    def test_save_select_live_and_deletion_restore_builtin_without_restart(self):
        w=self.window();w.palette.setCurrentText('Charli xcx — BRAT');w.start_music()
        self.wait(lambda:w.runtime.engine is not None);engine=w.runtime.engine;thread=engine.thread
        identifier=self.save(w)
        self.assertEqual(w.palette.currentData(),identifier);self.assertEqual(engine.colors,COLORS)
        self.assertEqual(w.music_preferences()['palette'],'Charli xcx — BRAT')
        changed=dict(COLORS,beat='#FFFFFF');self.save(w,'Night',changed,False,identifier)
        self.assertEqual(engine.colors,changed)
        self.assertTrue(w.submit_theme_job('delete',(identifier,)));self.wait(lambda:not w.theme_jobs.busy)
        self.assertIsNone(w.palette.currentData());self.assertEqual(engine.colors,preset_colors('Charli xcx — BRAT'))
        self.assertIs(w.runtime.engine,engine);self.assertIs(engine.thread,thread);self.assertEqual(len(self.f.f.engines),1)

    def test_save_without_select_preserves_active_theme_and_duplicates_builtin(self):
        w=self.window();w.start_music();self.wait(lambda:w.runtime.engine is not None)
        before=copy.deepcopy(w.runtime.engine.colors);self.save(w,select=False)
        self.assertIsNone(w.palette.currentData());self.assertEqual(w.runtime.engine.colors,before)
        dialog=w.open_theme_editor('duplicate');self.dialogs.append(dialog)
        self.assertEqual(dialog.name.text(),'Default copy');dialog.save_button.click()
        self.wait(lambda:not w.theme_jobs.busy)
        theme=next(t for t in w.themes.list() if t['name']=='Default copy')
        self.assertEqual(theme['colors'],preset_colors('Default'));self.assertIsNone(w.palette.currentData())
        self.assertFalse(w.theme_buttons['Edit'].isEnabled());self.assertFalse(w.theme_buttons['Delete'].isEnabled())

    def test_rename_stable_id_persists_selection_and_missing_id_falls_back(self):
        w=self.window();identifier=self.save(w)
        with patch('studio_qt.music_window.QInputDialog.getText',return_value=('Renamed',True)):w.theme_buttons['Rename'].click()
        self.wait(lambda:not w.theme_jobs.busy)
        self.assertEqual(w.palette.currentData(),identifier);self.assertEqual(w.palette.currentText(),'Custom · Renamed')
        prefs=Path(self.temp.name)/'qt.json';w.preferences_store=PreferencesStore(prefs);w.save_preferences();w.close()
        restored=MusicLiveWindow(preferences_path=prefs)
        try:
            self.assertEqual(restored.palette.currentData(),identifier);self.assertEqual(restored.palette.currentText(),'Custom · Renamed')
            self.assertEqual(restored.album.current_palette,COLORS)
            self.assertFalse(restored.runtime.busy);self.assertFalse(restored.c.adapter.music_active)
            self.assertFalse(restored.c.adapter.session.wanted);self.assertFalse(restored.c.adapter.hue.wanted)
        finally:restored.close()
        self.wait(lambda:w._cleanup_done)
        ThemeStore(self.path).delete(identifier)
        missing=MusicLiveWindow(preferences_path=prefs)
        try:
            self.assertIsNone(missing.palette.currentData());self.assertEqual(missing.palette.currentText(),'Default')
            self.assertIn('unavailable',missing.theme_notice.text());self.assertFalse(missing.runtime.busy)
        finally:missing.close()

    def test_album_colors_are_preserved_with_custom_selection_edits_and_delete(self):
        w=self.window();worker=self.f.select_album(w)
        artwork={k:'#00FF00' for k in COLORS};worker.publish(colors=artwork);w.album.poll()
        w.start_music();self.wait(lambda:w.runtime.engine is not None);engine=w.runtime.engine
        identifier=self.save(w);self.assertEqual(engine.colors,artwork)
        self.save(w,'Night',dict(COLORS,beat='#FFFFFF'),False,identifier);self.assertEqual(engine.colors,artwork)
        worker.publish(kind='fallback');w.album.poll();self.assertEqual(engine.colors,w.themes.get(identifier)['colors'])
        worker.publish(colors=artwork);w.album.poll()
        with patch('studio_qt.music_window.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes):w.theme_buttons['Delete'].click()
        self.wait(lambda:not w.theme_jobs.busy);self.assertEqual(engine.colors,artwork)
        worker.publish(kind='fallback');w.album.poll();self.assertEqual(engine.colors,preset_colors('Default'))

    def test_failed_save_does_not_select_or_apply_and_editor_stays_open(self):
        w=self.window();identifier=self.save(w);w.start_music();self.wait(lambda:w.runtime.engine is not None)
        before=copy.deepcopy(w.runtime.engine.colors);raw=self.path.read_bytes();dialog=w.open_theme_editor('edit');self.dialogs.append(dialog)
        dialog.colors['bass'].hex.setText('#FFFFFF')
        with patch('studio_qt.music_themes.os.replace',side_effect=OSError('disk failure')):
            dialog.select_button.click();self.wait(lambda:not w.theme_jobs.busy)
        self.assertTrue(isValid(dialog));self.assertTrue(dialog.isVisible());self.assertTrue(dialog.error.text());self.assertTrue(dialog.save_button.isEnabled())
        self.assertEqual(w.runtime.engine.colors,before);self.assertEqual(w.palette.currentData(),identifier);self.assertEqual(self.path.read_bytes(),raw)

    def test_save_disk_wait_does_not_block_gui_or_apply_before_commit(self):
        w=self.window();w.start_music();self.wait(lambda:w.runtime.engine is not None)
        entered=threading.Event();release=threading.Event();original=w.themes._persist
        def slow(records):entered.set();release.wait(2);return original(records)
        heartbeat=[];timer=QTimer(w);timer.setInterval(10);timer.timeout.connect(lambda:heartbeat.append(1));timer.start()
        before=copy.deepcopy(w.runtime.engine.colors)
        with patch.object(w.themes,'_persist',side_effect=slow):
            self.assertTrue(w.save_theme(None,'Night',COLORS,True))
            try:
                self.assertTrue(entered.wait(1));QTest.qWait(100)
                self.assertGreaterEqual(len(heartbeat),5);self.assertEqual(w.runtime.engine.colors,before)
                self.assertIsNone(w.palette.currentData());self.assertTrue(w.profile.isEnabled());self.assertTrue(w.sensitivity.isEnabled())
                self.assertFalse(w.save_theme(None,'Competing',COLORS,True))
            finally:release.set();timer.stop()
            self.wait(lambda:not w.theme_jobs.busy)
        self.assertEqual(w.runtime.engine.colors,COLORS)

    def test_close_during_save_waits_for_transaction_without_deleted_callbacks(self):
        w=self.window();entered=threading.Event();release=threading.Event();original=w.themes._persist
        def slow(records):entered.set();release.wait(2);return original(records)
        with patch.object(w.themes,'_persist',side_effect=slow):
            w.save_theme(None,'Night',COLORS,True)
            try:
                self.assertTrue(entered.wait(1));w.close();self.assertTrue(w._theme_close_pending)
            finally:release.set()
            self.wait(lambda:not w.theme_jobs.busy)
        self.assertIsNotNone(ThemeStore(self.path).get(w.palette.currentData()));self.assertFalse(w.theme_jobs.thread.is_alive())

    def test_corrupt_library_keeps_controls_usable_and_file_untouched(self):
        self.path.write_bytes(b'{broken');w=self.window();w.theme_notice.setText(w.themes.error);w.refresh_theme_buttons()
        self.assertFalse(w.theme_buttons['New'].isEnabled());self.assertTrue(w.profile.isEnabled())
        w.start_music();self.wait(lambda:w.runtime.engine is not None)
        self.assertFalse(w.save_theme(None,'Night',COLORS,True));self.assertEqual(self.path.read_bytes(),b'{broken')

    def test_custom_theme_real_engine_preview_without_devices(self):
        import numpy as np
        from studio_qt import music_engine as production
        from studio_qt.music_runtime import engine_factory
        w=self.window();identifier=self.save(w);w.runtime.factory=engine_factory
        class Recorder:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def record(self,numframes):
                mono=np.sin(np.arange(numframes)*2*np.pi*100/48000)*.1
                return np.column_stack([mono,mono])
        audio=SimpleNamespace(default_speaker=lambda:SimpleNamespace(name='Mock output'),get_microphone=lambda *a,**k:SimpleNamespace(recorder=lambda **k:Recorder()))
        with patch.object(production,'sc',audio):
            w.start_music();self.wait(lambda:w.album.virtual_rgb is not None)
            engine=w.runtime.engine;self.assertEqual(engine.colors,COLORS)
            self.assertEqual(w.album.virtual_rgb,w.c.adapter.corner_music_rgb(w.c.adapter.last_frame.rgb))
            self.assertFalse(self.f.f.f.corner.workers);self.assertFalse(self.f.f.f.drivers)
            w.stop_music();self.wait(lambda:not w.runtime.busy)
        self.assertEqual(w.palette.currentData(),identifier);self.assertEqual(w.album.current_palette,COLORS)


if __name__=='__main__':unittest.main()
