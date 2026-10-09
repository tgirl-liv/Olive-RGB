# Phase 1.8 — Manual LIVE Corner Lamp

This separate copy adds optional LotusLamp control to the approved Phase 1.7 Qt interface. DEMO remains the default startup choice. Opening LIVE does not create a Bluetooth worker, scan, connect, or write. Press **Connect Corner Lamp** explicitly.

**Physical validation is pending.** Automated tests replace the lamp transport with a fake. Screenshots of connected states are labeled TEST TRANSPORT and are not evidence of a physical connection.

## Run on Windows

1. Extract the complete project to a new folder. Keep the existing working application.
2. Run the unchanged `Setup Qt Preview.bat` if this copy has no working Qt environment.
3. For LIVE, run the new `Setup Live Corner Preview.bat`. This installs optional dependencies only into this copy's `.venv-studio-qt`.
4. Run the unchanged `Launch Qt Preview.bat`. Choose DEMO or explicitly choose LIVE.
5. In LIVE, press Connect Corner Lamp. Follow `WINDOWS_HARDWARE_CHECKLIST.md` before reporting success.

Optional LIVE requirements pin the inspected working environment's **lotus-lamp 1.1.0** and **bleak 3.0.2**, plus the existing Qt requirements. Validation used Windows, Python 3.14.8 and PySide6 6.12.0. No global packages or drivers were changed. Missing LIVE dependencies produce a LIVE error, never a silent DEMO fallback.

## Supported controls

- The configured Corner Lamp only: `MELK-OA10   7F`, `BE:28:87:00:08:7F`.
- Explicit connect/disconnect, manual wheel, HSV/HEX/RGB editing, local brightness and Follow Master.
- Master brightness multiplies local brightness when Follow Master is enabled. RGB channels are scaled and rounded using the existing application's behavior.
- Power is **software power**: OFF sends RGB black; ON restores the selected/last nonzero color. This is not a verified dedicated hardware power command or a mains-power switch.
- Controls display requested values, not lamp readback. Connecting alone does not push the initial UI color or brightness.

Hue hardware controls, Music/Screen lighting modes and scene application are disabled in LIVE. Audio Reactor is a static DEMO display. Workspace presets still change layout only. Use DEMO for the complete simulated preview. Production settings are untouched; only the existing UI workspace preference file may be saved on normal close/reset.

## Backend audit and integration boundary

The original `olive_rgb.py` does not create Tk until its main guard, but imports Tk, soundcard, capture, audio and Hue dependencies at module import. To avoid loading these unrelated backends, `studio_qt/corner_worker.py` contains a **verbatim BluetoothWorker class snapshot** with minimal imports. The original class and file remain unchanged. An AST equality regression test enforces class parity. This intentionally duplicates the class: a future production worker update must resynchronize the snapshot and pass that test.

The audited worker owns a persistent asyncio loop in one thread, configures the same LotusLamp, and sends colors through `set_rgb()` and its existing async RGB lock. Its public submission path can wait five seconds for readiness, so no Qt callback invokes that startup wait. The existing 0.25-second limiter and small-change suppression remain intact; the adapter never uses `force=True`. Small changes can take up to the existing 1.5-second threshold to settle.

The worker catches/logs connection and write exceptions. Its connect path may mark itself connected even when the underlying library returned without establishing a client. The adapter therefore checks the real client's `is_connected` and exact address before emitting connected. LotusLamp's existing single-connect implementation can fall back to its own name scan; no additional reconnection loop was added.

```text
Qt main thread: widgets → StudioController → CornerLampAdapter
    ↓ locked latest-color mailbox / explicit connection intent
CornerSession actor on the existing BluetoothWorker asyncio loop
    → unchanged worker connect / set_rgb / disconnect → LotusLamp
    ↑ immutable generation-tagged events → queued Qt signals → widgets
```

A lifecycle helper thread starts the worker, waits for readiness and joins it during shutdown. It performs no BLE operations and creates no asyncio loop. There is one worker per LIVE window, started on the first Connect and reused for subsequent explicit connections.

