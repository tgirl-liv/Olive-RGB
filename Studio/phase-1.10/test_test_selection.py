"""Selection safety, real Git change detection, and subprocess failure propagation."""
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import run_studio_tests as runner


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.stage = Path(self.directory.name)/'Studio'/'phase-1.10'
        self.stage.mkdir(parents=True)
        self.tests = set().union(*(set(v) for v in runner.GROUPS.values()))
        for name in self.tests:
            self.write(name+'.py', '')
    def write(self, path, text=''):
        file = self.stage/path;file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding='utf-8');return file
    def plan(self, path, tier='fast'):
        return runner.select(self.stage, [runner.PREFIX+path], tier)
    def test_isolated_preset_fast_selection(self):
        self.write('studio_qt/music_presets.py')
        plan = self.plan('studio_qt/music_presets.py')
        self.assertEqual(set(plan['selected']), {'test_music_presets'})
        self.assertFalse(plan['fallback']);self.assertIn('test_hue_api', plan['skipped'])
    def test_integration_follows_relative_lazy_and_fixture_imports(self):
        self.write('studio_qt/music_presets.py')
        self.write('studio_qt/music_runtime.py', 'def create():\n from .music_presets import MGK_PALETTES\n')
        self.write('test_music_live.py', 'from studio_qt.music_runtime import create\n')
        self.write('test_album_lighting.py', 'import test_music_live as fixtures\n')
        self.assertNotIn('test_album_lighting', self.plan('studio_qt/music_presets.py')['selected'])
        plan = self.plan('studio_qt/music_presets.py', 'integration')
        self.assertTrue({'test_music_presets','test_music_live','test_album_lighting'} <= plan['selected'].keys())
    def test_shared_ui_controller_state_inspector_layout_always_cross_component(self):
        for path in runner.SHARED_FILES:
            with self.subTest(path=path):
                self.write(path)
                plan = self.plan(path)
                self.assertTrue(runner.SHARED <= plan['selected'].keys())
                self.assertIn('test_screen_live', plan['selected'])
                self.assertIn('test_demo_launch', plan['selected'])
    def test_changed_test_fixture_selects_consumers_even_fast(self):
        self.write('test_album_lighting.py', 'import test_music_live as fixtures\n')
        plan = self.plan('test_music_live.py')
        self.assertTrue({'test_music_live','test_album_lighting'} <= plan['selected'].keys())
    def test_unknown_untracked_source_and_external_paths_force_full(self):
        for path in ('studio_qt/new_effect.py', 'requirements-studio-live.txt', 'olive_rgb.py', 'build_windows.bat', 'Olive RGB.spec'):
            self.write(path)
            self.assertEqual(set(self.plan(path)['selected']), self.tests)
        self.assertEqual(set(runner.select(self.stage,['README.py'],'fast')['selected']),self.tests)
    def test_deleted_source_and_renamed_old_path_force_full(self):
        plan = self.plan('studio_qt/music_presets.py')
        self.assertTrue(plan['fallback']);self.assertEqual(set(plan['selected']),self.tests)
    def test_new_test_is_discovered_and_forces_full(self):
        self.write('test_new_regression.py')
        plan = self.plan('test_new_regression.py')
        self.assertIn('test_new_regression',plan['selected'])
        self.assertTrue(plan['fallback']);self.assertEqual(len(plan['selected']),len(self.tests)+1)
    def test_runner_changes_force_full(self):
        for path in ('run_studio_tests.py','test_test_selection.py'):
            self.write(path);self.assertEqual(set(self.plan(path)['selected']),self.tests)
    def test_invalid_ast_forces_full_instead_of_guessing(self):
        self.write('studio_qt/music_presets.py','def broken(:\n')
        self.assertTrue(self.plan('studio_qt/music_presets.py')['fallback'])
    def test_full_with_no_changes_runs_every_module(self):
        plan=runner.select(self.stage,[],'full')
        self.assertEqual(set(plan['selected']),self.tests);self.assertFalse(plan['skipped'])
    def test_git_failure_forces_full(self):
        plan=runner.select(self.stage,[],'fast','unreadable Git')
        self.assertEqual(set(plan['selected']),self.tests)
    def test_docs_or_clean_tree_are_not_reported_as_validation(self):
        plan=runner.select(self.stage,['README.md'],'fast')
        self.assertFalse(plan['selected']);self.assertEqual(set(plan['skipped']),self.tests)
        self.assertEqual(set(self.plan('AGENTS.md')['selected']),self.tests)
    def test_all_current_tests_are_classified_and_shared_mouse_suites_are_selected(self):
        actual={p.stem for p in runner.STAGE.glob('test_*.py')}
        self.assertEqual(actual,self.tests)
        scene=self.write('studio_qt/widgets/scene_pad.py')
        self.assertIn('test_demo_launch',self.plan('studio_qt/widgets/scene_pad.py')['selected'])
        self.assertTrue(scene.is_file())
        from run_studio_tests import RULES
        for source in ('studio_qt/widgets/scene_pad.py','studio_qt/widgets/light_preview.py','studio_qt/corner_adapter.py','studio_qt/preferences.py'):
            self.assertIn('test_scene_live',RULES[source])


