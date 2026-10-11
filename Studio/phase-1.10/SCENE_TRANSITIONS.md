# LIVE Scene Pad Transitions — Qt Studio

Implementation branch: `development/qt-studio`.

The eight existing scene pads now use a GUI-owned, interruptible color
interpolator in LIVE mode. Scene Panel offers 0–5 s and Smooth / Linear /
Instant controls, saved in the existing version-1 Qt preferences under
`scenes.transition_seconds` and `scenes.transition_curve`. Missing keys
load defaults (1.2 s, Smooth).

## Routing and safety

- Scene requests stop Music/Screen capture and wait for both capture workers to
  drain before touching manual colors.
- Only connected, Follow Master-enabled, RGB-capable devices animate.
  Disconnected devices stage their final color without initiating a connection.
  Opted-out and unsupported Hue channels remain unchanged.
- Every sample calls the existing `set_rgb` adapter; BLE and Hue sessions keep
  their normal throttling and latest-value behavior. Actual output cadence
  depends on the device/session; a 100 ms UI tick does not imply 100 ms BLE writes.
- A new scene begins from the most recently **commanded** RGB values. Hardware
  may lag the command due to coalescing/throttling; no physical-readback claim.
- Selecting a different mode, manual color editing, or closing cancels the fade.
  Follow Master disabled during a fade prevents further updates to that channel.
- There is no new native LotusLamp animation protocol or per-LED addressing.

## Windows verification

From `Studio/phase-1.10` with project dependencies installed:

```powershell
python -m unittest test_scene_live -v
python run_studio_tests.py --help
```

Use the documented runner arguments from `--help` to run the full suite.
Automated fixtures simulate BLE/Hue/capture and are **not** hardware proof.

In `Launch Qt Preview.bat` choose LIVE, connect Corner and optionally Hue,
then check:

1. Set 2.0 s Smooth, click Ocean Breeze and watch a gradual change.
2. Click another pad midway; verify no reset to the original color.
3. Switch to Music/Screen while fading; verify the scene stops commanding color.
4. Turn Hue Follow Master off; verify Hue stays independent.
5. Disconnect one device and recall a scene; no automatic reconnection.
6. Set 0 s / Instant; verify immediate static recall.
7. Close/relaunch; verify transition settings persist without auto-recall.
8. Repeat with disconnected devices; previews should stage final colors.

Actual Windows software and physical LotusLamp/Hue acceptance remain pending.
