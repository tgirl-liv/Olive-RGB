# Olive RGB Studio — Phase 1.7

Adjustable workspace and aligned mock device channels, built in a separate copy of Phase 1.6. No production backend integration was performed.

## Run and adjust

Use the unchanged **Setup Qt Preview.bat** and **Launch Qt Preview.bat**. No new dependencies were added.

The toolbar below the branding contains:

- **Workspace:** Studio, Music or Compact. This changes layout only, not the selected page, device state or lighting mode.
- **Sidebar:** compact icon-only or expanded navigation. Ctrl+B toggles it. Narrow windows automatically use icons to protect control space; expanding the window restores the user's expanded-label preference.
- **Inspector:** show or hide the right panel. Ctrl+I toggles it. The toolbar remains visible when either panel is collapsed.
- **Reset layout:** restores Studio proportions, opens the inspector, clears the manual sidebar-collapse preference and places the window at a visible default geometry. It saves the reset UI layout immediately.

Drag the vertical splitter to resize the workspace/inspector. Tab can focus the handle; Left/Right moves it by 16 logical pixels, Shift+Left/Right by 40. The workspace has a 345-pixel minimum and the inspector a 280-pixel minimum. Hiding the inspector is explicit; dragging cannot squeeze an open panel to zero. Normal resizing and page navigation no longer reapply default splitter sizes.

## Device alignment

Both device rows share the same layout rules and widths: a name column calculated from all channel names with a common 128-pixel minimum, 12-pixel color/status indicator, 66-pixel Power control, 112-pixel Follow Master control, expanding brightness track, and 42-pixel right-aligned percentage.

Wide rows use six columns. Medium rows put brightness and percentage on a second line. The narrowest layout uses name/indicator/power on the first line and Follow Master/brightness/percentage on the second. Every row changes layout at the same thresholds, with no per-device offsets. The old grid minimum-size feedback that could keep a row wider than the scroll viewport was removed.

Tests compare both x positions and widths of all six controls, on both Studio and Devices pages at each target size. A separate viewport-bound assertion confirms controls do not extend beyond the visible horizontal area. All controls still call the same mock controller and adapter.

## Presets

| Preset | Workspace arrangement |
|---|---|
| Studio | Balanced reactor, eight scenes and both device channels; inspector open. Both device rows fit at 1440×900. |
| Music | Larger reactor, device controls before smaller scene cards; inspector initially hidden but can be reopened. |
| Compact | Icon sidebar, inspector initially hidden, Master and device channels first, shorter reactor and smaller scene cards. |

Changing presets intentionally resets panel proportions and initial collapse choices. Subsequent user splitter/collapse changes are preserved across page changes and saved on close. The workspace dropdown's Music choice is independent of the lighting-mode Music button.

## UI-only persistence

Normal launcher startup reads:

```text
%LOCALAPPDATA%\OliveRGBStudio\workspace-v1.json
```

The file contains schema version 1, sidebar/inspector collapse preferences, selected preset, last open splitter sizes and normal window geometry. It contains no colors, scenes, device addresses, pairing data, audio settings or lighting preferences. **Production `settings.json` is neither opened nor overwritten.**

Writes occur on normal window close and Reset Layout. They use a uniquely named temporary file in the same directory, flush/fsync, then atomic replacement. A failed replacement preserves the previous file and cleans up the temporary file. Missing files use defaults; malformed, oversized, invalid-field or unsupported-version files recover to defaults with a status message. Unwritable storage leaves the current session usable.

Saved geometry must fit within one currently available monitor area; otherwise it recovers to a visible primary-monitor default. Maximized windows save their normal geometry. The preview does not restore maximized state, span multiple monitors, or change OS display settings.

Tests and screenshot tools instantiate the window without a persistent path unless explicitly testing a temporary workspace file. Persistence tests use disposable directories inside the project and do not touch the user's actual workspace preferences.

## Validation

Windows / Python 3.14.8 / PySide6 6.12.0:

