# Movie/Gaming Screen Lighting — audit and Windows acceptance

## Audit and implementation

| Original feature / evidence | Previous Qt behavior | This sprint |
| --- | --- | --- |
| `olive_rgb.py:875` ScreenEngine, MSS context on capture thread | No LIVE capture | Verbatim `studio_qt/screen_engine.py`; lifecycle and latest-RGB mailbox in `screen_runtime.py` |
| Whole selected monitor, BGR→RGB, every twentieth pixel, average | Screen page placeholder | Same full-monitor region and analysis; monitor enumeration off GUI thread |
| Intensity 0.25–2.0, saturation 0.5–2.5 (`olive_rgb.py:1235`) | Missing | LIVE sliders, atomic Qt preference persistence, changes applied on capture thread without restart |
| Movie smoothing 0.78, scene brightness and 80 ms interval | Missing | Unchanged engine calculations |
| Gaming smoothing 0.35, luma-jump impact and 40 ms interval | Missing | Unchanged engine calculations |
| Music/Screen exclusion (`olive_rgb.py:1558`) | Music-only ownership | Old capture is stopped and joined off GUI thread before next mode starts; pending transitions are canceled on Stop/close |
| Preview receives same calculated RGB as lighting | Music preview only | Shared read-only preview renderer; Screen shows engine RGB and final Bluetooth-channel RGB after Master/device scaling |
| Corner output and Hue Follow Master routing | Manual/Music routes only | Existing LotusLamp/LEDBLE session and Hue session, existing cadence/capability checks; manual colors retained and restored on Stop |
| Monitor/intensity/saturation in Tkinter settings | No Screen preferences | Backward-compatible `live.screen` section in separate Qt preferences; no restored running mode or connection |

Original ScreenEngine has **no arbitrary crop selector or user-adjustable
responsiveness**. Capture region is the whole selected monitor. Movie/Gaming select
the original fixed response. This sprint does not invent additional analysis.
Unlike Tkinter's device-required start, Studio allows capture with no connected
lights to satisfy read-only Windows preview testing.

The original ScreenEngine, MusicEngine, BluetoothWorker, LEDBLE driver, Hue
transport and rate limits are unchanged. Screen does not use Music palettes or
participation; Music preferences remain retained. Hue follows Screen only with
Follow Master ON. Corner/LEDBLE keeps its existing local scaling and Follow Master
behavior. Album and Music previews remain on the Music page; Screen has a dedicated
preview using the same renderer, without a simulated lighting algorithm.

## Screen UI integration diagnostic

The actual Qt entry point is `studio_qt_preview.py` → `studio_qt.app.main()` →
`ScreenLiveWindow` when LIVE is selected. Search for **ScreenLiveWindow**, not
ScreenWindow. `Launch Qt Preview.bat` launches this entry point;
`Launch Studio Preview.bat` launches the older Tkinter `studio_preview.py`.

Screen navigation selects `NAVIGATION.index('Screen')` (currently 3). The initial
sprint incorrectly inserted its LIVE panel at index 2, the Devices page, leaving
Screen with the placeholder. The correction uses the named navigation index.
A launcher regression selects LIVE in the actual chooser, navigates to Screen,
asserts visible controls and preview, runs Movie/Gaming without hardware, and closes.

The UI correction is included on `origin/development/qt-studio`. Pull the updated
branch using the commands below; no separate patch is required. If you already
applied a local patch, reconcile it before pulling. Close existing Studio
processes before launching the corrected Qt entry point. Windows and physical
hardware acceptance remain pending.

## LIVE mode-selector verification — pending on Windows

The LIVE generic controller intentionally rejects automatic non-Manual mode
changes. The original Screen selector only navigated and kept Music ownership;
its checked styling also depended exclusively on running capture. The selector
now opens the idle Screen workspace, stops/releases Music, cancels queued capture
requests and selects Screen without starting capture or connections. Reopening
Screen during Movie/Gaming keeps that existing capture running. All three selector
buttons synchronize from ownership and the idle Screen selection.

After pulling the updated `development/qt-studio` branch and launching the Qt
entry point below, choose LIVE and perform these checks:

1. On Studio, click Manual, then Music. Confirm Music is highlighted and starts
   only through its existing explicit action. Use audio output on Windows.
2. Click the Master Screen selector. Confirm navigation to Screen, Movie/Gaming
   controls visible, Music stopped, and Screen highlighted. No screen capture or
   Bluetooth/Hue connection should start merely from selecting Screen.
3. Return to Studio through navigation. Screen remains highlighted. Click Manual:
   Manual becomes highlighted and output ownership returns to manual controls.
4. Select Screen again, explicitly Start Movie, return to Studio, and confirm only
   Screen is highlighted. Re-click Screen: reopen its page without restarting
   capture. Repeat with Gaming.
5. During Movie/Gaming return to Studio and click Manual. Capture stops cleanly;
   then click Music and confirm Music/Screen never own output together.
6. With no devices connected, repeat the selector sequence. No connections start.
   With devices explicitly connected, verify manual colors restore on leaving
   Music/Screen. Physical-device acceptance remains pending.

## Install and launch (PowerShell)

The Screen sprint is available on `origin/development/qt-studio`. Before testing,
confirm your Windows checkout is on that branch and preserve any local changes.
Pull with fast-forward-only; do not force a merge or overwrite local work. If you
previously applied the sprint patch, reconcile that local patch before pulling.

Run from the repository root; replace the repository location:

