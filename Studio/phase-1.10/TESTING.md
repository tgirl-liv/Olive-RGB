# Coordinated Music validation

27 automated tests and the mocked Tk/settings reload check passed. See [COORDINATED_MUSIC.md](COORDINATED_MUSIC.md) for details and pending hardware tests.

# Hue preview validation

See [HUE_UPDATE.md](HUE_UPDATE.md) for the current software results and pending hardware checklist.

# Olive RGB v1.3 Customization Update

Version: `1.3.0-preview`. Based directly on the six attached v1.2 Preview 2 files.

## Changes

- Appearance tab with live Tickets, Sakura, Blackout, and Cyberpunk themes.
- Music tab with Bass, Mids, Treble, and Beat buttons and clickable hex color swatches.
- Music profiles retain their analysis, smoothing, sensitivity, dominance, and beat-strength parameters. All profiles now use the selected colors; choosing MGK no longer replaces the palette.
- Beats blend 45% of the selected Beat color into the frequency color. The existing beat brightness boost and smoothing behavior remain.
- Theme and colors save immediately when changed, and again on exit, in the existing `%APPDATA%\OliveRGB\settings.json`. Existing settings keys are preserved. Missing or invalid color values use defaults; an unknown theme uses Tickets.
- The BluetoothWorker and ScreenEngine class bodies are unchanged. The 0.25-second limiter, serialized GATT writes, and 750-ms settling delay remain intact. Windows default audio-output switching remains in the original capture loop.
- Original icons and batch build setup retained. The supplied spec is renamed and its executable label updated for v1.3.

## Verification completed

- Python source compilation.
- Structural comparison of the complete BluetoothWorker and ScreenEngine against the original source.
- Structural comparison of frequency-band averaging, beat detection, profile definitions and analysis helpers against the original source.
- Dominant-band and blended custom color checks across all four profiles.
- Color validation and settings save/load checks, including invalid settings data.

The available verification runtime lacks usable Tcl/Tk files, so GUI launch, visual layout, Windows loopback audio, Bluetooth hardware, and executable building were not verified here.

## Later testing

1. Extract the complete folder and run or build in the same Windows Python environment used for v1.2 Preview 2.
2. Switch through all four themes in Appearance; check labels, tabs, dropdowns, sliders, and the System log.
3. Open Music; pick distinct Bass/Mids/Treble/Beat colors, cancel a picker once, and try each profile.
4. Restart and confirm the theme, colors, and existing controls are restored.
5. Connect the lamp and test Music, a change of Windows default audio output, Movie, Gaming, and static colors.
6. Check the Music controls at your normal window size and Windows display scaling.

The batch build still produces `dist\Olive RGB.exe`; building the supplied spec produces `dist\Olive RGB v1.3 Preview.exe`. Both need the baseline project's installed dependencies (`numpy`, `soundcard`, `mss`, `lotus_lamp`, and its Bluetooth dependencies) and PyInstaller. No executable is included.

## Automatic album-cover colors extension

Run `install_dependencies.bat` once. In Music, set Music Colors to Album cover and
play music in a Windows media-session-aware player. Check the track label, artwork,
and four swatches; skip to a different album and confirm they change. Check grayscale
and dark covers, pause/resume, unavailable artwork, and switching back to Custom.
Picking an individual color leaves automatic mode and keeps the displayed palette
as your new custom palette. Restart to verify the selected source persists and that
automatic colors have not overwritten your previous saved custom palette.

Additional checks passed: image palette extraction, single-color/grayscale covers,
invalid image rejection, simulated Windows media adapter reads and stream cleanup,
same-track re-enable, missing and delayed artwork recovery, stopped playback,
worker shutdown, manual palette preservation, and ignored messages in Custom mode.
The media adapter uses a separate thread and the GUI polls its queue. None of the
BluetoothWorker, MusicEngine, or ScreenEngine classes changed in this extension.

Live Windows media API, player compatibility, GUI rendering, and executable packaging
still need verification on the user's Windows Python installation. No online artwork
lookup is attempted when a player does not expose a cover to Windows.

## v1.4 verification
Source compilation passed. AST comparisons confirm BluetoothWorker, MusicEngine,
and ScreenEngine are unchanged. Checks passed for adjustment identity, black
output, grayscale, half brightness, and invalid saved slider values.
GUI, lamp output, and EXE build remain unverified for this update.
Test each preset; edit a color; switch Album cover/Custom; move both sliders;
restart and confirm settings; use Reset; check Movie/Gaming remain unaffected.

## v1.4.1-preview: profile sliders
Selecting Smooth, Reactive, Hyperpop, or MGK now moves Sensitivity and Smoothing
to that profile's defaults. Sliders show actual reaction values, with manual
tuning saved across restarts. Previous multiplier settings migrate on load.
Brightness, saturation, palettes, and engine definitions remain unchanged.
Compilation and simulated profile-selection/manual-tuning checks passed for all
four profiles. Live GUI and lamp testing still required for this fix.

## v1.4.2 LEDBLE support
See LEDBLE_UPDATE.md for setup, changes, validation and physical test steps.
