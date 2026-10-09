"""Verbatim BluetoothWorker isolated from olive_rgb.py for Qt.
The original application is untouched. test_corner_live asserts class AST equality.
Only this module imports the existing transport dependencies; DEMO never imports it.
"""
import asyncio
import threading
import time
from lotus_lamp import LotusLamp, DeviceConfig
from ledble_driver import LEDBLEDriver
LIGHT_UPDATE_INTERVAL = 0.25

class BluetoothWorker:
    def __init__(self, status_callback, log_callback):
        self.status_callback = status_callback
        self.log_callback = log_callback

        self.loop = None
        self.lamp = None
        self.lotus_lamp = None
        self.device_family = "LotusLamp Corner Lamp"
        self.connecting = False
        self.connected = False

        self.ready = threading.Event()

        self.last_rgb = None
        self.last_send_time = 0
        # Serialize BLE writes. Reactive modes can request colors faster than
        # the underlying GATT client finishes a write/discovery operation.
        self.rgb_lock = None

        self.thread = threading.Thread(
            target=self._start_loop,
            daemon=True
        )

        self.thread.start()

    def _debug(self, message):
        # Console output is intentional in v1.0.2 Debug.  It bypasses
        # Tkinter so we can see worker-thread failures even if GUI callbacks
        # are the thing that is broken in a frozen PyInstaller executable.
        try:
            print(f"[BLE DEBUG] {message}", flush=True)
        except Exception:
            pass

    def _start_loop(self):
        self._debug(f"worker thread started: {threading.current_thread().name}")
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.rgb_lock = asyncio.Lock()
            self._debug(f"event loop created; closed={self.loop.is_closed()}")

            self._debug("constructing LotusLamp with explicit device config")
            device_config = DeviceConfig(
                name="MELK-OA10   7F",
                address="BE:28:87:00:08:7F",
            )
            self.lamp = LotusLamp(device_config=device_config)
            self.lotus_lamp = self.lamp
            self._debug(f"LotusLamp constructed: {type(self.lamp).__name__}")

            self.ready.set()
            self._debug("ready set; entering run_forever")
            self.loop.run_forever()
            self._debug("run_forever returned")

        except Exception as e:
            self.ready.set()
            self._debug(f"worker exception: {type(e).__name__}: {e!r}")
            try:
                self.log_callback(f"Bluetooth worker error: {type(e).__name__}: {e}")
            except Exception as callback_error:
                self._debug(f"log callback also failed: {callback_error!r}")

    def _future_done(self, future):
        try:
            exc = future.exception()
            if exc is None:
                self._debug("submitted coroutine completed normally")
            else:
                self._debug(f"submitted coroutine exception: {type(exc).__name__}: {exc!r}")
                self.log_callback(f"Bluetooth task error: {type(exc).__name__}: {exc}")
        except Exception as e:
            self._debug(f"future inspection failed: {type(e).__name__}: {e!r}")

    def _submit(self, coroutine):
        self._debug(f"submit requested; ready={self.ready.is_set()} loop={self.loop!r}")
        if not self.ready.wait(timeout=5):
            self._debug("ready wait timed out")
            self.log_callback("Bluetooth worker failed to start")
            try:
                coroutine.close()
            except Exception:
                pass
            return None

        if self.loop is None:
            self._debug("event loop is None")
            self.log_callback("Bluetooth event loop unavailable")
            try:
                coroutine.close()
            except Exception:
                pass
            return None

        self._debug(
            f"before submit: running={self.loop.is_running()} closed={self.loop.is_closed()} "
            f"thread_alive={self.thread.is_alive()}"
        )
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
            self._debug(f"coroutine submitted: {future!r}")
            future.add_done_callback(self._future_done)
            return future
        except Exception as e:
            self._debug(f"run_coroutine_threadsafe failed: {type(e).__name__}: {e!r}")
            try:
                coroutine.close()
            except Exception:
                pass
            self.log_callback(f"Bluetooth submit error: {type(e).__name__}: {e}")
            return None

    async def _connect(self, device_family="LotusLamp Corner Lamp"):
        self._debug("_connect coroutine ENTERED")
        if self.connecting:
            return
        self.connecting = True
        try:
            if device_family not in ("LotusLamp Corner Lamp", "LEDBLE Strip"):
                raise ValueError("Unknown controller family")
            if device_family != self.device_family:
                # Switch adapters on the existing loop, after any in-flight RGB write.
                self.connected = False
                async with self.rgb_lock:
                    await self.lamp.disconnect()
                    self.lamp = LEDBLEDriver() if device_family == "LEDBLE Strip" else self.lotus_lamp
                    self.device_family = device_family
                    self.last_rgb = None
                    self.last_send_time = 0
            self.status_callback(
                "🟡 CONNECTING..."
            )

            self.log_callback(
                f"Connecting to {self.device_family}..."
            )

            await self.lamp.connect()

            # Give Windows/Bleak a brief settling window after GATT connect.
            # This prevents reactive modes from racing service discovery.
            await asyncio.sleep(0.75)

            self.connected = True

            self.status_callback(
                f"🟢 {self.device_family}"
            )

            self.log_callback(
                f"✓ {self.device_family} connected"
            )

        except Exception as e:
            self.connected = False

            self.status_callback(
                "🔴 ERROR"
            )

            self.log_callback(
                f"Bluetooth connection error: {e}"
            )

        finally:
            self.connecting = False

    def connect(self, device_family="LotusLamp Corner Lamp"):
        self._debug("connect() called from GUI")
        if not self.ready.wait(timeout=5):
            self.status_callback(
                "🔴 NOT READY"
            )

            self.log_callback(
                "Bluetooth worker failed to initialize"
            )

            return

        self._submit(
            self._connect(device_family)
        )

    async def _set_rgb(self, r, g, b):
        if not self.connected:
            return

        try:
            # Only one GATT color write may be in flight at a time.
            # This keeps Music/Movie/Gaming from racing Bleak service setup.
            if self.rgb_lock is None:
                return
            async with self.rgb_lock:
                await self.lamp.set_rgb(
                    int(r),
                    int(g),
                    int(b)
                )

        except Exception as e:
            self.log_callback(
                f"RGB error: {e}"
            )

    def set_rgb(self, r, g, b, force=False):
        if not self.connected:
            return

        rgb = (
            max(0, min(255, int(r))),
            max(0, min(255, int(g))),
            max(0, min(255, int(b)))
        )

        now = time.monotonic()

        if not force:
            elapsed = now - self.last_send_time

            # Never send faster than the lamp's conservative BLE limit.
            if elapsed < LIGHT_UPDATE_INTERVAL:
                return

            if self.last_rgb is not None:
                difference = max(
                    abs(rgb[i] - self.last_rgb[i])
                    for i in range(3)
                )

                # Ignore tiny screen fluctuations. Still refresh periodically
                # so the lamp cannot get stranded on an old color.
                if difference < 10 and elapsed < 1.5:
                    return

        self.last_rgb = rgb
        self.last_send_time = now

        self._submit(
            self._set_rgb(
                rgb[0],
                rgb[1],
                rgb[2]
            )
        )

    async def _disconnect(self):
        try:
            if self.connected:
                await self.lamp.disconnect()

        except Exception:
            pass

        self.connected = False

        self.status_callback(
            "⚪ DISCONNECTED"
        )

    def disconnect(self):
        if self.ready.is_set():
            self._submit(
                self._disconnect()
            )
