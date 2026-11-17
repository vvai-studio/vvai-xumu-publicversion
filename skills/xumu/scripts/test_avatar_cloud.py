"""Tests of avatar_cloud: the paid-call gates and the generate flow with a fake gateway (default model minimax-h3),
and the opening-frame helpers."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import audio_cloud as ac
import avatar_cloud as av
from test_audio_cloud import CFG, ENV, FakeHttp, Resp, quiet

HAS_FFMPEG = shutil.which('ffmpeg') is not None


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
        tts = self.edit / 'tts'
        tts.mkdir(parents=True)
        self.env = mock.patch.dict('os.environ', ENV)
        self.env.start()
        self.cfg = json.loads(json.dumps(CFG))
        self.cfg['avatar'] = {'provider': 'gw'}
        # narration from voice speak: four 9 s sections, so four H3 segments (enough to need a test take)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=300:duration=38',
                        '-ar', '48000', '-ac', '1', str(tts / 'narration.wav')], check=True)
        sections = [{'id': f'S{k}', 'file': f'S{k}.wav', 'text': f'这是第{k}段测试台词。', 'offset': round(0.45 + (k - 1) * 9.45, 2),
                     'seconds': 9.0} for k in range(1, 5)]
        (tts / 'manifest.json').write_text(json.dumps({'lead': 0.45, 'gap': 0.45, 'sections': sections, 'total': 38.25},
                                                      ensure_ascii=False), encoding='utf-8')
        self.image = self.tmp / 'me.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=gray:s=720x1280', '-frames:v', '1',
                        str(self.image)], check=True)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def clip(self, seconds, speech):
        f = self.tmp / f'clip_{seconds}.mp4'
        if not f.exists():
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc=s=720x1280:r=30:d={seconds}',
                            '-f', 'lavfi', '-i', f'sine=frequency=440:duration={speech}', '-filter_complex',
                            f'[1:a]apad=whole_dur={seconds}[a]', '-map', '0:v', '-map', '[a]', '-shortest',
                            '-pix_fmt', 'yuv420p', str(f)], check=True)
        return f.read_bytes()

    def http(self, seconds=11):
        done = {'is_final': True, 'status': 'completed', 'billing': {'actual_cost_credits': 0.9},
                'result': {'videos': [{'url': 'https://cdn.example/v.mp4'}]}}
        return FakeHttp([
            ('/v1/pricing-estimate', [Resp(200, {'billing_mode': 'fixed_amount', 'channels': [
                {'vendor': 'MEG', 'lane': 'minimax-h3@MEG:default', 'effective_total_rmb': 0.086 * seconds}]})]),
            ('/pricing', [Resp(200, {'channel_groups': [{'vendor': 'MEG', 'success_rate_24h': 100}]})]),
            ('/v1/files', [Resp(201, {'url': 'https://cdn.example/up'})]),
            ('/api/v1/model-runtime/invoke', [Resp(200, {'task_id': 'task-av-1'})]),
            ('/v1/tasks/', [Resp(200, {'is_final': False, 'status': 'processing'}), Resp(200, done)]),
            ('cdn.example/v.mp4', [Resp(200, content=self.clip(seconds, 9))])])

    def plan(self, model=None):
        av.avatar_decision(self.edit, '我要用数字人')
        with quiet():
            return av.make_plan(self.edit, cfg=self.cfg, model=model)

    def test_first_run_makes_one_test_take_without_asking(self):
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

    def test_segment_runs_on_h3_with_pinned_lane_and_is_reused(self):
        self.plan()
        http = self.http()
        with quiet():
            res = av.generate(self.cfg, self.edit, self.image, only='2', confirmed=True,
                              http=http, sleep=lambda s: None)
        sub = [c[2]['json'] for c in http.calls if c[1].endswith('/api/v1/model-runtime/invoke')]
        self.assertEqual(len(sub), 1)
        self.assertEqual(sub[0]['model_id'], 'minimax-h3')
        self.assertEqual(sub[0]['modality'], 'video')
        self.assertEqual(sub[0]['lane_id'], 'minimax-h3@MEG:default')
        self.assertEqual(sub[0]['params']['mode'], 'reference')
        self.assertIn('这是第2段测试台词。', sub[0]['params']['prompt'])
        self.assertTrue((self.edit / 'avatar' / 'seg_02.mp4').exists())
        self.assertEqual(res['missing'], [1, 3, 4])
        again = FakeHttp([])
        with quiet():
            av.generate(self.cfg, self.edit, self.image, only='2', confirmed=True, http=again)
        self.assertEqual([c for c in again.calls if 'invoke' in c[1]], [])

    def test_refused_submission_names_the_backup_model(self):
        self.plan()
        http = self.http()
        http.routes = [r for r in http.routes if r[0] != '/api/v1/model-runtime/invoke'] + [
            ('/api/v1/model-runtime/invoke', [Resp(403, {'error': {'code': 'likeness_consent_required',
                                                                   'message': 'likeness consent required'}})])]
        with quiet(), self.assertRaises(ac.Refused) as cm:
            av.generate(self.cfg, self.edit, self.image, only='1', confirmed=True, http=http, sleep=lambda s: None)
        msg = str(cm.exception)
        self.assertIn('未扣费', msg)
        self.assertIn('--model seedance-2-5-promo', msg)
        self.assertIn('不要让用户去网页手动上传', msg)

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
            av.generate(self.cfg, self.edit, self.image, all_segments=True, confirmed=True, max_cost=0.01, http=http)
        self.assertFalse([c for c in http.calls if '/v1/files' in c[1]])


if __name__ == '__main__':
    unittest.main()
