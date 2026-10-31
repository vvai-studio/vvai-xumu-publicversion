"""Tests of audio_cloud with recorded-shape responses and a fake HTTP client (no network, no account, no ffmpeg)."""
import contextlib
import io
import json
import re
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import audio_cloud as ac

ENV = {'LK_KEY': 'k1', 'GW_KEY': 'k2'}

CFG = {
    'budget': {'confirm_over': 10, 'min_success_rate': 0.8},
    'providers': {
        'lk': {'type': 'lk-media-task', 'base_url': 'https://lk.example', 'key_env': 'LK_KEY',
               'price': {'per': 'token', 'amount': 0.001}},
        'gw': {'type': 'gateway-media', 'base_url': 'https://gw.example', 'key_env': 'GW_KEY', 'currency': '¥'},
    },
    'voice': {'default': 'me', 'voices': {
        'me': {'provider': 'lk', 'model': 'speech-2.8', 'voice_id': 'LK_1'},
        'gwme': {'provider': 'gw', 'model': 'speech-2.8', 'voice_id': 'omfvc_1'}},
        'defaults': {'quality': 'hd', 'speed': 1}},
    'music': {'provider': 'gw', 'model': 'music', 'license': '用户确认可商用'},
}


class Resp:
    def __init__(self, status, body=None, content=b'', headers=None):
        self.status_code, self._body, self.content, self.headers = status, body, content, headers or {}
        self.text = json.dumps(body) if body is not None else ''

    def json(self):
        if self._body is None:
            raise ValueError('no json')
        return self._body


class FakeHttp:
    """Answers by URL substring (first match), popping queued answers; records calls."""
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def _answer(self, method, url, kw):
        self.calls.append((method, url, kw))
        for key, answers in self.routes:
            if key in url:
                return answers.pop(0) if len(answers) > 1 else answers[0]
        raise AssertionError(f'unexpected {method} {url}')

    def get(self, url, **kw):
        return self._answer('GET', url, kw)

    def post(self, url, **kw):
        return self._answer('POST', url, kw)


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.edit = self.tmp / 'edit'
        self.script = self.tmp / 'script.md'
        self.script.write_text('## S1\n我现在用我的声音克隆。\n\n## S2\n先说结论。<#0.8#>OPC 很重要。\n', encoding='utf-8')
        self.env = mock.patch.dict('os.environ', ENV)
        self.env.start()
        # no ffmpeg in unit tests: "converting" copies bytes, narration assembly is checked separately
        self.p1 = mock.patch.object(ac, 'to_wav', lambda src, dst: shutil.copyfile(src, dst))
        self.p2 = mock.patch.object(ac, 'build_narration', lambda edit, secs, lead, gap: {'total': 1.0, 'sections': secs})
        self.p1.start(); self.p2.start()

    def tearDown(self):
        self.env.stop(); self.p1.stop(); self.p2.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


