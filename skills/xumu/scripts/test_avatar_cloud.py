"""Tests of avatar_cloud: segment planning, the paid-call gates and the generate/finish flow with a fake gateway."""
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import numpy as np

import audio_cloud as ac
import avatar_cloud as av
from test_audio_cloud import CFG, ENV, FakeHttp, Resp, quiet

HAS_FFMPEG = shutil.which('ffmpeg') is not None


def speech_like(segments, sr=16000):
    """Loud noise for 'speech', silence for pauses: [(seconds, loud?), ...]."""
    rng = np.random.default_rng(0)
    return np.concatenate([(rng.standard_normal(int(s * sr)) * 0.3 if loud else np.zeros(int(s * sr))).astype(np.float32)
                           for s, loud in segments])


class CutTests(unittest.TestCase):
    def test_cuts_land_in_pauses_and_respect_the_maximum(self):
        parts = []
        for k in range(10):   # 10 × (8 s talk + 0.6 s pause) ≈ 86 s
            parts += [(8, True), (0.6, False)]
        cuts = av.cut_points(speech_like(parts), 16000, max_seg=30, min_seg=4)
        self.assertEqual(cuts[0], 0.0)
        for a, b in zip(cuts, cuts[1:]):
            self.assertLessEqual(b - a, 30.01)
        for c in cuts[1:-1]:   # every inner cut sits inside a pause
            pos = c % 8.6
            self.assertTrue(8.0 <= pos <= 8.6, c)

    def test_short_audio_is_one_segment_and_tiny_tail_is_folded(self):
        self.assertEqual(len(av.cut_points(speech_like([(10, True)]), 16000, 60)), 2)
        cuts = av.cut_points(speech_like([(29, True), (0.5, False), (2, True)]), 16000, max_seg=30, min_seg=4)
        self.assertEqual(len(cuts), 2)

    def test_no_pause_means_a_hard_cut_at_the_limit(self):
        cuts = av.cut_points(speech_like([(70, True)]), 16000, max_seg=30, min_seg=4)
        self.assertEqual(cuts[1], 30)


class PromptTests(unittest.TestCase):
    def test_prompt_describes_body_not_face(self):
        for level in av.MOTION:
            p = av.build_prompt(level)
            for word in ('嘴', '表情', '微笑', '眼神'):
                self.assertNotIn(word, p)
            self.assertIn('镜头固定', p)

    def test_unknown_motion_level_refused(self):
        with self.assertRaises(ac.Refused):
            av.build_prompt('超大')


