"""LEDBLE protocol/adapter. Called only from Olive's existing BLE worker loop."""

import traceback

_diagnostic_callback = print

def set_diagnostic_callback(callback):
    """Route LEDBLE-only diagnostics through the existing thread-safe GUI log."""
    global _diagnostic_callback
    _diagnostic_callback = callback

def diagnostic(message):
    try:
        _diagnostic_callback(message)
    except Exception:
        pass  # Logging must never alter BLE control flow.

def report_error(stage, error):
    diagnostic(f"LEDBLE_ERROR,{stage},{type(error).__name__},winerror={getattr(error, 'winerror', None)},{error}")
    # Backend traceback distinguishes internal GATT discovery from connect setup.
    for frame in traceback.extract_tb(error.__traceback__)[-6:]:
        diagnostic(f"LEDBLE_TRACE,{PathName(frame.filename)},{frame.name},{frame.lineno},{frame.line}")

def PathName(filename):
    return filename.replace('\\', '/').rsplit('/', 1)[-1]

def is_retryable_discovery_error(error):
    """Only the reported WinRT GATT discovery failure permits cache retries."""
    if not isinstance(error, OSError) or getattr(error, "winerror", None) != -2147024838:
        return False
    for frame in traceback.extract_tb(error.__traceback__):
        filename = frame.filename.replace("\\", "/").lower()
        if "/bleak/backends/winrt/" in filename and frame.name in ("_get_services", "get_services"):
            return True
    return False


class LEDBLEDriver:
    FRIENDLY_NAME = "LEDBLE Strip"
    DEVICE_NAME = "LEDBLE-00-0806"
    SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
    WRITE_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
    POWER_CONFIRMED = False

    def __init__(self):
        self.client = None
        self.characteristic = None
        self.write_response = False

    @staticmethod
    def matches(name):
        # Family recognition only; discovery targets the user's exact strip.
        return isinstance(name, str) and name.upper().startswith("LEDBLE-")

    @staticmethod
    def rgb_packet(r, g, b):
        rgb = [max(0, min(255, int(value))) for value in (r, g, b)]
        return bytes([0x7E, 0x07, 0x05, 0x03, *rgb, 0x00, 0xEF])

    @staticmethod
    def power_packet(on):
        """UNCONFIRMED; builder only. Never sent automatically by Olive."""
        return bytes([0x7E, 0x04, 0x04, 0x01 if on else 0x00,
                      0xFF, 0xFF, 0xFF, 0x00, 0xEF])

    async def connect(self):
        from bleak import BleakClient, BleakScanner
        if self.client is not None and self.client.is_connected:
            diagnostic("LEDBLE_ALREADY_CONNECTED")
            return
        found_name = None
        def target(device, advertisement):
            nonlocal found_name
            name = advertisement.local_name or device.name
            matched = self.matches(name) and name.upper() == self.DEVICE_NAME
            if matched:
                found_name = name
            return matched

        try:
            diagnostic(f"LEDBLE_SCAN_START,{self.DEVICE_NAME}")
            device = await BleakScanner.find_device_by_filter(target, timeout=12.0)
            if device is None:
                raise RuntimeError(f"{self.DEVICE_NAME} not found; turn on the strip and close other BLE control apps")
            diagnostic(f"LEDBLE_SCAN_FOUND,{found_name},{device.address}")
        except BaseException as error:
            report_error("scan", error)
            raise

        diagnostic("LEDBLE_SERVICE_FILTER,FFE0")
        modes = (("default", None), ("cached", True), ("uncached", False))
        for mode, cache_setting in modes:
            client = None
            stage = "BleakClient construction"
            diagnostic(f"LEDBLE_CONNECT_ATTEMPT,{mode}")
            try:
                diagnostic("LEDBLE_CLIENT_CREATE")
                options = {"services": [self.SERVICE_UUID]}
                if cache_setting is not None:
                    options["winrt"] = {"use_cached_services": cache_setting}
                # Reuse the fresh scan's BLEDevice, never a saved address.
                client = BleakClient(device, **options)
                stage = "client.connect (includes automatic GATT discovery)"
                diagnostic(f"LEDBLE_CONNECT_START,{device.address}")
                await client.connect()
                diagnostic("LEDBLE_CONNECTED")
                stage = "service discovery result (client.services)"
                services = client.services
                diagnostic("LEDBLE_SERVICES_READY")
                stage = "FFE0 lookup"
                diagnostic("LEDBLE_FFE0_LOOKUP")
                service = services.get_service(self.SERVICE_UUID)
                if service is None:
                    raise RuntimeError("Selected LEDBLE strip does not expose FFE0")
                diagnostic("LEDBLE_FFE0_FOUND")
                stage = "FFE1 lookup"
                diagnostic("LEDBLE_FFE1_LOOKUP")
                characteristic = service.get_characteristic(self.WRITE_UUID)
                if characteristic is None:
                    raise RuntimeError("Selected LEDBLE strip does not expose FFE1 under FFE0")
                diagnostic("LEDBLE_FFE1_FOUND")
                stage = "FFE1 write properties"
                properties = characteristic.properties
                if "write-without-response" in properties:
                    response = False
                elif "write" in properties:
                    response = True
                else:
                    raise RuntimeError("LEDBLE FFE1 does not support writes")
                diagnostic("LEDBLE_WRITE_MODE,response={}".format(response))
            except BaseException as error:
                diagnostic(f"LEDBLE_CONNECT_FAIL,{mode},{type(error).__name__}: {error}")
                report_error(stage, error)
                cleaned_up = True
                if client is not None:
                    try:
                        await client.disconnect()
                        diagnostic(f"LEDBLE_CLEANUP_OK,{mode}")
                    except BaseException as cleanup_error:
                        cleaned_up = False
                        report_error("cleanup disconnect", cleanup_error)
                if (cleaned_up and mode != "uncached"
                        and stage == "client.connect (includes automatic GATT discovery)"
                        and is_retryable_discovery_error(error)):
                    continue
                raise  # Stop on unrelated errors, exhausted modes, or failed cleanup.
            self.client = client
            self.characteristic = characteristic
            self.write_response = response
            self.first_write_pending = True
            return

    async def set_rgb(self, r, g, b):
        if self.client is None or not self.client.is_connected:
            raise RuntimeError("LEDBLE strip is disconnected; press CONNECT to reconnect")
        first = getattr(self, "first_write_pending", True)
        if first:
            diagnostic("LEDBLE_FIRST_WRITE_START")
        try:
            await self.client.write_gatt_char(self.characteristic, self.rgb_packet(r, g, b),
                                              response=self.write_response)
        except Exception as error:
            report_error("first write" if first else "RGB write", error)
            raise
        if first:
            diagnostic("LEDBLE_FIRST_WRITE_OK")
            self.first_write_pending = False

    async def disconnect(self):
        client = self.client
        self.client = None
        self.characteristic = None
        if client is not None:
            await client.disconnect()
