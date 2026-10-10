"""Opt-in bounded capture metadata. Never serialize frames or endpoint identities."""
import atexit
import datetime
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time


class Trace:
    def __init__(self,path):
        self.path=Path(path);self.queue=queue.Queue(256);self.seen={};self.lock=threading.Lock()
        self.closed=False;self.dropped=0;self.written=0
        self.thread=threading.Thread(target=self._write,name='Capture diagnostic writer',daemon=True);self.thread.start()

    def emit(self,event,generation=0,*,interval=0,**fields):
        now=time.monotonic();key=(event,generation,threading.get_ident())
        # Only static event names and scalar metadata; no exception text/identities.
        if any(type(value) not in (bool,int,float) for value in fields.values()):raise ValueError('Diagnostic metadata must be numeric or boolean')
        if not self.lock.acquire(blocking=False):return
        try:
            if self.closed:return
            if interval and now-self.seen.get(key,float('-inf'))<interval:return
            if len(self.seen)>1024:self.seen.clear()
            self.seen[key]=now
        finally:self.lock.release()
        record={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds'),
            'mono':round(now,3),'thread':threading.current_thread().name,'tid':threading.get_ident(),
            'event':event,'generation':generation,**fields}
        try:self.queue.put_nowait(record)
        except queue.Full:self.dropped+=1

    def _write(self):
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            with self.path.open('w',encoding='utf-8') as stream:
                while True:
                    try:record=self.queue.get(timeout=.2)
                    except queue.Empty:
                        if self.closed:return
                        continue
                    try:
                        if record is None:return
                        if self.written<10000:
                            stream.write(json.dumps(record)+'\n');stream.flush();self.written+=1
                    finally:self.queue.task_done()
        except OSError:
            # Optional diagnostics must never break capture or the GUI.
            self.closed=True

    def close(self):
        with self.lock:self.closed=True
        try:self.queue.put_nowait(None)
        except queue.Full:return
        self.thread.join(1)


_trace=None
_local=threading.local()

def enable(path):
    global _trace
    if _trace is not None:_trace.close()
    _trace=Trace(path)
    _trace.emit('session.environment',windows=sys.platform=='win32',python_major=sys.version_info.major,python_minor=sys.version_info.minor)
    return _trace

def bind(generation):_local.generation=generation

def emit(event,generation=None,**fields):
    if _trace is not None:_trace.emit(event,getattr(_local,'generation',0) if generation is None else generation,**fields)

if os.environ.get('OLIVE_STUDIO_DIAGNOSTICS')=='1':
    enable(Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'OliveRGBStudio'/'diagnostics'/'capture-latest.jsonl')
    atexit.register(lambda:_trace.close() if _trace is not None else None)
