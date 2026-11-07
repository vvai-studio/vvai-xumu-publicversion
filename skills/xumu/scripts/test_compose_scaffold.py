"""Behavioral tests of the HyperFrames scaffold: timing comes from the plan, provenance hash matches, no overwrite."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest

from compose_scaffold import HYPERFRAMES_VERSION, main
from plan_tools import main as plan_main
from test_plan_tools import example


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, json.loads(out.getvalue())


def clip(page, element_id):
    """The opening tag of the timed element with this id."""
    match = re.search(rf'<(?:section|video|audio|div) id="{re.escape(element_id)}"[^>]*>', page)
    return match.group(0) if match else None


class ScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xumu-scaffold-test-')
        self.edit = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        for name in ('画面.bin', '声音.bin', '参考.jpg', '短测.mp4', '音效.wav', '旁白.m4a', 'shot2.mp4'):
            (self.edit / name).write_bytes(b'synthetic fixture')
        self.plan = example()
        self.plan['timeline'].update(fps=25, total_frames=100, width=1920, height=1080)
        first = self.plan['shots'][0]
        first.update(duration_frames=60, screen_text='收集 → 分类', engine='hyperframes', status='planned')
        del first['asset']                    # placeholder shot
        second = json.loads(json.dumps(first))
        second.update(id='s2', from_frame=60, duration_frames=40, screen_text='第二镜')
        second['asset'] = {'file': 'shot2.mp4', 'timeline_revision': 'v1', 'alpha': False}
        overlay = json.loads(json.dumps(first))
        overlay.update(id='o1', role='overlay', route='real', from_frame=10, duration_frames=30, screen_text='贴纸')
        self.plan['shots'] = [first, second, overlay]
        os.environ.pop('PREVIEW_END', None)

    def write_plan(self):
        plan_file = self.edit / 'visual-plan.json'
        plan_file.write_text(json.dumps(self.plan, ensure_ascii=False, indent=1), encoding='utf-8')
        return plan_file

    def out(self):
        return self.edit / 'compose' / 'hyperframes'

    def test_skeleton_follows_the_plan(self):
        plan_file = self.write_plan()
        code, report = run('hyperframes', '--edit', str(self.edit))
        self.assertEqual(code, 0, report)
        self.assertEqual(report['shots'], 3)
        self.assertEqual(report['duration_s'], 4.0)
        self.assertTrue(any(f'hyperframes@{HYPERFRAMES_VERSION} check' in step for step in report['next']))
        page = (self.out() / 'index.html').read_text(encoding='utf-8')
        root = clip(page, 'root')
        for attr in ('data-composition-id="main"', 'data-width="1920"', 'data-height="1080"', 'data-fps="25"',
                     'data-duration="4.000"'):
            self.assertIn(attr, root)
        self.assertNotIn('<template', page)
        s1, s2, o1 = clip(page, 'shot-s1'), clip(page, 'shot-s2'), clip(page, 'shot-o1')
        self.assertIn('data-start="0.000" data-duration="2.400"', s1)
        self.assertIn('class="clip"', s1)
        self.assertIn('z-index: 1', s1)
        # A shot without a rendered file is a sub-composition: host id, file id and timeline key all shot-<id>.
        self.assertIn('data-composition-id="shot-s1" data-composition-src="compositions/shot-s1.html"', s1)
        self.assertIn('data-width="1920" data-height="1080"', s1)
        self.assertIn('data-start="2.400" data-duration="1.600"', s2)
        self.assertTrue(s2.startswith('<video'), s2)       # rendered file becomes a framework-owned video
        self.assertIn('src="assets/s2-shot2.mp4"', s2)     # staged inside the project, never ../ out of it
        self.assertEqual((self.out() / 'assets' / 's2-shot2.mp4').read_bytes(), b'synthetic fixture')
        self.assertIn('muted playsinline', s2)
        self.assertIn('data-start="0.400" data-duration="1.200"', o1)
        self.assertIn('z-index: 10', o1)
        self.assertLess(page.index('id="shot-s1"'), page.index('id="shot-s2"'))
        self.assertIn('window.__timelines["main"] = tl', page)
        shot_file = (self.out() / 'compositions' / 'shot-s1.html').read_text(encoding='utf-8')
        self.assertIn('<template>', shot_file)
        self.assertIn('data-composition-id="shot-s1"', shot_file)
        self.assertIn('data-duration="2.400"', shot_file)
        self.assertIn('id="shot-s1-inner"', shot_file)      # the untimed container the agent animates
        self.assertIn('收集 → 分类', shot_file)
        self.assertIn('window.__timelines["shot-" + id] = tl', shot_file)
        self.assertFalse((self.out() / 'compositions' / 'shot-s2.html').exists())
        data = json.loads((self.out() / 'data.json').read_text(encoding='utf-8'))
        self.assertEqual(data['source_plan_sha256'], hashlib.sha256(plan_file.read_bytes()).hexdigest())
        self.assertEqual(data['generated_from'], 'visual-plan.json')
        self.assertEqual([s['id'] for s in data['shots']], ['s1', 's2', 'o1'])
        self.assertEqual(data['shots'][1], {'id': 's2', 'start_s': 2.4, 'duration_s': 1.6, 'from_frame': 60,
                                            'duration_frames': 40, 'role': 'background', 'route': 'mg',
                                            'engine': 'hyperframes', 'style': None, 'screen_text': '第二镜',
                                            'inner_frames': {}, 'asset': 'assets/s2-shot2.mp4', 'composition': None})
        self.assertEqual(data['shots'][0]['composition'], 'compositions/shot-s1.html')
        package = json.loads((self.out() / 'package.json').read_text(encoding='utf-8'))
        self.assertEqual(package['devDependencies'], {'hyperframes': HYPERFRAMES_VERSION})
        for script in ('check', 'render', 'snapshot'):
            self.assertIn(f'npx --yes hyperframes@{HYPERFRAMES_VERSION} {script}', package['scripts'][script])

    def test_data_json_passes_preflight(self):
        self.write_plan()
        (self.edit / 'director.json').write_text(json.dumps({'mode': 'semi', 'grids': {'7': {'visual_tier': 'full'}}}),
                                                 encoding='utf-8')
        self.assertEqual(run('hyperframes', '--edit', str(self.edit))[0], 0)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            plan_main(['preflight', str(self.edit), '--data', str(self.out() / 'data.json')])
        report = json.loads(out.getvalue())
        # Other preflight gates (decision record, stills) are not this script's job; the data provenance is.
        self.assertFalse([e for e in report['errors'] if 'source_plan_sha256' in e], report['errors'])
        self.assertEqual(report['data'][0]['source_plan_sha256'], report['plan_sha256'])

    def test_narration_base_video_and_sfx(self):
        self.plan['input_mode'] = 'video'
        self.plan['narration'] = {'kind': 'original', 'file': '旁白.m4a', 'locked': True, 'timeline_revision': 'v1'}
        self.plan['base_video'] = {'file': '画面.bin', 'timeline_revision': 'v1', 'verified': True}
        self.plan['shots'][2].update(audio_policy='separate')
        self.plan['sfx'] = [{'id': 'fx1', 'shot_id': 'o1', 'timeline_revision': 'v1', 'offset_frames': 5,
                             'duration_frames': 10, 'gain': 4, 'file': '音效.wav'}]
        self.write_plan()
        code, report = run('hyperframes', '--edit', str(self.edit))
        self.assertEqual(code, 0, report)
        page = (self.out() / 'index.html').read_text(encoding='utf-8')
        narration = clip(page, 'narration')
        self.assertTrue(narration.startswith('<audio'), narration)
        self.assertIn('src="assets/narration-旁白.m4a" data-start="0.000" data-duration="4.000"', narration)
        self.assertTrue((self.out() / 'assets' / 'narration-旁白.m4a').is_file())
        self.assertTrue((self.out() / 'assets' / 'sfx-fx1-音效.wav').is_file())
        base = clip(page, 'base-video')
        self.assertTrue(base.startswith('<video'), base)
        self.assertIn('data-duration="4.000"', base)
        self.assertLess(page.index('id="base-video"'), page.index('id="shot-s1"'))
        fx = clip(page, 'sfx-fx1')
        self.assertIn('data-start="0.600" data-duration="0.400"', fx)   # shot o1 starts at frame 10, offset 5 → 0.6 s
        self.assertIn('data-volume="3.98"', fx)                        # plan gain 4 clamped to the attribute ceiling
        self.assertEqual(report['audio'], 2)
        self.assertEqual(report['videos'], 2)

    def test_refuses_overwrite_without_force(self):
        self.write_plan()
        self.assertEqual(run('hyperframes', '--edit', str(self.edit))[0], 0)
        before = (self.out() / 'index.html').read_bytes()
        (self.out() / 'index.html').write_bytes(b'edited by hand')
        (self.out() / 'compositions' / 'shot-s1.html').write_bytes(b'filled by hand')
        code, report = run('hyperframes', '--edit', str(self.edit))
        self.assertEqual(code, 1)
        self.assertTrue(any('--force' in e for e in report['errors']))
        self.assertEqual((self.out() / 'index.html').read_bytes(), b'edited by hand')
        self.assertEqual((self.out() / 'compositions' / 'shot-s1.html').read_bytes(), b'filled by hand')
        self.assertEqual(run('hyperframes', '--edit', str(self.edit), '--force')[0], 0)
        self.assertEqual((self.out() / 'index.html').read_bytes(), before)
        self.assertIn('<template>', (self.out() / 'compositions' / 'shot-s1.html').read_text(encoding='utf-8'))

    def test_refuses_invalid_plan(self):
        self.plan['shots'][0]['duration_frames'] = 500                 # beyond the timeline
        self.write_plan()
        code, report = run('hyperframes', '--edit', str(self.edit))
        self.assertEqual(code, 1)
        self.assertTrue(any('beyond timeline' in e for e in report['errors']))
        self.assertFalse(self.out().exists())

    def test_missing_plan_is_an_error(self):
        code, report = run('hyperframes', '--edit', str(self.edit))
        self.assertEqual(code, 1)
        self.assertTrue(any('visual-plan.json' in e for e in report['errors']))

    def test_preview_end_shortens_the_root_only(self):
        self.write_plan()
        out = self.edit / 'preview'
        code, report = run('hyperframes', '--edit', str(self.edit), '--out', str(out), '--preview-end', '1.5')
        self.assertEqual(code, 0, report)
        self.assertEqual(report['duration_s'], 1.5)
        self.assertEqual(report['preview_end'], 1.5)
        page = (out / 'index.html').read_text(encoding='utf-8')
        self.assertIn('data-duration="1.500"', clip(page, 'root'))
        self.assertIn('data-width="1920" data-height="1080"', clip(page, 'root'))   # resolution untouched
        self.assertIn('data-start="2.400" data-duration="1.600"', clip(page, 'shot-s2'))   # shot times unchanged
        self.assertIn('预览', json.loads((out / 'package.json').read_text(encoding='utf-8'))['scripts']['render'])
        os.environ['PREVIEW_END'] = '2'
        try:
            code, report = run('hyperframes', '--edit', str(self.edit), '--out', str(out), '--force')
        finally:
            del os.environ['PREVIEW_END']
        self.assertEqual(report['duration_s'], 2.0)


if __name__ == '__main__':
    unittest.main()
