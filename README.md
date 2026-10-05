# Olive RGB v1.3 Customization Update

This package turns the known-good V4.2 lamp controller into a Windows GUI app.

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

