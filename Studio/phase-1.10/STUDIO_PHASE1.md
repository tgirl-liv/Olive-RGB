# Olive RGB Studio — Phase 1 UI preview

## Launch

Extract this package to a separate folder and double-click **Launch Studio Preview.bat**. Or run:

```powershell
py -3 studio_preview.py
```

If the launcher is unavailable:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" studio_preview.py
```

The standalone preview uses Python's Tkinter/ttk/Canvas and standard-library modules only. No extra installation is needed for the preview. The original app and its requirements remain alongside it, unchanged; launch `studio_preview.py` for this phase, not `olive_rgb.py`.

## What to review

- Dark-neon navigation: Studio, Music, Devices, Screen, Scenes, Settings.
- Master Bus with mock power, brightness and mode selection.
- Combined synthetic spectrum and waveform; Play/Pause and animation controls.
- Four scene pads. Click a pad to apply its colors to following mock channels; click its star to favorite it. Favorites can be filtered.
- Scene transitions: use the Transition button or inspector Setup tab. Choose Smooth, Linear or Instant and a duration of 0–5 seconds. Channel color indicators interpolate; settings apply to the next scene launch.
- Corner Lamp and Philips Hue channels with mock power, brightness and Follow Master. Click a device to target the inspector. Both channels are explicitly simulated; Hue is presented as RGB capable.
- Persistent inspector with Color, Music and Setup tabs. Use the wheel, HSV sliders, HEX Apply/Enter and quick swatches. Selected target and inspector tab survive navigation.
- Music parameters are in-memory preview settings, not audio-engine controls. Screen contains a generated color field and mock display selector; it never captures the desktop.
- The layout was checked at 1080×760 and 800×600. The center reflows scene/device grids and Master brightness; the inspector remains on the right. Use vertical scrollbars at smaller sizes.

## Isolation and preservation

The project is a new directory copy of Olive RGB v1.5.1 Coordinated Music. All 28 supplied baseline files were verified byte-for-byte in both the original and copied directories using `STUDIO_BASELINE_SHA256.json`.

No BluetoothWorker, HueBLE/HueDriver, MusicEngine, ScreenEngine, MusicLightingRouter, LEDBLE, existing application, dependency, build or settings file was edited. No executable was rebuilt or replaced; the supplied source baseline contained no executable. The separately supplied `Olive RGB pre-Studio rollback.zip` is an exact copy of the supplied v1.5.1 release archive.

The preview does not import the real application or any backend. It does not create Bluetooth clients, capture sessions, threads or asyncio loops. State exists only in memory and resets on exit. No live settings are loaded or saved.

One Tk root owns one animation callback, scheduled every 34 ms (at most about 29 FPS, lower under load). Scene transitions share that callback. Close cancels the callback before destroying the root. Navigation does not create additional windows or animation loops.

## Added files (existing files unchanged)

- `studio_preview.py`: standalone entry point.
- `studio_ui/__init__.py`: preview package.
- `studio_ui/state.py`: mock channels, scene/favorite/navigation/inspector/transition state.
- `studio_ui/widgets.py`: scene pads, color wheel, synthetic reactor and scroll areas.
- `studio_ui/app.py`: dashboard, mock control bindings and animation lifecycle.
- `test_studio_preview.py`: 10 state/UI/isolation/shutdown tests.
- `Launch Studio Preview.bat`: Windows launch helper.
- `STUDIO_BASELINE_SHA256.json`: baseline file checksums.
- `STUDIO_PHASE1.md`: this guide.
- `studio-preview.png`, `studio-preview-small.png`: renders of the actual preview window at the two tested sizes.

## Validation results

**37 tests passed:** 10 new Studio tests plus the existing 27 mock regression tests. Syntax checks passed. Baseline checksums matched. Actual preview-window renders were inspected at both target sizes.

The tests cover scene selection and Follow Master isolation, favorites, navigation, inspector persistence, transition settings, HEX/HSV editing, mock controls, smaller-window layout, no-backend imports and cancellation on shutdown. Existing regression tests ran with isolated HueBLE package sources and mocked I/O, not real hardware. Python 3.14.8 was used.

Preview-only tests need no application dependencies:

```powershell
py -3 -B -m unittest test_studio_preview -v
```

To run the whole suite in a normal environment, first install the original requirements and then run:

```powershell
py -3 -B -m unittest discover -p "test_*.py" -v
```

## Phase 1 limitations

This is a reviewable design sandbox. Spectrum/beat-like motion and waveform are synthetic, not audio measurements. Music options store mock values; they are not implementations of production DSP or device coordination. Device connection/setup text is simulated. Colors are screen previews, not calibrated bulb output. Favorite and transition preferences intentionally do not survive restart. An executable build, additional display scaling factors and physical device behavior were not tested.

**Backend integration has not begun. Phase 1 ends here pending UI review.**

## Rollback

Close the preview and use your original v1.5.1 folder, which remains untouched. Alternatively extract the separate pre-Studio rollback ZIP. No live settings restore is needed because the preview never reads or writes them.