class TextTests(unittest.TestCase):
    def test_parse_markdown_sections(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 's.md'
            p.write_text('# 标题\n## A1\n第一行\n第二行\n## A2\nAfter the Rain.\nThe rain\n', encoding='utf-8')
            secs = ac.parse_script(p)
        self.assertEqual([s['id'] for s in secs], ['A1', 'A2'])
        self.assertEqual(secs[0]['text'], '第一行第二行')
        self.assertEqual(secs[1]['text'], 'After the Rain. The rain')

    def test_pronounce_skips_pause_marks_and_prefers_longest(self):
        table = {'GPT': 'G P T', 'GPT-5': 'G P T 五', '0.8': '零点八'}
        self.assertEqual(ac.apply_pronounce('GPT-5 和 GPT<#0.8#>', table), 'G P T 五 和 G P T<#0.8#>')

    def test_billing_units_two_per_cjk(self):
        self.assertEqual(ac.billing_units('你好AI<#0.5#>'), 6)

    def test_request_key_changes_with_text_or_voice(self):
        k = ac.request_key('lk', 'speech-2.8', 'v', {'speed': 1}, '你好')
        self.assertNotEqual(k, ac.request_key('lk', 'speech-2.8', 'v', {'speed': 1}, '你们好'))
        self.assertNotEqual(k, ac.request_key('lk', 'speech-2.8', 'v2', {'speed': 1}, '你好'))


class VoicePickTests(unittest.TestCase):
    def test_default_and_named(self):
        self.assertEqual(ac.pick_voice(CFG)[0], 'me')
        self.assertEqual(ac.pick_voice(CFG, 'gwme')[1]['voice_id'], 'omfvc_1')

    def test_unknown_name_is_refused_not_guessed(self):
        with self.assertRaises(ac.Refused) as e:
            ac.pick_voice(CFG, '小林')
        self.assertIn('me', str(e.exception))

    def test_no_voices_offers_alternatives(self):
        with self.assertRaises(ac.Refused) as e:
            ac.pick_voice({'providers': {}})
        self.assertIn('原声录音', str(e.exception))

    def test_several_without_default_asks(self):
        cfg = json.loads(json.dumps(CFG))
        del cfg['voice']['default']
        with self.assertRaises(ac.Refused):
            ac.pick_voice(cfg)


class ChannelTests(unittest.TestCase):
    def test_cheapest_reliable_channel_wins_and_skips_are_named(self):
        chans = [{'vendor': 'B', 'price': 0.9, 'success_rate': 0.99}, {'vendor': 'A', 'price': 0.6, 'success_rate': 0.33},
                 {'vendor': 'C', 'price': 1.2, 'success_rate': None}]
        best, ordered, notes = ac.choose_channel(chans, 0.8)
        self.assertEqual(best['vendor'], 'B')
        self.assertEqual([c['vendor'] for c in ordered], ['A', 'B', 'C'])
        self.assertTrue(notes and 'A' in notes[0] and '33%' in notes[0])

    def test_avoided_vendor_is_skipped_and_none_qualifying_falls_back(self):
        chans = [{'vendor': 'Z', 'price': 0.04, 'success_rate': 0.98}, {'vendor': 'X', 'price': 0.05, 'success_rate': 1.0}]
        self.assertEqual(ac.choose_channel(chans, 0.9, avoid=['Z'])[0]['vendor'], 'X')
        best, _, notes = ac.choose_channel(chans, 1.01)
        self.assertEqual(best['vendor'], 'Z')
        self.assertIn('没有渠道达到', notes[-1])

    def test_budget_defaults_are_balanced(self):
        b = ac.budget({})
        self.assertEqual(b['min_success_rate'], 0.9)
        self.assertEqual(b['avoid_vendors'], [])

    def test_gateway_errors_get_a_plain_hint(self):
        r = Resp(403, {'error': {'code': 'model_not_allowed', 'message': 'model not allowed'}})
        with self.assertRaises(RuntimeError) as e:
            ac.body(r, 'submit')
        self.assertIn('管理密钥', str(e.exception))

    def test_speech_tier_maps_quality(self):
        self.assertEqual(ac.speech_tier({'quality': 'hd'}), {'tier': 'hd'})
        self.assertEqual(ac.speech_tier({'tier': 'turbo', 'quality': 'hd'}), {'tier': 'turbo'})
        self.assertEqual(ac.speech_tier({'speed': 1}), {})

    def test_gateway_quote_merges_success_rates(self):
        http = FakeHttp([
            ('/v1/pricing-estimate', [Resp(200, {'billing_mode': 'fixed_amount', 'channels': [
                {'vendor': 'APM', 'lane': 'speech-2.8@APM:default', 'effective_total_rmb': 0.05},
                {'vendor': 'OLX', 'lane': 'speech-2.8@OLX:default', 'effective_total_rmb': 0.08}]})]),
            ('/pricing', [Resp(200, {'channel_groups': [{'vendor': 'APM', 'success_rate_24h': 99.4},
                                                         {'vendor': 'OLX', 'success_rate_24h': 66.7}]})])])
        with mock.patch.dict('os.environ', ENV):
            q = ac.provider_of(CFG, 'gw', http).quote('speech-2.8', {'input': 'x'})
        self.assertAlmostEqual(q['channels'][0]['success_rate'], 0.994)
        req = http.calls[0][2]['json']
        self.assertTrue(req['include_all_channels'])


class SpeakTests(Base):
    def lk_http(self, states=('success',)):
        audio = Resp(200, content=b'RIFFfake')
        return FakeHttp([
            ('/v1/media/generate', [Resp(200, {'code': 200, 'data': {'task_id': 101}}),
                                    Resp(200, {'code': 200, 'data': {'task_id': 102}})]),
            ('/v1/media/status', [Resp(200, {'is_final': True, 'state': s, 'result_url': 'https://cdn.example/a.mp3',
                                             'cost': 0.04, 'error': '' if s == 'success' else 'upstream busy'})
                                  for s in states]),
            ('cdn.example', [audio])])

    def test_speak_generates_logs_and_caches(self):
        http = self.lk_http()
        with quiet():
            ac.speak(CFG, self.script, self.edit, confirmed=True, http=http, sleep=lambda s: None)
        self.assertTrue((self.edit / 'tts' / 'S1.wav').exists())
        log = json.loads((self.edit / 'audio_log.json').read_text(encoding='utf-8'))
        self.assertEqual([e['state'] for e in log], ['success', 'success'])
        sent = [c[2]['json']['prompt'] for c in http.calls if c[0] == 'POST']
        self.assertIn('<#0.8#>', sent[1])
        # second run: nothing submitted, nothing charged
        http2 = FakeHttp([])
        with quiet():
            ac.speak(CFG, self.script, self.edit, confirmed=True, http=http2, sleep=lambda s: None)
        self.assertEqual(http2.calls, [])

    def test_pronounce_table_changes_only_sent_text(self):
        (self.edit).mkdir(parents=True)
        (self.edit / 'pronounce.json').write_text(json.dumps({'OPC': 'O P C'}), encoding='utf-8')
        http = self.lk_http()
        with quiet():
            ac.speak(CFG, self.script, self.edit, confirmed=True, http=http, sleep=lambda s: None)
        sent = [c[2]['json']['prompt'] for c in http.calls if c[0] == 'POST']
        self.assertIn('O P C', sent[1])

    def test_requires_confirmed(self):
        with quiet(), self.assertRaises(ac.Refused):
            ac.speak(CFG, self.script, self.edit, confirmed=False, http=FakeHttp([]))

    def test_over_limit_refuses_before_spending(self):
        cfg = json.loads(json.dumps(CFG))
        cfg['providers']['lk']['price']['amount'] = 1.0   # 40+ tokens -> over 10
        http = FakeHttp([])
        with quiet(), self.assertRaises(ac.Refused) as e:
            ac.speak(cfg, self.script, self.edit, confirmed=True, http=http)
        self.assertIn('--max-cost', str(e.exception))
        self.assertEqual(http.calls, [])

    def test_unknown_price_needs_explicit_cap(self):
        cfg = json.loads(json.dumps(CFG))
        del cfg['providers']['lk']['price']
        with quiet(), self.assertRaises(ac.Refused):
            ac.speak(cfg, self.script, self.edit, confirmed=True, http=FakeHttp([]))

    def test_failure_is_reported_not_retried(self):
        http = self.lk_http(states=('success', 'failed'))
        with quiet(), self.assertRaises(ac.Refused) as e:
            ac.speak(CFG, self.script, self.edit, confirmed=True, http=http, sleep=lambda s: None)
        self.assertIn('自动退款', str(e.exception))
        self.assertEqual(sum(1 for c in http.calls if c[0] == 'POST'), 2)   # no third submission

    def test_interrupted_run_resumes_task_instead_of_paying_again(self):
        sent = ac.apply_pronounce('我现在用我的声音克隆。', {})
        key = ac.request_key('lk', 'speech-2.8', 'LK_1', {'quality': 'hd', 'speed': 1}, sent)
        ac.write_log(self.edit, [{'key': key, 'section': 'S1', 'task_id': '77', 'state': 'submitted'}])
        http = self.lk_http()
        with quiet():
            ac.speak(CFG, self.script, self.edit, only=['S1'], confirmed=True, http=http, sleep=lambda s: None)
        self.assertFalse(any(c[0] == 'POST' for c in http.calls))
        polled = [c[2]['params']['task_id'] for c in http.calls if '/v1/media/status' in c[1]]
        self.assertEqual(polled, ['77'])

    def gw_http(self):
        return FakeHttp([
            ('/v1/pricing-estimate', [Resp(200, {'channels': [
                {'vendor': 'OLX', 'lane': 'L-OLX', 'effective_total_rmb': 0.09},
                {'vendor': 'APM', 'lane': 'L-APM', 'effective_total_rmb': 0.05}]})]),
            ('/pricing', [Resp(200, {'channel_groups': []})]),
            ('/v1/audio/speech/async', [Resp(202, {'task_id': 't1'}), Resp(202, {'task_id': 't2'})]),
            ('/v1/tasks/', [Resp(200, {'is_final': True, 'status': 'completed', 'output_url': 'https://cdn.example/x.wav',
                                       'billing': {'actual_cost_credits': 0.05}})]),
            ('cdn.example', [Resp(200, content=b'RIFF')])])

    def test_gateway_pins_cheapest_lane(self):
        http = self.gw_http()
        with quiet():
            ac.speak(CFG, self.script, self.edit, voice='gwme', confirmed=True, http=http, sleep=lambda s: None,
                     no_batch=True)
        subs = [c[2]['json'] for c in http.calls if c[1].endswith('/v1/audio/speech/async')]
        self.assertEqual(len(subs), 2)
        self.assertEqual({s['lane_id'] for s in subs}, {'L-APM'})
        self.assertEqual(subs[0]['voice'], 'omfvc_1')
        self.assertEqual(subs[0]['tier'], 'hd')

    def test_gateway_joins_short_sections_into_one_call_and_cuts_back(self):
        http = self.gw_http()

        def fake_split(wav, members, sr=16000):
            for m in members:
                Path(m['cache']).write_bytes(b'RIFF' + m['section'].encode())
        with quiet(), mock.patch.object(ac, 'split_chunk', fake_split):
            ac.speak(CFG, self.script, self.edit, voice='gwme', confirmed=True, http=http, sleep=lambda s: None)
        subs = [c[2]['json'] for c in http.calls if c[1].endswith('/v1/audio/speech/async')]
        self.assertEqual(len(subs), 1)
        self.assertIn(ac.BATCH_SEP, subs[0]['input'])
        self.assertEqual((self.edit / 'tts' / 'S2.wav').read_bytes(), b'RIFFS2')
        log = json.loads((self.edit / 'audio_log.json').read_text(encoding='utf-8'))
        self.assertEqual(log[0]['members'], ['S1', 'S2'])
        # rerun: every section cached, nothing submitted
        http2 = FakeHttp([])
        with quiet():
            ac.speak(CFG, self.script, self.edit, voice='gwme', confirmed=True, http=http2, sleep=lambda s: None)
        self.assertEqual(http2.calls, [])

    def test_uncuttable_join_is_reported_as_paid_and_not_resubmitted(self):
        http = self.gw_http()

        def bad_split(wav, members, sr=16000):
            raise ac.SplitError('没找到足够的长停顿')
        with quiet(), mock.patch.object(ac, 'split_chunk', bad_split), self.assertRaises(ac.Refused) as e:
            ac.speak(CFG, self.script, self.edit, voice='gwme', confirmed=True, http=http, sleep=lambda s: None)
        self.assertIn('已付费', str(e.exception))
        self.assertIn('--no-batch', str(e.exception))
        http2 = FakeHttp([])
        with quiet(), mock.patch.object(ac, 'split_chunk', bad_split), self.assertRaises(ac.Refused):
            ac.speak(CFG, self.script, self.edit, voice='gwme', confirmed=True, http=http2, sleep=lambda s: None)
        self.assertEqual(http2.calls, [])   # the paid audio is reused for another try, never bought twice


class BatchTests(unittest.TestCase):
    def jobs(self, sizes):
        return [{'section': f'S{k}', 'sent': '字' * n} for k, n in enumerate(sizes, 1)]

    def test_groups_reach_the_minimum_and_tail_joins_last(self):
        groups = ac.batch_groups(self.jobs([80, 90, 60, 250, 30]), 200)
        self.assertEqual([[j['section'] for j in g] for g in groups], [['S1', 'S2', 'S3'], ['S4', 'S5']])

    def test_max_chars_starts_a_new_group(self):
        groups = ac.batch_groups(self.jobs([150, 150, 150]), 200, max_chars=250)
        self.assertEqual([len(g) for g in groups], [1, 1, 1])

    def test_zero_minimum_keeps_one_call_per_section(self):
        self.assertEqual(len(ac.batch_groups(self.jobs([10, 10]), 0)), 2)

    def test_lk_providers_do_not_join_by_default(self):
        self.assertEqual(ac.batch_min_chars(CFG, ac.provider_of(CFG, 'lk')), 0)
        self.assertEqual(ac.batch_min_chars(CFG, ac.provider_of(CFG, 'gw')), 200)
        self.assertEqual(ac.batch_min_chars(CFG, ac.provider_of(CFG, 'gw'), no_batch=True), 0)

    def tone(self, sr, secs):
        import numpy as np
        return np.sin(np.arange(int(sr * secs)) * 0.3).astype(np.float32)

    def test_pause_cuts_pick_the_long_joining_pauses(self):
        import numpy as np
        sr = 1000
        z = lambda s: np.zeros(int(sr * s), np.float32)
        a = np.concatenate([self.tone(sr, 1), z(0.6), self.tone(sr, 1), z(2.1), self.tone(sr, 2), z(2.0), self.tone(sr, 1)])
        cuts = ac.pause_cuts(a, sr, 3)
        self.assertEqual(len(cuts), 2)
        self.assertAlmostEqual(cuts[0], 3.65, delta=0.05)    # the 0.6 s pause inside section 1 is not a cut
        self.assertAlmostEqual(cuts[1], 7.7, delta=0.05)    # centre of the 6.7–8.7 s pause
        self.assertIsNone(ac.pause_cuts(a, sr, 4))

    def test_piece_lengths_must_match_their_text(self):
        ac.check_pieces([(0, 2.0), (3, 7.1)], [10, 20])
        with self.assertRaises(ac.SplitError):
            ac.check_pieces([(0, 6.0), (7, 7.5)], [10, 20])


class PresetTests(Base):
    def test_shipped_presets_are_checked_entries(self):
        rows = ac.load_presets()
        self.assertGreaterEqual(len(rows), 10)
        self.assertTrue(all({'id', 'name', 'gender', 'lang'} <= set(r) for r in rows))
        self.assertIn('male-qn-qingse', {r['id'] for r in rows})
        self.assertTrue(ac.presets(gender='女'))

    def test_audition_quotes_each_voice_and_saves_samples(self):
        http = FakeHttp([
            ('/v1/pricing-estimate', [Resp(200, {'channels': [{'vendor': 'OLX', 'lane': 'L', 'effective_total_rmb': 0.1}]})]),
            ('/pricing', [Resp(200, {'channel_groups': []})]),
            ('/v1/audio/speech/async', [Resp(202, {'task_id': 'a1'}), Resp(202, {'task_id': 'a2'})]),
            ('/v1/tasks/', [Resp(200, {'is_final': True, 'status': 'completed', 'output_url': 'https://cdn.example/s.wav'})]),
            ('cdn.example', [Resp(200, content=b'RIFF')])])
        out = self.tmp / 'aud'
        with quiet():
            got = ac.audition(CFG, 'gw', ['male-qn-qingse', 'female-tianmei'], out, confirmed=True, http=http,
                              sleep=lambda s: None)
        self.assertEqual(got, ['male-qn-qingse', 'female-tianmei'])
        voices = [c[2]['json']['voice'] for c in http.calls if c[1].endswith('/v1/audio/speech/async')]
        self.assertEqual(voices, ['male-qn-qingse', 'female-tianmei'])

    def test_register_preset_needs_yes_and_skips_account_lookup(self):
        path = self.tmp / 'backends.local.json'
        http = FakeHttp([])
        with quiet(), self.assertRaises(ac.Refused):
            ac.register(CFG, '旁白', 'gw', preset='male-qn-qingse', http=http, path=path)
        with quiet():
            ac.register(CFG, '旁白', 'gw', preset='male-qn-qingse', yes=True, http=http, path=path)
        entry = json.loads(path.read_text(encoding='utf-8'))['audio']['voice']['voices']['旁白']
        self.assertEqual(entry['voice_id'], 'male-qn-qingse')
        self.assertTrue(entry['preset'])
        self.assertEqual(http.calls, [])

    def test_no_voice_message_points_to_library_then_presets(self):
        with self.assertRaises(ac.Refused) as e:
            ac.pick_voice({'providers': {}})
        self.assertIn('voice list', str(e.exception))
        self.assertIn('voice presets', str(e.exception))


class SetupTests(Base):
    def test_setup_writes_defaults_keeps_existing_and_never_the_key(self):
        path = self.tmp / 'backends.local.json'
        path.write_text(json.dumps({'refs': {'dir': 'x'}, 'audio': {'budget': {'confirm_over': 10}}}), encoding='utf-8')
        lines = []
        with mock.patch.dict('os.environ', {'VVAI_API_KEY': 'sk-secret'}):
            with self.assertRaises(ac.Refused):
                ac.setup(path, out=lines.append)
            ac.setup(path, yes=True, out=lines.append)
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data['refs'], {'dir': 'x'})
        self.assertEqual(data['audio']['budget'], {'confirm_over': 10})
        self.assertEqual(data['audio']['providers']['vvai']['key_env'], 'VVAI_API_KEY')
        self.assertEqual(data['image']['defaults'], {'resolution': '4K', 'quality': 'high'})
        self.assertNotIn('sk-secret', path.read_text(encoding='utf-8'))
        self.assertNotIn('sk-secret', '\n'.join(lines))

    def test_setup_without_key_explains_how_to_set_it(self):
        lines = []
        with mock.patch.dict('os.environ', {}, clear=True):
            ac.setup(self.tmp / 'b.json', yes=True, out=lines.append)
        text = '\n'.join(lines)
        self.assertIn('key_setup.py', text)
        self.assertIn('setx VVAI_API_KEY', text)
        self.assertIn('不要发到聊天', text)


