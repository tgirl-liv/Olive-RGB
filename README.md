# Olive RGB v1.0.0

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
