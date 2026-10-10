"""Conservative change selection over the existing unittest modules (stdlib only)."""
import argparse
import ast
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

STAGE = Path(__file__).resolve().parent
PREFIX = 'Studio/phase-1.10/'
GROUPS = {
    'Qt UI/layout/focus': ('test_studio_qt', 'test_workspace', 'test_appearance_parity', 'test_live_inspector'),
    'Controller/modes': ('test_studio_adapter', 'test_music_live', 'test_dual_live', 'test_screen_live', 'test_music_interaction', 'test_music_coordination', 'test_corner_shutdown'),
    'Music/FFT': ('test_spectrum', 'test_capture_diagnostics', 'test_audio_reactor', 'test_music_live', 'test_album_lighting', 'test_music_adjustments', 'test_music_presets', 'test_music_themes', 'test_music_interaction'),
    'Screen': ('test_screen_live',),
    'Scene Pads': ('test_scene_live', 'test_studio_qt', 'test_studio_adapter', 'test_studio_preview', 'test_demo_launch'),
    'Hue': ('test_hue_api', 'test_hue_integration', 'test_hue_color', 'test_hue_parity', 'test_dual_live'),
    'BLE': ('test_corner_live', 'test_corner_shutdown', 'test_ledble', 'test_ledble_retry', 'test_ledble_studio'),
    'Preferences/persistence': ('test_preferences', 'test_workspace', 'test_music_themes', 'test_music_presets', 'test_music_adjustments', 'test_appearance_parity', 'test_ledble_studio', 'test_hue_parity'),
    'Virtual preview': ('test_album_lighting', 'test_music_adjustments', 'test_screen_live', 'test_audio_reactor'),
    'Packaging/launch': ('test_demo_launch', 'test_screen_live', 'test_studio_preview'),
    'Selection runner': ('test_test_selection',),
}
SHARED = set(GROUPS['Qt UI/layout/focus'] + GROUPS['Controller/modes'] +
             ('test_live_inspector', 'test_preferences', 'test_corner_live', 'test_demo_launch', 'test_scene_live'))
SHARED_FILES = {
    'studio_qt/app.py', 'studio_qt/controller.py', 'studio_qt/backend_adapter.py',
    'studio_qt/workspace.py', 'studio_ui/state.py', 'studio_qt/theme.py',
    'studio_qt/widgets/common.py', 'studio_qt/widgets/controls.py',
    'studio_qt/widgets/inspector.py', 'studio_qt/widgets/live_inspector.py',
    'studio_qt/live_window.py', 'studio_qt/dual_window.py',
    'studio_qt/music_window.py', 'studio_qt/screen_window.py',
}
RULES = {}


def rule(paths, tests):
    for path in paths.split():
        RULES[path] = tuple(tests.split())


rule('studio_qt/appearance.py studio_qt/widgets/appearance_settings.py', 'test_appearance_parity test_workspace')
rule('studio_qt/widgets/icons.py', 'test_studio_qt')
rule('studio_qt/widgets/scene_pad.py', 'test_studio_qt test_studio_adapter test_studio_preview test_demo_launch test_scene_live')
rule('studio_qt/widgets/color_wheel.py', 'test_studio_qt test_live_inspector test_demo_launch')
rule('studio_qt/widgets/audio_reactor.py', 'test_audio_reactor')
rule('studio_qt/spectrum_data.py studio_qt/spectrum_engine.py', 'test_spectrum test_capture_diagnostics test_audio_reactor test_screen_live')
rule('studio_qt/audio_capture.py studio_qt/music_engine.py', 'test_music_live test_spectrum test_capture_diagnostics test_screen_live')
rule('studio_qt/native_capture.py studio_qt/capture_diagnostics.py', 'test_capture_diagnostics test_spectrum test_screen_live')
rule('studio_qt/music_runtime.py', 'test_music_live test_music_interaction test_spectrum test_album_lighting test_music_themes test_screen_live')
rule('studio_qt/music_adapter.py music_coordination.py', 'test_music_coordination test_music_live test_dual_live test_live_inspector test_music_adjustments test_screen_live')
rule('studio_qt/music_adjustments.py', 'test_music_adjustments')
rule('studio_qt/music_presets.py', 'test_music_presets')
rule('studio_qt/music_themes.py studio_qt/widgets/music_theme_editor.py', 'test_music_themes test_music_interaction')
rule('album_colors.py studio_qt/album_artwork.py studio_qt/widgets/album_lighting.py', 'test_album_lighting test_music_interaction test_music_adjustments')
rule('studio_qt/widgets/light_preview.py', 'test_album_lighting test_music_adjustments test_screen_live test_scene_live')
rule('studio_qt/screen_engine.py studio_qt/screen_runtime.py studio_qt/screen_adapter.py', 'test_screen_live test_hue_parity')
rule('hue_driver.py', 'test_hue_api test_hue_integration test_hue_color test_hue_parity test_dual_live')
rule('hue_controls.py studio_qt/hue_session.py studio_qt/hue_identity.py studio_qt/widgets/hue_preferences.py', 'test_hue_parity test_dual_live test_hue_color')
rule('studio_qt/dual_adapter.py', 'test_dual_live test_live_inspector test_music_live test_screen_live test_hue_parity')
rule('ledble_driver.py', 'test_ledble test_ledble_retry test_ledble_studio test_corner_live test_screen_live')
rule('studio_qt/corner_adapter.py studio_qt/corner_session.py studio_qt/corner_worker.py', 'test_corner_live test_corner_shutdown test_ledble_studio test_live_inspector test_music_live test_screen_live test_scene_live')
rule('studio_qt/device_families.py', 'test_ledble_studio test_ledble test_corner_live test_screen_live')
rule('studio_qt/preferences.py', 'test_preferences test_music_adjustments test_music_presets test_music_themes test_album_lighting test_ledble_studio test_hue_parity test_screen_live test_appearance_parity test_scene_live')
rule('studio_ui/app.py studio_ui/widgets.py studio_ui/theme.py studio_preview.py', 'test_studio_preview')
for path in SHARED_FILES:
    RULES[path] = tuple(sorted(SHARED))