class RateLimitTests(unittest.TestCase):
    def test_429_waits_then_succeeds(self):
        waits = []
        http = FakeHttp([('/x', [Resp(429, {}, headers={'Retry-After': '2'}), Resp(200, {'ok': 1})])])
        r = ac.call(http, 'get', 'https://h/x', headers={}, sleep=waits.append)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(waits, [2.0])


class RegisterTests(Base):
    def test_register_needs_yes_then_writes(self):
        http = FakeHttp([('/v1/skills/voices', [Resp(200, {'voices': [
            {'voice_id': 'LK_9', 'name': 'VV', 'status': 'active', 'is_permanent': True}]})])])
        path = self.tmp / 'backends.local.json'
        path.write_text(json.dumps({'refs': {'dir': 'x'}}), encoding='utf-8')
        with quiet(), self.assertRaises(ac.Refused):
            ac.register(CFG, 'VV', 'lk', http=http, path=path)
        with quiet():
            ac.register(CFG, 'VV', 'lk', owner='本人', yes=True, http=http, path=path)
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data['refs'], {'dir': 'x'})               # other settings untouched
        self.assertEqual(data['audio']['voice']['voices']['VV']['voice_id'], 'LK_9')
        self.assertNotIn('activation_pending', data['audio']['voice']['voices']['VV'])

    def test_register_unknown_lists_account_voices(self):
        http = FakeHttp([('/v1/audio/voices', [Resp(200, {'data': [{'id': 'omfvc_2', 'name': '小林', 'status': 'ready'}]})])])
        with quiet(), self.assertRaises(ac.Refused) as e:
            ac.register(CFG, 'VV', 'gw', http=http, path=self.tmp / 'b.json')
        self.assertIn('小林', str(e.exception))


