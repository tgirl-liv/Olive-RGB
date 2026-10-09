# Olive RGB v1.5.1 Coordinated Music

Adds coordinated Music colors for the corner lamp and Hue. See [COORDINATED_MUSIC.md](COORDINATED_MUSIC.md) for current setup, settings, tests and rollback.

The underlying Hue preview adds an independent Philips Hue Bluetooth device and optional Follow Master to the supplied v1.4.2 application. Read [HUE_UPDATE.md](HUE_UPDATE.md) for setup, pairing, validation and rollback. This package contains source; build a fresh executable.

## Build on your Windows PC

1. Extract this folder.
2. Double-click `build_windows.bat`.
3. Wait for the build to finish.
4. Your application will be at:
   `dist\Olive RGB.exe`
5. You can right-click the EXE and create a shortcut on the Desktop or Start Menu.

The build uses `--windowed`, so the finished app opens without a console window.

## Persistent settings

Olive RGB stores user settings outside the EXE at:

`%APPDATA%\OliveRGB\settings.json`

That means replacing `Olive RGB.exe` with a future version will not erase your saved
music profile, sensitivity, smoothing, monitor, screen intensity, or saturation.

## Updating

v1.0.0 is prepared for replace-in-place updates: settings are external to the EXE.
Once an update host (for example GitHub Releases) is available, an updater/checker can
be added without changing where your settings live.

## Important

The stable BLE protection from V4.2 remains in the source. Do not raise the lamp update
rate unless deliberately testing the controller's stability.


## v1.0.2 BLE diagnostics
This debug release adds console diagnostics around the Bluetooth worker thread, asyncio event loop, coroutine submission, and task completion. It does not change the lamp RGB rate limiter.


## v1.1.1
- Softer Sakura Dark palette for improved readability.
- Music mode automatically follows changes to the Windows default audio output device.

## v1.3.0-preview
See TESTING.md for customization changes, verification, and later testing steps.

## Automatic album-cover colors

Double-click `install_dependencies.bat` once (or run `py -m pip install -r requirements.txt`).
Start with `py olive_rgb.py`, then choose **Music → Music Colors → Album cover**.
Play a song in a player that shares its current artwork with Windows. Olive extracts
Bass/Mids/Treble/Beat colors from that cover and updates them as the track changes.
The current song and cover appear beside the signal meters. No music-service login
is required. Windows must receive media metadata and artwork from the player;
otherwise Olive uses your saved custom colors. Paused/stopped playback also uses
the custom palette. Choose Custom, or pick any individual color, to leave automatic mode.

The selected source persists. Automatic palettes do not overwrite your saved custom
palette. Cover polling runs separately from audio capture and Bluetooth. Covers
are read from the Windows media session, not searched for on the web.

The build script now installs the listed dependencies before packaging and includes
Pillow and the Windows media adapter. Include `album_colors.py` beside `olive_rgb.py`
when running from source. Windows 10 version 1809 or later is needed for the media API;
dependency wheel availability also depends on your Python version and architecture.


## v1.4.0-preview
Music now includes artist-inspired presets for The Weeknd (After Hours, Dawn FM,
Starboy) and Charli xcx (BRAT, Crash). Select one below Music Colors. Presets
switch to Custom and save the four colors as your editable fallback palette.
Album cover mode remains available and preserves those saved colors.
Brightness and Saturation sliders appear beside the live signal. They apply live
to all Music palettes, persist on restart, and reset to 100% with one button.
Swatches show the underlying palette before lighting adjustments. Saturation
0% produces grayscale; brightness 0% turns Music output black.

## v1.4.1-preview: profile sliders
Selecting Smooth, Reactive, Hyperpop, or MGK now moves Sensitivity and Smoothing
to that profile's defaults. Sliders show actual reaction values, with manual
tuning saved across restarts. Previous multiplier settings migrate on load.
Brightness, saturation, palettes, and engine definitions remain unchanged.
Compilation and simulated profile-selection/manual-tuning checks passed for all
four profiles. Live GUI and lamp testing still required for this fix.

## v1.4.2 LEDBLE support
See LEDBLE_UPDATE.md for setup, changes, validation and physical test steps.


## Qt Studio Album Cover Lighting

The LIVE Music page has a separate Album Cover Lighting source selector.
Album artwork supplies bass, mids, treble and beat LIGHT colors; it does not
change the Studio UI theme. Start Music explicitly to apply the palette through
the existing participation and device coordination controls. Master/local power
and brightness remain effective; stopping Music restores manual ownership.

The read-only Virtual Light Preview shows the calculated final Corner Lamp Music
RGB/hex and the engine RGB before device brightness/power. It uses the same
calculation as the Corner transport, including local settings and Follow Master.
It works with no devices connected, reflects measured beat effects and engine
smoothing, and clears on stale audio or Stop. It does not send commands, create
connections, or report hardware feedback. The existing Hue coordination is
unchanged; this preview represents the Corner output.

Windows players must expose a playing media session and thumbnail. Missing
artwork, paused playback or unavailable optional dependencies use the selected
production preset. The source preference is saved only in Qt preferences;
launching never starts audio capture or connects devices. DEMO is unchanged.

Optional installation, from the repository root in PowerShell:

```powershell
python -m pip install -r .\Studio\phase-1.10\requirements-studio-album.txt
python .\Studio\phase-1.10\studio_qt_preview.py
```

Normal LIVE installation still uses `requirements-studio-live.txt` and does not
require Pillow or WinRT. Windows media support needs Windows 10 1809 or later
and compatible WinRT wheels for your Python version/architecture. Non-Windows
LIVE uses preset fallback. Player status shows the Windows source application ID.