def git_paths(repo, base=None):
    """HEAD worktree diff includes staged/unstaged/deleted files; -z is path-safe."""
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE)
    paths = set(git('diff', '--name-only', '-z', '--no-renames', '--').decode('utf-8', 'surrogateescape').split('\0'))
    paths.update(git('diff', '--cached', '--name-only', '-z', '--no-renames', 'HEAD', '--').decode('utf-8', 'surrogateescape').split('\0'))
    paths.update(git('ls-files', '--others', '--exclude-standard', '-z').decode('utf-8', 'surrogateescape').split('\0'))
    if base:
        commit = git('rev-parse', '--verify', '--end-of-options', base + '^{commit}').decode().strip()
        paths.update(git('diff', '--name-only', '-z', '--no-renames', commit, 'HEAD', '--').decode('utf-8', 'surrogateescape').split('\0'))
    return sorted(paths - {''})


def dependency_graph(stage):
    """Read imports, including relative and lazy imports, without importing apps."""
    sources = list(stage.glob('*.py'))
    for package in ('studio_qt', 'studio_ui'):
        sources.extend(p for p in (stage / package).rglob('*.py') if '__pycache__' not in p.parts)
    files = {'.'.join(p.relative_to(stage).with_suffix('').parts).removesuffix('.__init__'): p for p in sources}
    graph = {}
    for module, path in files.items():
        package = module if path.name == '__init__.py' else module.rpartition('.')[0]
        edges = set()
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if isinstance(node, ast.Import):
                edges.update(a.name for a in node.names if a.name in files)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = package.split('.') if package else []
                    base = '.'.join(parts[:len(parts) - node.level + 1])
                    base = '.'.join(filter(None, (base, node.module)))
                else:
                    base = node.module or ''
                edges.update(candidate for candidate in [base, *(base + '.' + a.name for a in node.names)] if candidate in files)
        graph[module] = edges
    return graph


def dependents(graph, seeds):
    reached = set(seeds)
    while True:
        extra = {module for module, edges in graph.items() if edges & reached} - reached
        if not extra:
            return reached
        reached.update(extra)


def select(stage, paths, tier, change_error=None):
    tests = {p.stem for p in stage.glob('test_*.py')}
    reasons = {}
    fallback = []
    known = set().union(*(set(v) for v in GROUPS.values())) | {'test_live_inspector'}
    if tests - known:
        fallback.append('unclassified test modules: ' + ', '.join(sorted(tests - known)))
    if change_error:
        fallback.append('Git changes unavailable: ' + change_error)
    if tier == 'full':
        fallback.append('full tier requested (release/merge/packaging gate)')
    try:
        graph = dependency_graph(stage)
    except (SyntaxError, UnicodeError, OSError) as error:
        graph = {}
        fallback.append('dependency scan failed: ' + type(error).__name__)
    seeds = set()
    for path in paths:
        if path.endswith('.md') and Path(path).name != 'AGENTS.md':
            continue
        if not path.startswith(PREFIX):
            fallback.append('unknown or repository-wide impact: ' + path)
            continue
        local = path[len(PREFIX):]
        if not (stage / local).is_file():
            fallback.append('deleted/renamed path: ' + path)
        elif local in ('run_studio_tests.py', 'test_test_selection.py'):
            fallback.append('test-selection workflow changed: ' + path)
        elif local.startswith('test_') and local.endswith('.py') and Path(local).stem in tests:
            module = Path(local).stem
            seeds.add(module)
            reasons.setdefault(module, []).append('test changed: ' + path)
            # Fixtures are imported by other suites; never skip their consumers.
            for dependent in dependents(graph, {module}) & tests:
                reasons.setdefault(dependent, []).append('changed test/fixture dependency: ' + module)
        elif local in RULES:
            seeds.add(local[:-3].replace('/', '.'))
            for module in RULES[local]:
                if module not in tests:
                    fallback.append('mapped test missing: ' + module)
                else:
                    reasons.setdefault(module, []).append(('mandatory shared regression: ' if local in SHARED_FILES else 'direct coverage: ') + path)
        else:
            fallback.append('unmapped source/config/resource/launch/build path: ' + path)
    if tier == 'integration':
        for module in dependents(graph, seeds) & tests:
            reasons.setdefault(module, []).append('transitive import dependency on changed code')
    if fallback:
        reasons = {module: ['full fallback: ' + '; '.join(fallback)] for module in tests}
    return {'tier': tier, 'changed': paths, 'fallback': fallback,
            'selected': {k: reasons[k] for k in sorted(reasons)},
            'skipped': {k: 'no mapped impact in this tier; not executed, not assumed passing' for k in sorted(tests - reasons.keys())},
            'groups': {k: sorted(set(v) & reasons.keys()) for k, v in GROUPS.items() if set(v) & reasons.keys()}}


