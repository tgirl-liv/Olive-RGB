# Olive RGB Studio — pre-hardware freeze checklist

Branch: `development/qt-studio`. Reviewed for the final pre-hardware commit.
Studio is feature-frozen pending physical hardware acceptance; resume repairs
only from acceptance findings.

## Evidence and limits

- **Automated:** simulated Hue/audio/BLE boundaries, real Qt controls, identity and
  appearance round trips, capability gates, RGB/white switching, bounded explicit
  retry, Manual/Music/Screen ownership and restoration, shutdown, existing
  regressions and DEMO smoke. See test results below.
- **Windows software:** this sprint has not been tested on Windows. Prior user
  recordings/acceptance findings are not certification of this build. All Windows
  checks below are pending.
- **Physical hardware:** no lamps/bridge are available. Every physical output,
  authentication, reconnect and multi-device check below remains pending.
- Original and Studio Hue use **HueBLE 2.2.3 direct bulb BLE**, not a Hue bridge API.
  Bridge discovery and bridge-button pairing are unsupported by both implementations
  and are not added here. Verify Windows BLE pairing of the intended bulb. Bridge
  functionality cannot be certified or reproduced with the existing transport.
- White-temperature uses the driver's existing `set_colour_temp` and bulb-bound
  clamping. Studio exposes the original 153–500 mired range. Actual range, color
  accuracy and readback require a real bulb. RGB is requested, not observed.
- Reconnect remains user initiated. Each Connect request has a bounded timeout;
  errors stop attempts until explicit retry. Cleanup failure remains terminal until
  Studio is reopened, preventing duplicate/uncertain connections.

## Reviewable changes

**Stage 1 — Hue:** Settings → Philips Hue BLE Target; save bulb name/address hint
without connecting. Detected stable bulb identity, manual RGB/white mode and mired
value persist in separate Qt preferences. Setup inspector links to these controls.
Color/temperature controls require a successful capability probe and manual output
ownership. Music/Screen output uses existing routing; releasing ownership restores
manual RGB/white state. Choosing RGB from the inspector selects color mode. Power
and brightness stay independent of manual white's stored RGB intensity.

**Stage 2 — appearance:** Settings → Appearance/System offers Studio (unchanged
initial appearance) plus exact original Tickets/Sakura/Blackout/Cyberpunk semantic
colors. Appearance changes do not change lighting palettes, artwork, output or
capture. DEMO and LIVE preferences remain separate. Status/error history is
read-only, bounded to 500 lines and session-only, with Copy/Clear. Custom-painted
Audio Reactor, swatches, icons and lighting previews keep their existing styling;
this restores interface theme behavior without redesigning those widgets.

Existing Music brightness/saturation/Reset, static colors, Master/device feedback,
settings and ownership remain covered by regressions. No backend protocol, BLE
cadence, original app, MusicEngine or ScreenEngine changes. The subsequent priority
Hue color correction changes only the shared driver’s `rgb_to_xy()` matrix;
its transport, capability detection, API calls and encoding remain unchanged.
See `HUE_COLOR_ACCURACY.md` for the color pipeline and expected payloads.

## Windows launch

Pull the reviewed sprint into your Windows checkout using fast-forward-only,
preserving local changes. Run from the repository root. Use one Python environment
for install and launch; keep it outside the repository.

```powershell
Set-Location 'C:\path\to\Olive-RGB'
git branch --show-current
git status --short
if ((git branch --show-current) -ne 'development/qt-studio') { throw 'Wrong checkout' }
git pull --ff-only origin development/qt-studio
if ($LASTEXITCODE -ne 0) { throw 'Pull failed; preserve and reconcile local changes' }
$studioEnv = Join-Path $env:LOCALAPPDATA 'OliveRGBStudio\test-venv'
py -3 -m venv $studioEnv
$studioPython = Join-Path $studioEnv 'Scripts\python.exe'
& $studioPython -m pip install -r '.\Studio\phase-1.10\requirements-studio-live.txt'
# Optional Windows album integration only:
& $studioPython -m pip install -r '.\Studio\phase-1.10\requirements-studio-album.txt'
& $studioPython -m pip check
& $studioPython '.\Studio\phase-1.10\studio_qt_preview.py'
```

Qt preferences are `%LOCALAPPDATA%\OliveRGBStudio\preferences-v1.json`; custom Music
library is beside them. Original `%APPDATA%\OliveRGB\settings.json` is not written.
A missing Qt Hue identity can read the original identity on the first explicit
Connect; saving a Qt target overrides it. Restart never connects or starts capture.

## Acceptance record (all pending for this build)

Record Windows/Python versions, commit or patch identity, device model/firmware,
result, error log and date. Use separate software/hardware columns.