```powershell
Set-Location 'C:\path\to\Olive-RGB'
git branch --show-current
git status --short
if ((git branch --show-current) -ne 'development/qt-studio') { throw 'Use the development/qt-studio checkout' }
git pull --ff-only origin development/qt-studio
if ($LASTEXITCODE -ne 0) { throw 'Pull failed; resolve local changes before testing' }
py -3 -m venv .venv-studio
& '.\.venv-studio\Scripts\python.exe' -m pip install -r '.\Studio\phase-1.10\requirements-studio-live.txt'
& '.\.venv-studio\Scripts\python.exe' -m pip check
& '.\.venv-studio\Scripts\python.exe' '.\Studio\phase-1.10\studio_qt_preview.py'
```

An existing Studio virtual environment may be used instead of creating one;
install and launch with that same Python executable. Optional Album dependencies
remain in `Studio/phase-1.10/requirements-studio-album.txt` and are unnecessary for
Screen capture. No changes to production Tkinter settings are required.

## No-lights Windows checklist — pending

Choose LIVE, leave both device connections disconnected, and open Screen using
the navigation or Master Screen button. The Master Screen button opens the page;
**Start Movie / Start Gaming** explicitly starts capture. Neither connects devices.

- [ ] Launch stays idle; monitor discovery completes and labels show dimensions
      and desktop offsets, including monitors to the left of the primary display.
- [ ] Select a monitor, show large red/green/blue/white/black images on that monitor,
      and Start Movie. Check the preview's color indicator, engine RGB and scaled
      output readout. Other monitors must not determine output.
- [ ] Start Gaming and compare the faster transitions/impact response. Movie must
      remain smoother. Preview does not imply hardware writes were performed.
- [ ] Change intensity and saturation during capture. UI and navigation remain
      interactive; capture does not restart. Color should reflect the original
      weighted grayscale saturation calculation, not a UI theme change.
- [ ] Change monitor while capturing. Old capture finishes before the selected
      monitor starts; no old frames may continue driving output.
- [ ] Test Master/device brightness and software power. Preview reflects scaling,
      black when powered off, and independent device behavior when Follow is OFF.
- [ ] Start Music, switch to Movie/Gaming, then back to Music. No overlapping
      capture ownership or stale colors; Album fallback/custom themes still work.
- [ ] Stop Screen, select Manual, and press Esc. Screen stops, preview clears,
      manual color settings remain intact. Music participation does not control
      Screen ownership.
- [ ] Restart Studio: monitor/intensity/saturation persist; capture, audio and
      connections remain stopped. Remove a saved monitor and check safe fallback.
- [ ] Test monitor hot-plug, capture permission errors and temporary unavailable
      display. Errors are visible; manual ownership is restored without reconnect.
- [ ] Close during capture, monitor discovery and a queued mode transition.
      Confirm process exit with no hanging capture/lifecycle threads.
- [ ] Launch DEMO; no MSS capture starts, and existing DEMO behavior is unchanged.

## Hardware checklist — pending

- [ ] Explicitly connect LotusLamp, then LEDBLE in separate runs; test Movie/Gaming
      colors, existing 250 ms BLE limiter, family switching and no duplicate links.
- [ ] Connect Hue and enable Follow Master. Verify screen colors, capability
      gating, Master/local scaling and power. Disable Follow Master and verify
      independent manual color. Repeat Music→Screen→Manual transitions.
- [ ] Disconnect/reconnect while Screen runs; confirm only explicit connections
      are made and current measured output resumes through existing sessions.
- [ ] Close during active transport writes; confirm unchanged clean BLE/Hue teardown.

## Limitations

Windows capture and physical hardware acceptance remain pending. Automated capture,
audio and device tests simulate input/I/O. A separate real MSS check on Linux Xvfb
verifies capture and UI shutdown, not Windows behavior. Protected/DRM video, secure
desktops, exclusive fullscreen, HDR and display scaling require Windows checks;
MSS may return black or unavailable content. Letterboxing and the Studio window
itself are included in the original whole-monitor average. No HDR tone mapping,
window exclusions or crop regions are added.

Native capture cannot be forcefully interrupted safely: shutdown waits
asynchronously for the current MSS grab to return. If data is stale, output
ownership is released and capture is stopped; an indefinitely blocked native grab
can still prevent complete process teardown and needs Windows diagnosis.

## Cloud validation

The original sprint passed 326 automated tests (28 Screen tests plus 298 regressions), the actual
DEMO launcher smoke passed, and a separate actual LIVE launcher / real Linux Xvfb
MSS smoke passed. No uncaught thread exceptions or deleted-object errors were
reported. Dependencies passed the environment package compatibility check.
These results do not constitute Windows or physical-device acceptance.

The UI integration correction passed 327 tests (29 Screen tests plus 298
regressions), DEMO smoke, and LIVE MSS smoke with visible Screen navigation.
The launcher regression failed before the page-placement correction and passes
after it. One existing fake-BLE write-spacing assertion failed on the first full
run; it passed unchanged on recheck and on the final full-suite rerun. Windows
verification of the UI correction remains pending.

The mode-selector fix passed 332 tests (34 Screen tests plus 298 regressions),
DEMO smoke and a real Linux MSS launcher smoke using Screen/Manual selector
clicks. Tests cover physical Qt clicks through Manual→Music→Screen→Manual,
Movie/Gaming styling, no automatic capture/connections, queued-start cancellation
and late audio error reporting without losing Screen selection. Windows and
physical-device acceptance of this selector fix remain pending.