class DoctorTests(unittest.TestCase):
    def test_missing_key_reported_without_value(self):
        lines = []
        with mock.patch.dict('os.environ', {'GW_KEY': 'secret-value'}, clear=True):
            ok = ac.doctor(CFG, http=FakeHttp([('/v1/audio/voices', [Resp(200, {'data': []})])]), out=lines.append)
        text = '\n'.join(lines)
        self.assertFalse(ok)
        self.assertIn('LK_KEY', text)
        self.assertNotIn('secret-value', text)

    def test_no_config_points_to_recording(self):
        lines = []
        self.assertFalse(ac.doctor({}, out=lines.append))
        self.assertIn('自己录音', lines[0])


class AlignTests(unittest.TestCase):
    def test_matching_and_homophone_interpolation(self):
        words = [{'text': '我们', 'start': 0.0, 'end': 0.4}, {'text': '艺人', 'start': 0.4, 'end': 0.8},
                 {'text': '公司', 'start': 0.8, 'end': 1.2}]
        times, suspects, _ = ac.align_section('我们一人公司。', words, (0.0, 1.3))
        self.assertAlmostEqual(times[0][0], 0.0)
        self.assertEqual([round(x, 2) for x in times[2]], [0.4, 0.6])   # 一 fills the gap before the matched 人
        self.assertAlmostEqual(times[3][0], 0.6)
        self.assertEqual(suspects, [{'text': '一', 'start': 0.4, 'end': 0.6, 'idx': (2, 3)}])

    def test_vowel_peaks_place_unheard_syllables(self):
        words = [{'text': '开始', 'start': 0.0, 'end': 0.5}]
        times, _, _ = ac.align_section('开始四是四', words, (0.0, 1.4), syllables=[0.6, 0.9, 1.2])
        self.assertEqual([round(t[0], 2) for t in times[2:]], [0.6, 0.9, 1.2])

    def test_english_words_spread_to_letters(self):
        words = [{'text': ' After', 'start': 1.0, 'end': 1.5}, {'text': ' the', 'start': 1.5, 'end': 1.7}]
        times, suspects, _ = ac.align_section('After the', words, (0.0, 2.0))
        self.assertEqual(times[0], (1.0, 1.5))
        self.assertEqual(times[5], (1.5, 1.7))
        self.assertEqual(suspects, [])

    def test_voiced_chunks_split_on_long_quiet(self):
        import numpy as np
        sr = 1000
        tone = np.sin(np.arange(sr) * 0.3).astype(np.float32)
        a = np.concatenate([tone, np.zeros(sr, np.float32), tone])
        chunks = ac.voiced_chunks(a, sr)
        self.assertEqual(len(chunks), 2)
        self.assertLess(chunks[0][1], 1.2)
        self.assertGreater(chunks[1][0], 1.8)

    def test_breath_blips_are_dropped(self):
        import numpy as np
        sr = 1000
        a = np.zeros(3 * sr, np.float32)
        a[100:200] = np.sin(np.arange(100) * 0.3)        # 0.1 s breath
        a[1000:2000] = np.sin(np.arange(1000) * 0.3)     # 1 s of speech
        self.assertEqual(len(ac.voiced_chunks(a, sr)), 1)


