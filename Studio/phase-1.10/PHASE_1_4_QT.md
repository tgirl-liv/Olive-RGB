# Olive RGB Studio — Phase 1.4 Qt prototype

This is a separate, interactive **mock-only** PySide6 preview. The supplied Phase 1.3 project remains intact. Production migration has not started.

## Run on Windows

1. Extract this entire folder.
2. With Python 3.14 installed, run **Setup Qt Preview.bat** once. It creates `.venv-studio-qt` and installs the separate pinned Qt dependency.
3. Run **Launch Qt Preview.bat**.

The existing **Launch Studio Preview.bat** still opens the unchanged Tkinter preview. Neither Qt launcher starts Olive RGB or uses live settings. No standalone executable is included.

For a terminal launch after setup:

```powershell
.\.venv-studio-qt\Scripts\python.exe studio_qt_preview.py
```

## Implemented interactions

- Master power, brightness and Manual/Music/Screen selection update the shared mock state. Output color selects the corner channel for editing. The reactor runs only in Music while the master is on and Play is enabled.
- One root-owned 34 ms Qt timer drives the 72-bar synthetic spectrum, peak decay, derived waveform and scene transitions. Hidden, paused and Reduced Motion reactor states do not advance. Hiding or closing the window stops the timer; closing cancels transitions.
- Eight original scene names/palettes are preserved. Select a card, toggle its heart, or filter Favorites. Return/Space recalls a focused card; F toggles its favorite. A new selection replaces the current transition from its current displayed color.
- Inspector Setup exposes transition duration, Smooth/Linear/Instant curves and Reduced Motion. Reduced Motion applies scenes immediately and retains a static reactor.
- Both device channels expose local power, local brightness and Follow Master. Follow Master OFF preserves the channel during subsequent scene recalls and freezes an in-progress transition for that channel.
- Color wheel, HSV sliders/spin boxes, HEX editor, seven swatches and expandable RGB editor all update the selected mock device. Invalid HEX shows an inline message without changing its color. Wheel arrow keys provide a mouse-free alternative.
- Inspector Music exposes mock relationship, separation and sensitivity settings. These are state controls, not a music-analysis or lighting engine.
- Navigation uses compact text abbreviations below 1100 px; tooltips and accessible names retain full labels. Alt+1 through Alt+6 selects Studio, Music, Devices, Screen, Scenes and Settings. Tab reaches controls. Scenes and Devices have working dedicated views. Music, Screen and Settings explicitly label their workspace content as a preview and link to inspector controls.
- All state resets on restart. There are no application settings writes, Bluetooth commands, audio capture sessions or screen capture sessions. The separate developer capture utility renders only the preview's own widget.

## Visual comparison

| Area | Approved mockup | Phase 1.3 Tkinter | Phase 1.4 Qt |
|---|---|---|---|
| Structure | Three-column DAW dashboard | Three regions with mostly square containers | Rounded panels, movable splitter, independent workspace/inspector scroll areas |
| Reactor | Large luminous spectrum and waveform | Canvas bars, stepped wheel and waveform rendering | Antialiased gradient bars, peak holds/decay, clearer waveform, restrained glow |
| Scenes | Detailed illustrative thumbnails | Flat procedural mountains/clouds | Cached 720×400 local artwork, layered cloud gradients, city, waves, neon and cinema motifs |
| Color Lab | Smooth ring, sliders, compact controls | Raster-like wheel with multiple editor tabs | Smooth painted ring, synchronized numeric controls, HEX and collapsible RGB |
| Density | All controls at reference size | Broad dashboard, dense inspector | All dashboard sections visible at 1440×900; smaller windows scroll vertically |
| Navigation | Pictorial icons and labels | Symbols and labels | Labels on desktop, readable compact abbreviations with tooltips |

The Qt version improves rounded rendering and resizing while keeping the existing data model. It is not a pixel-identical recreation: artwork remains procedural rather than the mockup's richly illustrated images; there are no realistic bulb thumbnails, independent transition side panel or Advanced Mixer palette. Secondary workspaces and routing remain explicitly mocked. The framework is promising for further UI work, but this prototype does not establish production performance, accessibility certification or backend migration readiness.

## Screenshots and scaling

`qt-screenshots/` contains window-only captures at all four required sizes:

- `qt-1440x900-scale-1.png`
- `qt-1280x800-scale-1.png`
- `qt-1080x760-scale-1.png`
- `qt-800x600-scale-1.png`

These four logical and pixel dimensions match exactly. Visual review found no overlapping controls or horizontal overflow. At smaller heights, below-fold controls remain accessible by vertical scrolling. The dedicated Scenes view puts all eight cards within easy reach at 800×600; an additional screenshot demonstrates it. Inspector controls also scroll at that size. The splitter supports user adjustment within minimum widths.

