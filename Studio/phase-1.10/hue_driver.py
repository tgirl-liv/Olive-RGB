"""HueBLE 2.2.3 adapter and serialized actor on Olive's existing BLE loop."""
import asyncio
import queue
import threading
import time


def rgb_to_xy(rgb):
    """Convert 8-bit sRGB to device-independent CIE xy (D65).

    Decode sRGB once, then use its own primaries. The former wide-gamut
    matrix changed chromaticity even for standard sRGB primaries/white.
    Brightness and bulb-specific gamut handling are separate from this
    conversion; never assume a bulb gamut or apply a corrective hue offset.
    """
    channels = [max(0, min(255, int(c))) / 255 for c in rgb]
    r, g, b = [((c + .055) / 1.055) ** 2.4 if c > .04045 else c / 12.92 for c in channels]
    x = .4124564*r + .3575761*g + .1804375*b
    y = .2126729*r + .7151522*g + .0721750*b
    z = .0193339*r + .1191920*g + .9503041*b
    total = x+y+z
    return (x/total, y/total) if total else (.3127, .3290)


def managed_light_class():
    from importlib.metadata import version
    if version('HueBLE') != '2.2.3':
        raise RuntimeError('This Hue adapter requires HueBLE 2.2.3; run install_dependencies.bat')
    import HueBLE

    class ManagedLight(HueBLE.HueBleLight):
        """Pin-specific hooks prevent HueBLE's implicit/untracked reconnects.

        The actor owns retries. HueBLE continues to own packet encoding, service
        detection, state subscriptions and the actual Bleak connection.
        """
        allow_connect = False

        async def connect(self, **kwargs):
            if self.connected:
                return
            if not self.allow_connect:
                raise ConnectionError('Hue disconnected; waiting for the bounded reconnect cycle')
            await super().connect(max_attempts=1, connection_timeout=12,
                                  wait_timeout=14, run_callbacks=False)

        async def pair(self):
            # Tv lamp must already be paired in Windows; never reset/unpair it.
            return

        def _disconnect_callback(self, client):
            # The actor observes .connected; do not spawn library reconnect tasks.
            return

        async def _read_gatt(self, property, **kwargs):
            return await super()._read_gatt(property, attempt_timeout=4, max_attempts=1)

        async def _write_gatt(self, property, data, **kwargs):
            return await super()._write_gatt(property, data, attempt_timeout=4, max_attempts=1)

    return ManagedLight


class HueDriver:
    def __init__(self, identity, emit):
        self.identity = dict(identity)
        self.emit = emit
        self.light = None
        self.capabilities = dict(power=False, brightness=False, color=False, temperature=False)

    @property
    def connected(self):
        return bool(self.light and self.light.connected)

    async def connect(self):
        from bleak import BleakScanner
        Light = managed_light_class()
        name = self.identity.get('name', 'Tv lamp')
        results = await BleakScanner.discover(timeout=6, return_adv=True)
        candidates = [device for device, adv in results.values()
                      if (adv.local_name or device.name or '').casefold() == name.casefold()]
        hint = self.identity.get('address_hint', '').upper()
        preferred = [d for d in candidates if d.address.upper() == hint]
        if len(preferred) == 1:
            device = preferred[0]
        elif len(candidates) == 1:
            device = candidates[0]
        else:
            raise RuntimeError(f'Hue: found {len(candidates)} bulbs named {name!r}; require one identifiable bulb')
        self.light = Light(device)
        self.light.allow_connect = True
        try:
            await self.light.connect()
        finally:
            self.light.allow_connect = False
        stable_id = None
        try:
            stable_id = await self.light.poll_zigbee_address()
        except Exception:
            pass
        expected = self.identity.get('zigbee_address')
        if expected and stable_id != expected:
            raise RuntimeError('Hue identity could not be verified; refusing a different or unidentified bulb')
        self.identity.update(name=name, address_hint=device.address)
        if stable_id:
            self.identity['zigbee_address'] = stable_id
        # Read the actual connected bulb's features; unsupported/failed probes
        # stay disabled. A successful power read also checks authentication.
        if not self.light.supports_on_off:
            raise RuntimeError('Hue bulb does not expose power control')
        power = await self.light.poll_power_state()
        self.capabilities['power'] = True
        for key, supported, probe in (
            ('brightness', self.light.supports_brightness, self.light.poll_brightness),
            ('color', self.light.supports_colour_xy, self.light.poll_colour_xy),
            ('temperature', self.light.supports_colour_temp, self.light.poll_colour_temp),
        ):
            try:
                if supported:
                    await probe()
                    self.capabilities[key] = True
            except Exception as error:
                self.emit('log', f'Hue {key} unavailable: {error}')
        self.emit('identity', dict(self.identity))
        self.emit('capabilities', dict(self.capabilities))
        self.emit('observed_power', bool(power))

    async def write(self, key, value):
        if not self.connected:
            raise ConnectionError('Hue connection lost')
        if key == 'power' and self.capabilities['power']:
            await self.light.set_power(bool(value))
        elif key == 'brightness' and self.capabilities['brightness']:
            await self.light.set_brightness(max(1, min(254, int(value))))
        elif key == 'color' and self.capabilities['color']:
            await self.light.set_colour_xy(*rgb_to_xy(value))
        elif key == 'temperature' and self.capabilities['temperature']:
            low = self.light.minimum_mireds or 153
            high = self.light.maximum_mireds or 500
            await self.light.set_colour_temp(max(low, min(high, int(value))))

    async def disconnect(self):
        light, self.light = self.light, None
        if light is not None:
            await asyncio.wait_for(light.disconnect(), 5)