class HardChunkTests(unittest.TestCase):
    def test_fit_peaks_drops_weakest_split_vowel(self):
        peaks = [(0.1, -1), (0.4, -2), (0.55, -9), (0.8, -1)]
        self.assertEqual(ac.fit_peaks(peaks, 3), [0.1, 0.4, 0.8])
        self.assertIsNone(ac.fit_peaks(peaks, 1))

    def test_unfollowed_chinese_chunk_moves_to_peaks(self):
        import numpy as np
        sr = 1000
        a = np.zeros(sr * 2, np.float32)
        for start in (200, 600, 1000, 1400):
            a[start:start + 150] = np.sin(np.arange(150) * 0.5)
        times = [(0.0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4)]   # ASR-shaped nonsense
        placed = ac.refine_chunks('四是四十', times, [True, False, False, False], [(0.0, 2.0)], a, sr)
        self.assertEqual(placed, [(0.0, 2.0, [0, 1, 2, 3])])
        self.assertEqual([round(t[0], 2) for t in times], [0.12, 0.52, 0.92, 1.32])


class ChunkOnsetTests(unittest.TestCase):
    def test_first_character_snaps_to_chunk_onset(self):
        import numpy as np
        a = np.zeros(4000, np.float32)   # silence: no vowel peaks, so only the onset rule applies
        times = [(1.6, 1.8), (1.8, 2.0)]
        ac.refine_chunks('AB', times, [True, True], [(0.95, 2.5)], a, 1000)
        self.assertAlmostEqual(times[0][0], 1.0)
        self.assertEqual(times[1], (1.8, 2.0))

    def test_characters_in_a_gap_join_the_next_chunk(self):
        members = ac.chunk_members([(0.1, 0.2), (1.2, 1.3), (2.1, 2.2)], [(0.0, 1.0), (2.0, 3.0)])
        self.assertEqual(members, [[0], [1, 2]])