@unittest.skipUnless(HAS_FFMPEG, 'needs ffmpeg')
class FlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.edit = self.tmp / 'edit'
        (self.edit / 'tts').mkdir(parents=True)
        self.env = mock.patch.dict('os.environ', ENV)
        self.env.start()
        self.cfg = json.loads(json.dumps(CFG))
        self.cfg['avatar'] = {'provider': 'gw', 'model': 'kling-avatar', 'max_seg': 30, 'min_seg': 4}
        # narration: 4 × (9 s tone + 0.8 s silence), about 39 s: two segments at max_seg=30, four at 10 (enough to need a sample)
        parts = []
        for k in range(4):
            parts += [f'sine=frequency={300 + k * 50}:duration=9', 'anullsrc=r=16000:cl=mono:d=0.8']
        inputs = sum((['-f', 'lavfi', '-i', p] for p in parts), [])
        graph = ''.join(f'[{i}:a]aresample=16000,aformat=channel_layouts=mono[a{i}];' for i in range(len(parts))) + \
            ''.join(f'[a{i}]' for i in range(len(parts))) + f'concat=n={len(parts)}:v=0:a=1[o]'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', graph, '-map', '[o]',
                        str(self.edit / 'tts' / 'narration.wav')], check=True)
        self.image = self.tmp / 'me.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=gray:s=720x1280', '-frames:v', '1',
                        str(self.image)], check=True)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def clip(self, seconds):
        f = self.tmp / f'clip_{seconds}.mp4'
        if not f.exists():
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc=s=720x1280:r=30:d={seconds}',
                            '-pix_fmt', 'yuv420p', str(f)], check=True)
        return f.read_bytes()

    def http(self, seconds=10.6):
        done = {'is_final': True, 'status': 'completed', 'billing': {'actual_cost_credits': 3.4},
                'result': {'videos': [{'url': 'https://cdn.example/v.mp4'}]}}
        return FakeHttp([
            ('/v1/pricing-estimate', [Resp(200, {'billing_mode': 'fixed_amount', 'channels': [
                {'vendor': 'OLX', 'lane': 'Kling-2', 'effective_total_rmb': 0.68 * seconds}]})]),
            ('/pricing', [Resp(200, {'channel_groups': [{'vendor': 'OLX', 'success_rate_24h': 100}]})]),
            ('/v1/files', [Resp(201, {'url': 'https://cdn.example/up'})]),
            ('/api/v1/model-runtime/invoke', [Resp(200, {'task_id': 'task-av-1'})]),
            ('/v1/tasks/', [Resp(200, {'is_final': False, 'status': 'processing'}), Resp(200, done)]),
            ('cdn.example/v.mp4', [Resp(200, content=self.clip(seconds))])])

    def plan(self):
        av.avatar_decision(self.edit, '我要用数字人')
        with quiet():
            return av.make_plan(self.edit, cfg=self.cfg)

    def test_plan_writes_segments_and_audio(self):
        plan = self.plan()
        self.assertGreaterEqual(len(plan['segments']), 2)
        for s in plan['segments']:
            self.assertTrue((self.edit / 'avatar' / s['audio']).exists())
            self.assertLessEqual(s['seconds'], 30.01)

    def test_first_run_makes_one_test_take_without_asking(self):
        self.cfg['avatar']['max_seg'] = 10   # four segments
        plan = self.plan()
        self.assertEqual(len(plan['segments']), 4)
        want = av.test_segment(plan['segments'])['n']
        http = self.http()
        with quiet():   # no --voice-ok, no sample refusal: one test take only
            res = av.generate(self.cfg, self.edit, self.image, confirmed=True, http=http, sleep=lambda s: None)
        self.assertEqual(res['test'], want)
        self.assertEqual(len([c for c in http.calls if c[1].endswith('/api/v1/model-runtime/invoke')]), 1)
        self.assertTrue((self.edit / 'avatar' / f'seg_{want:02d}.mp4').exists())
        self.assertEqual(len(res['missing']), 3)
        again = FakeHttp([])   # a second run without --all stays on the test take: reused, nothing submitted
        with quiet():
            res2 = av.generate(self.cfg, self.edit, self.image, confirmed=True, http=again)
        self.assertEqual(res2['test'], want)
        self.assertEqual([c for c in again.calls if 'invoke' in c[1]], [])

    def test_test_segment_is_closest_to_ten_seconds(self):
        segs = [{'n': 1, 'seconds': 3.0}, {'n': 2, 'seconds': 12.5}, {'n': 3, 'seconds': 9.0}, {'n': 4, 'seconds': 11.0}]
        self.assertEqual(av.test_segment(segs)['n'], 3)

    def test_sample_segment_runs_with_pinned_lane_and_is_reused(self):
        self.cfg['avatar']['max_seg'] = 10
        self.plan()
        http = self.http()
        with quiet():
            res = av.generate(self.cfg, self.edit, self.image, only='2', confirmed=True,
                              http=http, sleep=lambda s: None)
        sub = [c[2]['json'] for c in http.calls if c[1].endswith('/api/v1/model-runtime/invoke')]
        self.assertEqual(len(sub), 1)
        self.assertEqual(sub[0]['model_id'], 'kling-avatar')
        self.assertEqual(sub[0]['modality'], 'video')
        self.assertEqual(sub[0]['lane_id'], 'Kling-2')
        self.assertNotIn('嘴', sub[0]['params']['prompt'])
        self.assertTrue((self.edit / 'avatar' / 'seg_02.mp4').exists())
        self.assertEqual(res['missing'], [1, 3, 4])
        again = FakeHttp([])
        with quiet():
            av.generate(self.cfg, self.edit, self.image, only='2', confirmed=True, http=again)
        self.assertEqual([c for c in again.calls if 'invoke' in c[1]], [])

    def test_frame_keeps_the_photo_pixels_over_the_scene(self):
        scene = self.tmp / 'scene.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=1080x1920', '-frames:v', '1',
                        str(scene)], check=True)

        def cutter(src, dst):   # stand-in for the matting model: keep the left half of the photo, clear the rest
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-vf',
                            "format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lt(X,W/2),255,0)'", str(dst)], check=True)

        rep = av.make_frame(self.edit, self.image, scene, cutter=cutter)
        self.assertEqual(rep['size'], '720x1280')   # the photo's own frame
        def pixel(x, y):
            return subprocess.run(['ffmpeg', '-v', 'error', '-i', rep['frame'], '-vf', f'crop=1:1:{x}:{y}', '-f', 'rawvideo',
                                   '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
        left, right = pixel(180, 640), pixel(540, 640)
        self.assertTrue(abs(left[0] - left[2]) < 20)   # grey photo pixels kept
        self.assertGreater(right[2], right[0] + 100)   # blue scene shows where the person is not
        self.assertFalse((self.edit / 'avatar' / 'frame_photo.png').exists())
        with self.assertRaises(ac.Refused):
            av.make_frame(self.edit, self.tmp / 'missing.jpg', scene, cutter=cutter)

    def test_blend_frame_sends_photo_then_scene_and_builds_the_compare_sheet(self):
        scene = self.tmp / 'scene.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=1080x1920', '-frames:v', '1',
                        str(scene)], check=True)
        calls = []

        def gen(**k):   # stand-in for image_cloud.generate: two takes in <edit>/images
            calls.append(k)
            (self.edit / 'images').mkdir(exist_ok=True)
            for t in 'AB':
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=720x1280', '-frames:v', '1',
                                str(self.edit / 'images' / f'avatar_frame_{t}.png')], check=True)
            return {'files': ['avatar_frame_A.png', 'avatar_frame_B.png']}

        with quiet():
            rep = av.blend_frame(self.cfg, self.edit, self.image, scene, light='窗外夕阳从后方打来', gen=gen, confirmed=True)
        k = calls[0]
        self.assertEqual(k['refs'], [str(self.image), str(scene)])   # the real photo first, then the scene
        self.assertEqual((k['aspect'], k['count'], k['name']), ('9:16', 2, 'avatar_frame'))
        self.assertIn('窗外夕阳从后方打来', k['prompt'])
        self.assertIn('同一张脸', k['prompt'])
        self.assertEqual(len(rep['takes']), 2)
        self.assertEqual(av.probe(rep['compare'])['height'], 960)   # photo | take A | take B
        self.assertGreater(av.probe(rep['compare'])['width'], 3 * 500)

    def test_changed_narration_invalidates_plan(self):
        self.plan()
        with open(self.edit / 'tts' / 'narration.wav', 'ab') as f:
            f.write(b'\0' * 64)
        with self.assertRaisesRegex(ac.Refused, '重新运行 plan'):
            av.load_plan(self.edit)

    def test_over_limit_is_refused_before_upload(self):
        self.plan()
        http = self.http()
        with quiet(), self.assertRaisesRegex(ac.Refused, '超过上限'):
            av.generate(self.cfg, self.edit, self.image, all_segments=True, confirmed=True, max_cost=1, http=http)
        self.assertFalse([c for c in http.calls if '/v1/files' in c[1]])

    def test_finish_joins_and_keeps_the_original_voice(self):
        plan = self.plan()
        for s in plan['segments']:   # takes slightly off in length, as models return them
            (self.edit / 'avatar' / f'seg_{s["n"]:02d}.mp4').write_bytes(self.clip(math.ceil(s["seconds"] + 0.3)))
        with quiet():
            rep = av.finish(self.edit)
        self.assertAlmostEqual(rep['duration'], plan['duration'], delta=0.15)
        self.assertTrue(Path(rep['video']).exists())
        self.assertTrue((self.edit / 'avatar' / 'anomalies.json').exists())
        self.assertTrue(all(q['diff_s'] > 0 for q in rep['segments']))


if __name__ == '__main__':
    unittest.main()
