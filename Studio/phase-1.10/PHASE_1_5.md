# Olive RGB Studio — Phase 1.5

Standalone Qt polish and mock backend boundary, developed in a separate copy of Phase 1.4. The original Phase 1.4 folder and ZIP remain available as the baseline. All production source, Tkinter preview, settings and build scripts are preserved.

## Launch

Extract the entire folder, run **Setup Qt Preview.bat** once, then **Launch Qt Preview.bat**. Setup creates a dedicated `.venv-studio-qt`; it uses the unchanged `requirements-studio-qt.txt` pin, PySide6 6.12.0. Python 3.14 is used by the supplied setup script. No new dependencies or executable builds were added.

This is a simulated application. It does not connect real lights or save live settings. The older Phase 1.4 report is retained as historical documentation; this report describes the current iteration.

## UI changes

- **Master Bus:** larger gradient brightness track, custom vector power button, mutually selected Manual/Music/Screen buttons, compact output swatch, keyboard focus and hover styling. At narrow widths, modes occupy a second row. Space toggles power, arrow keys adjust brightness, and Tab reaches each mode. The color swatch opens the corner channel's Color inspector.
- **Navigation:** local scalable QPainter icons for home, music, devices, screen, scenes and settings. Compact mode has icons rather than abbreviations; full-name tooltips and accessible names remain. Alt+1 through Alt+6 and keyboard button activation are preserved. No runtime icon downloads.
- **Inspector:** full device names, explicit simulated connection status, separated Color Lab / HSV / quick-color sections, aligned numeric controls, collapsible advanced RGB values and consistent tabs. Invalid HEX remains inline and does not change state. Empty error space is hidden. Device controls follow the color controls without the earlier large stretch gap.
- **Adapter:** lighting intents now pass through a minimal Protocol and `MockLightingAdapter`. Discovery/status and normalized meter records return through queued signals. The reactor's four meters consume the adapter notifications; spectrum and waveform remain synthetic. Detailed future integration constraints and the per-method confirmation checklist are in `BACKEND_ADAPTER_ARCHITECTURE.md`.

## Verification

Windows / Python 3.14.8 / PySide6 6.12.0:

| Check | Result |
|---|---|
| Qt UI tests | 20 passed |
| Mock adapter tests | 5 passed |
| Existing Tkinter Studio tests | 17 passed unchanged |
| Existing Hue, LEDBLE and coordinated-music regressions | 27 passed unchanged, using mocks |
| Total distinct automated tests | **69 passed** |
| Extra DPI checks | 3 UI checks repeated successfully at 125% and 150% |
| Timer / adapter cleanup | Timer stops; transition cancelled; adapter closes; late meter delivery ignored |
| Control bounds | No out-of-parent controls in the four-size check, including expanded RGB editor |

Run new tests with the Qt environment:

```powershell
.\.venv-studio-qt\Scripts\python.exe -B -m unittest test_studio_qt test_studio_adapter -v
```

Existing Studio/backend suites ran separately in the existing application environment. Their connection log lines describe mocks; no physical testing was performed.

Screenshots in `qt-screenshots/` cover 1440×900, 1280×800, 1080×760 and 800×600. All four scale-1 captures have the exact requested dimensions. At smaller sizes the center and inspector scroll independently; controls below the viewport are reachable, not overlaid or compressed out of use. The Scenes page remains a quick route to all cards.

Additional captures use `QT_SCALE_FACTOR=1.25` and `1.5` on the native Windows Qt platform. This tests Qt rendering at those factors; Windows Display Settings were not changed. At 150%, Windows clamps requested 1280×800 and 1080×760 windows to 707 logical pixels tall on this display. Filenames retain requested sizes; `metrics-scale-*.json` records actual dimensions. Real OS scaling and mixed-monitor movement remain manual checks.

## Files and protection

Existing Qt files updated:

- `studio_qt/app.py`: vector navigation, adapter notifications, shutdown.
- `studio_qt/controller.py`: lighting intents routed through the adapter.
- `studio_qt/theme.py`: Master Bus, mode, navigation, slider and tab styles.
- `studio_qt/widgets/controls.py`: responsive Master Bus redesign.
- `studio_qt/widgets/inspector.py`: layout, device labels and queued status handling.
- `studio_qt/widgets/audio_reactor.py`: displayed meter values from the adapter.
- `test_studio_qt.py`: expanded UI/adapter-boundary checks.
- `capture_studio_qt.py`: deterministic adapter meter input for captures.

New files:

- `studio_qt/backend_adapter.py`
- `studio_qt/widgets/icons.py`
- `test_studio_adapter.py`
- `BACKEND_ADAPTER_ARCHITECTURE.md`, `PHASE_1_5.md`
- `PHASE15_BASELINE_SHA256.json`, `PHASE15_VALIDATION.json`

Screenshots and their metrics were regenerated. `PHASE15_BASELINE_SHA256.json` records the Phase 1.4 source baseline; `QT_BASELINE_SHA256.json` preserves the original 53-file Phase 1.3 manifest. The validation manifest reports final hashes and changed files. All 53 original application/Tkinter/configuration files are byte-for-byte unchanged. The original source directories are not edited.

## Remaining issues / Phase 2 recommendations

1. Review the UI first. Secondary Music, Screen and Settings workspaces remain labeled preview pages. No backend migration has begun.
2. Confirm every production mapping in the adapter architecture document, especially brightness semantics, Follow Master, scene transition ownership and service-loop ownership. Add asynchronous failure/acknowledgement tests before live implementation.
3. The adapter is deliberately mock-only, with optimistic UI state. Production discovery, connection, authentication, errors, reconnection and shutdown acknowledgements are not implemented.
4. Hover and selection feedback use immediate QSS states rather than new animation timers. Procedural scene artwork is unchanged. Native screen-reader behavior, actual Windows display scaling and mixed-monitor usage still need hands-on review.
5. No installer or executable was built. Packaging remains a separate task, with the same PySide6 footprint and licensing/deployment considerations noted in Phase 1.4.

**Stopped after Phase 1.5. Real hardware requires explicit approval.**