class MusicTests(Base):
    def gw_http(self, status='completed'):
        done = {'is_final': True, 'status': status, 'billing': {'actual_cost_credits': 0.62},
                'error': None if status == 'completed' else {'message': 'upstream busy'},
                'result': {'audios': [{'url': 'https://cdn.example/a.mp3'}, {'url': 'https://cdn.example/b.mp3'}]}}
        return FakeHttp([
            ('/v1/pricing-estimate', [Resp(200, {'channels': [
                {'vendor': 'MXH', 'lane': 'music@MXH', 'effective_total_rmb': 0.93},
                {'vendor': 'APM', 'lane': 'music@APM', 'effective_total_rmb': 0.65}]})]),
            ('/pricing', [Resp(200, {'channel_groups': [{'vendor': 'APM', 'success_rate_24h': 99.4},
                                                         {'vendor': 'MXH', 'success_rate_24h': 33.3}]})]),
            ('/v1/media/generate', [Resp(200, {'code': 200, 'data': {'task_id': 'task-9'}})]),
            ('/v1/tasks/', [Resp(200, {'is_final': False, 'status': 'processing'}), Resp(200, done)]),
            ('cdn.example', [Resp(200, content=b'ID3')])])

    def test_generate_pins_cheapest_downloads_both_and_records_license(self):
        http = self.gw_http()
        with quiet():
            rec = ac.generate_music(CFG, self.edit, '轻快的综艺配乐', style='playful, ukulele', confirmed=True,
                                    http=http, sleep=lambda s: None, check=False)
        sub = next(c[2]['json'] for c in http.calls if c[1].endswith('/v1/media/generate'))
        self.assertEqual(sub['params']['lane_id'], 'music@APM')
        self.assertEqual(sub['params']['mode'], 'instrumental')
        self.assertIn('vocals', sub['params']['negative_tags'])
        self.assertEqual(rec['files'], ['bgm_A.mp3', 'bgm_B.mp3'])
        self.assertTrue((self.edit / 'music' / 'bgm_B.mp3').exists())
        self.assertEqual(rec['license'], '用户确认可商用')
        # same request again: reused, nothing submitted
        http2 = FakeHttp([])
        with quiet():
            ac.generate_music(CFG, self.edit, '轻快的综艺配乐', style='playful, ukulele', confirmed=True, http=http2,
                              check=False)
        self.assertEqual(http2.calls, [])

    def test_failure_lists_alternatives_without_retry(self):
        http = self.gw_http(status='failed')
        with quiet(), self.assertRaises(ac.Refused) as e:
            ac.generate_music(CFG, self.edit, 'x', confirmed=True, http=http, sleep=lambda s: None, check=False)
        self.assertIn('MXH', str(e.exception))
        self.assertIn('自动退款', str(e.exception))
        self.assertEqual(sum(1 for c in http.calls if c[1].endswith('/v1/media/generate')), 1)

    def test_success_after_a_failed_attempt_is_reused(self):
        with quiet(), self.assertRaises(ac.Refused):
            ac.generate_music(CFG, self.edit, 'x', confirmed=True, http=self.gw_http(status='failed'),
                              sleep=lambda s: None, check=False)
        with quiet():
            ac.generate_music(CFG, self.edit, 'x', confirmed=True, http=self.gw_http(), sleep=lambda s: None, check=False)
        http3 = FakeHttp([])
        with quiet():
            ac.generate_music(CFG, self.edit, 'x', confirmed=True, http=http3, check=False)
        self.assertEqual(http3.calls, [])   # reads the newest attempt, not the old failure

    def test_no_music_provider_refuses(self):
        with self.assertRaises(ac.Refused):
            ac.generate_music({'providers': {}}, self.edit, 'x', confirmed=True)

    def test_over_limit_refuses(self):
        cfg = json.loads(json.dumps(CFG))
        cfg['budget']['confirm_over'] = 0.5
        http = self.gw_http()
        with quiet(), self.assertRaises(ac.Refused):
            ac.generate_music(cfg, self.edit, 'x', confirmed=True, http=http, check=False)
        self.assertFalse(any(c[1].endswith('/v1/media/generate') for c in http.calls))


