# LEDBLE update — v1.4.2-preview

Baseline: the exact supplied Olive RGB v1.4.1 Customization Update.zip.
This is a complete source project; no EXE or physical testing is included.

## Usage
Close the old app, extract this project, run install_dependencies.bat, then
run `py olive_rgb.py`. Choose **LEDBLE Strip** in the header and press CONNECT.
The menu chooses the next connection target; the status shows the connected
family. Only one device is controlled at a time. Switching and pressing CONNECT
stops reactive modes, disconnects the previous controller, then connects the
selected one. Select **LotusLamp Corner Lamp** to return to your original lamp.
The selection persists. The default remains LotusLamp.

## Driver and identification
New ledble_driver.py defines LEDBLEDriver, with connect/set_rgb/disconnect methods
matching the existing lamp interface. Family identification requires LEDBLE-;
discovery intentionally targets the exact LEDBLE-00-0806 name supplied by the user.
No device is claimed merely because it advertises FFE0/FFE1. The connected device
must expose service 0000ffe0-0000-1000-8000-00805f9b34fb and its characteristic
0000ffe1-0000-1000-8000-00805f9b34fb. Writes prefer response=False when supported,
otherwise use response=True. No notification subscription is needed for RGB.

Packet builder: bytes([0x7E,0x07,0x05,0x03,R,G,B,0x00,0xEF]), with each channel
converted to int and clamped to 0–255.
Red: 7E070503FF000000EF
Green: 7E07050300FF0000EF
Blue: 7E0705030000FF00EF

Power packet builders exist, marked POWER_CONFIRMED=False:
ON 7E040401FFFFFF00EF; OFF 7E040400FFFFFF00EF.
They are UNCONFIRMED and are never transmitted by the app. No power UI was added.

## Worker integration and preservation
The existing worker creates LotusLamp using the same DeviceConfig, name, and
address, and retains that instance for switching back. No LotusLamp dependency
code or packets were replaced. Narrow worker changes add family state, a
concurrent-connect guard, adapter switching, and family-specific status messages.
Switching happens on its existing loop and waits for its existing RGB lock before
disconnecting. The 750 ms post-connect settling delay remains.
_submit, _set_rgb, set_rgb, _disconnect, disconnect, _future_done and _debug are
structurally unchanged. Thus the shared serialized write path, 0.25 s limiter,
delta threshold of 10, 1.5 s refresh, and original explicit force behavior remain.
No new Bluetooth thread or event loop exists. Discovery and writes run through
the worker, never the UI thread. MusicEngine and ScreenEngine are structurally
unchanged; Music, Movie and Gaming still call the shared worker.
Existing reconnect mechanics were retained; no automatic reconnect system was
introduced. If the strip drops its link, press CONNECT to reconnect.

## Files changed
- olive_rgb.py: v1.4.2 version, minimal adapter switching, device selector, settings.
- requirements.txt: explicit bleak>=0.22 dependency (already used by LotusLamp).
- README.md and TESTING.md: this update and test instructions.
- New ledble_driver.py, test_ledble.py, LEDBLE_UPDATE.md, BASELINE_SHA256.json.
The build batch and both specs are unchanged; their normal import analysis
includes the new driver and their existing Bleak collection remains in place.

## Validation and limits
Run `py -B -m unittest discover -s . -p test_ledble.py -v` from this folder.
Six offline tests cover exact RGB bytes, clamping, safe identification,
unconfirmed power builders, mocked discovery/service validation/write behavior,
cleanup, Lotus/strip switching, rate/delta/refresh handling, and waiting for the
shared RGB lock. Mock I/O tests execute coroutines inline without actual Bluetooth.
Source compilation and AST comparisons against the supplied baseline check
preserved worker methods, reactive engines, and thread/event-loop counts.
The original asynchronous unittest runner stalled in the bundled environment;
offline tests avoid that runtime dependency. No live GUI, BLE, audio or EXE build
was tested here. LotusLamp preservation is established by source and mocks,
not by a physical regression test.

At home test LotusLamp first, then strip red/green/blue, then each reactive mode.
Switch back to LotusLamp; test reconnects and repeat with the rebuilt EXE.
Assumption: the strip advertises its supplied exact name and accepts the user's
physically confirmed RGB packet; additional LEDBLE devices require an explicit
target configuration rather than automatically choosing the first family member.
