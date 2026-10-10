# Change-aware Studio tests

Use the same Python environment that launches Studio. Install
`requirements-studio-live.txt` (includes Qt/capture dependencies); optional Windows
album integration remains in `requirements-studio-album.txt`. GUI tests need a
desktop or virtual display. Do not substitute mocked/Linux results for Windows
capture or physical-light acceptance.

From `Studio/phase-1.10`:

```powershell
# Windows: the actual launch environment
& '.\.venv-studio-qt\Scripts\python.exe' .\run_studio_tests.py fast
& '.\.venv-studio-qt\Scripts\python.exe' .\run_studio_tests.py integration
& '.\.venv-studio-qt\Scripts\python.exe' .\run_studio_tests.py full
```

On Linux/macOS with the configured environment, use
`python -B run_studio_tests.py fast` (or `integration` / `full`). This runner does
not install dependencies, start a display server, or start audio services.

- **Fast:** mapped modules for the current edit. Shared controller, mode state,
  Inspector, theme/layout and window changes always include cross-component GUI
  regressions, even here. This is an iteration check, not a release gate.
- **Integration:** fast coverage plus tests that transitively import changed
  project modules, including relative/lazy imports and imported test fixtures.
  Use before completing a feature or after interacting subsystems change.
- **Full:** every current `test_*.py` module, including the actual DEMO launcher
  smoke. Required for release candidates, merges into the release branch, and
  packaging. It runs anew even when the worktree is clean.

The mandatory gate command is `python -B run_studio_tests.py full --gate release`
(use `--gate merge` / `--gate packaging` for those operations). Other tiers are
rejected with `--gate`. Any failure, timeout, zero-test module, background
traceback, or actual test skip fails a gate. Do not merge/package after a failed
gate. There is no existing CI or build integration in this repository: the gate
must be invoked before these operations; the runner does not intercept Git or
PyInstaller commands. Hardware acceptance is a separate prerequisite.

## How selection works

The runner unions **staged**, **unstaged**, **deleted/renamed**, and **untracked,
nonignored** Git paths using NUL separators. It does not change Git state.
`--base origin/development/qt-studio` also includes committed differences from
that ref to HEAD. For a feature branch, specify its reviewed base explicitly;
a clean worktree without `--base` has no changes to target. Rename detection is
disabled so old and new paths are both examined.

`--dry-run` prints all changed paths, selected modules with reasons, omitted
modules with reasons, group membership, and full-fallback reasons without
importing application code. Every test in a selected module runs. Verbose module
logs contain individual test IDs and unittest skip reasons; `report.json`
contains exact commands, counts, actual skips, timings and exit codes. A skipped
module is **not executed**, not presumed passing. A clean/docs-only fast run is
reported as no validation, not a successful test run.

No previous passing result or cached dependency graph is used. Unknown sources,
unclassified new tests, deleted/renamed paths, requirements/config/resources,
launch/build files, the original backend, runner changes, invalid Python, or
unavailable Git/base information force the full suite. Ordinary Markdown-only
documentation changes select no tests; `AGENTS.md` is excluded from this rule.
Package initializers are conservatively unmapped and force full validation.
If a new module needs narrow selection, add its direct rule and tests together;
until reviewed, full fallback protects it. Static imports cannot prove all dynamic
coupling: the explicit rules and mandatory shared regressions supplement them.

## Audited groups (overlapping)

| Group | Existing coverage |
|---|---|
| Qt UI/layout/focus | `test_studio_qt`, `test_workspace`, `test_appearance_parity`, `test_live_inspector` |
| Controller/mode switching | `test_studio_adapter`, `test_music_live`, `test_dual_live`, `test_screen_live`, `test_music_interaction`, `test_music_coordination`, `test_corner_shutdown` |
| Music capture/FFT | `test_spectrum`, `test_capture_diagnostics`, `test_audio_reactor`, Music/album/theme/adjustment/preset/interaction tests |
| Screen capture | `test_screen_live` |
| Scene Pads | Qt/state/adapter tests and `test_demo_launch` |
| Hue | `test_hue_api`, `test_hue_integration`, `test_hue_color`, `test_hue_parity`, `test_dual_live` |
| BLE | `test_corner_live`, `test_corner_shutdown`, `test_ledble`, `test_ledble_retry`, `test_ledble_studio` |
| Preferences/persistence | Preferences/workspace/themes/presets/adjustments/appearance/LEDBLE/Hue tests |
| Virtual preview | Album/adjustment/Screen/reactor tests |
| Packaging/launch | `test_demo_launch`, existing LIVE launcher tests in `test_screen_live`, Tk preview tests; packaging changes force full |
| Runner safety | `test_test_selection` |

Actual mouse tests include LIVE Master Bus startup/FFT/preview, focus and scroll
geometry with both Inspector states, live Music combo interaction, and DEMO mode,
Inspector tabs/color wheel and Scene Pad clicks. Their relevant modules are
selected by shared/leaf rules; no new simulation engine is introduced.

## Isolation and speed

Tests use existing `unittest` in separate, sequential processes to preserve
Tk/Qt and DEMO import isolation. The current Python interpreter is reused.
Bytecode is disabled; logs and overridden APPDATA/LOCALAPPDATA/XDG runtime state
go into a system temporary directory outside Git. `--output-dir` may select a
persistent external directory; an in-repository directory is rejected.
No parallel execution or automatic retry can conceal timing failures.
`--timeout` sets a positive per-module limit (default 180 seconds).

Expected savings depend on the edit: a preset-only fast run selects 7 tests,
reactor-only 11, adjustments-only 10, compared with 390 existing regressions
plus the new workflow checks. Shared UI/mode edits deliberately run much more.
Integration can approach full coverage because GUI fixtures import common
windows. Use the recorded timings, not a universal speedup promise; full runs
remain mandatory at the gates above. Changing the runner itself forces full in
all tiers, so this implementation's current worktree correctly selects full.
