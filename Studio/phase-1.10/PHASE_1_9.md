# Phase 1.9 — Manual LIVE Corner Lamp + Philips Hue

Complete source in a separate copy of the working Phase 1.8 release. The original Phase 1.8 folder/archive and original Tkinter application remain available. **No physical Bluetooth test was performed during this work.** The user has confirmed Phase 1.8 works; Hue integration still needs the physical checklist below.

## Start on Windows

1. Extract this release into its own folder. Close other applications controlling either lamp.
2. Run `Setup Qt Preview.bat` if this copy does not have a Qt environment.
3. Run `Setup Live Corner Preview.bat`. Its historical filename is retained; in this release it installs the optional requirements for **both** Corner and Hue into this copy's `.venv-studio-qt`.
4. Run `Launch Qt Preview.bat`. DEMO is still selected by default.
5. Explicitly choose LIVE. Connect Corner Lamp and/or Connect Hue independently. Opening LIVE does not connect, scan, pair, or create Bluetooth workers.

Dependency versions match the inspected working Python 3.14.8 environment: lotus-lamp 1.1.0, Bleak 3.0.2, HueBLE 2.2.3 and bleak-retry-connector 4.7.1. Qt remains PySide6 6.12.0. The only new optional LIVE dependencies relative to Phase 1.8 are HueBLE and its retry connector pin. No global package, driver, pairing or production build changes were made.

The download is a source ZIP: inherited `build/`, `dist/` and virtual environments are omitted. They remain preserved in the local development copy and original Phase 1.8 folder. Any inherited `dist/Olive RGB.exe` is the previous application, not a newly built Qt Phase 1.9 executable; launch this release with `Launch Qt Preview.bat`.

## Controls and feedback

The approved dashboard, icons, device alignment and workspace presets remain intact. LIVE gains one Hue connection/status row and a small capability/readback note in the existing inspector.

- Hue native power, brightness and RGB controls enable only after the unchanged Hue backend confirms their capability through the connected device. Unsupported controls are disabled with capability explanations.
- Hue connection/error indicators are real adapter state, never simulated success. Connecting alone sends no lighting state or default color.
- The backend reads power and brightness on connection. Those readings initialize the corresponding controls and are identified as **read on connect**. The RGB wheel/HEX/RGB values are requested colors, not fabricated XY-to-RGB readback.
- After editing, controls represent requested local settings. The inspector's connection-time readings are not advertised as continuous current-state telemetry. Changes made by another controller are not synchronized continuously.
- Corner controls retain the exact Phase 1.8 implementation, including RGB-black software power. Hue uses the existing driver's native power operation.
- Hue Follow Master defaults OFF. Local settings survive Master changes. When ON, local brightness is multiplied by Master brightness and local power is gated by Master power. Turning Follow Master off restores the local calculation.
- Hue RGB stays unscaled for the existing RGB-to-XY conversion. RGB value/intensity is applied once to brightness, alongside the local and optional Master multiplier. Black/zero intensity produces native OFF. Before the user has selected an RGB color, no placeholder RGB intensity is applied to the observed brightness.
- The small Master output-color button remains the existing **Corner color editor**, as its tooltip states. It is not a new global color control. Master power and brightness can operate with either or both devices connected.

Hue white-temperature support is still detected by the existing backend, but no temperature control was added to the frozen UI. Music, Screen and scene playback stay disabled in LIVE. DEMO retains all existing mock behavior. Workspace presets change layout only.

## Identity and pairing audit

`hue_driver.py`, `hue_controls.py` and the existing Hue tests were inspected. HueDriver already owns fresh Windows scanning, identity selection, capability probes, RGB conversion, HueBLE commands and constrained connection behavior. It is reused **without edits**.

On the first explicit Hue Connect, the Hue thread reads only the Hue identity from `%APPDATA%\OliveRGB\settings.json` (the same location the original application uses). It never writes this file or imports production lighting settings. Missing identity uses the original `Tv lamp` default. Malformed saved identity/settings produce an error rather than silently dropping a saved identity restriction.

The unchanged driver scans for the saved advertised name, uses its address hint when available, passes the fresh BLEDevice to HueBLE and verifies the saved stable Zigbee ID when one exists. Ambiguous name matches fail. Learned identity is retained for reconnects in this session; it is not persisted by Studio. No new discovery UI or pairing procedure was introduced. Existing Windows pairing must already be suitable; authentication failures are reported. Nothing resets or unpairs the bulb.

## Thread and lifecycle ownership

The production HueService is an actor supplied with an external asyncio loop. It performs bounded automatic retries and writes desired state immediately after connecting. Reusing its run loop directly would conflict with this milestone's explicit manual connection and no initial writes, so the new `HueSession` reuses **HueDriver** and the service's conservative serialized/latest-state approach, not its automatic-retry policy.

```text
Qt widgets → StudioController → DualLightingAdapter
  ├─ unchanged CornerLampAdapter / CornerSession
  │    → unchanged BluetoothWorker's persistent loop → LotusLamp
  └─ HueSession latest-state mailbox
       → one dedicated Hue asyncio thread/loop → unchanged HueDriver → HueBLE

Both devices → generation-tagged events → queued Qt signals → Qt widgets
```

Hue owns no Corner client and does not start a Corner worker. Its dedicated loop is necessary to allow Hue-only use and independent lifecycle cleanup while leaving Phase 1.8's loop ownership untouched. Each client has one owner loop; no client is shared between loops. There is no second worker or loop for the Corner Lamp. Hue starts at most one thread per LIVE instance and reuses it across explicit reconnects.

