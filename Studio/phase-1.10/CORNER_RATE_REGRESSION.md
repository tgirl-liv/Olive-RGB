# Corner color-rate regression investigation

Baseline: `development/qt-studio`, `bffe1af6c6518b09d104329339acd929dc4e0417`.

## Confirmed findings

The original test failed in 3/30 isolated Linux runs, before editing any code. A further instrumented run of 20 isolated cases plus three groups of neighboring tests (35 cases total) reproduced three failures. All reproduced failures were the `.245` assertion on mock `FakeLamp.set_rgb()` entry timestamps. One failure had **253.546 ms between command admissions**, but **233.270 ms between mock write entries**. Another had **254.658 ms admissions versus 244.436 ms entries**.

`CornerSession.color()` maintains one latest RGB snapshot, tagged with the connection generation. Its actor calls the original `BluetoothWorker.set_rgb()` without `force`, waits for the submitted operation, and clears the snapshot only if it has not been replaced. Disconnect/close invalidate the generation and pending snapshot; teardown cancels/drains the actual asynchronous write before disconnecting.

`BluetoothWorker.set_rgb()` checks the monotonic clock against `last_send_time`, rejects elapsed time below `LIGHT_UPDATE_INTERVAL = 0.25`, then records the admission timestamp and submits `_set_rgb()` asynchronously. `_set_rgb()` serializes access with the existing RGB lock. The test measured a later boundary: entry into the fake transport. If the first coroutine is scheduled later than the second, its observed start gap can be smaller than the correct admission gap. Algebraically, start gap = admission gap + second scheduling delay − first scheduling delay.

This establishes a fragile assertion against the wrong timing boundary; it does not establish a production limiter defect or a physical BLE failure. Isolated reproduction means test-order interference is not needed to trigger it. The supplied Windows summary identifies the same test but does not include its assertion traceback; native Windows reproduction is unavailable in this Linux cloud environment.

## Focused repair

Only `test_corner_live.py` changes executable code:

- Observe admitted RGB commands through the existing session submission wrapper, recording the original worker's `last_send_time` and `last_rgb` without changing scheduling or production code.
- Assert the exact **250 ms** admission minimum, replacing the old 245 ms transport-entry approximation; no tolerance or rate-limit relaxation.
- Retain bounded write count and one-in-flight assertions, and verify every admission corresponds to delivered RGB.
- Require the final red write to occur **after** the observed blue write, then wait for completed delivery and an empty pending mailbox. An earlier red in the initial burst cannot satisfy this check.
- Add three deterministic virtual-clock tests: reject at 249 ms/accept at 250 ms without changing the rejected timestamp; defer coroutine execution while preserving the admission contract; preserve the small-delta threshold and 1.5-second refresh behavior. These use the original worker methods without a worker thread or hardware, and contain no real sleeps.

The original 150 ms simulated transport delay remains unchanged. There are no changes to `olive_rgb.py`, `corner_worker.py`, `corner_session.py`, adapters, protocols, connection settling, GUI logic, or rate-limit constants. Actual spacing between physical GATT transactions remains unverified; the existing limiter guarantees command admission spacing, not scheduler-independent native write-entry spacing.

## Windows verification (pending)

After applying the reviewed test-only fix, run from `Studio\phase-1.10` using the same Python environment as Studio:

```powershell
python -B -m unittest test_corner_live.WorkerRateLimitTests -v
1..50 | ForEach-Object {
    python -B -m unittest test_corner_live.LiveTests.test_rapid_colors_coalesce_latest_and_limit_rate -v
    if ($LASTEXITCODE -ne 0) { throw "Isolated rate test failed on iteration $_" }
}
python -B -m unittest test_corner_live -v
python -B run_studio_tests.py full --gate release
if ($LASTEXITCODE -ne 0) { throw "Release regression failed" }
```

The full suite now includes the original 428 tests plus three new boundary tests. The runner isolates test modules and stores output outside the repository. To inspect the previous Windows failure, use:

```powershell
Select-String -Path .\regression-clean.txt -Pattern '^FAIL:' -CaseSensitive -Context 0,15
```

All transport calls in these automated tests are simulated. Do not infer physical BLE/Hue validation from passing tests or their diagnostic output.

## Completed validation and remaining limits

Linux cloud validation, with real Qt and simulated devices:

- Revised coalescing test: **50/50 consecutive isolated passes**.
- Three repeated groups of neighboring tests: **15/15 passed** (including disconnect invalidation and GUI responsiveness).
- Full Corner module: **31 passed**, including three new virtual-clock tests and the original worker-preservation/shutdown checks.
- Full release run: **431 executed; 430 passed, one unrelated baseline failure; no skips**. Actual DEMO launcher smoke passed. The gate correctly reports failure rather than claiming a clean full suite. Report: `/workspace/olive-rgb-rate-release/report.json`.
- Remaining failure: `test_audio_reactor.ReactorTests.test_live_uses_exact_same_painter_for_identical_display_data`, line 101, the inequality assertion on the 150–195 px image strip. It also fails in an isolated process with `test_corner_live` loaded from committed `HEAD` source and no working-tree test modifications imported. This is independent of the Corner repair; Audio Reactor code/tests were not modified. Baseline confirmation: `/tmp/olive-rate-baseline-reactor.log`.
- `git diff --check` passed. Only this report and `test_corner_live.py` are changed. No commit or push.

Native Windows reproduction remains unavailable here. The supplied Windows output identifies the failing test but omits the specific assertion traceback. The matching rate-spacing defect is reproduced and explained on Linux; Windows must rerun the corrected test and full suite before claiming Windows validation. Physical transport timing is not verified by these mock-device tests.
