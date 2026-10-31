"""first_run.py: the one-time entry point runs its steps in order, stamps backends.local.json, and never opens the key
page in --check / --no-key mode. Sibling scripts are replaced by a fake runner so nothing is installed here."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import first_run as fr


class FirstRunTests(unittest.TestCase):
    def setUp(self):
        fr.steps.clear()
        self.calls = []

    def fake_run(self, code_by_script):
        def _run(args, timeout=None):
            name = Path(args[0]).name
            self.calls.append((name, tuple(args[1:])))
            return code_by_script.get(name, 0)
        return _run

    def test_check_mode_runs_nothing_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(fr, 'CONFIG', Path(d) / 'backends.local.json'), \
                mock.patch.object(fr, 'run', self.fake_run({})), \
                mock.patch.dict('os.environ', {}, clear=False), \
                mock.patch.object(fr, 'load_user_env', lambda: None):
            import os
            os.environ.pop(fr.KEY_VAR, None)
            code = fr.main(['--check'])
        self.assertEqual(code, 0)
        self.assertEqual([c for c in self.calls], [('setup_env.py', ('--check',))])   # no key page, no setup/doctor
        self.assertFalse((Path(d) / 'backends.local.json').exists())
        names = [n for n, _, _ in fr.steps]
        self.assertEqual(names, ['环境', '相邻 Skill', '造物社密钥', '声音与生图配置'])

    def test_full_run_with_key_present_stamps_config(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(fr, 'CONFIG', Path(d) / 'backends.local.json'), \
                mock.patch.object(fr, 'run', self.fake_run({})), \
                mock.patch.dict('os.environ', {fr.KEY_VAR: 'x'}), \
                mock.patch.object(fr, 'load_user_env', lambda: None):
            (Path(d) / 'backends.local.json').write_text('{"audio": {"budget": 1}}', encoding='utf-8')
            code = fr.main([])
            data = json.loads((Path(d) / 'backends.local.json').read_text(encoding='utf-8'))
        self.assertEqual(code, 0)
        scripts = [n for n, _ in self.calls]
        self.assertEqual(scripts, ['setup_env.py', 'audio_cloud.py', 'audio_cloud.py'])   # env, setup --yes, doctor
        self.assertEqual(self.calls[1][1], ('setup', '--yes'))
        self.assertEqual(self.calls[2][1], ('doctor',))
        self.assertEqual(data['audio'], {'budget': 1})                                    # existing config kept
        self.assertEqual(data['first_run']['version'], fr.skill_version())
        self.assertTrue(data['first_run']['steps']['环境'])

    def test_missing_required_env_item_fails_but_still_reports_the_rest(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(fr, 'CONFIG', Path(d) / 'backends.local.json'), \
                mock.patch.object(fr, 'run', self.fake_run({'setup_env.py': 1})), \
                mock.patch.dict('os.environ', {fr.KEY_VAR: 'x'}), \
                mock.patch.object(fr, 'load_user_env', lambda: None):
            code = fr.main(['--no-key'])
        self.assertEqual(code, 1)
        self.assertFalse(fr.steps[0][1])
        self.assertIn('声音与生图配置', [n for n, _, _ in fr.steps])

    def test_key_page_timeout_returns_2(self):
        import os
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(fr, 'CONFIG', Path(d) / 'backends.local.json'), \
                mock.patch.object(fr, 'run', self.fake_run({'key_setup.py': 2})), \
                mock.patch.dict('os.environ', {}, clear=False), \
                mock.patch.object(fr, 'load_user_env', lambda: None):
            os.environ.pop(fr.KEY_VAR, None)
            code = fr.main(['--key-timeout', '60'])
        self.assertEqual(code, 2)
        self.assertIn(('key_setup.py', ('--var', fr.KEY_VAR, '--timeout', '60')), self.calls)
        self.assertNotIn('doctor', [a for _, args in self.calls for a in args])

    def test_a_sandbox_that_refuses_the_save_is_reported_as_such(self):
        import os
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(fr, 'CONFIG', Path(d) / 'backends.local.json'), \
                mock.patch.object(fr, 'run', self.fake_run({'key_setup.py': 4})), \
                mock.patch.dict('os.environ', {}, clear=False), \
                mock.patch.object(fr, 'load_user_env', lambda: None):
            os.environ.pop(fr.KEY_VAR, None)
            code = fr.main([])
        self.assertEqual(code, 0)
        note = next(n for name, _, n in fr.steps if name == '造物社密钥')
        self.assertIn('沙箱', note)

    def test_unwritable_skill_folder_stops_before_anything_runs(self):
        with mock.patch.object(fr, 'can_write_skill', lambda: False), \
                mock.patch.object(fr, 'run', self.fake_run({})):
            self.assertEqual(fr.main([]), 3)
        self.assertEqual(self.calls, [])

    def test_check_mode_still_reports_from_inside_a_sandbox(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(fr, 'CONFIG', Path(d) / 'backends.local.json'), \
                mock.patch.object(fr, 'can_write_skill', lambda: False), \
                mock.patch.object(fr, 'run', self.fake_run({})), \
                mock.patch.object(fr, 'load_user_env', lambda: None):
            self.assertIn(fr.main(['--check']), (0, 1))
        self.assertEqual(self.calls, [('setup_env.py', ('--check',))])

    def test_can_write_skill_leaves_nothing_behind(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(fr, 'CONFIG', Path(d) / 'backends.local.json'):
            self.assertTrue(fr.can_write_skill())
            self.assertEqual(list(Path(d).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
