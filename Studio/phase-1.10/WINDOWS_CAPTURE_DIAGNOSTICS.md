# Windows Music / Screen failure audit

## MASTER BUS button verification

The actual side-by-side controls are `MasterBus.modes['Music']` and
`MasterBus.modes['Screen']` in `studio_qt/widgets/controls.py`, created by
`StudioWindow` in `studio_qt/app.py`. `Launch Qt Preview.bat` launches
`studio_qt_preview.py`; choosing LIVE constructs `ScreenLiveWindow`.
Each `clicked(bool)` connection captures its own mode name and calls
`StudioController.request_mode()`. That resolves the current LIVE handler at click
time: `ScreenLiveWindow.request_mode()`, replacing the music-only handler installed
by its superclass. The same dispatcher handles `controller.set('mode', ...)`.
There is no disconnect/reconnect of button signals, no captured DEMO handler, and
no extra audio or screen worker. The sidebar remains navigation only.

The existing MASTER BUS route already activated capture in automated reproduction;
no broken or overwritten connection was established. The selector now explicitly
shows Starting until the first measured frame, then Active. A failure restores
Manual and shows Error in the header; its tooltip contains the actual error.
This is button wiring/feedback verification, not proof of Windows native capture.

`test_launched_master_buttons_start_production_capture_and_previews` drives the
real launcher and uses mouse clicks on its actual MASTER BUS controls. It runs the
production runtime and processing paths with synthetic audio and MSS pixels,
checks one capture stream, FFT delivery and calculated previews, and switches
to Screen and Manual without connecting lights. Production input-boundary tests
also exercise Starting, changing pixels, silence, and startup failures.

Windows acceptance: from the repository root run
`Set-Location .\Studio\phase-1.10`, then
`$env:OLIVE_STUDIO_DIAGNOSTICS='1'` and `& '.\Launch Qt Preview.bat'`.
Choose LIVE, leave lights disconnected, and click **MASTER BUS → Music** on
the Studio dashboard without visiting the Music page. Play audio on the default
Windows playback device. Expect Starting, then Active, responsive FFT bars and
calculated RGB. Silence should report running silence rather than a startup error.
Return to Studio and click **MASTER BUS → Screen**: expect Starting, then Active
with the saved monitor/Movie/Gaming settings and a preview that changes with
screen content. Screen currently opens its page automatically; return to Studio
to access the MASTER BUS again. Click Manual and check both captures stop.
Repeat selection and Music/Screen/Manual switching; no lights should connect.
If Error appears, record its tooltip and collect the diagnostic log using the
procedure below. Windows audio/screen capture and physical lights remain pending.

Follow-up validation: 387 unique automated tests passed across the full test
groups, plus the actual launcher DEMO smoke test and dependency compatibility
check. The initial full run failed the existing
`test_rapid_colors_coalesce_latest_and_limit_rate` 245 ms fake-write spacing
assertion; the unchanged 28-test Corner group passed on rerun. Both logs are
retained outside Git in `/workspace/olive-rgb-master-mode-validation`. No BLE
timing, test thresholds, capture algorithms, or COM initialization were changed.
This follow-up remains uncommitted for review.

## Evidence and limits

The audited local working tree initially had no uncommitted changes, on
`development/qt-studio` at `7cfdea67492944b27aeec1222588ab043242b115`.
This audit's changes are uncommitted. No Windows execution or physical lights are
available in the cloud. Linux or mocked results do not establish Windows functionality.

Confirmed code defect: SoundCard 0.4.6 `mediafoundation._COMLibrary` calls
`CoInitializeEx` when the module is imported, only on the importing thread.
`_DeviceEnumerator` subsequently calls `CoCreateInstance` without initializing its
calling thread. Studio presets can import SoundCard on the GUI thread, while
`MusicRuntime._run` and the engine's capture `_run` are different threads.
The capture thread previously had no COM initialization. Windows COM requires it
per thread. The observer now initializes MTA COM around the unchanged engine loop
and releases only its own successful initialization, on that same thread.
`RPC_E_CHANGED_MODE` leaves an existing apartment owned by its original initializer.
If the GUI already has an STA apartment, SoundCard ignores `RPC_E_CHANGED_MODE`
and its import creates no MTA. That is a plausible difference from Tkinter startup,
not a measured Windows result. `music.backend.import` logs COM ownership at import
and its thread; `music.com.ready` logs the capture-thread initialization.
This fixes a concrete lifecycle omission; it does not prove that it caused every
reported Windows failure. Windows logs are still needed.

Exact ID matching is valid for this SoundCard WASAPI version: `all_microphones(True)`
constructs loopbacks from playback endpoints, and `_Device.id` retains that endpoint
ID. The original Tkinter engine uses name/fuzzy matching instead. No arbitrary device
fallback was added. Playback endpoint identity never appears in the diagnostic log.

