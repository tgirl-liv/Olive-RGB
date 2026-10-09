"""Independent manual Hue actor. The unchanged HueDriver owns all BLE details."""
import asyncio
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class HueEvent:
    generation: int
    kind: str
    value: object


def driver_factory(identity, emit):
    from hue_driver import HueDriver
    return HueDriver(identity, emit)


class HueSession:
    WRITE_INTERVAL = .25

    def __init__(self, notify, finished, factory=None, identity=None):
        self.notify, self.finished = notify, finished
        self.factory = factory or driver_factory
        self.identity = dict(identity) if identity is not None else None
        self.lock = threading.RLock()
        self.generation = 0
        self.wanted = self.closed = False
        self.pending = {}
        self.thread = self.driver = None
        self.cleanup_failed = False

    def emit(self, generation, kind, value):
        self.notify(HueEvent(generation, kind, value))

    def connect(self):
        with self.lock:
            if self.closed or self.wanted:return
            self.generation += 1
            self.wanted = True
            self.pending = {}
            self.emit(self.generation, 'status', 'connecting')
            if self.thread is None:
                self.thread = threading.Thread(target=self._thread, name='Studio Hue BLE', daemon=True)
                self.thread.start()

    def disconnect(self):
        with self.lock:
            if self.closed:return
            self.generation += 1
            self.wanted = False
            self.pending = {}
            self.emit(self.generation, 'status', 'disconnecting' if self.thread else 'disconnected')

    def update(self, values):
        with self.lock:
            if self.wanted and not self.closed:self.pending.update(values)

    def close(self):
        with self.lock:
            if self.closed:return
            self.closed = True
            self.wanted = False
            self.pending = {}
            self.generation += 1
            if self.thread is None:self.finished()

    def valid(self, generation):
        with self.lock:return not self.closed and self.wanted and self.generation == generation

    async def operation(self, awaitable, generation, timeout):
        task = asyncio.ensure_future(awaitable)
        end = time.monotonic() + timeout
        try:
            while not task.done():
                await asyncio.wait({task}, timeout=.025)
                if not self.valid(generation):return False
                if time.monotonic() > end:raise TimeoutError('Hue operation timed out')
            task.result()
            return self.valid(generation)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def drop(self):
        driver, self.driver = self.driver, None
        if driver is not None:
            try:await asyncio.wait_for(driver.disconnect(), 6)
            except Exception:
                self.cleanup_failed = True
                raise

    def _thread(self):
        try:asyncio.run(self.run())
        except Exception as error:self.emit(self.generation, 'error', f'Hue session: {error}')
        finally:
            with self.lock:self.closed = True;self.wanted = False;self.pending = {}
            self.finished()

    async def run(self):
        active = -1
        sent = {}
        last_write = 0.
        cursor = 0
        disconnected = -1
        try:
            while not self.closed:
                with self.lock:generation, wanted = self.generation, self.wanted
                try:
                    if self.driver is not None and (not wanted or active != generation):
                        await self.drop()
                    if not wanted:
                        if disconnected != generation:
                            disconnected = generation
                            # A failure has already provided its meaningful error.
                            if active != generation:self.emit(generation, 'status', 'disconnected')
                        await asyncio.sleep(.025)
                        continue
                    if self.driver is None:
                        active = generation
                        if self.identity is None:
                            from .hue_identity import load_hue_identity
                            self.identity = load_hue_identity()
                        self.driver = self.factory(dict(self.identity), lambda kind, value, gen=generation: self.emit(gen, kind, value))
                        if not await self.operation(self.driver.connect(), generation, 40):continue
                        if not self.driver.connected:raise ConnectionError('Hue did not establish a connection')
                        self.identity = dict(self.driver.identity)
                        # Power is emitted by the driver. Read brightness only when
                        # its existing capability probe succeeded; no RGB inference.
                        if self.driver.capabilities.get('brightness'):
                            async def read_brightness():
                                value = await self.driver.light.poll_brightness()
                                self.emit(generation, 'observed_brightness', value)
                            if not await self.operation(read_brightness(), generation, 6):continue
                        sent = {};last_write = 0.
                        self.emit(generation, 'capabilities', dict(self.driver.capabilities))
                        self.emit(generation, 'identity', dict(self.identity))
                        self.emit(generation, 'status', 'connected')
                    if not self.driver.connected:raise ConnectionError('Hue connection lost')
                    with self.lock:desired = dict(self.pending)
                    if time.monotonic() - last_write >= self.WRITE_INTERVAL:
                        fields = ['brightness', 'color']
                        keys = ['power'] if desired.get('power') is False else ['power'] + fields[cursor:] + fields[:cursor]
                        for key in keys:
                            if key not in desired or not self.driver.capabilities.get(key) or sent.get(key) == desired[key]:continue
                            value = desired[key]
                            if not await self.operation(self.driver.write(key, value), generation, 6):break
                            sent[key] = value
                            last_write = time.monotonic()
                            if key in fields:cursor = (fields.index(key) + 1) % len(fields)
                            break
                    await asyncio.sleep(.025)
                except Exception as error:
                    with self.lock:
                        current = generation == self.generation and not self.closed
                        if current:self.wanted = False;self.pending = {}
                    if current:self.emit(generation, 'error', f'{type(error).__name__}: {error} · Connect Hue to retry')
                    try:await self.drop()
                    except Exception as cleanup:self.emit(generation, 'error', f'{error}; disconnect: {cleanup}')
                    if self.cleanup_failed:
                        # Do not replace an uncertain connection with another
                        # client. Leave a terminal error until LIVE is reopened.
                        with self.lock:self.closed = True;self.wanted = False;self.pending = {}
        finally:
            try:await self.drop()
            except Exception as error:self.emit(self.generation, 'error', f'Hue cleanup: {error}')
