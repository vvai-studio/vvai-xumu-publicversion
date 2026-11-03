"""Tests of avatar_cloud's decision gate and the speaking models (minimax-h3 / kling-v4 / wan-3-0: the model says the lines)."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import audio_cloud as ac
import avatar_cloud as av
import director
from test_audio_cloud import CFG, ENV, quiet

HAS_FFMPEG = shutil.which('ffmpeg') is not None


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.edit = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.edit, ignore_errors=True)

    def doc(self, avatar, status):
        grids = {k: {'status': 'confirmed'} for k in director.GRIDS}
        grids['7'] = {'status': status, 'visual_ratio': {'person': 1}, 'avatar': avatar}
        (self.edit / 'director.json').write_text(json.dumps({'grids': grids}), encoding='utf-8')

    def test_no_doc_needs_the_users_words(self):
        with self.assertRaisesRegex(ac.Refused, '--user-asked'):
            av.avatar_decision(self.edit)
        self.assertIn('我要数字人', av.avatar_decision(self.edit, '我要数字人'))
        self.assertIn('我要数字人', av.avatar_decision(self.edit))   # recorded for later runs

    def test_doc_without_avatar_is_refused(self):
        self.doc({'use': False}, 'confirmed')
        with self.assertRaisesRegex(ac.Refused, '第 7 格'):
            av.avatar_decision(self.edit, '我要数字人')   # with a doc, grid 7 decides

    def test_suggestion_needs_reason_and_confirmation(self):
        self.doc({'use': True, 'source': 'suggested', 'reason': '没有出镜素材，口播需要人脸建立信任'}, 'proposed')
        with self.assertRaisesRegex(ac.Refused, '还没经用户确认'):
            av.avatar_decision(self.edit)
        self.doc({'use': True, 'source': 'suggested', 'reason': ''}, 'confirmed')
        with self.assertRaisesRegex(ac.Refused, 'reason'):
            av.avatar_decision(self.edit)
        self.doc({'use': True, 'source': 'suggested', 'reason': '没有出镜素材'}, 'confirmed')
        self.assertIn('用户已确认', av.avatar_decision(self.edit))

    def test_director_validation_wants_source_and_reason(self):
        grids = {'7': {'avatar': {'use': True, 'source': 'maybe', 'reason': ''}}}
        errors = director.validate({'grids': grids})
        self.assertTrue(any('avatar.source' in e for e in errors))
        self.assertTrue(any('avatar.reason' in e for e in errors))
        self.assertEqual(director.AVATAR_OFF['use'], False)


@unittest.skipUnless(HAS_FFMPEG, 'needs ffmpeg')
class SpeakTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.edit = self.tmp / 'edit'
        tts = self.edit / 'tts'
        tts.mkdir(parents=True)
        self.env = mock.patch.dict('os.environ', ENV)
        self.env.start()
        self.cfg = json.loads(json.dumps(CFG))
        self.cfg['avatar'] = {'provider': 'gw'}
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=300:duration=20',
                        '-ar', '48000', '-ac', '1', str(tts / 'narration.wav')], check=True)
        long_text = '第一句讲清楚问题是什么。' * 6 + '第二部分给出三个办法，<#0.4#>每个都能马上用。' * 4
        sections = [{'id': 'S1', 'file': 'S1.wav', 'text': '大家好，这是数字人。', 'offset': 0.45, 'seconds': 3.2},
                    {'id': 'S2', 'file': 'S2.wav', 'text': long_text, 'offset': 4.1, 'seconds': 44.0}]
        (tts / 'manifest.json').write_text(json.dumps({'lead': 0.45, 'gap': 0.45, 'sections': sections, 'total': 48.6},
                                                      ensure_ascii=False), encoding='utf-8')
        av.avatar_decision(self.edit, '我要数字人')

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plan(self, model=None):
        with quiet():
            return av.make_plan(self.edit, cfg=self.cfg, model=model)

    def test_default_model_plans_from_the_script(self):
        plan = self.plan()
        self.assertEqual(plan['model'], 'minimax-h3')
        self.assertEqual(plan['kind'], 'speak')
        ref = self.edit / 'avatar' / 'voice_ref.mp3'
        self.assertLessEqual(av.probe(ref)['duration'], av.REF_MAX + 0.1)
        segs = plan['segments']
        self.assertEqual(segs[0]['text'], '大家好，这是数字人。')
        self.assertGreaterEqual(len(segs), 3)   # the 44 s section is split at sentence ends
        for s in segs:
            self.assertLessEqual(s['duration'], 30)
            self.assertGreaterEqual(s['duration'], s['seconds'])
            self.assertNotIn('<#', s['text'])
            self.assertTrue(s['text'].endswith('。'))

    def test_wan_lengths_snap_to_its_menu(self):
        for s in self.plan('wan-3-0')['segments']:
            self.assertIn(s['duration'], av.MODELS['wan-3-0']['durations'])

    def test_audio_flag_is_refused_for_speaking_models(self):
        with self.assertRaisesRegex(ac.Refused, 'kling-avatar'):
            av.make_plan(self.edit, audio=self.edit / 'tts' / 'narration.wav', cfg=self.cfg)

    def test_h3_default_uses_the_official_format_and_fits_15_seconds(self):
        plan = self.plan()
        a = av.settings(self.cfg, plan['model'])
        self.assertLessEqual(max(s['duration'] for s in plan['segments']), 15)
        s = plan['segments'][0]
        p = av.seg_params(a, plan, s, av.prompt_of(plan, s, '中', ''))
        self.assertEqual((p['mode'], p['resolution']), ('reference', '768p'))
        self.assertIn('<d>[Mandarin Chinese] ' + s['text'] + '</d>', p['prompt'])
        for field in ('subject_definitions:', 'summary:', 'retention_analysis:', 'detailed_description:',
                      'overall_soundscape:', 'non_diegetic_music:'):
            self.assertIn(field, p['prompt'])
        for word in ('face', 'lips', 'mouth', 'smile'):
            self.assertNotIn(word, p['prompt'])
        with self.assertRaisesRegex(ac.Refused, '动作幅度'):
            av.prompt_of(plan, s, '特大', '')

    def test_prompt_carries_the_line_and_no_face_words(self):
        plan = self.plan(model='kling-v4')
        a = av.settings(self.cfg, plan['model'])
        s = plan['segments'][0]
        p = av.seg_params(a, plan, s, av.prompt_of(plan, s, '中', ''))
        self.assertEqual((p['mode'], p['resolution']), ('reference', '720p'))
        self.assertIn('大家好，这是数字人。', p['prompt'])
        self.assertIn('不加字幕', p['prompt'])
        for word in ('表情', '微笑', '嘴'):
            self.assertNotIn(word, p['prompt'])

    def test_finish_keeps_the_model_voice_and_trims_the_tail(self):
        plan = self.plan()
        d = self.edit / 'avatar'
        for s in plan['segments']:   # a take: speech for its seconds, then silence to the requested length
            speech = min(s['seconds'], s['duration'] - 1)
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc=s=720x1280:r=24:d={s["duration"]}',
                            '-f', 'lavfi', '-i', f'sine=frequency=440:duration={speech}', '-filter_complex',
                            f'[1:a]apad=whole_dur={s["duration"]}[a]', '-map', '0:v', '-map', '[a]', '-shortest',
                            '-pix_fmt', 'yuv420p', str(d / f'seg_{s["n"]:02d}.mp4')], check=True)
        with quiet():
            rep = av.finish(self.edit, align=False)
        man = json.loads((d / 'voice' / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(man['sections']), len(plan['segments']))
        self.assertEqual(man['sections'][0]['text'], plan['segments'][0]['text'])
        self.assertLess(rep['duration'], sum(s['duration'] for s in plan['segments']) - 0.5)   # silent tails trimmed
        self.assertAlmostEqual(rep['duration'], man['total'], delta=0.2)
        self.assertIn('音色像不像本人的克隆声音', rep['unverified'])


if __name__ == '__main__':
    unittest.main()