Only one RGB operation is in flight and one latest pending color is retained. Disconnect, reconnect and close invalidate older generations. Stale status events are discarded on the Qt thread. Cancellation drains the actual async write task before disconnect. A partially connected client is also disconnected if the worker's connected flag was never set. No queued color is replayed automatically on reconnection.

Closing stops accepting commands and keeps Qt responsive while cleanup finishes; the worker loop is then stopped and joined off the GUI thread. A command already transmitted before cancellation cannot be undone. Cancellation assumes the installed driver cooperates with asyncio cancellation; a noncooperative driver could delay final cleanup without blocking Qt callbacks. There is no automatic retry after connection or write failure.

`CornerLampAdapter` retains the existing LightingAdapter-facing methods. It uses MockLightingAdapter internally only for in-memory validation/state mutations; all physical commands go exclusively through CornerSession. This helper is never a fallback transport. LIVE rejects unsupported mode/scene commands and reports genuine errors.

## Validation

| Suite | Result |
|---|---:|
| New live adapter/actual worker with fake lamp | 28 passed |
| Existing Qt, adapter and workspace | 43 passed |
| Existing Tkinter preview and backend regressions | 44 passed |
| Total | **115 passed** |

Tests cover no automatic connection/write, connection identity, false success protection, failure without retry, disconnect and immediate reconnect, one worker, 4 Hz limiting, latest-color coalescing, brightness, Follow Master, software power and unsupported power, connection loss, stale notifications, close during connect/write, DEMO/LIVE isolation, missing dependencies, GUI responsiveness and all four target window sizes. No existing tests were weakened.

Run suites separately so LIVE's intentional worker imports do not contaminate DEMO import-isolation tests:

```powershell
.\.venv-studio-qt\Scripts\python.exe -X utf8 -B -m unittest test_corner_live -q
.\.venv-studio-qt\Scripts\python.exe -X utf8 -B -m unittest test_studio_qt test_studio_adapter test_workspace -q
# In the original application's dependency environment:
python -X utf8 -B -m unittest test_studio_preview test_hue_api test_hue_integration test_ledble_retry test_ledble test_music_coordination -q
```

The live suite uses the actual isolated worker with only the lamp transport replaced; no real BLE client is constructed. Existing backend diagnostic output is also from mocks. This run used the installed production BLE environment plus the isolated Qt site-packages for live tests; the optional setup batch has not been exercised against hardware.

`live-validation-screenshots/` contains disconnected, mocked-error and mocked-connected views at 1440×900, 1280×800, 1080×760 and 800×600. `qt-screenshots/` includes refreshed scale-1 DEMO captures. All four requested sizes were achieved, with bounds checks on essential controls. Smaller windows retain vertical scrolling. Native mixed-DPI Windows behavior remains a manual check; no OS display settings were changed.

## Changed files

Existing files changed only for integration hooks:

- `studio_qt/app.py`: adapter injection and explicit startup selection.
- `studio_qt/controller.py`: reject unsupported LIVE mode/scene application.
- `studio_qt/widgets/inspector.py`: distinguish actual and simulated status.

Added:

- `studio_qt/corner_worker.py`, `corner_session.py`, `corner_adapter.py`, `live_window.py`.
- `test_corner_live.py`, `capture_live_validation.py`.
- `requirements-studio-live.txt`, `Setup Live Corner Preview.bat`.
- This report, hardware checklist, baseline/validation manifests, gallery and live screenshots.

The validation manifest records SHA-256 comparisons. All 53 original production/Tkinter/configuration files are unchanged, including the working application, drivers, worker source, MusicEngine, ScreenEngine and coordination. The Phase 1.7 icons, theme, device layout, workspace implementation, artwork, state model, mock adapter, existing tests and existing launchers remain unchanged. Original Phase 1.7 stays in its own folder. Refreshed DEMO screenshots are the only other changed existing artifacts.

## Remaining limitations

Hardware success, radio reliability and software power restoration need the user's physical confirmation. This phase targets the existing configured address; there is no new device picker or address editor. LIVE does not synchronize color state back from hardware or persist lighting settings. Hue, live audio, capture and production scene transitions are deliberately not integrated. No new executable/installer was built. The original Tkinter application can still be launched independently, but close other lamp controllers before testing LIVE.

**Stopped at Phase 1.8. No hardware was contacted during implementation or validation.**