The installed WASAPI implementation synthesizes zero frames after an idle interval
and also handles `AUDCLNT_BUFFERFLAGS_SILENT`. Measured silence is therefore distinct
from no returned frames, a blocked recorder, or an exception. No new silence or FFT
algorithm is introduced. Windows recorder behavior remains unverified here.

No Windows Screen root cause is established. MSS discovery, context construction,
context entry, first grab, RGB calculation, mailbox, Qt delivery and preview are now
observable. Monitor indices remain MSS's 1-based indices (0 is the combined desktop).
Monitor/intensity/saturation and Movie/Gaming settings retain existing semantics.

`Setup Qt Preview.bat` installs Qt only. LIVE additionally requires
`requirements-studio-live.txt` in the **same** `.venv-studio-qt` used by the launcher.
Missing packages are an environment hypothesis until the Windows dependency check
confirms them. The existing `Setup Live Corner Preview.bat` installs this file.

## Run through the actual Windows launcher

Apply this uncommitted patch to your Windows source before collecting logs. From the
repository root in PowerShell:

```powershell
Set-Location .\Studio\phase-1.10
& '.\.venv-studio-qt\Scripts\python.exe' -m pip check
& '.\.venv-studio-qt\Scripts\python.exe' -m pip show PySide6 SoundCard numpy mss
# Only if LIVE dependencies are missing:
# & '.\.venv-studio-qt\Scripts\python.exe' -m pip install -r .\requirements-studio-live.txt
$env:OLIVE_STUDIO_DIAGNOSTICS = '1'
& '.\Launch Qt Preview.bat'
```

Choose LIVE, leave Hue/Bluetooth disconnected, and play audio through the Windows
**default playback output**. Select Music on the Master bus. Record the visible
startup/error status, whether LEVEL rises, whether FFT bars move and whether the Album
section's read-only RGB preview changes. Pause and resume playback to check measured
silence without restarting capture. Select Screen; show changing red/green/blue content
on the saved monitor and check the read-only Screen preview. Test both Movie and Gaming,
Manual stop, repeated selection, rapid Music/Screen switching and closing during startup.
Do not infer success from highlighting alone.

Close Studio, then collect the metadata log (copy it before another diagnostic launch):

```powershell
$log = Join-Path $env:LOCALAPPDATA 'OliveRGBStudio\diagnostics\capture-latest.jsonl'
Get-Content $log
Copy-Item $log (Join-Path $env:TEMP 'olive-studio-windows-capture.jsonl')
Remove-Item Env:\OLIVE_STUDIO_DIAGNOSTICS
```

The log stays outside Git. Logging is opt-in, latest-run only, bounded to a 256-record
queue and 10,000 written records, with one-second heartbeat limits. File I/O runs on a
separate diagnostic writer; capture producers never wait for file writes or queue space.
Rows contain UTC/monotonic timestamps, thread name/ID, worker generation, static stages,
counts, booleans and elapsed durations. No audio samples, screen images, endpoint names,
endpoint IDs, credentials or exception text are serialized. Share the log and the GUI
error separately; redact identifying text from the GUI status before sharing.

## Interpret stages

| Last stage / pattern | Meaning and next check |
|---|---|
| No `controller.mode.request` / `mode.request` | Wrong window/launcher, disabled control or click delivery; confirm patched source and LIVE choice. |
| Request without `*.runtime.request` | Previous capture is draining, or request cancelled. Compare stop/finished rows and generation IDs. |
| `music.com.failed` | COM initialization HRESULT; no recorder should start. |
| `music.endpoint.default.begin` without return | Default-output enumeration blocked. |
| `music.endpoints.enumeration.ready`, no exact match | Missing enabled loopback for default playback endpoint; check Windows output and installation. |
| `music.recorder.create.begin` or `enter.begin` without corresponding ready | Recorder initialization/context entry blocked or failed; capture GUI error. |
| `music.record.begin` without return | Native recording blocked; timeout cannot forcibly abort WASAPI. GUI remains responsive and new modes wait for old worker completion. |
| `music.frame.mailbox` with `silence=true` | Measured silence; inspect the playback application's output assignment. |
| Frames but no `music.fft.mailbox` | FFT observer/callback delivery missing. |
| Mailbox rows without `music.qt.first_frame` / `music.qt.poll` delivery | Qt polling or lifecycle generation issue. |
| `music.visualizer.update` with `accepted=false` | Renderer rejected visual frame (for example stale data); compare generation/timestamps. |
| Router rows without `*.preview.update` / available output | GUI preview delivery or ownership problem. |
| `screen.scan.ready` but no capture create/enter/grab | Capture startup/monitor selection blocked or failed. |
| `screen.grab.return` but no `screen.frame.mailbox` | Native grab returned; screen processing failed or generation was cancelled. |
| `screen.qt.first_frame` and preview rows | Measured Screen output delivered; verify changing content visually on Windows. |
| `*.startup.timeout` | Elapsed time without first measured frame; preceding native stage identifies where progress stopped. |

