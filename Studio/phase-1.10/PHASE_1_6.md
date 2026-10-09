# Olive RGB Studio — Phase 1.6

Focused visual and interaction refinement of the Phase 1.5 Qt preview. Work was performed in this separate copy. Everything remains simulated; no hardware integration or new lighting features were added.

## Launch

Run the existing **Setup Qt Preview.bat** once if this extracted copy has no Qt environment, then **Launch Qt Preview.bat**. Both launchers are byte-for-byte unchanged. Dependencies remain PySide6 6.12.0 and its existing dependencies; no new packages, runtime downloads or external icon assets were added.

## Changes

- Centralized local vector icons now share a 24-unit canvas, 1.75-unit rounded strokes, transparent backing and device-scale rendering. Devices uses a bulb, Screen a monitor and Settings a gear. Favorites and branding also use drawn icons rather than Unicode symbols. Normal, active/hover, selected and disabled icon colors are supported; keyboard focus is shown by the containing control.
- Branding has a local waveform mark and pink RGB accent. Secondary text is slightly larger, headings share consistent typography, device rows lose their redundant outer borders, and keyboard focus is more visible. Master Bus, inspector fields, tabs, sliders and navigation use coordinated hover/selected/focus styling.
- All eight scene names, palettes and original artwork-generation code are preserved. Artwork scales with preserved aspect ratio using a centered crop. A darker label area supports readable names, with two-line space at narrow widths. Favorite hearts use the common vector system; duration appears in a consistent top-left badge. The selected card has a pink outline and side marker, separate from the keyboard-focus outline.
- The synthetic reactor retains its 72 bars, data generator, peak decay and Reduced Motion support. Presentation changes include more even bar gaps, a quieter grid, interpolated waveform amplitude with round stroke joins, and left-aligned band labels with right-aligned values.
- The root-owned animation timer now stops when paused, reduced-motion, hidden, on another page, or scrolled out of view, provided no scene transition is active. It resumes when needed. A scene transition can finish while the reactor is paused, then the timer stops. There are no new animation timers or threads.

## Screenshots

Open **PHASE16_COMPARISON.html** for before/after pairs at the four requested sizes.

- `phase16-before/`: preserved Phase 1.5 captures, including its original scaling metrics.
- `qt-screenshots/`: Phase 1.6 captures at 1440×900, 1280×800, 1080×760 and 800×600, plus compact Scenes and scaled captures.

The four scale-1 screenshots match the requested dimensions. Visual inspection and automated bounds checks found no overlapping controls or clipped scene names. At smaller sizes, controls below the viewport remain reachable by vertical scrolling. The inspector and center scroll independently, as in Phase 1.5.

Qt rendering was checked with `QT_SCALE_FACTOR` at 1, 1.25 and 1.5 on Windows. Windows Display Settings were not changed. The same screen-height constraint remains: at scale 1.5, requested 1280×800 and 1080×760 windows are clamped to 707 logical pixels tall. Filenames reflect requested sizes; `metrics-scale-*.json` records actual logical/pixel sizes and DPR. Native OS scaling changes and mixed-monitor movement remain manual checks.

## Tests

Windows, Python 3.14.8, PySide6 6.12.0:

| Suite | Result |
|---|---|
| Qt UI tests | 25 passed |
| Existing mock adapter tests | 5 passed |
| Existing Tkinter Studio tests | 17 passed |
| Existing Hue / LEDBLE / music regressions | 27 passed |
| Total distinct tests | **74 passed** |
| Repeated DPI checks | 3 checks at each of 125% and 150%, all passed |

New tests cover every vector icon at each scale and mode, scene text bounds, favorite icons, idle timer stop/resume, paused transition completion, and scrolling the reactor offscreen. Existing navigation, HSV/RGB/HEX, device selection, adapter commands, Follow Master, startup, resizing and shutdown tests still pass. The bounds test includes the expanded RGB editor at all four target sizes.

Paused-idle validation confirms the timer is inactive and reactor frame count stays constant. This eliminates our periodic animation work; it is not a claim that the Qt process or Windows consumes literally zero CPU. No physical device testing occurred. Existing regression log connection messages describe mocks.

```powershell
.\.venv-studio-qt\Scripts\python.exe -B -m unittest test_studio_qt test_studio_adapter -v
```

The unchanged Tkinter and backend suites were run separately in the original application environment.

## Changed files and protected-file comparison

Updated Qt files:

- `studio_qt/widgets/icons.py`: normalized icons, favorites/logo, color states and scaled pixmaps.
- `studio_qt/widgets/scene_pad.py`: card presentation and favorite icon; artwork function unchanged.
- `studio_qt/widgets/audio_reactor.py`: rendering refinements only.
- `studio_qt/widgets/controls.py`: borderless device row styling and painted-color indicator.
- `studio_qt/app.py`: branding, favorite filter icon and idle timer lifecycle.
- `studio_qt/theme.py`: consistent typography and feedback states.
- `test_studio_qt.py`: five additional tests; existing tests retained.

New artifacts: this report, `PHASE16_COMPARISON.html`, `PHASE16_BASELINE_SHA256.json`, `PHASE16_VALIDATION.json`, `phase16-before/`. Current screenshots were regenerated. Historical Phase 1.4/1.5 reports and validation manifests remain reference material, not results for this release.

`PHASE16_VALIDATION.json` includes expected and actual hashes for every protected file. All 53 files from the original application/Tkinter baseline are unchanged. The Qt mock adapter, controller, adapter tests and both Qt Windows launchers are also unchanged relative to Phase 1.5. The scene artwork function was compared independently and is identical. No production drivers, settings, requirements or build scripts were modified.

## Remaining issues

- The application still uses procedural scene artwork, not the reference mockup's illustrated thumbnails; this phase deliberately preserves the existing artwork.
- Small windows require scrolling. The dedicated Scenes page keeps scene selection easy to reach.
- Hover/selection changes are lightweight immediate style changes, not animated fades. Screen-reader behavior and mixed-monitor DPI still need hands-on review.
- Secondary workspaces remain labeled placeholders. Mock status is not a real device connection. The Phase 1.5 architecture document and its production-confirmation checklist remain applicable and unchanged.
- No executable or installer was built. Packaging and any backend integration remain separate, unapproved work.

**Stopped after Phase 1.6. No real hardware integration.**
