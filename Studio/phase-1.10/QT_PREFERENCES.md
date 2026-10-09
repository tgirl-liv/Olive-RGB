# Qt Studio preferences (Phase 1.12)

The Studio launcher saves lighting and music configuration to
`%LOCALAPPDATA%/OliveRGBStudio/preferences-v1.json` on Windows, or
`~/.local/share/OliveRGBStudio/preferences-v1.json` when LOCALAPPDATA is absent.
This is separate from Tkinter's `OliveRGB/settings.json` and the existing
`workspace-v1.json` layout file. Qt never imports or migrates Tkinter settings.

Schema version 1 contains separate `demo` and `live` objects. Each stores:

- `master`: power and brightness (0–1).
- `devices`: Corner and Hue power, brightness, six-digit HEX color, and Follow Master.
- `music`: production profile and palette names, sensitivity, smoothing,
  relationship, separation (0–1), and Corner/Hue participation.

LIVE sensitivity is 0.25–3 and smoothing is 0.25–1.4; DEMO tuning is 0–1.
These are configuration values, not evidence of device state. Hue retains its
existing capability checks and power/brightness readback on explicit connection.

Loading validates types, ranges, finite numbers, colors and available choices.
Missing v1 fields use defaults. Corrupt files fall back to defaults with a visible
notice and can be replaced by a subsequent valid save. Unknown schema versions
fall back safely but are preserved without saving over them. The store refuses
the original Tkinter settings path. Saving flushes and fsyncs a temporary file in
the same directory, then atomically replaces the preferences file; a failed save
preserves the previous file and shows a notice.

Changes save after 200 ms of inactivity, and closing flushes the latest values.
Preferences do not contain connections, capture state, playing state, running
modes, or transient device capabilities. Every launcher start uses Manual mode
with audio stopped and devices disconnected. Connection and Start Music remain
explicit actions. Screen and scene simulation remain DEMO-only; no ScreenEngine
integration has been added. LIVE separation uses the existing music router input.

Window constructors accept an optional `preferences_path`; `None` retains the
existing temporary preview/test behavior without disk I/O. The actual launcher
passes the Qt preferences path. Workspace layout remains on its existing schema;
preview motion and transition controls are temporary.

Simultaneous application instances are not coordinated: atomic writes prevent
partial files, but the last writer wins. Windows Bluetooth hardware and real
Windows loopback capture require separate hardware validation.
