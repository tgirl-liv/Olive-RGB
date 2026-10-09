import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from studio_qt.app import StudioWindow
from studio_qt.workspace import Workspace,WorkspaceStore,visible_geometry
from studio_qt.widgets.controls import DeviceChannel


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent);self.path=Path(self.tmp.name)/'workspace-v1.json'
        self.w=StudioWindow(workspace_path=self.path);self.w.show();self.app.processEvents()
    def tearDown(self):
        self.w.close();self.w.deleteLater();self.app.processEvents()
        assert Path(self.tmp.name).resolve().is_relative_to(Path(__file__).resolve().parent)
        self.tmp.cleanup()
    def test_device_columns_align(self):
        for page in ['Studio','Devices']:
            self.w.c.navigate(page)
            for size in [(1440,900),(1280,800),(1080,760),(800,600)]:
                self.w.resize(*size);self.app.processEvents()
                rows=self.w.pages.currentWidget().findChildren(DeviceChannel);self.assertEqual(len(rows),2)
                for name in ['select','dot','power','follow','level','value']:
                    a,b=[getattr(row,name) for row in rows]
                    self.assertEqual((a.geometry().x(),a.width()),(b.geometry().x(),b.width()),(size,name))
                    viewport=self.w.pages.currentWidget().viewport()
                    for control in (a,b):
                        from PySide6.QtCore import QPoint
                        x=control.mapTo(viewport,QPoint(0,0)).x()
                        self.assertGreaterEqual(x,0);self.assertLessEqual(x+control.width(),viewport.width(),(size,name))
                self.assertEqual(rows[0].select.width(),rows[1].select.width())
    def test_splitter_keyboard_and_pages(self):
        self.w.resize(1440,900);self.app.processEvents();self.w.splitter.setSizes([700,450]);self.app.processEvents()
        before=self.w.splitter.sizes();handle=self.w.splitter.handle(1);QTest.keyClick(handle,Qt.Key.Key_Left)
        self.assertLess(self.w.splitter.sizes()[0],before[0]);adjusted=self.w.splitter.sizes()
        for page in ['Scenes','Devices','Studio']:self.w.c.navigate(page);self.app.processEvents();self.assertEqual(self.w.splitter.sizes(),adjusted)
    def test_sidebar_collapse_restore(self):
        self.w.resize(1440,900);self.app.processEvents();self.w.sidebar_toggle.click();self.assertEqual(self.w.sidebar.width(),56)
        self.w.sidebar_toggle.click();self.assertEqual(self.w.sidebar.width(),140)
    def test_inspector_collapse_restore(self):
        sizes=self.w.splitter.sizes();self.w.inspector_toggle.click();self.app.processEvents();self.assertTrue(self.w.inspector_scroll.isHidden())
        self.w.inspector_toggle.click();self.app.processEvents();self.assertFalse(self.w.inspector_scroll.isHidden())
        self.assertLess(abs(self.w.splitter.sizes()[1]-sizes[1]),3)
    def test_presets_do_not_touch_lighting(self):
        state=copy.deepcopy(self.w.c.state);commands=list(self.w.c.adapter.commands)
        for preset in ['Music','Compact','Studio']:
            self.w.preset.setCurrentText(preset);self.app.processEvents();self.assertEqual(self.w.c.state,state)
            self.assertEqual(list(self.w.c.adapter.commands),commands)
            self.assertEqual(self.w.workspace.preset,preset)
        self.assertFalse(self.w.inspector_scroll.isHidden())
    def test_persistence_and_restart(self):
        self.w.apply_preset('Music');self.w.toggle_sidebar();self.w.toggle_inspector();self.w.splitter.setSizes([680,380]);self.app.processEvents()
        self.w.save_workspace();saved=WorkspaceStore(self.path).load();self.w.close()
        second=StudioWindow(workspace_path=self.path);second.show();self.app.processEvents()
        try:
            self.assertEqual(second.workspace.preset,'Music');self.assertEqual(second.workspace.sidebar_collapsed,saved.sidebar_collapsed)
            self.assertEqual(second.workspace.inspector_collapsed,saved.inspector_collapsed)
            self.assertLess(abs(second.splitter.sizes()[1]-saved.splitter_sizes[1]),15)
        finally:second.close();second.deleteLater()
    def test_reset_persisted_defaults(self):
        self.w.apply_preset('Compact');self.w.reset_button.click();self.app.processEvents()
        loaded=WorkspaceStore(self.path).load();self.assertEqual(loaded.preset,'Studio');self.assertFalse(loaded.sidebar_collapsed);self.assertFalse(loaded.inspector_collapsed)
        self.assertTrue(self.w.timer.isActive())
    def test_corrupt_and_invalid_configs(self):
        for raw in ['{bad','[]','null','{"version":99}',json.dumps({'version':1,'sidebar_collapsed':False,'inspector_collapsed':False,'preset':'Studio','splitter_sizes':[0,-1]})]:
            self.path.write_text(raw);store=WorkspaceStore(self.path);self.assertEqual(store.load(),Workspace());self.assertTrue(store.error)
    def test_atomic_write_failure_preserves_previous(self):
        store=WorkspaceStore(self.path);store.save(Workspace());before=self.path.read_bytes()
        with patch('studio_qt.workspace.os.replace',side_effect=OSError('test failure')):
            self.assertFalse(store.save(Workspace(preset='Music')))
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(list(self.path.parent.glob('.workspace-*.tmp')),[])
    def test_offscreen_geometry_recovered(self):
        result=visible_geometry((90000,90000,1440,900))
        self.assertTrue(any(s.availableGeometry().contains(result) for s in self.app.screens()))
    def test_collapsed_restart_can_restore(self):
        self.w.apply_preset('Compact');self.w.save_workspace();second=StudioWindow(workspace_path=self.path);second.show();self.app.processEvents()
        try:
            self.assertTrue(second.inspector_scroll.isHidden());second.inspector_toggle.click();self.app.processEvents();self.assertGreaterEqual(second.inspector_scroll.width(),280)
        finally:second.close();second.deleteLater()
    def test_close_cleans_timer_and_writes_only_workspace(self):
        self.w.close();self.assertFalse(self.w.timer.isActive());self.assertTrue(self.w.c.adapter.closed)
        self.assertEqual([p.name for p in self.path.parent.iterdir()],['workspace-v1.json'])
    def test_studio_shows_both_device_rows_at_desktop_size(self):
        from PySide6.QtCore import QPoint
        self.w.resize(1440,900);self.w.apply_preset('Studio');self.app.processEvents()
        viewport=self.w.pages.widget(0).viewport()
        for row in self.w.channels.values():
            control=row.level;point=control.mapTo(viewport,QPoint(0,control.height()))
            self.assertLessEqual(point.y(),viewport.height())

if __name__=='__main__':unittest.main()