| Check | Windows software, no lights | Physical hardware |
|---|---|---|
| Startup/restoration | Choose DEMO/LIVE; neither starts effects or connections. Save each interface theme and restart; mode is Manual, devices idle. | Bulbs remain unchanged on launch. |
| Hue bridge/pairing | Confirm direct BLE integration; bridge discovery/pairing not supported. Verify intended bulb name and Windows Bluetooth pairing prerequisites. | Pair intended BLE-capable Hue bulb in Windows; do not reset/unpair other bulbs. |
| Hue identity | Save name/address; navigate/select devices; verify no auto-connect. Restart retains identity. | Connect explicitly; verify correct stable bulb, reject wrong/ambiguous bulb. |
| Hue RGB/white | Disconnected controls disabled; unsupported mode clearly explained. The sRGB/D65 conversion and eight reference XY payloads are verified with mocked GATT. | Pink `#FF69B4` hardware color accuracy remains pending; see `HUE_COLOR_ACCURACY.md`. Color-capable bulb: RGB → white → identical RGB; warm/cool endpoints, brightness and power. White-only bulb: RGB disabled; white and dimming work. |
| Hue retry/restart | Failure produces readable log; no endless reconnect. | Disconnect/reconnect repeatedly, remove power during write, retry explicitly; no duplicate connections. Restart retains target but stays disconnected. |
| LotusLamp Corner | Family persists; switching family disconnects, clears pending output; explicit Connect required. | Existing manual RGB/power/brightness; Music/Screen updates at preserved transport cadence. |
| LEDBLE Strip | Select LEDBLE; restart retains family; no new connection. | Correct strip chosen; connect/cancel/disconnect/reconnect, RGB and power; no protocol or rate regression. |
| Manual/Music/Screen | Manual → Music → Screen → Manual; correct highlights, idle Screen selection starts nothing. Preview and production controls remain interactive. | Exclusive output ownership; manual RGB/white restored on stop/opt-out; Master/local power/brightness scale correctly. |
| Album/custom themes | With Windows media playback, artwork preview and status; missing artwork/dependencies fall back to selected palette. Custom CRUD and live switch without capture restart. Virtual output works with no connected devices. | Palette/artwork changes affect lights only, not interface theme; participation respected. |
| Movie/Gaming | Select actual monitor, explicitly Start; Movie/Gaming preview, intensity/saturation, monitor switching, capture shutdown, stale/error handling. See `QT_SCREEN_ACCEPTANCE.md`. | Corner/Hue follow intended screen output; independent Hue does not follow; opt-out restores manual state. |
| Device switching | Save Hue target during capture: disconnects Hue, no new connection/effect. Change pages/inspector target without connecting. | Old target receives no queued commands after disconnect; only explicit new connection receives output; other device unaffected. |
| Close/settings/logs | Close while capturing/connecting; restart idle; brightness, saturation, palette, themes, family and monitors persist. Log is readable, Copy/Clear work; no output spam. | No stuck connections or continued writes after close; hardware cleanup errors remain visible. |

Protected video may capture black; HDR/color accuracy and Windows permissions/media
support need acceptance. Simulated tests do not certify hardware protocol support
beyond preserved existing implementations.

## Automated results

- Final full suite after the priority Hue color correction: **362 tests passed**
  (332 existing + 15 new Hue parity + 8 new appearance + 7 new color tests).
  No failures/skips reported. The color tests also passed a focused recheck with
  explicit values below/above the gamma threshold; repeated runs are not counted
  as additional tests.
- Actual-launcher DEMO smoke: passed, including navigation, controls, mock-only
  operation and clean event-loop exit.
- Linux Qt Tickets/Cyberpunk rendering smoke: passed; screenshots inspected for
  readable Settings/inspector controls and log contrast.
- Dependency compatibility (`uv pip check`): passed. No unexpected warnings,
  thread exceptions or deleted-Qt-object tracebacks in final validation logs.
- Automated device/audio tests use simulated I/O. Linux rendering is software
  evidence only. Windows and physical acceptance remain pending.

Final logs and screenshots are outside Git at
`/workspace/olive-rgb-prehardware-validation-final/` (parity) and
`/workspace/olive-rgb-hue-color-validation/` (priority color correction).

## Files for review

- Shared integration/schema: `studio_qt/app.py`, `studio_qt/preferences.py`.
- Hue: `studio_qt/dual_adapter.py`, `studio_qt/dual_window.py`,
  `studio_qt/hue_identity.py`, `studio_qt/hue_session.py`,
  `studio_qt/music_adapter.py`, `studio_qt/screen_adapter.py`,
  `studio_qt/widgets/live_inspector.py`,
  `studio_qt/widgets/hue_preferences.py`, `test_hue_parity.py`.
- Appearance: `studio_qt/appearance.py`,
  `studio_qt/widgets/appearance_settings.py`, `test_appearance_parity.py`.
- Priority color correction: `hue_driver.py` (conversion helper only),
  `test_hue_color.py`, `HUE_COLOR_ACCURACY.md`.
- Freeze/acceptance: this document.

Review baseline before this sprint: `ff55406fcf1884297fa5335e529231cd49d73cb7`.
The reviewed sprint uses commit message
`fix(studio): correct Hue colors and complete parity` on `development/qt-studio`.
No merge, main-checkout change, transport rewrite or automatic hardware/effect
startup is included. Hardware-dependent results remain unverified during the
feature freeze.

Final pre-commit rerun: all 362 tests and DEMO smoke passed; dependency check
passed. Logs are outside Git at
`/workspace/olive-rgb-prehardware-commit-validation/`. Windows and physical
hardware acceptance remain unverified.
