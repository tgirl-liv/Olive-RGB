# Coordinated Multi-Light Music — v1.5.1 Preview

## Start here

This complete source update is based on the supplied v1.5 Hue Preview. Keep the accompanying `Olive RGB v1.5 pre-coordinated rollback.zip`: it is an exact copy of that release ZIP. The original folder was left unchanged. There was no Git repository available.

1. Close Olive RGB and copy `%APPDATA%\OliveRGB\settings.json` somewhere safe if you want a settings rollback too.
2. Extract this update into a new folder. Install dependencies using `install_dependencies.bat`, then run `py olive_rgb.py`, or build as described below.
3. Use the existing controls to connect the corner lamp and **HUE / MASTER > Connect / Reconnect** for Tv lamp. Keep the existing Windows Hue pairing.
4. Enable Hue's **Follow Master**. In MUSIC, **Color Relationship** defaults to **Coordinated Colors**. Start Music and play audio through your normal output device.
5. Scroll the Music tab if the new controls are below the visible area. Existing minimum window dimensions are unchanged.

## Relationships

- **Same Color:** both participating lights receive the same primary RGB, preserving the prior music routing.
- **Coordinated Colors (default):** the corner retains the original primary output. Hue receives a smoothly changing HSV accent, with an immediate brightness boost on the same detected beat and a short decaying envelope.
- **Independent Devices:** audio analysis and meters continue, but the corner retains its pre-Music color and Hue uses its saved independent controls even when Follow Master is checked. Independent settings and the Follow Master setting are not overwritten. To edit Hue independently, turn Follow Master off as usual.

**Color Separation** moves from a 20-degree analogous offset to a 180-degree complementary offset; the default is 60 degrees. Hue changes interpolate over the shortest circular hue path, more gently during quiet sections. No random colors are generated. Hue brightness follows the primary intensity, with a small mid/treble contribution and a beat envelope. White/black output cannot always show a visibly different hue. Music brightness/saturation and Master power/brightness still apply to participating outputs.

Follow Master OFF always preserves Hue's independent state. White-only bulbs skip RGB and follow supported brightness/power. Switching relationship does not alter the saved independent Hue controls. Stopping Music restores the pre-Music Master color and rejects late audio frames. Movie, Gaming, manual colors and existing presets use the original routing outside Music.

## Audio and Bluetooth preservation

The existing MusicEngine still owns the single audio capture and FFT/beat analysis. A new immutable MusicFrame callback exposes its primary RGB, normalized bass/mid/treble, RMS energy, beat flag and timestamp to the application router. The existing audio algorithm and capture loop are otherwise unchanged.

The corner BluetoothWorker, its LotusLamp connection and 4 Hz limiter are exact source matches to v1.5. HueDriver and pairing behavior are unchanged. The Hue actor's connection, write loop, 250 ms write interval and coalescing remain unchanged. The only HueService change lets Independent Devices select the already-saved manual state. The LEDBLE driver is byte-identical.

Coordinated RGB uses the same latest-state Hue mailbox; no tasks or queues are created per frame. The beat envelope starts immediately and lasts up to 650 ms to survive coalescing; there is no scheduled playback delay or new blocking sleep. Hue brightness and color are separate writes, sharing its existing limit of four commands per second, so physical transmission times will differ. This aims for coordinated visual motion, not sample-accurate synchronization. Disconnects retain the existing bounded recovery behavior and do not gate the other output.

## Windows launch and build

Dependencies and build files are unchanged from v1.5. HueBLE remains pinned to 2.2.3, with bleak-retry-connector 4.7.1. No new packages are needed.

Run `build_windows.bat` to create `dist\Olive RGB.exe`. This source ZIP does not include an executable. If the `py` launcher is unavailable, open PowerShell in the extracted folder:

```powershell
$rgbPython = 'C:\Users\olive\AppData\Local\Programs\Python\Python314\python.exe'
& $rgbPython -m pip install -r requirements.txt
& $rgbPython olive_rgb.py
# Optional executable build:
& $rgbPython -m pip install pyinstaller
& $rgbPython -m PyInstaller --noconfirm --clean 'Olive RGB.spec'
```

## Validation

27 automated tests passed using software mocks, including the real pinned HueBLE API with mocked I/O and the existing LEDBLE regressions. New tests cover shared capture/frame publication, primary preservation, distinct hue relationships, Same Color, Master scaling, Follow Master OFF, independent-state restoration, stop/late frames, disconnected-state routing, immediate beat envelope, quiet transitions, energy/darkness and configuration validation.

The Tk smoke check passed for controls, Hue-only mode startup, settings export/reload, shutdown and reachability of the new settings at 920x680. It uses mocked workers and in-memory settings; it does not write your real settings. Source comparisons confirmed protected driver/worker sections and dependencies/build files unchanged. Python syntax and the output ZIP were checked.

Run after installing requirements:

```powershell
py -B -m unittest discover -p "test_*.py" -v
py -B check_music_gui.py
```

**Physical Bluetooth, real audio capture, visible beat synchronization and the generated Windows executable remain untested here.**

### Hardware checklist

- Connect each device separately, then together. Confirm the usual corner presets still work.
- Play audio with both connected. Confirm distinct coordinated colors and shared energy/beat reactions; try low and high separation.
- Try Same Color, then Independent Devices; confirm manual states return.
- Turn Follow Master OFF and verify Hue remains independent during Music and Master changes.
- Test brightness-only behavior if Hue does not expose color.
- Disconnect either light while Music plays; verify the other continues and the GUI remains responsive.
- Stop Music, then use Movie/Gaming/manual colors; confirm normal routing resumes.
- Restart the app and check Color Relationship, Color Separation and Follow Master settings.
- Exit while connected; confirm the process closes.

## Changed files

- `olive_rgb.py`: optional shared analysis callback, Music controls and scrolling, callback wiring, mode lifecycle and persistence; version 1.5.1-preview.
- `music_coordination.py` (new): immutable audio frame, deterministic HSV accent/envelope and Music-only router.
- `hue_driver.py`: one condition in desired-state selection for Independent Devices. HueDriver and actor Bluetooth operations are unchanged.
- `hue_controls.py`: imports the Music-capable router; no controls or connection changes.
- `test_music_coordination.py` (new): 11 coordination/shared-capture tests.
- `check_music_gui.py` (new): reproducible mock GUI and settings-reload check.
- `COORDINATED_MUSIC.md`, `README.md`, `TESTING.md`: current instructions and results. Older update documents remain historical references.

Settings add `music_relationship` and `music_separation` to the existing settings file. Missing or invalid values fall back to Coordinated Colors and 0.25.

## Rollback

Close the update and extract `Olive RGB v1.5 pre-coordinated rollback.zip` into a separate folder. Launch/build the original v1.5 source. Restore your saved settings.json if desired; the original app otherwise ignores the new music settings. This preserves the supplied baseline but does not imply additional physical validation of that baseline.