Writes are awaited serially per device. Hue retains at most one latest value for each of power/brightness/color, prioritizes OFF, rotates brightness/color to avoid starvation, and waits at least 0.25 seconds after each completed write before the next. Corner's original 0.25-second limiter, small-change suppression and session are byte-for-byte unchanged.

Disconnect/reconnect/close invalidate generations, cancel and drain in-flight operations, discard pending state and ignore stale notifications. No new state is accepted after close. Already transmitted physical commands cannot be undone. No Hue automatic retry/reconnect loop or DEMO fallback exists. Connect uses a 40-second bound; writes and disconnect use six-second outer bounds around the existing driver. A disconnect failure becomes a terminal Hue error to avoid opening a second client over an uncertain connection; Corner remains usable.

Qt stays alive while both cleanup paths finish. No GUI callback waits for Bluetooth or joins a thread. Async cancellation assumes the driver cooperates; a noncooperative driver can delay cleanup, but Qt callbacks remain unblocked.

## Validation results

| Suite, run separately | Result |
|---|---:|
| New dual-device and identity tests | 27 passed |
| Existing Phase 1.8 live Corner tests | 28 passed |
| Existing Qt / adapter / workspace tests | 43 passed |
| Existing Tkinter / Hue / LEDBLE / coordination regressions | 44 passed |
| Total distinct tests | **142 passed** |

New tests cover Hue-only, Corner-only, both connected, independent colors, Follow Master and brightness calculations, reconnect, failures/loss on either side, unsupported capabilities, rapid coalesced writes, stale events, disconnect during writes, terminal cleanup failure, close during operations, no startup hardware, no initial writes, DEMO separation, Qt responsiveness, all four target sizes and read-only saved identity handling. Existing tests were not modified or weakened. The existing real HueBLE API test still runs with mocked Bluetooth I/O.

**Timing qualification:** two combined live-suite runs failed the existing Corner write-timestamp spacing assertion. The same unchanged test passed in isolation, and both the untouched Phase 1.8 suite and Phase 1.9 Corner suite passed separately. This timing sensitivity remains documented; the Corner worker/session and test thresholds were deliberately not changed. It is not evidence of physical device validation. The final table records the separate suite runs.

Tests were run on Windows with the existing Python/BLE packages and isolated Qt packages. No fake transport constructed a real BLE client. Run the suites separately in the applicable dependency environments:

```powershell
.\.venv-studio-qt\Scripts\python.exe -X utf8 -B -m unittest test_dual_live -q
.\.venv-studio-qt\Scripts\python.exe -X utf8 -B -m unittest test_corner_live -q
.\.venv-studio-qt\Scripts\python.exe -X utf8 -B -m unittest test_studio_qt test_studio_adapter test_workspace -q
# Original application environment:
python -X utf8 -B -m unittest test_studio_preview test_hue_api test_hue_integration test_ledble_retry test_ledble test_music_coordination -q
```

Screenshots and geometry checks cover 1440×900, 1280×800, 1080×760 and 800×600. They use clearly labeled fake transports. At smaller sizes, the unchanged scroll areas provide access to lower controls. No horizontal overlap was found. Native Windows mixed-DPI behavior remains a manual validation item. Open `PHASE19_GALLERY.html` for screenshots.

## Files and baseline protection

Added: `studio_qt/hue_session.py`, `hue_identity.py`, `dual_adapter.py`, `dual_window.py`, `test_dual_live.py`, `capture_dual_validation.py`, this report, Phase 1.9 checklist, baseline/validation manifests, gallery and screenshots.

Changed existing files:

- `studio_qt/app.py`: select the dual-device LIVE window only after explicit LIVE startup choice.
- `studio_qt/live_window.py`: optional injected adapter and startup wording for both devices; old Corner-only class remains usable by its unchanged tests.
- `studio_qt/widgets/inspector.py`: query per-device LIVE status.
- `requirements-studio-live.txt`: add pinned existing Hue dependencies.
- `WINDOWS_HARDWARE_CHECKLIST.md`: point to the Phase 1.9 checklist; Phase 1.8 copy is preserved in its original release.

`PHASE19_VALIDATION.json` records hashes against the supplied Phase 1.8 files captured before editing. All 53 protected source/configuration files are unchanged against that baseline. The supplied `Olive RGB.spec` already differed from its older historical Qt manifest; its supplied version is preserved, not reverted. The Phase 1.8 Corner worker snapshot, CornerSession, CornerLampAdapter, mock adapter, UI state, theme/icons, device layout, workspace module, existing tests and existing Windows launchers are unchanged. The original Tkinter application and drivers remain independently launchable. Production lighting settings are read only for Hue identity and are never written. Only the existing separate workspace preferences may be saved by the preview.

## Remaining limitations

Physical Hue RGB, brightness, pairing/authentication and concurrent Windows radio reliability require the user's checklist. No continuous device-state reconciliation or RGB readback is implemented. Hue temperature controls, lighting-state persistence, live music, screen synchronization and scene playback remain out of scope. The pre-existing Corner timing-test sensitivity described above remains. No new executable or installer was built; use the source launcher in a separate folder. Do not run multiple controlling applications against the same device simultaneously.

**Stopped after Phase 1.9. No music integration or real hardware tests were performed.**