class FitPlanTests(unittest.TestCase):
    def test_long_track_is_one_cut(self):
        self.assertEqual(ac.fit_plan(72.0, 29.6, 0.2, 10.0), [(0.2, 29.8)])

    def test_short_track_loops_from_loop_point(self):
        pieces = ac.fit_plan(20.0, 45.0, 0.0, 8.0, xfade=1.0)
        self.assertEqual(pieces[0], (0.0, 20.0))
        self.assertTrue(all(p[0] == 8.0 for p in pieces[1:]))
        total = sum(b - a for a, b in pieces) - 1.0 * (len(pieces) - 1)
        self.assertGreaterEqual(total, 45.0)

    def test_mix_graph_ducks_music_under_voice(self):
        g = ac.mix_graph(-11, 6, 40, 350, 0.03)
        self.assertIn('volume=-11dB', g)
        self.assertIn('sidechaincompress', g)
        self.assertIn('[m][sc]', g)


class ShippedExampleTests(unittest.TestCase):
    def test_example_config_has_placeholders_only(self):
        text = (ac.SKILL_ROOT / 'backends.local.example.json').read_text(encoding='utf-8')
        self.assertIsNone(re.search(r'sk-[A-Za-z0-9]{8}|LK_\d|omfvc_[a-z0-9]', text))   # no keys or voice ids
        hosts = re.findall(r'https?://([^/"]+)', text)
        self.assertTrue(hosts and all(h.endswith('example.com') for h in hosts), hosts)   # placeholder hosts only
        self.assertIn('"audio"', text)


if __name__ == '__main__':
    unittest.main()
