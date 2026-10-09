# Phase 1.10 — LIVE Music integration

This is a separate, recoverable copy of Phase 1.9. Its source hashes matched the Phase 1.9 validation manifest before implementation. `PHASE110_BASELINE_SHA256.json` records that checkpoint. Phase 1.9 and earlier releases remain untouched.

**Hardware evidence:** the user confirmed Phase 1.8 Corner control works on Windows. This chat contains no physical confirmation of Phase 1.9 Hue or Phase 1.10 music behavior. All tests/screenshots for this phase use fake audio/device I/O. No real audio capture or Bluetooth connection was performed during implementation.

## Run

Extract the source ZIP into a separate folder. Run `Setup Qt Preview.bat` if needed, then rerun `Setup Live Corner Preview.bat` in this copy. Its historical filename remains, but it now installs both device dependencies and the existing production audio dependencies into this copy's Qt environment. Run `Launch Qt Preview.bat`.

DEMO remains the default. LIVE never starts audio or connects lights automatically. Explicitly select LIVE, connect either/both lights, open the **Music** navigation page, select the production profile/palette, choose participants, and press **Start Music**. Start/Stop remain visible on every page. **Stop Music**, **Esc**, or selecting **Manual** releases music control. Workspace preset selection still changes layout only.

The backend captures the **Windows default playback output via loopback**. It has no arbitrary input-selector API; change the default output in Windows. Its existing output-change detection follows a changed default device. This phase does not add microphone selection or audio recording to disk.

The source ZIP excludes virtual environments and inherited build/executable artifacts. Use the Qt launcher; no Phase 1.10 executable was built. The original Tkinter app remains independently launchable, but do not run competing controllers/capture sessions while validating this release.

## Reused production implementation

- `MusicEngine` was audited in `olive_rgb.py`: one SoundCard loopback recorder, stereo 48 kHz / 4096-frame blocks, production FFT band analysis, adaptive baselines, RMS, profiles, smoothing, beat detection and palette behavior.
- Its immutable `MusicFrame` carries primary RGB, normalized relative bass/mid/treble proportions, RMS energy, beat flag and monotonic timestamp. Raw waveform samples and individual FFT bins are not exposed.
- `MusicLightingRouter` and `AccentGenerator` in `music_coordination.py` are imported unchanged. Same Color and Coordinated Colors reuse their existing output rules. No new harmony/DSP algorithm was written.
- `studio_qt/music_engine.py` is a verbatim isolated snapshot of the production MusicEngine class, required constants and helpers. Importing the complete Tkinter module would load unrelated capture/Hue/UI dependencies. AST equality tests enforce class/helper parity. The original source is untouched; future engine changes must resynchronize this snapshot.
- Corner worker/session/adapter, Hue driver/session and device packet formats remain unchanged.

Profiles Smooth, Reactive, Hyperpop and MGK expose the existing production response. The Music page exposes sensitivity/smoothing multipliers and the existing default/artist palettes. Profile-driven brightness response and reactive intensity remain the production behavior; local/Master brightness provides output scaling. Controls that reset analysis are configured before Start and disabled while capture runs. There is no new song recognition or per-song choreography. Color separation retains the router's existing default of 0.25.

## Ownership and routing

Each device has an independent **participates in Music** checkbox. Both initially checked means eligibility, not a connection or an automatic write.

| Device condition | Color owner | Manual behavior |
|---|---|---|
| Music stopped | Manual | Existing Phase 1.9 controls |
| Music running, connected, participant | Music | Manual color controls disabled; local power/brightness still work |
| Music running, not participating | Manual | Full supported manual controls remain available |
| Disconnected | None | No music writes; other devices/audio continue |

Follow Master is separate from participation: ON additionally applies Master power and brightness; OFF leaves local power/brightness in charge even while music owns color. This precedence is explained in the Music panel. A device can therefore react independently to music without following Master.

The production router generates unscaled primary/accent RGB through transport bridge objects. Per-device local brightness and optional Master brightness are applied once at the final transport boundary. Corner receives scaled RGB through its unchanged mailbox/worker. Hue receives unscaled chromaticity RGB plus one intensity/local/Master brightness calculation and its native power state. A white-only Hue skips RGB and can still react through verified power/brightness capabilities.

Music never overwrites the stored manual RGB in the UI state. Stop or opting out restores the device's **requested manual settings** after music has routed a frame. These are not a physical pre-music color snapshot: neither backend reads original RGB back into Studio. As in Phase 1.9, unedited initial color values are UI defaults, not device readback. Connecting or stopping before any frame arrives does not push router placeholder colors.

Scenes and Screen synchronization remain disabled. The Master color swatch retains its existing role as the Corner manual-color editor; the persistent audio status shows the actual primary reactive color.

## Threads, buffering and Stop

```text
Explicit Start on Qt thread
  → one lifecycle helper initializes/configures the production MusicEngine
  → MusicEngine's single capture thread owns its recorder context
  → one latest MusicFrame + bounded status/error fields under a lock
  → Qt-owned 33 ms poll consumes the latest frame
  → unchanged MusicLightingRouter through per-device ownership bridges
  → existing Corner/Hue latest-state mailboxes and existing async BLE owners
```

No capture, dependency import or thread join runs in Qt callbacks. There is one active engine, not one per light. A new start is prevented until the previous capture thread exits. The helper joins the engine off the GUI thread; Qt widgets are only updated by Qt. Audio analysis never waits for Bluetooth.

Intermediate frames coalesce into a single slot instead of accumulating signals. Each transport retains its existing bounded latest state and serialization. Corner's 0.25-second limiter and small-change suppression are unchanged. Hue's existing 0.25-second per-operation cadence is unchanged. Actual radio completion times need not coincide.

