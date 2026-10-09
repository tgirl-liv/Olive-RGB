"""Deterministic Qt lifetime ordering; real worker, fake lamp, no BLE I/O."""
import asyncio
import sys
import threading
import unittest
from unittest.mock import patch

import shiboken6
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from studio_qt.corner_adapter import CornerLampAdapter
from studio_qt.live_window import LiveStudioWindow
import test_corner_live as fixtures


class CornerShutdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.LiveTests.setUpClass()

    def setUp(self):
        self.f = fixtures.LiveTests()
        self.f.setUp()
        self.errors = []
        self.hooks = [
            patch.object(threading, 'excepthook', lambda error: self.errors.append(error.exc_value)),
            patch.object(sys, 'excepthook', lambda kind, error, tb: self.errors.append(error)),
        ]
        for hook in self.hooks:
            hook.start()

    def tearDown(self):
        try:
            self.f.tearDown()
            self.assertEqual(self.errors, [], 'Uncaught background/Qt exception')
        finally:
            for hook in reversed(self.hooks):
                hook.stop()

    def join(self, session):
        session.thread.join(5)
        self.assertFalse(session.thread.is_alive(), 'Lifecycle thread did not finish')
        if session.worker is not None:
            self.assertFalse(session.worker.thread.is_alive(), 'BLE worker did not finish')

    def window(self):
        window = LiveStudioWindow(worker_factory=self.f.factory)
        self.f.windows.append(window)
        self.f.adapters.append(window.c.adapter)
        window.show()
        self.f.app.processEvents()
        return window

    def test_adapter_deleted_after_worker_exit_before_finished_callback(self):
        adapter = self.f.adapter()
        self.f.connect(adapter)
        session = adapter.session
        entered, release = threading.Event(), threading.Event()
        finished = session.finished

        def delayed_finished():
            entered.set()
            if not release.wait(5):
                raise TimeoutError('Test did not release lifecycle callback')
            finished()

        session.finished = delayed_finished
        try:
            adapter.close()
            self.f.wait(entered.is_set)
            self.assertFalse(session.worker.thread.is_alive())
            self.assertTrue(session.thread.is_alive())
            self.f.adapters.remove(adapter)
            shiboken6.delete(adapter)
            self.assertFalse(shiboken6.isValid(adapter))
        finally:
            release.set()
            self.join(session)
        self.assertEqual(self.errors, [])

    def test_window_completion_waits_until_lifecycle_thread_exits(self):
        window = self.window()
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.f.connect(window.c.adapter)
        adapter = window.c.adapter
        session = window.c.adapter.session
        entered, release = threading.Event(), threading.Event()
        finished = session.finished
        completions = []
        window.c.adapter.finished.connect(lambda: completions.append(session.thread.is_alive()))

        def delayed_return():
            finished()
            entered.set()
            if not release.wait(5):
                raise TimeoutError('Test did not release lifecycle return')

        session.finished = delayed_return
        try:
            window.close()
            self.f.wait(entered.is_set)
            QTest.qWait(80)
            self.assertTrue(shiboken6.isValid(window))
            self.assertFalse(window._cleanup_done)
            self.assertEqual(completions, [])
        finally:
            # Deleted-on-close objects cannot remain in the legacy fixture lists.
            self.f.windows.remove(window)
            self.f.adapters.remove(adapter)
            release.set()
            self.join(session)
        self.f.wait(lambda: not shiboken6.isValid(window))
        self.assertEqual(completions, [False])

    def test_parent_destroyed_during_worker_initialization(self):
        parent = QWidget()
        entered, release = threading.Event(), threading.Event()

        def factory(*args):
            entered.set()
            if not release.wait(5):
                raise TimeoutError('Test did not release worker factory')
            return self.f.factory(*args)

        adapter = CornerLampAdapter(parent=parent, worker_factory=factory)
        session = adapter.session
        adapter.connect_corner()
        try:
            self.f.wait(entered.is_set)
            shiboken6.delete(parent)
            self.assertFalse(shiboken6.isValid(adapter))
            self.assertTrue(session.closed, 'QObject destruction must request session cleanup')
        finally:
            session.close()
            release.set()
            self.join(session)
        self.assertFalse(session.worker.connected)
        self.assertFalse(session.worker.lamp.client.is_connected)
        self.assertEqual(self.errors, [])

    def test_window_close_during_disconnect_remains_responsive(self):
        window = self.window()
        self.f.connect(window.c.adapter)
        session = window.c.adapter.session
        lamp = self.f.lamps[0]
        entered, release = threading.Event(), threading.Event()
        disconnect = lamp.disconnect

        async def delayed_disconnect():
            entered.set()
            while not release.is_set():
                await asyncio.sleep(.01)
            await disconnect()

        lamp.disconnect = delayed_disconnect
        counter = []
        timer = QTimer()
        timer.timeout.connect(lambda: counter.append(1))
        timer.start(10)
        try:
            window.disconnect_button.click()
            self.f.wait(entered.is_set)
            window.close()
            QTest.qWait(100)
            self.assertFalse(window._cleanup_done)
            self.assertGreater(len(counter), 3)
        finally:
            release.set()
            timer.stop()
        self.f.wait(lambda: window._cleanup_done)
        self.join(session)
        self.assertFalse(lamp.client.is_connected)
        self.assertEqual(lamp.disconnect_overlaps, 0)

    def test_repeated_cycles_reuse_one_worker_and_finish_once(self):
        adapter = self.f.adapter()
        completions = []
        adapter.finished.connect(lambda: completions.append(adapter.session.thread.is_alive()))
        for _ in range(5):
            self.f.connect(adapter)
            adapter.disconnect_corner()
            self.f.wait(lambda: adapter.status == 'disconnected')
        self.assertEqual(len(self.f.workers), 1)
        adapter.close()
        adapter.close()
        self.f.wait(lambda: bool(completions))
        self.join(adapter.session)
        self.assertEqual(completions, [False])
        self.assertFalse(self.f.lamps[0].client.is_connected)

    def test_failed_initialization_reports_error_and_finished_after_thread_exit(self):
        def missing(*args):
            raise ImportError('mock missing dependency')

        adapter = CornerLampAdapter(worker_factory=missing)
        self.f.adapters.append(adapter)
        completions = []
        adapter.finished.connect(lambda: completions.append(adapter.session.thread.is_alive()))
        adapter.connect_corner()
        self.f.wait(lambda: bool(completions))
        self.join(adapter.session)
        self.assertEqual(adapter.status, 'error')
        self.assertIn('mock missing dependency', adapter.message)
        self.assertEqual(completions, [False])


if __name__ == '__main__':
    unittest.main()