| Suite | Result |
|---|---|
| Existing Qt UI tests | 25 passed |
| Existing adapter tests | 5 passed |
| New workspace tests | 13 passed |
| Existing Tkinter Studio tests | 17 passed |
| Existing Hue / LEDBLE / music regressions | 27 passed |
| Total distinct tests | **87 passed** |
| Extra scaling checks | Device alignment, keyboard splitter and inspector restoration passed at 125% and 150% |

Workspace tests cover shared row positions and viewport bounds, splitter movement, page-switch preservation, collapse/restore, preset isolation, file round-trip/restart, collapsed restart, reset, corrupt/invalid configuration, failed atomic replacement, offscreen geometry, close cleanup and Studio device visibility. Existing color synchronization, navigation, scenes, Follow Master, idle animation behavior and adapter tests still pass. No tests were removed or weakened.

Run Qt/workspace tests with:

```powershell
.\.venv-studio-qt\Scripts\python.exe -B -m unittest test_studio_qt test_studio_adapter test_workspace -v
```

The unchanged Tkinter/backend suites ran separately in the original application environment. Their connection diagnostics are mock output; no physical-device tests occurred.

## Screenshots

Open **PHASE17_GALLERY.html** for all presets and corrected device rows at 1440×900, 1280×800, 1080×760 and 800×600.

- `workspace-screenshots/`: Studio, Music, Compact and dedicated device alignment at all four sizes.
- `qt-screenshots/`: default workspace and compact Scenes captures at scale factors 1, 1.25 and 1.5, with actual-size metrics.

The four scale-1 target sizes match exactly. Visual checks and tests found no horizontal control clipping or misaligned device rows. Smaller heights require vertical scrolling; Compact keeps lighting controls near the top.

DPI validation uses `QT_SCALE_FACTOR` on the native Windows Qt platform, not changes to Windows Display Settings. At 150%, this display clamps requested 1280×800 and 1080×760 windows to 707 logical pixels tall. Scaled filenames describe requested sizes; the JSON metrics record actual dimensions. Native OS scaling, monitor hot-plug and mixed-DPI movement remain manual validation items.

## Changed files and protection

Updated:

- `studio_qt/widgets/controls.py`: common device columns and responsive reflow.
- `studio_qt/app.py`: workspace toolbar, preset layout, collapse/restore, geometry and persistence lifecycle.
- `studio_qt/theme.py`: visible hover/focus splitter handles.

Added:

- `studio_qt/workspace.py`: versioned storage, atomic writes, geometry recovery and keyboard splitter.
- `test_workspace.py`, `capture_workspace.py`.
- This report, `PHASE17_GALLERY.html`, `PHASE17_BASELINE_SHA256.json`, `PHASE17_VALIDATION.json`, and workspace screenshots.

Default screenshots were regenerated. Historical reports/manifests describe their earlier releases, not this validation run.

The validation manifest includes expected/actual SHA-256 comparisons. All 53 original application/Tkinter/configuration files are unchanged. The mock adapter, controller, icon system, original Qt/adapter tests and both Windows Qt launchers are also unchanged relative to Phase 1.6. No production settings, build scripts, BluetoothWorker, HueService, MusicEngine, ScreenEngine, MusicLightingRouter or driver files were modified.

## Remaining limitations

- Workspace preferences save on clean close or Reset, not after every drag; a crash may lose the latest adjustment. Concurrent preview instances use last-close-wins behavior.
- Below 1100 pixels, the sidebar uses icons automatically even when expanded labels are preferred. All navigation remains accessible through icons, tooltips and Alt+1…Alt+6.
- Reset and offscreen recovery restore a normal visible window, not prior maximized/multi-monitor spanning state. A display with less than the supported 800×600 usable space cannot show the full minimum window.
- Secondary pages remain the existing mock placeholders. All device status and audio visualization are simulated. No installer or executable packaging was added.

**Stopped after Phase 1.7. Real hardware integration has not begun.**