class GitTests(unittest.TestCase):
    def test_staged_unstaged_untracked_ignored_and_committed_base(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=Path(directory)
            def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.PIPE).decode().strip()
            git('init');git('config','user.name','Test');git('config','user.email','test@example.invalid')
            for name in ('staged.py','unstaged.py','canceled.py','renamed.py'):(repo/name).write_text('old')
            (repo/'.gitignore').write_text('ignored.py\n')
            git('add','.');git('commit','-m','baseline');base=git('rev-parse','HEAD')
            (repo/'staged.py').write_text('new');git('add','staged.py')
            (repo/'canceled.py').write_text('index change');git('add','canceled.py')
            (repo/'canceled.py').write_text('old')  # Working tree == HEAD, index still differs.
            (repo/'unstaged.py').write_text('new')
            (repo/'new space Ω.py').write_text('new');(repo/'ignored.py').write_text('ignored')
            git('mv','renamed.py','renamed new.py')
            changed=set(runner.git_paths(repo))
            self.assertEqual(changed,{'staged.py','canceled.py','unstaged.py','new space Ω.py','renamed.py','renamed new.py'})
            git('add','.');git('commit','-m','changes')
            self.assertFalse(runner.git_paths(repo))
            self.assertEqual(set(runner.git_paths(repo,base)),changed-{'canceled.py'})
    def test_nul_separated_paths_preserve_newlines(self):
        with patch.object(runner.subprocess,'check_output',side_effect=[b'a\nb.py\0',b'',b'space name.py\0']):
            self.assertEqual(runner.git_paths(Path('.')),['a\nb.py','space name.py'])


class ExecutionTests(unittest.TestCase):
    def run_child(self, source, timeout=180):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);stage=root/'source';stage.mkdir();output=root/'output';output.mkdir()
            (stage/'test_child.py').write_text(source,encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                return runner.execute(stage,{'selected':{'test_child':['test fixture']}},output,timeout)['test_child']
    def test_child_results_and_nonzero_failure(self):
        result=self.run_child('import unittest\nclass T(unittest.TestCase):\n def test_failure(self): self.fail("intentional")\n')
        self.assertNotEqual(result['exit_code'],0);self.assertEqual(result['tests_run'],1)
    def test_success_uses_current_interpreter_and_external_runtime_state(self):
        result=self.run_child('import unittest,os,sys\nfrom pathlib import Path\nclass T(unittest.TestCase):\n def test_environment(self):\n  self.assertEqual(sys.flags.dont_write_bytecode,1)\n  self.assertNotIn(Path.cwd(),Path(os.environ["APPDATA"]).parents)\n  self.assertFalse((Path.cwd()/"__pycache__").exists())\n')
        self.assertEqual(result['exit_code'],0);self.assertEqual(result['tests_run'],1)
    def test_no_tests_cannot_pass(self):
        self.assertNotEqual(self.run_child('')['exit_code'],0)
    def test_all_skipped_cannot_pass_and_reasons_are_reported(self):
        result=self.run_child('import unittest\nclass T(unittest.TestCase):\n @unittest.skip("native unavailable")\n def test_skip(self): pass\n')
        self.assertNotEqual(result['exit_code'],0);self.assertIn('native unavailable',result['actual_skips'][0])
    def test_background_traceback_cannot_pass(self):
        result=self.run_child('import unittest\nclass T(unittest.TestCase):\n def test_output(self): print("Exception in thread capture:")\n')
        self.assertNotEqual(result['exit_code'],0)
    def test_timeout_cannot_pass(self):
        self.assertNotEqual(self.run_child('import time\ntime.sleep(10)\n',.2)['exit_code'],0)
    def test_release_gate_rejects_fast_and_output_inside_repository(self):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
            runner.main(['fast','--gate','release'])
        self.assertEqual(error.exception.code,2)
        with patch.object(runner,'git_paths',return_value=[]),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
            runner.main(['full','--output-dir',str(runner.STAGE/'results')])
        self.assertEqual(error.exception.code,2);self.assertFalse((runner.STAGE/'results').exists())
    def test_empty_full_suite_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(runner,'STAGE',Path(directory)/'Studio'/'phase-1.10'),patch.object(runner,'git_paths',return_value=[]),contextlib.redirect_stdout(io.StringIO()):
            runner.STAGE.mkdir(parents=True)
            self.assertEqual(runner.main(['full']),1)
    def test_release_gate_fails_if_any_actual_tests_are_skipped(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(runner,'git_paths',return_value=[]),patch.object(runner,'execute',return_value={'sample':{'exit_code':0,'actual_skips':['requires native device']}}),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(['full','--gate','release','--output-dir',directory]),1)


if __name__=='__main__':unittest.main()