Stop immediately gates future frame routing, drops the capture mailbox, stops accepting music color ownership and replaces participating devices' pending music state with requested manual state. A Bluetooth operation already in flight cannot be undone. The original engine releases its recorder context when its current read returns. Closing waits asynchronously for capture and both device cleanup paths, without blocking Qt.

Audio errors restore manual ownership and remain visible; no silent switch to DEMO occurs. Default-output changes use existing engine behavior. A missing/removed device produces an error through the existing exception path. If no fresh frame arrives for over a second, the display says it is waiting and clears stale meters. A driver that hangs inside a blocking read can delay resource release and final window closure; Stop still gates lighting immediately. No replacement engine or uncontrolled retry loop is started.

## Visualization

DEMO retains the existing synthetic spectrum/waveform and accesses no real audio or hardware.

LIVE uses the same reactor area to show **three measured/computed band proportions, raw RMS and beat activity**. The proportions are normalized relative-band strengths from the existing engine, not absolute band energy or 72 measured FFT bins. The status row shows primary RGB. LIVE does not invent a waveform or populate fake frequency bins. There is no synthetic animation in LIVE. Direct meter updates add no decorative animation; Reduced Motion adds no interpolation. Polling stops once audio is idle and cleanup is complete.

## Dependencies

LIVE adds NumPy 2.5.3 and SoundCard 0.4.6 to its isolated setup requirements, matching the inspected existing Python 3.14.8 environment. Both are already production dependencies; no new audio library was introduced. Existing PySide6 6.12.0, LotusLamp, Bleak and Hue pins are retained. No global environment, drivers or production settings were modified.

## Validation

| Suite | Passed |
|---|---:|
| New music integration and mocked production capture | 20 |
| Existing dual-device/identity | 27 |
| Existing Corner LIVE | 28 |
| Existing Qt / adapter / workspace | 43 |
| Existing Tkinter / Hue / LEDBLE / coordination | 44 |
| Total distinct tests | **162** |

Additionally, all **24 existing manual dual-device tests** passed when rerun against MusicLightingAdapter/MusicLiveWindow. No old tests or thresholds were weakened. The Corner suite ran separately because Phase 1.9 documented combined-run timestamp sensitivity; it passed in this phase.

Tests cover start/stop, initialization failure, missing/default device loss, actual unchanged DSP with a fake recorder and context cleanup, participation, Corner-only/Hue-only/both routing, white-only Hue, manual ownership, Follow Master scaling, coalescing, device loss, Qt thread ownership, startup/shutdown, DEMO isolation and four target sizes. Syntax and protected-file hashes are recorded in `PHASE110_VALIDATION.json`.

Run tests in the appropriate installed dependency environments:

```powershell
.\.venv-studio-qt\Scripts\python.exe -X utf8 -B -m unittest test_music_live test_dual_live -q
.\.venv-studio-qt\Scripts\python.exe -X utf8 -B -m unittest test_corner_live -q
.\.venv-studio-qt\Scripts\python.exe -X utf8 -B -m unittest test_studio_qt test_studio_adapter test_workspace -q
# Original production environment:
python -X utf8 -B -m unittest test_studio_preview test_hue_api test_hue_integration test_ledble_retry test_ledble test_music_coordination -q
```

Screenshots in `phase110-screenshots/` show Studio and Music pages at 1440×900, 1280×800, 1080×760 and 800×600, all labeled TEST AUDIO/TRANSPORT. Qt layout settling and narrow meter labels were checked. Smaller windows scroll to lower settings/participation controls; Stop remains outside scrolling. Native mixed-DPI behavior and physical response still require the checklist.

## Files changed and protection

Added: `studio_qt/music_engine.py`, `music_runtime.py`, `music_adapter.py`, `music_window.py`, `test_music_live.py`, `capture_music_validation.py`, this report, physical checklist, checkpoint/validation manifests, gallery and screenshots.

Modified existing files:

- `studio_qt/app.py`: select MusicLiveWindow only after explicit LIVE selection.
- `studio_qt/live_window.py`: clarify optional audio capture in the startup choice.
- `studio_qt/dual_window.py`: optional adapter injection; existing two-device behavior unchanged.
- `studio_qt/widgets/audio_reactor.py`: real three-band rendering branch, leaving DEMO rendering intact.
- `requirements-studio-live.txt`: existing production audio dependencies.
- `WINDOWS_HARDWARE_CHECKLIST.md`: link to this phase's checklist.

All 53 protected original application/configuration files match the supplied baseline. `olive_rgb.py`, MusicLightingRouter, BluetoothWorker, HueService/driver, Corner/Hue session implementations, Tkinter preview, device packets, rate limits, workspace state, icons, device row layout and existing launch/build scripts remain unchanged. Audio configuration and participation are in memory only; production settings are not written. The existing read-only Hue identity import and separate UI workspace persistence are retained.

## Limitations and recommended next phase

Physical audio, Hue color/brightness and simultaneous radio behavior are unverified here. The original profile minimum brightness can keep lights dimly lit during silence; this is preserved production behavior. The backend follows only the default Windows output. No raw waveform/FFT-bin export, continuous device readback, audio-setting persistence or arbitrary source selection was added. Slow/hung audio-driver reads can delay cleanup. Manual restoration uses requested UI state, not unknown physical RGB. Existing Corner combined-run timing-test sensitivity remains documented in Phase 1.9.

The recommended next step is **user hardware validation and a focused reliability review of its results**, including Stop, independent ownership and audio-output changes. Do not expand into screen, choreography or timeline work until that evidence is available. No Phase 1.11 work has begun.
