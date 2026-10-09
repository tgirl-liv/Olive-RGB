"""Bounded Corner Lamp session on the existing worker's sole asyncio loop.

One bootstrap/cleanup thread waits for the worker; it is NOT another BLE loop.
Only immutable RGB snapshots and a connection intent cross the mailbox lock.
"""
import asyncio
import threading
import time
from dataclasses import dataclass

LAMP_NAME = 'MELK-OA10   7F'
LAMP_ADDRESS = 'BE:28:87:00:08:7F'


@dataclass(frozen=True)
class CornerEvent:
    generation: int
    state: str
    message: str


def worker_factory(status, log):
    from .corner_worker import BluetoothWorker
    return BluetoothWorker(status, log)


class CornerSession:
    def __init__(self, notify, finished, factory=None):
        self.notify, self.finished = notify, finished
        self.factory = factory or worker_factory
        self.lock = threading.RLock()
        self.generation = 0
        self.wanted = False
        self.closed = False
        self.pending = None
        self.thread = None
        self.worker = None
        self._operation_generation = 0
        self._write_generation = 0
        self._last_submit = None
        self._write_task = None
        self._error = ''

    def _emit(self, generation, state, message):
        self.notify(CornerEvent(generation, state, message))

    def connect(self):
        with self.lock:
            if self.closed or self.wanted:return
            self.generation += 1;self.wanted = True;self.pending = None
            generation = self.generation
            self._emit(generation,'connecting',f'Connecting to {LAMP_NAME} · {LAMP_ADDRESS}')
            if self.thread is None:
                self.thread = threading.Thread(target=self._bootstrap,name='Corner session lifecycle',daemon=True)
                self.thread.start()

    def disconnect(self):
        with self.lock:
            if self.closed:return
            self.generation += 1;self.wanted = False;self.pending = None
            self._emit(self.generation,'disconnecting' if self.worker else 'disconnected','Disconnect requested' if self.worker else 'Disconnected')

    def color(self,rgb):
        with self.lock:
            if self.closed or not self.wanted:return False
            self.pending=(self.generation,tuple(rgb));return True

    def close(self):
        with self.lock:
            if self.closed:return
            self.closed=True;self.wanted=False;self.pending=None;self.generation+=1
            if self.thread is None:self.finished()

    def valid(self,generation):
        with self.lock:return not self.closed and self.wanted and generation==self.generation

    def _log(self,message):
        # The worker catches connect/write exceptions; retain them for the actor.
        if 'error' in message.lower() or 'failed' in message.lower():self._error=str(message)

    def _bootstrap(self):
        try:
            self.worker=self.factory(lambda message:None,self._log)
            w=self.worker
            if not w.ready.wait(5) or w.loop is None or w.lamp is None:raise RuntimeError(self._error or 'Bluetooth worker did not initialize')
            original_submit=w._submit
            def submit(coroutine):
                future=original_submit(coroutine);self._last_submit=future;return future
            w._submit=submit
            original_write=w._set_rgb
            async def guarded_write(*rgb):
                self._write_task=asyncio.current_task()
                if self.valid(self._write_generation):await original_write(*rgb)
            w._set_rgb=guarded_write
            future=w._submit(self._run())
            if future is None:raise RuntimeError('Could not start Corner Lamp session')
            # Join only here, never in a Qt callback. _run requests loop shutdown.
            w.thread.join()
            if not w.loop.is_closed():w.loop.close()
        except Exception as error:
            with self.lock:self.wanted=False;self.pending=None
            self._emit(self.generation,'error',f'LIVE unavailable: {type(error).__name__}: {error}')
            if self.worker and self.worker.loop and self.worker.loop.is_running():
                self.worker.loop.call_soon_threadsafe(self.worker.loop.stop)
                self.worker.thread.join(5)
            if self.worker and self.worker.loop and not self.worker.thread.is_alive() and not self.worker.loop.is_closed():
                self.worker.loop.close()
            # A failed initialization is terminal for this adapter. Reopen LIVE.
            with self.lock:self.closed=True
        finally:
            with self.lock:self.closed=True;self.wanted=False;self.pending=None
            self.finished()

    async def _operation(self,awaitable,generation,timeout):
        task=asyncio.ensure_future(awaitable)
        deadline=time.monotonic()+timeout
        try:
            while not task.done():
                await asyncio.wait({task},timeout=.025)
                if not self.valid(generation):
                    task.cancel();await asyncio.gather(task,return_exceptions=True);return False
                if time.monotonic()>deadline:raise TimeoutError('Bluetooth operation timed out')
            task.result();return self.valid(generation)
        finally:
            if not task.done():task.cancel();await asyncio.gather(task,return_exceptions=True)

    async def _drop(self):
        w=self.worker
        try:
            # Cancellation of the cross-thread Future can precede completion of
            # its asyncio task. Drain that actual task before disconnecting.
            task=self._write_task
            if task is not None and not task.done():
                task.cancel();await asyncio.gather(task,return_exceptions=True)
            # _disconnect preserves the known connection/status behavior.
            await asyncio.wait_for(w._disconnect(),6)
            # A cancelled/failed connect may own a client before connected=True.
            client=getattr(w.lamp,'client',None)
            if client is not None and client.is_connected:
                await asyncio.wait_for(client.disconnect(),6)
        finally:
            w.connected=False;w.connecting=False;w.last_rgb=None;w.last_send_time=0

    def _fail(self,generation,error):
        with self.lock:
            if generation!=self.generation or self.closed:return
            self.wanted=False;self.pending=None
        self._emit(generation,'error',str(error)+' · press Connect to retry')

    async def _run(self):
        w=self.worker;attempted=-1;disconnected=-1;connected_generation=-1
        try:
            while True:
                with self.lock:
                    closed,wanted,generation,pending=self.closed,self.wanted,self.generation,self.pending
                if closed:break
                if not wanted:
                    if disconnected!=generation:
                        await self._drop();disconnected=generation
                        # Do not replace a failure with a misleading success state.
                        if attempted!=generation:self._emit(generation,'disconnected','Disconnected')
                    await asyncio.sleep(.05);continue
                try:
                    if w.connected and connected_generation!=generation:
                        await self._drop()
                    if not w.connected:
                        if attempted==generation:
                            await asyncio.sleep(.05);continue
                        attempted=generation;self._operation_generation=generation;self._error=''
                        if not await self._operation(w._connect('LotusLamp Corner Lamp'),generation,40):
                            await self._drop();continue
                        client=getattr(w.lamp,'client',None)
                        if self._error or not w.connected or client is None or not client.is_connected:
                            raise ConnectionError(self._error or 'Lamp did not establish a BLE connection')
                        if str(client.address).upper()!=LAMP_ADDRESS:
                            raise ConnectionError('Connected address does not match the configured Corner Lamp')
                        w.last_rgb=None;w.last_send_time=0
                        connected_generation=generation
                        self._emit(generation,'connected',f'Connected · {LAMP_NAME} · {LAMP_ADDRESS}')
                    if not w.lamp.client.is_connected:raise ConnectionError('Corner Lamp connection lost')
                    with self.lock:pending=self.pending
                    if pending and pending[0]==generation:
                        rgb=pending[1]
                        if rgb==w.last_rgb:
                            with self.lock:
                                if self.pending==pending:self.pending=None
                        else:
                            self._error='';self._write_generation=generation;self._last_submit=None
                            w.set_rgb(*rgb)  # Existing 0.25s / delta limiter. Never force.
                            future=self._last_submit
                            if future is not None:
                                if not await self._operation(asyncio.wrap_future(future),generation,8):
                                    await self._drop();continue
                                if self._error:raise ConnectionError(self._error)
                                with self.lock:
                                    if self.pending==pending:self.pending=None
                    await asyncio.sleep(.025)
                except Exception as error:
                    self._fail(generation,error)
                    try:await self._drop()
                    except Exception as cleanup:self._emit(generation,'error',f'{error}; cleanup: {cleanup}')
        except Exception as error:
            self._fail(self.generation,error)
        finally:
            try:await self._drop()
            except Exception as error:self._emit(self.generation,'error',f'Disconnect cleanup failed: {error}')
            # All owned I/O is awaited/cancelled before stopping this owned loop.
            w.loop.call_later(.05,w.loop.stop)