Additional captures use `QT_SCALE_FACTOR=1.25` and `1.5` on the Windows Qt platform. These test Qt scaling, **not a change to Windows Display Settings**. Windows constrained some taller windows to available screen space, so scaled filenames describe the requested size; the accompanying `metrics-scale-*.json` files record actual logical dimensions, pixel dimensions and device-pixel ratio. At 150%, requested 1280×800 and 1080×760 became 1280×707 and 1080×707. Actual OS scaling, mixed-monitor movement and taskbar placement still need user validation.

Qt 6 handles high-DPI scaling automatically; `QT_SCALE_FACTOR` is an explicit test override. See [Qt high-DPI documentation](https://doc.qt.io/qtforpython-6/overviews/qtdoc-highdpi.html).

## Validation

Validated using Windows, Python 3.14.8 and an isolated PySide6 6.12.0 environment:

| Check | Result |
|---|---|
| New Qt tests | 14 passed |
| Unchanged Studio tests | 17 passed, including all 6 non-GUI StateTests |
| Existing Hue/LEDBLE/music regressions | 27 passed using mocks |
| Python syntax parsing | 14 new Python files passed |
| Original Phase 1.3 SHA-256 comparison | 53 of 53 identical |
| Native control bounds check, expanded RGB at 800×600 | No out-of-parent controls |
| Four target window sizes | Exact at scale 1; no horizontal scrollbar overflow |
| Shutdown | Timer stopped; pending transition cancelled |

The tests cover navigation, favorites, Follow Master, HSV/RGB/HEX synchronization, validation, channel selection and controls, transition replacement, mid-transition opt-out, Reduced Motion, hidden/paused reactor, resizing, startup isolation and shutdown. Existing test files were neither modified nor weakened. Regression log device names refer to mocked Bluetooth objects; **no physical connection tests were performed**.

Qt suite, after setup:

```powershell
.\.venv-studio-qt\Scripts\python.exe -B -m unittest test_studio_qt -v
```

Run the unchanged Tkinter and backend suites separately using the existing Olive RGB Python environment:

```powershell
python -B -m unittest test_studio_preview -v
python -B -m unittest test_hue_api test_hue_integration test_ledble test_ledble_retry test_music_coordination -v
```

`capture_studio_qt.py` is an optional developer utility, not imported by the preview. It writes screenshots only to `qt-screenshots/`.

## Dependencies and packaging

The only directly added requirement is **PySide6==6.12.0**, in `requirements-studio-qt.txt`. This environment resolved PySide6_Essentials, PySide6_Addons and shiboken6 at 6.12.0, plus PySide6_WebEngine and PySide6_Pdf at 6.12.0.140. The prototype imports only QtCore, QtGui and QtWidgets; tests additionally use QtTest. The virtual environment is outside the delivered archive. Existing `requirements.txt` and all build files remain unchanged.

Qt wheels bundle Qt libraries, making this substantially larger than the Tkinter preview. See [Qt for Python installation guidance](https://doc.qt.io/qtforpython-6/gettingstarted.html). A future executable needs its own packaging configuration, the Windows Qt platform plugin, dependency/license review and a clean-machine test. [pyside6-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html) is an official option to evaluate. No production build configuration was changed and no executable packaging was claimed or tested.

## Files

All changes are additions within this separate `Olive RGB Studio Qt Phase 1.4` directory:

- `studio_qt_preview.py`: standalone entry point.
- `studio_qt/app.py`: responsive layout, navigation, scene grid and owned timer.
- `studio_qt/controller.py`: Qt signals and cancellable mock transitions around the unchanged model.
- `studio_qt/theme.py`: QSS using existing palette tokens.
- `studio_qt/widgets/common.py`: shared layout/control helpers.
- `studio_qt/widgets/controls.py`: Master Bus and device channels.
- `studio_qt/widgets/audio_reactor.py`: cached gradients and synthetic visualization.
- `studio_qt/widgets/scene_pad.py`: local artwork and interactive cards.
- `studio_qt/widgets/color_wheel.py`: painted interactive hue ring.
- `studio_qt/widgets/inspector.py`: selected-device mock controls and validation.
- Two `__init__.py` package files.
- `test_studio_qt.py`, `capture_studio_qt.py`.
- `requirements-studio-qt.txt`, `Setup Qt Preview.bat`, `Launch Qt Preview.bat`.
- `QT_BASELINE_SHA256.json`, `QT_VALIDATION.json`, this report, and `qt-screenshots/`.

The existing `studio_ui/state.py` is reused unchanged. `QT_BASELINE_SHA256.json` records every file extracted from the supplied Phase 1.3 ZIP, including all production source, Tkinter preview, existing documentation, screenshots and configuration. `QT_VALIDATION.json` records the final integrity result. The original supplied ZIP remains the known-good baseline.

**Stop point: Phase 1.4 prototype only. Review the UI before approving any production migration.**