Stop and lifecycle-finished rows show cleanup order. A new runtime must not start while
the previous lifecycle thread remains busy. Native calls cannot safely be force-killed;
a timed-out worker must return before another capture starts.

## Preservation and automated checks

Original Tkinter code, MusicEngine class/helpers, ScreenEngine class, lighting math,
Hue/BLE transports, color conversion and timings are unchanged. The Music observer
now wraps the original capture loop with a COM context; the compatibility test verifies
that delegation, unchanged start/stop, exactly one recorder, identical lighting outputs
and identical FFT work. The existing engine AST-preservation test remains intact.
Screen's dependency binding adds transparent capture observations only. Tests patch
MSS at its native boundary so enumeration and capture use the same controlled backend.
Automated COM tests use a simulated Windows API, not actual WASAPI.

## Change manifest

| File | Functions / changes |
|---|---|
| `studio_qt/capture_diagnostics.py` (new) | `Trace.emit/_write/close`, `enable/bind/emit`: bounded opt-in metadata writer, rate limiting and thread-generation scope. |
| `studio_qt/native_capture.py` (new) | `audio_apartment`: balanced Windows COM; `Loopback.recorder`, `Recorder.__enter__/record/__exit__`, `Capture.monitors/grab`, `MSS`: transparent native-stage observations. |
| `studio_qt/audio_capture.py` | `LoopbackAudio.default_speaker/get_microphone`: enumeration/match observations; observed recorder binding; import-time COM ownership metadata. |
| `studio_qt/spectrum_engine.py` | `SpectrumMusicEngine._run`: COM scope around preserved engine; `publish_spectrum`: mailbox acceptance metadata. |
| `studio_qt/controller.py` | `StudioController.set`: LIVE selector delivery metadata. |
| `studio_qt/music_runtime.py` | `MusicRuntime.start/_run/stop`: lifecycle, generation, error, measured-frame and stop observations. |
| `studio_qt/music_window.py` | `MusicLiveWindow.poll_music/live_controls`: first-frame receipt, timeout reason, FFT renderer acceptance and preview availability. |
| `studio_qt/screen_engine.py` | Import binding only; unchanged ScreenEngine delegates MSS calls through observations. |
| `studio_qt/screen_runtime.py` | `engine_factory` / `CaptureEngine._run`: capture-thread generation scope; `refresh_monitors/start/_run/stop`: discovery, lifecycle, mailbox, error and stop observations. |
| `studio_qt/screen_window.py` | `request_mode/activation_failed/poll_screen/live_controls`: mode entry, failures, first-frame age, timeout, routing and preview observations. |
| `test_capture_diagnostics.py` (new) | COM ownership/thread/error cleanup, transparent observers, privacy, timestamps, rate limiting, full-queue nonblocking behavior and logging I/O failure. |
| `test_screen_live.py` | Native MSS mock boundary adjusted to exercise the wrapper while keeping monitor/capture regression assertions. |
| `test_spectrum.py` | Explicit COM-context delegation assertions added to existing recorder/FFT/lighting equivalence checks; original engine AST-preservation test unchanged. |
| `WINDOWS_CAPTURE_DIAGNOSTICS.md` (new) | Evidence, hypotheses, actual batch launcher, environment checks, metadata collection, stage interpretation and change manifest. |

## Observed diagnostic example (Linux only)

The native cloud probe produced these content-free stages on 2026-10-10 UTC:

```text
13:44:05.190  Thread-2 (_run)  gen=1  music.recorder.enter.ready
13:44:06.495  Thread-2 (_run)  gen=1  music.frame.mailbox silence=false
13:44:06.497  MainThread      gen=1  music.qt.first_frame spectrum=true
13:44:06.499  MainThread      gen=1  music.visualizer.update accepted=true
13:44:06.499  MainThread      gen=1  music.preview.update output_available=true
13:44:07.139  Music lifecycle gen=1  music.lifecycle.finished
13:44:07.337  Thread-3 (_run)  gen=3  screen.grab.return duration_ms=13
13:44:07.358  MainThread      gen=3  screen.qt.first_frame age_ms=21
13:44:07.361  MainThread      gen=3  screen.preview.update output_available=true
13:44:07.616  Screen lifecycle gen=3 screen.lifecycle.finished
```

This confirms that the diagnostic stages span native capture and GUI delivery on the
cloud's virtual PulseAudio/Xvfb environment. It provides no Windows capture result.

## Validation result

386 unique automated tests passed across the complete regression groups, including
9 new diagnostic/COM tests. Final capture recheck: 73 tests passed. DEMO actual-launcher
smoke passed; installed dependency checks passed. One initial run failed the existing
BLE fake-write coalescing test's 245 ms assertion; its unchanged 28-test group passed
on rerun. The initial failure log is retained separately. No BLE timing or test
assertion was changed. These results do not verify Windows or physical lights.
