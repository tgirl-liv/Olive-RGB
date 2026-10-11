# Audio Reactor image regression

Baseline: `development/qt-studio`, `bffe1af6c6518b09d104329339acd929dc4e0417`. The preceding uncommitted Corner test correction is preserved.

## Failure and root cause

`test_audio_reactor.ReactorTests.test_live_uses_exact_same_painter_for_identical_display_data`, old line 101, asserted inequality between `demo_image.copy(0,150,720,45)` and the corresponding LIVE crop. Both images were equal at device-pixel ratio (DPR) 1. The committed baseline failed all three repeated attempts. The current production renderer independently reproduced the same equality.

Baseline crop evidence (RGBA/RGB image bytes captured outside the repository):

| Logical/image crop at DPR 1 | Expected by old assertion | Actual |
|---|---|---|
| y=150–195, full width | Different | Equal; both SHA-256 `9c2e35a2ce772139a3e8d1fb9ded60718609380de284d1c7c0e17558d7c01cf3` |
| y=100–145, full width | Not tested | Different; DEMO `f203d52f584e478553ea3b52c92408ed6c9a6474e26e23b349fd250231c133e2`, LIVE `27b4347f661c20500801600c58c41600517a6210e693aa9ec5ea5480d7dede21` |
| y=206–240, meters | Equal | Equal |
| y=40–120, curve region | Different | Different |

Inspection of `studio_qt/widgets/audio_reactor.py::paintEvent()` explains the result. For height 240, the bar baseline is `240−42=198`. DEMO extent is `198−20=178`; LIVE deliberately reserves floating-curve space and uses 70% of this, 124.6. At the test's 50% level, bar tops are **109 (DEMO)** and **135.7 (LIVE)**. The entire 150–195 crop lies in their common lower fill, whose gradients and rounded bottoms are identical. Peak lines lie above it (87.2 and 119.24). Equality there is correct rendering, not missing bar-height differentiation.

A second defect is coordinate interpretation. `QWidget.grab()` returns physical pixels at the screen DPR, whereas `QImage.copy()` takes physical pixel coordinates. At Qt scale 1.25, a 720×240 widget produces a 900×300 image. The old y=150–195 crop then samples logical y=120–156: it intersects the differing bar tops, so the old inequality happens to hold. The supposed meter crop samples logical y≈165–192 instead of the meters. The same crop changed from equal at 1× to unequal at 1.25× on Linux. This establishes DPI-dependent test expectations; it does not constitute a native Windows test.

The failing fixture starts no capture or animation timer. `enable_live()` calls `reset_live()`, which stops the timer, and the test installs fixed levels, peaks and meters. Synchronous rendering and static geometry explain the failure without timing, asynchronous processing, or test-order assumptions. Failure on baseline alone was not used as proof: the painter geometry, crop data and scaling experiment establish the incorrect expectations. No genuine production rendering defect was found.

## Fix and coverage

Executable changes are confined to `test_audio_reactor.py`:

- Render synchronously into initialized `QImage`s with explicit DPRs **1, 1.25 and 2**, and map logical regions to physical pixels.
- Retain exact pixel equality for the shared meters and overlapping gradient fill. Whole-widget pixel equality is **not** required: LIVE bar extent and curve position intentionally differ from DEMO.
- Compare the region containing the actual bar-top difference, and explicitly prove that a point between the two tops is inside the DEMO bar but outside the LIVE bar, relative to empty renders.
- Isolate curve comparison with bars and peaks absent; validate peak-marker placement separately against renders with no peaks.
- Retain the 72-gradient assertion for both modes.

There are no golden image comparisons across operating systems, tolerances, skips, sleeps, production-code edits or new dependencies. Pixel equality remains exact where the specification requires shared output within the same rendering environment. Production capture, FFT, visualization math, DEMO behavior, BLE/Hue transport and the Corner correction are unchanged.

## Windows independent verification

After applying the reviewed changes, run from `Studio\phase-1.10` using the Python environment used for the previous regression:

```powershell
1..30 | ForEach-Object {
    python -B -m unittest test_audio_reactor.ReactorTests.test_live_uses_exact_same_painter_for_identical_display_data -v
    if ($LASTEXITCODE -ne 0) { throw "Audio image test failed on iteration $_" }
}
python -B -m unittest test_audio_reactor -v
if ($LASTEXITCODE -ne 0) { throw "Audio Reactor tests failed" }
python -B -m unittest test_spectrum -v
if ($LASTEXITCODE -ne 0) { throw "Spectrum tests failed" }
python -B -m unittest test_corner_live -v
if ($LASTEXITCODE -ne 0) { throw "Corner tests failed" }
python -B -m unittest test_demo_launch -v
if ($LASTEXITCODE -ne 0) { throw "DEMO smoke failed" }
python -B run_studio_tests.py full --gate release
if ($LASTEXITCODE -ne 0) { throw "Full regression failed" }
```

Repeat the image command at your usual Windows display scales (for example 100%, 125%, 200%) if available. Explicit image DPR coverage already runs inside each invocation. Native Windows font/backend behavior still requires Windows execution; no Windows or physical-device validation is claimed here.

## Final validation

- Before: the unchanged committed image test failed 3/3 isolated baseline executions at DPR 1. The old lower-bar images were exactly equal, contrary to its inequality assertion. A native 1.25× run incorrectly passed by sampling a different logical region.
- After: the repaired case passed 30/30 isolated executions with fresh widget fixtures. Each execution checks explicit DPR 1, 1.25, and 2. It also passed separate processes using native Qt scaling 1.25 and the offscreen platform.
- Related: all 11 Audio Reactor tests and all 15 spectrum tests passed.
- Preserved Corner fix: the rate/coalescing case passed another 20/20 executions; all 31 Corner tests passed in the final suite. The earlier 50-run Corner validation remains intact.
- Full release gate: **431 tests passed across 31 modules, zero failures and zero skips**, 220.502 seconds summed module execution time. This includes the successful DEMO launch smoke test. No runtime warnings or traceback output were found in the module logs (matching test names are not warnings).
- Full result and individual logs: `/workspace/olive-rgb-reactor-regression-release/report.json` and adjacent module logs, outside Git.
- No application, capture, rendering, lighting, Bluetooth, or dependency files were changed. The pending Corner test/report changes were preserved. No commit or push was performed.

These results establish Linux Qt regression behavior, including explicit image scaling and both Xvfb/xcb and offscreen rendering. Windows native rendering, Windows capture, and physical light behavior remain unverified; run the PowerShell commands above before claiming Windows acceptance.
