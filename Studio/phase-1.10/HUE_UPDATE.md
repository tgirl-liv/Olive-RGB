# Olive RGB v1.5 Hue Preview

Built from the latest v1.4.2 LEDBLE Compatibility project supplied in this chat. This is a complete source package; build a new executable locally. No physical Bluetooth connection was attempted during this integration.

## Setup

1. Close Olive RGB. Back up `%APPDATA%\OliveRGB\settings.json` if it exists (for example, as `settings.pre-hue.json`).
2. Extract this package to a new folder. Keep the original application available.
3. Pair **Tv lamp** in Windows Bluetooth settings, as in your successful test. This integration never resets, unpairs, or automatically pairs the bulb. Close other apps actively controlling it.
4. Run `install_dependencies.bat` using Python 3.14, then `py olive_rgb.py`. To build an executable, run `build_windows.bat`; the new executable is `dist\Olive RGB.exe`.
5. If `py` is unavailable, open PowerShell in the extracted folder and use:

```powershell
$rgbPython = 'C:\Users\olive\AppData\Local\Programs\Python\Python314\python.exe'
& $rgbPython -m pip install -r requirements.txt
& $rgbPython olive_rgb.py
```

For an executable with that interpreter, install PyInstaller and run the supplied specification:

```powershell
& $rgbPython -m pip install pyinstaller
& $rgbPython -m PyInstaller --noconfirm --clean 'Olive RGB.spec'
```

6. Open **HUE / MASTER**, then **Connect / Reconnect**. The existing connection controls still belong to the original corner/strip device. Hue does not automatically connect at startup.

## Controls and capability checks

Follow Master defaults off. With it off, Hue power, brightness, color and white temperature are independent. Unsupported controls stay disabled. The connected bulb's HueBLE service capabilities and successful state reads determine which controls become available; brightness and color have not been physically verified here. Your previous physical test established power control only.

With Follow Master on, Hue follows Master power, brightness, color and the existing Light presets and reactive output. Its independent settings remain saved and return when Follow Master is disabled. White-only bulbs follow power and supported brightness, skipping RGB. White temperature is an independent control in mireds (153 cooler to 500 warmer); the library's range is used, not a measured bulb-specific range.

Master defaults preserve existing RGB output. Master power off sends black through the existing corner RGB path. Hue receives its own power command. Master brightness scales the original RGB output, and Hue brightness also follows the RGB intensity. Hue must be connected with Follow Master enabled to start reactive modes when the corner is disconnected.

## Connection and worker behavior

Hue scans for the exact advertised name `Tv lamp` and passes the fresh BLEDevice to HueBLE. Settings store the name, learned address hint and a stable Zigbee identifier when readable. A saved stable identifier must match on reconnect. Ambiguous name matches without a matching hint fail rather than choosing arbitrarily. The historical address is not hardcoded.

Hue uses one actor on the existing Bluetooth worker's persistent asyncio loop. It has its own latest-state mailbox, serializes writes at least 250 ms apart, and coalesces rapid updates. There is no new Bluetooth thread or event loop. At most three connection attempts occur per manual Connect cycle, including later connection losses; command failures require manual Reconnect. A connection attempt is limited to 40 seconds, writes to 6 seconds, and disconnect to 5 seconds. Disconnect requests during connection are handled after that bounded attempt; application shutdown cancels the attempt.

HueBLE's automatic reconnect and implicit command reconnect paths are constrained by a small version-specific subclass. Packet encoding and service detection remain in HueBLE. This adapter pins HueBLE 2.2.3 and bleak-retry-connector 4.7.1. The inspected Python 3.14.8 environment had Bleak 3.0.2 and no installed HueBLE; these packages were inspected and tested in an isolated workspace. The existing environment was not changed. Your separate test_hue.py was not found.

## Hardware checklist (pending)

1. Start with Follow Master off. Connect Tv lamp; verify status and toggle OFF, then ON.
2. Check detected capabilities. Test brightness and RGB or white temperature only if enabled.
3. Connect the corner lamp through its original controls. Verify its usual presets, Music, Movie and Gaming behavior.
4. Change Master with Follow Master off; confirm Hue's independent settings remain unaffected.
5. Enable Follow Master; check Master power, brightness, color and compatible presets/modes.
6. Test both connected, only corner connected, only Hue connected, and both disconnected.
7. Disconnect/power-cycle Hue. Confirm the corner and GUI remain responsive, retries stop after the bounded cycle, and manual Reconnect works.
8. Exit while connected and while connecting. Confirm the app process exits. Relaunch and confirm saved settings.

## Software validation

16 automated tests passed: eight existing LEDBLE tests and eight Hue tests, including the real pinned HueBLE API with mocked Bluetooth. They cover discovery with a fresh device, power/brightness/color calls, capabilities, independent/Master routing, coalescing, serial writes, reconnect limits and cancellation. A separate Tk smoke check passed for GUI initialization, capability gating, Follow Master, Hue-only mode startup, settings export and shared-loop shutdown, using mocked hardware.

BluetoothWorker, MusicEngine and ScreenEngine match the baseline source exactly. LEDBLE driver, album helper and icons are byte-identical. Python/spec syntax was checked. Physical Bluetooth, actual reactive capture and the packaged executable have not been tested. This source package does not contain the old executable.

After installing dependencies, run:

```powershell
py -B -m unittest discover -p "test_*.py" -v
```

## Files changed

- `olive_rgb.py`: version, additive panel, application-level RGB fan-out, Hue-only mode eligibility, settings and coordinated exit.
- `hue_driver.py` (new): HueBLE adapter, capability checks, bounded actor and Master router.
- `hue_controls.py` (new): separate Hue/Master tab and persistence.
- `requirements.txt`: pinned Hue dependencies.
- `build_windows.bat`, `Olive RGB.spec`, `Olive RGB v1.4 Preview.spec`: include Hue library, version metadata and retry connector in builds. The older preview spec retains its original filename.
- `test_hue_api.py`, `test_hue_integration.py` (new): mock-based regression tests.
- `README.md`, `TESTING.md`, `HUE_UPDATE.md`: setup, validation and rollback documentation.

The inherited LEDBLE documents and BASELINE_SHA256.json remain historical baseline references. The original worker and driver were not rewritten.

## Rollback

Close the new app and extract the separately supplied `Olive RGB pre-Hue rollback.zip`. It is an exact copy of the original v1.4.2 ZIP, verified by SHA-256. Launch that version's original executable or source. If desired, restore your saved pre-Hue settings.json while the app is closed. The older app otherwise ignores the added Hue/Master settings. No Git repository was available for a baseline commit.
