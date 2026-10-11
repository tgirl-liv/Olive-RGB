# Scene transition preview correction

Baseline: `development/qt-studio`, `3c52cf94e577a2d9e6b6a184c66395f486d43861`. Corner rate-limiter and Audio Reactor test corrections remain unchanged.

## Confirmed behavior and root cause

Saved ScenePad artwork is a static thumbnail (`widgets/scene_pad.py::artwork`); it is intentionally not a live-output indicator. The compact `VirtualLightPreview` in each `app.py::ScenePanel` represents the Corner/BLE channel's intended output, including master/device power and brightness scaling. It is not confirmation of a physical light's state and is not a Hue preview.

Mouse activation calls `StudioController.select_scene`, dispatches to `ScreenLiveWindow.request_scene`, stops/drains capture through the centralized Manual mode request, and calls `finish_scene`. `CornerLightingAdapter.stage_scene_transition` stages disconnected preferences immediately and returns only connected, participating, RGB-capable routes. Previously, `finish_scene` constructed `SceneTransition` only for those connected routes. Consequently a disconnected LIVE scene had no intermediate samples, and the preview showed final preferences immediately. DEMO already had interpolation via `StudioController.advance` and `display_colors`.

The LIVE panel also read stored `state.channels['Corner'].color`, whereas transition output belongs in `display_colors`. Connected adapter writes update channel colors, so connected transitions were already capable of refreshing the old preview. The evidence establishes a missing disconnected intended-output transition and inappropriate state binding, not a universally broken widget or a verified hardware fault. The panel already subscribes to `changed` and `output_changed`; no new signal is needed.

Two new regression cases were run against a separate, unmodified archive of the committed baseline outside Git. Linear/Smooth zero-time checks both failed: actual scaled preview `(51, 31, 19)` versus expected `(0, 0, 0)` for black → Sunset Chill at 20% combined brightness. Rapid interrupted recalls also failed because the preview jumped from `#FF995D` to `#2365DD` instead of remaining at the current interpolated color. Baseline log: `/tmp/scene-preview-baseline.log` (two cases, four assertion/subtest failures, zero errors).

## Focused repair

- `studio_qt/screen_window.py`: capture the current interpolated source before cancellation; construct one existing `SceneTransition` covering eligible intended output, including disconnected devices. Retain the adapter-returned connected route set separately. Each existing 100 ms Qt timer tick samples the same engine once, routes only connected-approved colors through unchanged adapters, and publishes the sampled `display_colors` using `output_changed`.
- `studio_qt/app.py`: bind the LIVE preview to sampled display colors while a scene is active. Label it intended output/hardware unverified. DEMO retains its existing interpolation and gains the same explicit intended-output wording.
- `test_scene_live.py`: add five mouse-driven cases for disconnected Linear/Smooth samples and scaling, interruption/rapid recall, connected adapter routing, close cleanup, and DEMO interpolation. Update the former disconnected-no-fade assertion to verify a preview fade exists with zero hardware routes and unchanged opted-out state. Existing instant-recall, capability, persistence, ownership, scroll/focus, and transition tests remain.

There is no second easing algorithm, recorder, thread, new dependency, increased timer frequency, or additional BLE/Hue transport route. Disconnected preferences still stage immediately for persistence; only the read-only display interpolates. Static thumbnails stay unchanged. The current fade is replaced on recall, so the timer reads only the latest engine; it retains no old-fade callback. Closing cancels the fade and stops its QObject-owned timer. Existing transport rate limits still apply and the UI describes intended color rather than acknowledged physical output.

## Windows independent verification

From the repository root, use the same Python environment as Studio:

```powershell
Set-Location .\Studio\phase-1.10
$StudioPython = (Resolve-Path ".\.venv-studio-qt\Scripts\python.exe").Path
& $StudioPython -B -m unittest test_scene_live -v
if ($LASTEXITCODE -ne 0) { throw "Scene regression failed" }
& $StudioPython -B -m unittest test_corner_live test_corner_shutdown test_ledble_studio -v
if ($LASTEXITCODE -ne 0) { throw "BLE regression failed" }
& $StudioPython -B -m unittest test_studio_qt test_workspace test_audio_reactor -v
if ($LASTEXITCODE -ne 0) { throw "Qt regression failed" }
& $StudioPython -B -m unittest test_demo_launch -v
if ($LASTEXITCODE -ne 0) { throw "DEMO smoke failed" }
& $StudioPython -B run_studio_tests.py full --gate release
if ($LASTEXITCODE -ne 0) { throw "Full release gate failed" }
& ".\Launch Qt Preview.bat"
```

Without connecting lights, choose LIVE, set Scene transition duration to 3 seconds and Linear, and click two differently colored Scene Pads. Watch the compact Scene preview begin at the existing color, pass through intermediate colors, and settle at the destination. Repeat with Smooth, interrupt midway, and click several pads rapidly: the latest scene should win without a jump to an old destination. Check Instant/0 seconds, Master/device brightness and power, Follow Master OFF, Inspector visible/hidden, dashboard scroll position, Scene → Music/Screen → Scene, and closing during a fade. In DEMO repeat with Motion enabled; existing DEMO interpolation is preserved. Thumbnail artwork should remain static apart from the existing selection/focus decoration.

Native Windows UI and physical BLE/Hue output remain pending. Hardware acceptance must separately verify actual colors, throttling, disconnect during a fade, and selected Hue capabilities. Automated tests use simulated transport only.

## Completed validation

Linux Qt GUI validation, using simulated capture/devices:

- Before: two new regression cases failed on the unmodified committed baseline (four assertion/subtest failures, zero errors); no original archive or older checkout was modified.
- Direct Scene suite: **18 passed**, including five new GUI cases and the existing transition/ownership/capability/persistence tests.
- Change-aware **fast**: **248 passed**, 15 modules, zero skips.
- Change-aware **integration**: **363 passed**, 23 modules, zero skips.
- **Full release gate: 436 passed across 31 modules, zero failures and zero skips.** Includes all 31 Corner cases, six Corner shutdown cases, LEDBLE/LEDBLE Studio, Hue, all Scene/Qt UI tests, the unchanged Audio Reactor test fix, and successful DEMO launcher smoke.
- No unexpected runtime warning or traceback output was found in the full module logs. `git diff --check` passed.
- Reports and module logs are outside Git: `/workspace/olive-scene-preview-fast/report.json`, `/workspace/olive-scene-preview-integration/report.json`, `/workspace/olive-scene-preview-release/report.json`.

Changed files are `studio_qt/app.py`, `studio_qt/screen_window.py`, `test_scene_live.py`, and this report. No capture/math, transport, dependency, thumbnail, or previous test-fix files changed. No commit or push was performed. Windows and physical hardware acceptance remain pending.
