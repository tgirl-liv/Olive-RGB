"""Portable DEMO smoke through the actual launcher, with real Qt mouse input."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QRadioButton
from studio_qt import app as launcher
from studio_qt.app import StudioWindow
from studio_qt.backend_adapter import MockLightingAdapter


class DemoLauncherTests(unittest.TestCase):
    def test_demo_launcher_mouse_controls_and_clean_exit_without_hardware(self):
        app = QApplication.instance() or QApplication([])
        errors, windows = [], []
        old_quit = app.quitOnLastWindowClosed()
        app.setQuitOnLastWindowClosed(False)
        stage = 0
        def drive():
            nonlocal stage
            try:
                if stage == 0:
                    dialog = app.activeModalWidget()
                    if not isinstance(dialog, QDialog):
                        return
                    self.assertTrue(next(r for r in dialog.findChildren(QRadioButton) if r.text().startswith('DEMO')).isChecked())
                    control = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
                    QTest.mouseClick(control, Qt.MouseButton.LeftButton)
                    stage = 1
                elif stage == 1:
                    window = next((w for w in app.topLevelWidgets() if isinstance(w, StudioWindow) and w.isVisible()), None)
                    if window is None:
                        return
                    windows.append(window)
                    self.assertIsInstance(window.c.adapter, MockLightingAdapter)
                    self.assertFalse(getattr(window.c.adapter, 'live', False))
                    self.assertFalse(hasattr(window, 'runtime'))
                    self.assertFalse(hasattr(window, 'screen_runtime'))
                    for name in ('Manual', 'Music', 'Screen'):
                        QTest.mouseClick(window.master.modes[name], Qt.MouseButton.LeftButton)
                        self.assertEqual(window.c.state.mode, name)
                    window.c.set('mode', 'Manual')
                    tabs = window.inspector.tabs.tabBar()
                    for index in (2, 0):
                        window.inspector_scroll.ensureWidgetVisible(tabs)
                        QTest.mouseClick(tabs, Qt.MouseButton.LeftButton, pos=tabs.tabRect(index).center())
                        self.assertEqual(window.inspector.tabs.currentIndex(), index)
                    window.c.set_hex('#0011FF')
                    wheel = window.inspector.wheel
                    window.inspector_scroll.ensureWidgetVisible(wheel)
                    QTest.mouseClick(wheel, Qt.MouseButton.LeftButton, pos=QPoint(wheel.width()*3//4, wheel.height()//2))
                    self.assertNotEqual(window.c.state.channels[window.c.state.selected_channel].color.upper(), '#0011FF')
                    card = window.scenes.cards[2]
                    window.pages.widget(0).ensureWidgetVisible(card)
                    QTest.mouseClick(card, Qt.MouseButton.LeftButton)
                    self.assertEqual(window.c.state.scene, card.name)
                    window.close();stage = 2
                elif stage == 2 and not windows[0].isVisible():
                    app.quit()
            except BaseException as error:
                errors.append(error);app.exit(1)
        timer = QTimer();timer.timeout.connect(drive);timer.start(25)
        watchdog = QTimer();watchdog.setSingleShot(True)
        watchdog.timeout.connect(lambda: (errors.append(AssertionError('DEMO launcher timed out')), app.exit(1)))
        watchdog.start(10000)
        try:
            with tempfile.TemporaryDirectory() as directory, patch.object(launcher, 'default_path', return_value=Path(directory)/'workspace.json'), patch.object(launcher, 'preferences_path_default', return_value=Path(directory)/'preferences-v1.json'):
                result = launcher.main()
            self.assertFalse(errors, str(errors));self.assertEqual(result, 0)
            self.assertEqual(stage, 2);self.assertEqual(len(windows), 1)
        finally:
            timer.stop();watchdog.stop()
            for w in windows:
                w.close();w.deleteLater()
            app.processEvents();app.setQuitOnLastWindowClosed(old_quit)


if __name__ == '__main__':
    unittest.main()
