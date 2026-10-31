"""Tests of image_cloud with recorded-shape responses and a fake HTTP client (no network, no account)."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import audio_cloud as ac
import image_cloud as ic
from test_audio_cloud import CFG, ENV, FakeHttp, Resp, quiet

ICFG = {'provider': 'gw', 'model': 'gt-image-2.5-flare'}
PNG = b'\x89PNG\r\n\x1a\n' + b'\0' * 16


def gw_http(status='completed'):
    done = {'is_final': True, 'status': status, 'billing': {'actual_cost_credits': 0.036},
            'error': None if status == 'completed' else {'message': 'upstream busy'},
            'data': [{'url': 'https://cdn.example/x.png.q95.jpg', 'original_url': 'https://cdn.example/x'}]}
    return FakeHttp([
        ('/v1/pricing-estimate', [Resp(200, {'billing_mode': 'fixed_amount', 'channels': [
            {'vendor': 'ZQI', 'lane': 'img@ZQI:kuaisu', 'effective_total_rmb': 0.036},
            {'vendor': 'XUE', 'lane': 'img@XUE:vip-o', 'effective_total_rmb': 0.045}]})]),
        ('/pricing', [Resp(200, {'channel_groups': [{'vendor': 'ZQI', 'success_rate_24h': 97.9},
                                                     {'vendor': 'XUE', 'success_rate_24h': 100}]})]),
        ('/v1/files', [Resp(201, {'id': 'file-1', 'url': 'https://cdn.example/uploads/ref.png'})]),
        ('/api/v1/model-runtime/invoke', [Resp(200, {'task_id': 'task-img-1', 'status': 'pending'})]),
        ('/v1/tasks/', [Resp(200, {'is_final': False, 'status': 'processing'}), Resp(200, done)]),
        ('cdn.example', [Resp(200, content=PNG)])])


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.edit = self.tmp / 'edit'
        self.env = mock.patch.dict('os.environ', ENV)
        self.env.start()
        self.size = mock.patch.object(ic, 'size_of', lambda p: '3840x2160')
        self.size.start()

    def tearDown(self):
        self.env.stop(); self.size.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def submitted(self, http):
        return [c[2]['json'] for c in http.calls if c[1].endswith('/api/v1/model-runtime/invoke')]

    def test_defaults_are_4k_high_and_lossless_original_is_saved(self):
        http = gw_http()
        with quiet():
            rec = ic.generate(CFG, ICFG, self.edit, 'cover', '书桌俯拍', confirmed=True, http=http, sleep=lambda s: None)
        sub = self.submitted(http)[0]
        self.assertEqual(sub['model_id'], 'gt-image-2.5-flare')
        self.assertEqual(sub['modality'], 'image')
        self.assertEqual(sub['params']['resolution'], '4K')
        self.assertEqual(sub['params']['quality'], 'high')
        self.assertEqual(sub['params']['aspect_ratio'], '16:9')
        self.assertTrue(sub['client_request_id'].startswith('xumu-'))
        self.assertEqual(rec['files'], ['cover.png'])   # extension from the bytes; the URL had none
        got = [c[1] for c in http.calls if c[1].startswith('https://cdn.example/')]
        self.assertEqual(got, ['https://cdn.example/x'])   # original_url, not the compressed url

    def test_balanced_lane_is_pinned(self):
        cfg = json.loads(json.dumps(CFG))
        cfg['budget']['min_success_rate'] = 0.99   # ZQI's 97.9% is under the bar
        http = gw_http()
        with quiet():
            ic.generate(cfg, ICFG, self.edit, 'a', 'x', confirmed=True, http=http, sleep=lambda s: None)
        self.assertEqual(self.submitted(http)[0]['lane_id'], 'img@XUE:vip-o')

    def test_same_request_is_reused_without_paying(self):
        with quiet():
            ic.generate(CFG, ICFG, self.edit, 'a', 'x', confirmed=True, http=gw_http(), sleep=lambda s: None)
        http2 = FakeHttp([])
        with quiet():
            ic.generate(CFG, ICFG, self.edit, 'a', 'x', confirmed=True, http=http2)
        self.assertEqual(http2.calls, [])

    def test_interrupted_run_resumes_the_task(self):
        with quiet(), self.assertRaises(RuntimeError):
            ic.generate(CFG, ICFG, self.edit, 'a', 'x', confirmed=True, http=gw_http(), sleep=lambda s: None,
                        poll_every=1, timeout=0)
        http = gw_http()
        with quiet():
            ic.generate(CFG, ICFG, self.edit, 'a', 'x', confirmed=True, http=http, sleep=lambda s: None)
        self.assertEqual(self.submitted(http), [])

    def test_reference_images_are_uploaded_and_set_the_mode(self):
        ref = self.tmp / 'ref.png'
        ref.write_bytes(PNG)
        http = gw_http()
        with quiet():
            ic.generate(CFG, ICFG, self.edit, 'a', '换成海边背景', refs=[str(ref)], transparent=True, confirmed=True,
                        http=http, sleep=lambda s: None)
        p = self.submitted(http)[0]['params']
        self.assertEqual(p['images'], ['https://cdn.example/uploads/ref.png'])
        self.assertEqual(p['mode'], 'image-edit')
        self.assertEqual((p['background'], p['output_format']), ('transparent', 'png'))

    def test_user_overrides_win(self):
        p = ic.image_params({'defaults': {'quality': 'xhigh'}}, 'x', '9:16', 2, [], {'resolution': '2K'})
        self.assertEqual((p['resolution'], p['quality'], p['count'], p['aspect_ratio']), ('2K', 'xhigh', 2, '9:16'))

    def test_over_limit_and_unconfirmed_refuse_before_submitting(self):
        cfg = json.loads(json.dumps(CFG))
        cfg['budget']['confirm_over'] = 0.01
        http = gw_http()
        with quiet(), self.assertRaises(ac.Refused):
            ic.generate(cfg, ICFG, self.edit, 'a', 'x', confirmed=True, http=http)
        with quiet(), self.assertRaises(ac.Refused):
            ic.generate(CFG, ICFG, self.edit, 'b', 'x', confirmed=False, http=http)
        self.assertEqual(self.submitted(http), [])

    def test_failure_lists_alternatives_without_retry(self):
        http = gw_http(status='failed')
        with quiet(), self.assertRaises(ac.Refused) as e:
            ic.generate(CFG, ICFG, self.edit, 'a', 'x', confirmed=True, http=http, sleep=lambda s: None)
        self.assertIn('XUE', str(e.exception))
        self.assertEqual(len(self.submitted(http)), 1)

    def test_refunded_no_image_is_retried_on_the_same_lane_with_a_new_request_id(self):
        failed = {'is_final': True, 'status': 'failed', 'refunded': True, 'error_class': 'image_task_failed',
                  'error': '这次上游模型没有出图，只回了一段文字（偶发情况），本次未扣费'}
        done = {'is_final': True, 'status': 'completed', 'data': [{'url': 'https://cdn.example/y'}]}
        http = gw_http()
        http.routes = [r for r in http.routes if r[0] not in ('/v1/tasks/', '/api/v1/model-runtime/invoke')] + [
            ('/api/v1/model-runtime/invoke', [Resp(200, {'task_id': 't1'}), Resp(200, {'task_id': 't2'})]),
            ('/v1/tasks/', [Resp(200, failed), Resp(200, done)])]
        with quiet():
            rec = ic.generate(CFG, ICFG, self.edit, 'a', 'x', confirmed=True, http=http, sleep=lambda s: None)
        subs = self.submitted(http)
        self.assertEqual(len(subs), 2)
        self.assertEqual(subs[0]['lane_id'], subs[1]['lane_id'])
        self.assertNotEqual(subs[0]['client_request_id'], subs[1]['client_request_id'])
        self.assertEqual(rec['state'], 'success')
        http2 = FakeHttp([])   # the newest log entry (the success) is the one that counts
        with quiet():
            ic.generate(CFG, ICFG, self.edit, 'a', 'x', confirmed=True, http=http2)
        self.assertEqual(http2.calls, [])

    def test_blocked_content_is_not_retried(self):
        blocked = {'is_final': True, 'status': 'failed', 'refunded': True, 'error_class': 'content_blocked',
                   'error': '审核未通过'}
        http = gw_http()
        http.routes = [r for r in http.routes if r[0] != '/v1/tasks/'] + [('/v1/tasks/', [Resp(200, blocked)])]
        with quiet(), self.assertRaises(ac.Refused):
            ic.generate(CFG, ICFG, self.edit, 'a', 'x', confirmed=True, http=http, sleep=lambda s: None)
        self.assertEqual(len(self.submitted(http)), 1)

    def test_no_image_provider_points_to_setup(self):
        with self.assertRaises(ac.Refused) as e:
            ic.generate(CFG, {}, self.edit, 'a', 'x', confirmed=True)
        self.assertIn('setup', str(e.exception))


if __name__ == '__main__':
    unittest.main()