class HueService:
    """One actor, one pending latest state, no new thread or event loop."""
    RETRY_DELAY = 2.0
    MAX_ATTEMPTS = 3
    WRITE_INTERVAL = .25
    POLL_INTERVAL = .05
    def __init__(self, identity, independent, follow=False, driver_factory=HueDriver):
        self.identity = dict(identity)
        self.independent = dict(independent)
        self.follow = bool(follow)
        self.master = dict(power=True, brightness=1.0, rgb=(255,255,255))
        self.events = queue.SimpleQueue()
        self._mailbox = threading.Lock()
        self._intent = None
        self._closed = False
        self.connected = False
        self.loop = self.task = self.driver = None
        self._async_task = None
        self.driver_factory = driver_factory

    def emit(self, kind, value):
        self.events.put((kind, value))

    def start(self, loop):
        self.loop = loop
        self.task = asyncio.run_coroutine_threadsafe(self.run(), loop)

    def request(self, intent):
        with self._mailbox:
            if not self._closed:
                self._intent = intent

    def update(self, independent=None, follow=None, master=None):
        with self._mailbox:
            if independent is not None: self.independent = dict(independent)
            if follow is not None: self.follow = bool(follow)
            if master is not None: self.master = dict(master)

    def desired(self):
        with self._mailbox:
            if not self.follow or self.master.get('music_independent', False):
                state = dict(self.independent)
                rgb = tuple(state.pop('rgb'))
                mode = state.pop('mode', 'color')
                if mode == 'color': state['color'] = rgb; state.pop('temperature', None)
                return state
            m = dict(self.master)
        intensity = max(m['rgb']) / 255.0 * m['brightness']
        return dict(power=bool(m['power'] and intensity > 0),
                    brightness=max(1, min(254, round(intensity*254))), color=tuple(m['rgb']))

    async def drop(self):
        self.connected = False
        self.emit('capabilities', dict(power=False, brightness=False, color=False, temperature=False))
        if self.driver:
            try:
                await self.driver.disconnect()
            except Exception as error:
                self.emit('log', f'Hue disconnect: {error}')
            self.driver = None

    async def run(self):
        self._async_task = asyncio.current_task()
        wanted, attempts, retry_at = False, 0, 0.0
        sent = {}
        last_write = 0.0
        field_cursor = 0
        try:
            while not self._closed:
                with self._mailbox:
                    intent, self._intent = self._intent, None
                if intent:
                    await self.drop()
                    wanted = intent == 'connect'
                    attempts, retry_at, sent = 0, 0.0, {}
                    self.emit('status', 'Disconnected')
                if self.driver and not self.driver.connected:
                    await self.drop()
                    # Connection loss uses the remaining attempts from this manual cycle.
                    retry_at, sent = time.monotonic()+self.RETRY_DELAY, {}
                    self.emit('status', 'Disconnected — reconnect pending' if attempts < self.MAX_ATTEMPTS else 'Disconnected — press Reconnect')
                if wanted and not self.driver and attempts < self.MAX_ATTEMPTS and time.monotonic() >= retry_at:
                    attempts += 1
                    self.emit('status', f'Connecting ({attempts}/{self.MAX_ATTEMPTS})')
                    self.driver = self.driver_factory(self.identity, self.emit)
                    try:
                        await asyncio.wait_for(self.driver.connect(), 40)
                        self.identity = dict(self.driver.identity)
                        self.connected = True
                        self.emit('status', 'Connected')
                        sent = {}
                    except Exception as error:
                        self.emit('log', f'Hue connection failed: {error}. For authentication errors, pair Tv lamp in Windows.')
                        await self.drop()
                        retry_at = time.monotonic()+self.RETRY_DELAY
                        self.emit('status', 'Disconnected — press Reconnect' if attempts == self.MAX_ATTEMPTS else 'Disconnected — retry pending')
                if self.driver and time.monotonic()-last_write >= self.WRITE_INTERVAL:
                    desired = self.desired()
                    caps = self.driver.capabilities
                    # OFF takes priority; do not send stale colors after power off.
                    fields = ['brightness','color','temperature']
                    keys = ['power'] if not desired.get('power') else ['power']+fields[field_cursor:]+fields[:field_cursor]
                    for key in keys:
                        if key in desired and caps.get(key) and sent.get(key) != desired[key]:
                            try:
                                await asyncio.wait_for(self.driver.write(key, desired[key]), 6)
                                sent[key] = desired[key]
                                if key in fields: field_cursor = (fields.index(key)+1)%len(fields)
                                # Brightness/color-temperature writes may change the active color mode.
                                if key == 'color': sent.pop('temperature', None)
                                if key == 'temperature': sent.pop('color', None)
                                last_write = time.monotonic()
                            except Exception as error:
                                self.emit('log', f'Hue command failed: {error}')
                                await self.drop()
                                wanted = False  # Do not flood auth/unsupported-command failures.
                                self.emit('status', 'Disconnected — press Reconnect')
                            break
                await asyncio.sleep(self.POLL_INTERVAL)
        finally:
            await self.drop()
            self.emit('status', 'Disconnected')

    async def close_async(self):
        with self._mailbox:
            self._closed = True
        if self._async_task:
            self._async_task.cancel()
            await asyncio.gather(self._async_task, return_exceptions=True)


class LightingRouter:
    """Application-layer fan-out; corner worker code/timing remains unchanged."""
    def __init__(self, corner, hue, power=True, brightness=1.0):
        self.corner, self.hue = corner, hue
        self.lock = threading.Lock()
        self.power, self.brightness = bool(power), float(brightness)
        self.rgb = (255,255,255)
        self.last_nonzero = self.rgb
        self.hue.update(master=dict(power=self.power, brightness=self.brightness, rgb=self.rgb))

    def set_rgb(self, r, g, b, force=False):
        with self.lock:
            self.rgb = tuple(max(0,min(255,int(c))) for c in (r,g,b))
            if max(self.rgb): self.last_nonzero = self.rgb
            self._send(force)

    def _send(self, force=False):
        rgb = tuple(round(c*self.brightness) for c in self.rgb) if self.power else (0,0,0)
        self.corner.set_rgb(*rgb, force=force)
        self.hue.update(master=dict(power=self.power, brightness=self.brightness, rgb=self.rgb))

    def set_master(self, power, brightness):
        with self.lock:
            self.power, self.brightness = bool(power), max(0,min(1,float(brightness)))
            if self.power and not max(self.rgb): self.rgb = self.last_nonzero
            self._send()
