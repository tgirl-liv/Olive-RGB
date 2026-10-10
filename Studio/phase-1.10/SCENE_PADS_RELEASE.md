# Scene Pads release review

## Original versus Studio

| Behavior | Original evidence | Studio before | Studio after |
|---|---|---|---|
| Static recall | `olive_rgb.py` STATIC COLORS list (PINK, PURPLE, CYAN, RED, WARM, WHITE, MGK, OFF); `set_manual_color()` | Original shortcuts already restored; eight illustrated pads were DEMO-only | Original shortcuts retained; all eight Studio pads recall their defined two-device colors in LIVE |
| Stop effects before static output | `set_manual_color()` calls `stop_modes()` before RGB output | LIVE scene handler returned without action; panels disabled | Scene request uses `ScreenLiveWindow.request_mode('Manual')`; polling waits for both workers to drain before adapter output |
| Immediate preview | `set_manual_color()` calls `set_preview(rgb)` | DEMO transition only | Read-only Scene preview uses existing final Corner output scaling; recall updates once ownership is released, without waiting for hardware |
| Device routing | Existing lighting router and Hue Follow setting | No LIVE scene route | Connected devices use normal `set_rgb`; disconnected values are staged without I/O; unsupported Hue RGB is reported |
| Brightness/power | Static recall changes RGB, not saved brightness or power | Existing channel/master settings | Preserved; preview includes existing master/channel scaling and power, Follow Master opt-outs remain independent |
| Selected scene feedback | No named scene library | Default pad appeared selected despite no LIVE recall | Highlight requires successful recall and Manual mode; waiting/error/inactive status is visible |
| Create/edit/rename/delete scenes | No such controls, data model or stored scene library in the original | None | Not added: not a Tkinter parity gap. Custom **Music themes** remain separate and untouched |
| Save/reload scenes | Original `save_settings()` has no scene library/scene identifier | Channel preferences saved; pad selection/favorites ephemeral | Existing atomic Qt preferences now also save built-in selection/favorites; restart stays idle and does not auto-recall |

The eight Studio presets retain their existing colors and artwork in `studio_ui/state.py::SCENES`. Movie Mode is a **static preset**, not a command to start screen capture. Built-ins have no editing/deletion API. There is no custom scene persistence test because no custom scene functionality exists in the reference application; creating a scene editor would exceed this parity sprint.

## Files and safety

- `studio_qt/controller.py`: dispatch scene intent, track successful activation.
- `studio_qt/screen_window.py`: latest scene request, Manual transition, deferred application after capture stops, cancellation on another mode request or closure, visible failures.
- `studio_qt/corner_adapter.py`: validated static recall via existing manual routes; no transport changes.
- `studio_qt/app.py`, `live_window.py`, `widgets/scene_pad.py`, `widgets/light_preview.py`: enable supported LIVE pads, compact read-only preview/status, truthful selection, avoid unnecessary grid rebuilding on every state update.
- `studio_qt/preferences.py`: backward-compatible selection/favorites fields in existing versioned atomic Qt storage, separate from Tkinter.
- `test_scene_live.py`, `test_corner_live.py`: actual mouse regression coverage and updated static adapter contract.
- `run_studio_tests.py`: include scene GUI tests in Scene and shared-component regression groups. Existing pending test-workflow files are preserved.

No capture processing, COM initialization, Hue conversion, BLE/Hue protocols, worker cadence or automatic connection behavior changed. Deferred capture shutdown can postpone recall; the status explicitly says it is waiting, rather than claiming that output has already changed. Adapter failures leave Manual ownership and an error instead of a successful scene highlight; physical writes already sent cannot be rolled back atomically across devices.

## Windows acceptance (pending)

Launch `Studio\phase-1.10\Launch Qt Preview.bat`, select LIVE. No hardware is necessary for software checks:

1. Click every dashboard Scene Pad and repeat clicks. Confirm Manual active, selected outline, matching RGB/HEX preview, no connection attempt.
2. Start Music from MASTER BUS while playing Windows audio; click a scene. Confirm capture stops, reactor decays, static preview appears. Switch back to Music and confirm measured audio returns.
3. Start Screen from MASTER BUS with changing screen content; click a scene. Confirm screen capture stops and static preview appears. Switch back to Screen and confirm measured screen RGB returns.
4. Repeat with Inspector visible/hidden and at different dashboard scroll positions. No vertical jump on recall; Scenes-page pads should behave identically.
5. Change brightness and power before recall. Confirm values remain unchanged, preview scales/turns black accordingly. Disable Follow Master on a channel; its color must remain independent.
6. Favorite a pad, recall it, close/relaunch. Selection/favorites/colors/settings persist, capture remains stopped, and no hardware connects automatically. Highlight is inactive until recall.
7. With hardware later available, connect explicitly and verify Corner/LEDBLE scaled RGB, Hue color, independent opt-outs, unsupported white-only Hue feedback, disconnect/reconnect safety and rapid scene changes.

Automated capture and transport fixtures are simulated. Actual Windows UI/capture acceptance and physical light output remain unverified until the checklist is performed. No known software release blocker may be declared cleared solely from hardware mocks.

## Validation results

- Scene-focused mouse suite: **6 passed**, including a final fresh run using the actual Inspector collapse toolbar button. Covers all eight pads, repeated clicks, dashboard geometry/scroll/focus, Scenes page, disconnected preview, connected simulated routing, unsupported Hue capabilities, Music/Screen transitions, pending-request cancellation, persistence and invalid/partial-failure handling.
- Fast Scene impact selection: **365 tests executed**; exposed the added preview's desktop viewport regression. Corrected by sharing a compact footer row with status, without weakening the original viewport assertion. The affected workspace suite then passed **13/13**; the earlier unavailable-message regression was also repaired and Corner passed **28/28**.
- Fresh integration selection: **372 passed in 25 modules**, no skips. Report: `/workspace/olive-rgb-scenes-integration/report.json`.
- Unfiltered full release gate: **421 passed in 31 modules**, no skips, including **1 actual DEMO launcher smoke test**. Report: `/workspace/olive-rgb-scenes-release/report.json`.
- Pending test-runner infrastructure forces a conservative full fallback through its normal CLI. Development tiers used the runner's `select()`/`execute()` API with the Scene scope recorded in the reports; the final gate included the entire working tree and the runner's own 24 tests. Scene tests are now mandatory for shared components and directly mapped for scene pads, preview, preferences and the Corner adapter; mapping assertions were added to `test_test_selection.py`.
- `git diff --check` passed. No generated preferences, theme libraries, bytecode or environment files were added to the repository. Existing pending test-workflow work remains present. No commit or push performed.

There are no known remaining automated Scene release blockers. Windows software acceptance and physical Corner/LEDBLE/Hue output verification remain pending. The automated capture and hardware boundaries are simulated; the Qt mouse interactions and DEMO launcher are real.
