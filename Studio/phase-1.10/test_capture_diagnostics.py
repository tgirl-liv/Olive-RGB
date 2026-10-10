"""Metadata/privacy and COM thread ownership; simulated native calls, not Windows."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from studio_qt.capture_diagnostics import Trace
from studio_qt.native_capture import audio_apartment,Recorder,Capture
from studio_qt.spectrum_engine import SpectrumMusicEngine
from studio_qt.music_engine import MusicEngine


class Ole:
    def __init__(self,result=0):self.result=result;self.calls=[];self.active=False
    def CoInitializeEx(self,*args):self.calls.append(('init',threading.get_ident()));self.active=True;return self.result
    def CoUninitialize(self):self.calls.append(('release',threading.get_ident()));self.active=False


class DiagnosticsTests(unittest.TestCase):
    def test_com_owned_success_and_existing_mta_balance(self):
        for code in (0,1):
            ole=Ole(code)
            with audio_apartment(ole):self.assertTrue(ole.active)
            self.assertFalse(ole.active);self.assertEqual([c[0] for c in ole.calls],['init','release'])
    def test_existing_sta_not_uninitialized(self):
        ole=Ole(-2147417850)
        with audio_apartment(ole):pass
        self.assertEqual([c[0] for c in ole.calls],['init'])
    def test_com_failure_does_not_enter_capture_or_uninitialize(self):
        ole=Ole(-2147467259)
        with self.assertRaisesRegex(OSError,'HRESULT 0x80004005'):
            with audio_apartment(ole):self.fail('Capture must not run')
        self.assertEqual([c[0] for c in ole.calls],['init'])
    def test_capture_thread_initializes_com_and_releases_after_engine_error(self):
        ole=Ole();messages=[];calls=[]
        def native(engine):
            self.assertTrue(ole.active);calls.append(threading.get_ident());raise RuntimeError('native failure')
        engine=SpectrumMusicEngine(lambda *args:None,lambda *args:None,lambda:None,messages.append)
        with patch('studio_qt.spectrum_engine.audio_apartment',lambda:audio_apartment(ole)),patch.object(MusicEngine,'_run',native):
            engine.start();engine.thread.join(2)
        self.assertFalse(engine.thread.is_alive());self.assertFalse(engine.running)
        self.assertEqual(len(calls),1);self.assertNotEqual(calls[0],threading.get_ident())
        self.assertEqual(ole.calls,[('init',calls[0]),('release',calls[0])]);self.assertIn('native failure',messages[-1])
    def test_rate_limited_content_free_timestamped_thread_generation_log(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'capture.jsonl';trace=Trace(path)
            for _ in range(100):trace.emit('music.frame.mailbox',7,interval=1,silence=True)
            trace.queue.join();trace.close()
            records=[json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(records),1);record=records[0]
            self.assertEqual(record['generation'],7);self.assertTrue(record['silence'])
            self.assertIn('utc',record);self.assertIn('mono',record);self.assertEqual(record['tid'],threading.get_ident())
            self.assertNotIn('samples',record);self.assertNotIn('device_id',record)
    def test_payloads_and_identifiers_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            trace=Trace(Path(directory)/'capture.jsonl')
            try:
                for value in ('endpoint-secret',[1,2,3],{'password':'secret'}):
                    with self.assertRaises(ValueError):trace.emit('unsafe',value=value)
            finally:trace.close()
    def test_observers_preserve_native_values_and_cleanup(self):
        calls=[];data=object()
        class Native:
            monitors=[{},{}]
            def __enter__(self):calls.append('enter');return self
            def __exit__(self,*args):calls.append('close')
            def record(self,**kwargs):return [data]
            def grab(self,region):return data
        with Recorder(Native()) as recorder:self.assertIs(recorder.record(numframes=1)[0],data)
        with Capture(Native()) as capture:
            self.assertEqual(len(capture.monitors),2);self.assertIs(capture.grab({}),data)
        self.assertEqual(calls,['enter','close','enter','close'])
    def test_full_queue_drops_metadata_without_blocking_producer(self):
        gate=threading.Event()
        with tempfile.TemporaryDirectory() as directory,patch.object(Trace,'_write',lambda self:gate.wait(2)):
            trace=Trace(Path(directory)/'capture.jsonl')
            try:
                start=time.monotonic()
                for index in range(300):trace.emit('music.frame',index)
                self.assertLess(time.monotonic()-start,.2)
                self.assertEqual(trace.queue.qsize(),256);self.assertGreater(trace.dropped,0)
            finally:gate.set();trace.thread.join(2);trace.close()

    def test_logging_failure_cannot_break_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            trace=Trace(Path(directory))
            trace.thread.join(2);self.assertTrue(trace.closed)
            trace.emit('music.runtime.request',1);trace.close()

if __name__=='__main__':unittest.main()
