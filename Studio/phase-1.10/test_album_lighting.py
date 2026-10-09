"""Album integration: synthetic artwork/media, simulated audio and devices only."""
import asyncio
import io
import queue
import sys
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from PySide6.QtCore import QThread
import test_music_live as fixtures
from album_colors import AlbumArtworkWorker,palette_from_artwork
from studio_qt.album_artwork import StudioAlbumArtworkWorker
from studio_qt.music_runtime import MusicRuntime,preset_colors,validated_palette
from studio_qt.preferences import defaults,validate,PreferencesStore


def cover():
    image=Image.new('RGB',(300,200),'red')
    image.paste('blue',(100,0,200,200));image.paste('green',(200,0,300,200))
    stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()


COLORS={'bass':'#123456','mids':'#654321','treble':'#ABCDEF','beat':'#EEEEEE'}


class FakeArtwork:
    def __init__(self):self.messages=queue.Queue(maxsize=1);self.closed=False;self.enabled=False
    def set_enabled(self,value):self.enabled=value
    def close(self):self.closed=True
    def publish(self,kind='artwork',colors=None,data=None):
        self.messages.put_nowait((kind,'Player: Simulated player\nTrack: Test song',colors or COLORS,data))


class AlbumTests(unittest.TestCase):
    def test_existing_extractor_handles_color_and_grayscale(self):
        colors=palette_from_artwork(cover());self.assertEqual(set(colors),set(COLORS))
        self.assertGreaterEqual(len(set(colors.values())),3);validated_palette(colors)
        stream=io.BytesIO();Image.new('RGB',(10,10),(25,25,25)).save(stream,format='PNG')
        gray=palette_from_artwork(stream.getvalue());self.assertEqual(gray['bass'],'#5A5A5A')

    def test_palette_validation_is_strict_and_does_not_mutate(self):
        runtime=MusicRuntime();engine=SimpleNamespace(colors=dict(COLORS));runtime.engine=engine
        colors={k:v.lower() for k,v in COLORS.items()};runtime.set_palette(colors);old=engine.colors
        self.assertEqual(old,COLORS);colors['bass']='#FFFFFF';self.assertEqual(old,COLORS)
        for invalid in (None,{},dict(COLORS,bass='red'),dict(COLORS,bass=1),dict(COLORS,extra='#FFFFFF')):
            with self.assertRaises(ValueError):runtime.set_palette(invalid)
            self.assertIs(engine.colors,old)
        runtime.set_palette(dict(COLORS,beat='#FFFFFF'));self.assertIsNot(engine.colors,old)

    def test_concurrent_palette_replacements_never_expose_partial_dictionary(self):
        runtime=MusicRuntime();engine=SimpleNamespace(colors=dict(COLORS));runtime.engine=engine
        other={k:'#FFFFFF' for k in COLORS};done=threading.Event();bad=[]
        def update():
            try:
                for n in range(2000):runtime.set_palette(other if n%2 else COLORS)
            finally:done.set()
        worker=threading.Thread(target=update);worker.start()
        while not done.is_set():
            snapshot=engine.colors
            if snapshot!=COLORS and snapshot!=other:bad.append(snapshot)
        worker.join(1);self.assertFalse(worker.is_alive());self.assertEqual(bad,[])

    def test_source_schema_roundtrip_and_old_preferences(self):
        import tempfile
        from pathlib import Path
        values=defaults('live');values['music']['color_source']='Album artwork'
        with tempfile.TemporaryDirectory() as folder:
            store=PreferencesStore(Path(folder)/'qt.json');self.assertTrue(store.save('live',values))
            self.assertEqual(store.load('live')['music']['color_source'],'Album artwork')
        del values['music']['color_source'];self.assertEqual(validate(values,'live')['music']['color_source'],'Preset')
        self.assertNotIn('color_source',defaults('demo')['music'])
        values['music']['color_source']='Unknown'
        with self.assertRaises(ValueError):validate(values,'live')

    def test_worker_preserves_original_watcher_and_description(self):
        self.assertIs(StudioAlbumArtworkWorker._watch,AlbumArtworkWorker._watch)
        props=SimpleNamespace(title='Song',artist='Artist');session=SimpleNamespace(source_app_user_model_id='Player ID')
        original=AlbumArtworkWorker.__new__(AlbumArtworkWorker)
        self.assertEqual(original._describe(session,props),'Song — Artist')
        studio=StudioAlbumArtworkWorker.__new__(StudioAlbumArtworkWorker)
        self.assertEqual(studio._describe(session,props),'Player: Player ID\nTrack: Song — Artist')

    def test_cancel_pending_media_wait_without_hanging_thread(self):
        started=threading.Event();cancelled=threading.Event()
        class Waiting(StudioAlbumArtworkWorker):
            async def _watch(self):
                started.set()
                try:await asyncio.sleep(60)
                finally:cancelled.set()
        worker=Waiting()
        try:self.assertTrue(started.wait(1))
        finally:worker.close();worker.thread.join(1)
        self.assertFalse(worker.thread.is_alive());self.assertTrue(cancelled.is_set())

    def test_close_before_loop_start_is_safe(self):
        for n in range(15):
            worker=StudioAlbumArtworkWorker();worker.close();worker.thread.join(1)
            self.assertFalse(worker.thread.is_alive())

    def test_missing_optional_dependency_reports_fallback(self):
        with patch.dict(sys.modules,{'winrt.windows.media.control':None}):
            worker=StudioAlbumArtworkWorker()
            try:
                worker.set_enabled(True);message=worker.messages.get(timeout=2)
                self.assertEqual(message[0],'fallback');self.assertIn('requirements-studio-album.txt',message[1])
            finally:worker.close();worker.thread.join(1)
        self.assertFalse(worker.thread.is_alive())

    def test_real_worker_with_simulated_windows_media_extracts_off_gui(self):
        thread_ids=[];streams=[];data=cover()
        class Stream:
            size=len(data)
            async def read_async(self,*args):return bytearray(data)
            def close(self):streams.append('closed')
        async def open_read():return Stream()
        props=SimpleNamespace(title='Song',artist='Artist',album_title='Album',thumbnail=SimpleNamespace(open_read_async=open_read))
        async def properties():thread_ids.append(threading.get_ident());return props
        session=SimpleNamespace(source_app_user_model_id='Test.Player',get_playback_info=lambda:SimpleNamespace(playback_status=1),try_get_media_properties_async=properties)
        manager=SimpleNamespace(get_current_session=lambda:session,get_sessions=lambda:[session])
        async def request():return manager
        modules={'winrt.windows.media.control':SimpleNamespace(GlobalSystemMediaTransportControlsSessionManager=SimpleNamespace(request_async=request),GlobalSystemMediaTransportControlsSessionPlaybackStatus=SimpleNamespace(PLAYING=1)),
                 'winrt.windows.storage.streams':SimpleNamespace(Buffer=lambda size:bytearray(size),InputStreamOptions=SimpleNamespace(READ_AHEAD=1))}
        with patch.dict(sys.modules,modules):
            worker=StudioAlbumArtworkWorker()
            try:
                worker.set_enabled(True);kind,description,colors,preview=worker.messages.get(timeout=2)
                self.assertEqual(kind,'artwork');self.assertIn('Test.Player',description);validated_palette(colors)
                with Image.open(io.BytesIO(preview)) as image:self.assertLessEqual(max(image.size),110)
                self.assertNotEqual(thread_ids,[threading.get_ident()]);self.assertEqual(streams,['closed'])
            finally:worker.close();worker.thread.join(1)
        self.assertFalse(worker.thread.is_alive())

    def test_no_playing_session_or_missing_player_artwork_falls_back(self):
        async def properties():return SimpleNamespace(thumbnail=None)
        player=SimpleNamespace(get_playback_info=lambda:SimpleNamespace(playback_status=1),try_get_media_properties_async=properties)
        for session,expected in ((None,'No playing media session'),(player,'This player has no artwork')):
            with self.subTest(session=expected):
                manager=SimpleNamespace(get_current_session=lambda:session,get_sessions=lambda:[])
                async def request():return manager
                modules={'winrt.windows.media.control':SimpleNamespace(GlobalSystemMediaTransportControlsSessionManager=SimpleNamespace(request_async=request),GlobalSystemMediaTransportControlsSessionPlaybackStatus=SimpleNamespace(PLAYING=1)),
                         'winrt.windows.storage.streams':SimpleNamespace(Buffer=None,InputStreamOptions=None)}
                with patch.dict(sys.modules,modules):
                    worker=StudioAlbumArtworkWorker()
                    try:
                        worker.set_enabled(True);message=worker.messages.get(timeout=2)
                        self.assertEqual(message[0],'fallback');self.assertIn(expected,message[1]);self.assertIn('preset colors',message[1])
                    finally:worker.close();worker.thread.join(1)
                self.assertFalse(worker.thread.is_alive())


class AlbumUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.MusicTests.setUpClass()
    def setUp(self):
        self.f=fixtures.MusicTests();self.f.setUp();self.workers=[];self.errors=[]
        self.hook=patch.object(sys,'excepthook',lambda *exc:self.errors.append(exc[1]));self.hook.start()
    def tearDown(self):
        try:self.f.tearDown();self.assertEqual(self.errors,[])
        finally:self.hook.stop()
    def factory(self):
        worker=FakeArtwork();self.workers.append(worker);return worker
    def window(self):
        w=self.f.window();w.album.worker_factory=self.factory;return w
    def select_album(self,w):w.album.source.setCurrentText('Album artwork');return self.workers[-1]

    def test_artwork_only_changes_palette_not_theme_manual_or_ownership(self):
        w=self.window();state={k:c.color for k,c in w.c.state.channels.items()};theme=w.styleSheet()
        worker=self.select_album(w);worker.publish(data=cover());w.album.poll()
        self.assertEqual(w.album.current_palette,COLORS);self.assertIn('Test song',w.album.status.text())
        self.assertFalse(w.album.preview.pixmap().isNull());self.assertFalse(w.runtime.busy)
        self.assertFalse(w.c.adapter.music_active);self.assertFalse(self.f.f.corner.workers);self.assertFalse(self.f.f.drivers)
        self.assertEqual({k:c.color for k,c in w.c.state.channels.items()},state);self.assertEqual(w.styleSheet(),theme)
        self.assertEqual(w.album.thread(),QThread.currentThread())
        w.start_music();self.f.wait(lambda:w.runtime.engine is not None)
        self.assertEqual(w.runtime.engine.colors,COLORS);self.assertEqual(len(self.f.engines),1)
        w.stop_music();self.f.wait(lambda:not w.runtime.busy);self.assertEqual(w.c.state.mode,'Manual')

    def test_palette_update_while_opening_is_not_lost(self):
        w=self.window();opening=threading.Event();release=threading.Event();original=w.runtime.factory
        def factory(*args):opening.set();release.wait(2);return original(*args)
        w.runtime.factory=factory;w.start_music()
        try:
            self.assertTrue(opening.wait(1));worker=self.select_album(w);worker.publish();w.album.poll()
        finally:release.set()
        self.f.wait(lambda:w.runtime.engine is not None)
        self.assertEqual(w.runtime.engine.colors,COLORS)

    def test_fallback_reuses_selected_preset_and_capture(self):
        w=self.window();w.palette.setCurrentText('Charli xcx — BRAT');worker=self.select_album(w)
        w.start_music();self.f.wait(lambda:w.runtime.engine is not None);engine=w.runtime.engine
        worker.publish();w.album.poll();self.assertEqual(engine.colors,COLORS)
        worker.publish(kind='fallback');w.album.poll()
        self.assertEqual(engine.colors,preset_colors('Charli xcx — BRAT'));self.assertIs(w.runtime.engine,engine)
        self.assertEqual(len(self.f.engines),1);self.assertIn('Fallback: Charli',w.album.status.text())
        self.assertTrue(w.album.preview.pixmap().isNull())

    def test_album_palette_reaches_real_engine_and_existing_light_pipeline(self):
        import numpy as np
        from studio_qt import music_engine as production
        from studio_qt.music_runtime import engine_factory
        w=self.window();w.runtime.factory=engine_factory
        self.f.f.connect_corner(w.c.adapter);w.c.adapter.set_master(True,1);w.c.adapter.set_brightness('Corner',1)
        worker=self.select_album(w);worker.publish();w.album.poll();closed=[]
        class Recorder:
            def __enter__(self):return self
            def __exit__(self,*args):closed.append(True)
            def record(self,numframes):
                mono=np.sin(np.arange(numframes)*2*np.pi*100/48000)*.1
                return np.column_stack([mono,mono])
        audio=SimpleNamespace(default_speaker=lambda:SimpleNamespace(name='Mock output'),get_microphone=lambda *a,**k:SimpleNamespace(recorder=lambda **k:Recorder()))
        with patch.object(production,'sc',audio):
            w.start_music();self.f.wait(lambda:w.c.adapter.last_frame is not None)
            engine=w.runtime.engine
            rgb,_=engine._palette(np.array([100.,0.,0.]))
            self.assertEqual(tuple(rgb),(0x12,0x34,0x56))
            self.f.wait(lambda:any(c[0]=='rgb' for c in self.f.f.corner.lamps[0].calls))
            self.assertTrue(w.c.adapter.owns('Corner'));self.assertIsNotNone(w.reactor.spectrum_frame)
            self.assertEqual(w.album.virtual_rgb,w.c.adapter.corner_music_rgb(w.c.adapter.music_colors['Corner']))
            before=w.c.adapter.last_frame.rgb
            with patch.object(engine,'_detect_beat',return_value=True):
                self.f.wait(lambda:w.c.adapter.last_frame.beat and w.c.adapter.last_frame.rgb!=before)
                measured=w.c.adapter.last_frame.rgb
                self.assertEqual(w.album.virtual_rgb,w.c.adapter.corner_music_rgb(measured))
                self.assertIn('Engine: RGB '+', '.join(map(str,measured)),w.album.light_readout.text())
            worker.publish(kind='fallback');w.album.poll();self.assertEqual(engine.colors,preset_colors('Default'))
            self.assertIs(w.runtime.engine,engine)
            self.f.wait(lambda:w.c.adapter.last_frame.rgb!=measured)
            self.assertEqual(w.album.virtual_rgb,w.c.adapter.corner_music_rgb(w.c.adapter.last_frame.rgb))
            w.stop_music();self.f.wait(lambda:not w.runtime.busy)
        self.assertEqual(closed,[True]);self.assertFalse(w.c.adapter.owns('Corner'))

    def test_virtual_preview_runs_without_connected_devices(self):
        w=self.window();self.assertIsNone(w.album.virtual_rgb)
        w.start_music();self.f.wait(lambda:w.album.virtual_rgb is not None)
        frame=w.c.adapter.last_frame
        self.assertEqual(w.album.virtual_rgb,w.c.adapter.corner_music_rgb(frame.rgb))
        expected='#'+''.join(f'{c:02X}' for c in w.album.virtual_rgb)
        self.assertIn(expected,w.album.light_indicator.styleSheet());self.assertIn(expected,w.album.light_readout.text())
        self.assertIn('disconnected; no light required',w.album.light_readout.text())
        self.assertFalse(self.f.f.corner.workers);self.assertFalse(self.f.f.drivers)

    def test_preview_matches_exact_connected_transport_rgb(self):
        w=self.window();a=w.c.adapter;self.f.f.connect_corner(a);w.start_music()
        self.f.wait(lambda:a.last_frame is not None);w.music_timer.stop()
        a.state.channels['Corner'].brightness=.37;a.state.channels['Corner'].follow=True
        a.state.master_brightness=.81
        from music_coordination import MusicFrame
        with patch.object(a.session,'color') as output:
            for rgb in ((101,202,77),(0,0,0),(255,255,255)):
                a.apply_frame(MusicFrame(rgb,.6,.3,.1,.07,True,time.monotonic()));w.live_controls()
                self.assertEqual(w.album.virtual_rgb,output.call_args.args[0])
                self.assertEqual(w.album.virtual_rgb,tuple(round(c*.37*.81) for c in rgb))

    def test_preview_respects_master_local_power_and_follow_without_writes(self):
        w=self.window();w.start_music();self.f.wait(lambda:w.album.virtual_rgb is not None)
        w.music_timer.stop();a=w.c.adapter;channel=a.state.channels['Corner']
        original=a.last_frame.rgb
        with patch.object(a.session,'color') as corner,patch.object(a.hue,'update') as hue:
            a.state.master_power=False;channel.follow=True;w.live_controls()
            self.assertEqual(w.album.virtual_rgb,(0,0,0))
            channel.follow=False;w.live_controls()
            self.assertEqual(w.album.virtual_rgb,tuple(round(c*channel.brightness) for c in original))
            channel.power=False;w.live_controls();self.assertEqual(w.album.virtual_rgb,(0,0,0))
            corner.assert_not_called();hue.assert_not_called()

    def test_preview_stale_and_stop_clear_measured_output(self):
        w=self.window();w.start_music();self.f.wait(lambda:w.album.virtual_rgb is not None)
        w.music_timer.stop()
        with patch('studio_qt.music_window.time.monotonic',return_value=w.c.adapter.last_frame.timestamp+1.1):w.live_controls()
        self.assertIsNone(w.album.virtual_rgb);self.assertNotIn('Output: RGB',w.album.light_readout.text())
        w.live_controls();self.assertIsNotNone(w.album.virtual_rgb)
        w.stop_music();self.assertIsNone(w.album.virtual_rgb)

    def test_preview_participation_off_remains_read_only_and_calculated(self):
        w=self.window();w.c.adapter.set_participation('Corner',False)
        w.start_music();self.f.wait(lambda:w.album.virtual_rgb is not None)
        self.assertIn('participation off; calculated only',w.album.light_readout.text())
        self.assertFalse(w.c.adapter.owns('Corner'));self.assertFalse(self.f.f.corner.workers)

    def test_rapid_switch_discards_old_queue_even_after_reenable(self):
        w=self.window();old=self.select_album(w);old.publish()
        w.album.source.setCurrentText('Preset');self.assertTrue(old.closed)
        new=self.select_album(w);w.album.poll()
        self.assertEqual(w.album.current_palette,preset_colors('Default'))
        new.publish(colors=dict(COLORS,beat='#FFFFFF'));w.album.poll()
        self.assertEqual(w.album.current_palette['beat'],'#FFFFFF')
        w.album.source.setCurrentText('Preset');self.assertEqual(w.album.current_palette,preset_colors('Default'))

    def test_invalid_artwork_palette_falls_back(self):
        w=self.window();worker=self.select_album(w);worker.publish(colors={'bass':'red'});w.album.poll()
        self.assertIn('Invalid artwork palette',w.album.status.text())
        self.assertEqual(w.album.current_palette,preset_colors('Default'))

    def test_shutdown_detaches_worker_and_late_results(self):
        w=self.window();worker=self.select_album(w);w.close();self.assertTrue(worker.closed)
        self.assertFalse(w.album.timer.isActive());before=dict(w.album.current_palette)
        worker.publish();w.album.poll();self.assertEqual(w.album.current_palette,before)

    def test_non_windows_fallback_does_not_start_worker_or_audio(self):
        w=self.window();w.album.worker_factory=None
        with patch('studio_qt.widgets.album_lighting.sys.platform','linux'):
            w.album.source.setCurrentText('Album artwork')
        self.assertIsNone(w.album.worker);self.assertIn('unavailable on this platform',w.album.status.text())
        self.assertFalse(w.runtime.busy);self.assertFalse(w.c.adapter.music_active)

    def test_widget_destruction_closes_media_without_deleted_qt_callbacks(self):
        from studio_qt.widgets.album_lighting import AlbumLightingPanel
        from PySide6.QtWidgets import QComboBox
        from PySide6.QtCore import QCoreApplication,QEvent
        preset=QComboBox();preset.addItem('Default')
        panel=AlbumLightingPanel(MusicRuntime(),preset,'Album artwork',self.factory)
        worker=self.workers[-1];panel.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.assertTrue(worker.closed);preset.deleteLater()

    def test_saved_source_does_not_start_capture_or_connect_devices(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'qt.json';w=self.window();w.preferences_store=PreferencesStore(path)
            self.select_album(w);w.save_preferences();self.assertEqual(PreferencesStore(path).load('live')['music']['color_source'],'Album artwork')
            w.close()
            values=PreferencesStore(path).load('live')
            self.assertEqual(values['music']['color_source'],'Album artwork')
            # Use production loading path; real media worker is substituted only.
            from studio_qt.music_window import MusicLiveWindow
            restored=MusicLiveWindow(preferences_path=path,album_worker_factory=self.factory)
            try:
                self.assertEqual(restored.album.source.currentText(),'Album artwork')
                self.assertFalse(restored.runtime.busy);self.assertFalse(restored.c.adapter.music_active)
                self.assertFalse(restored.c.adapter.session.wanted);self.assertFalse(restored.c.adapter.hue.wanted)
            finally:restored.close()


if __name__=='__main__':unittest.main()