def execute(stage, plan, output_dir, timeout=180):
    """Separate processes preserve Tk/Qt and DEMO import-isolation assertions."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(stage))
    for key, directory in (('APPDATA', 'appdata'), ('LOCALAPPDATA', 'local'),
                           ('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache'), ('XDG_DATA_HOME', 'data')):
        env[key] = str(output_dir / directory)
    results = {}
    for module in plan['selected']:
        start = time.monotonic()
        command = [sys.executable, '-X', 'utf8', '-B', '-m', 'unittest', module, '-v']
        try:
            process = subprocess.run(command, cwd=stage, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, timeout=timeout, encoding='utf-8', errors='replace')
            text, code = process.stdout, process.returncode
        except subprocess.TimeoutExpired as error:
            text = (error.stdout or b'').decode('utf-8', 'replace') if isinstance(error.stdout, bytes) else (error.stdout or '')
            text += '\nFAIL: module timeout; subprocess stopped\n'
            code = 1
        counts = re.findall(r'^Ran (\d+) tests?', text, re.M)
        count = int(counts[-1]) if counts else 0
        if not count or re.search(r'^Exception in thread|^Traceback \(most recent call last\):', text, re.M):
            code = 1
        (output_dir / (module + '.log')).write_text(text, encoding='utf-8')
        skips = [line for line in text.splitlines() if re.search(r'\.\.\. skipped ', line)]
        if count and len(skips) == count:
            code = 1
        results[module] = {'exit_code': code, 'tests_run': count, 'actual_skips': skips, 'seconds': round(time.monotonic() - start, 3),
                           'command': command, 'log': str(output_dir / (module + '.log'))}
        print(f'{module}: {"PASS" if code == 0 else "FAIL"} ({count} tests, {results[module]["seconds"]:.2f}s)', flush=True)
        if code:
            print(text, flush=True)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tier', choices=('fast', 'integration', 'full'))
    parser.add_argument('--base', help='include committed differences from this Git commit/ref to HEAD')
    parser.add_argument('--dry-run', action='store_true', help='show the plan without executing tests')
    parser.add_argument('--output-dir', type=Path, help='logs/report directory outside the repository (default: system temp)')
    parser.add_argument('--timeout', type=float, default=180, help='per-module timeout seconds')
    parser.add_argument('--gate', choices=('release', 'merge', 'packaging'), help='requires the full tier for this gate')
    args = parser.parse_args(argv)
    if args.gate and args.tier != 'full':
        parser.error('release, merge, and packaging gates require full')
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be positive')
    repo = STAGE.parents[1]
    error = None
    try:
        paths = git_paths(repo, args.base)
    except (OSError, subprocess.CalledProcessError):
        paths, error = [], 'cannot read HEAD/worktree/base (no previous test result is reused)'
    plan = select(STAGE, paths, args.tier, error)
    print(json.dumps(plan, indent=2), flush=True)
    if args.dry_run:
        print('Dry run only: no tests executed. Selected entries include every test in that module.')
        return 0
    if not plan['selected']:
        print('No tests selected; this is not a validation pass. Use full for any release gate.')
        return 1 if args.tier == 'full' else 0
    base_output = args.output_dir.resolve() if args.output_dir else Path(tempfile.gettempdir()).resolve()
    if base_output == repo or repo in base_output.parents:
        parser.error('--output-dir and the system temporary directory must be outside the Git repository')
    output = base_output if args.output_dir else Path(tempfile.mkdtemp(prefix='olive-studio-tests-', dir=base_output))
    if output == repo or repo in output.parents:
        parser.error('--output-dir must be outside the Git repository')
    output.mkdir(parents=True, exist_ok=True)
    results = execute(STAGE, plan, output, args.timeout)
    report = {**plan, 'results': results, 'gate': args.gate,
              'passed': all(r['exit_code'] == 0 for r in results.values()) and
                        (not args.gate or not any(r['actual_skips'] for r in results.values()))}
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Report: ' + str(output / 'report.json'), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
