"""Tests of transcribe_cloud with recorded-shape responses and a fake HTTP client (no network, no account)."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import transcribe_cloud as tc

PACK = Path(__file__).resolve().parents[2] / 'video-use' / 'helpers' / 'pack_transcripts.py'

# Shapes follow the official examples (Azure fast transcription 2025-10-15, Fun-ASR file transcription).
AZURE = {'durationMilliseconds': 4200,
         'combinedPhrases': [{'text': '今天讲剪辑。先看口播。'}],
         'phrases': [
             {'offsetMilliseconds': 300, 'durationMilliseconds': 1200, 'text': '今天讲剪辑。', 'locale': 'zh-CN',
              'confidence': 0.9, 'speaker': 1,
              'words': [{'text': '今天', 'offsetMilliseconds': 300, 'durationMilliseconds': 400},
                        {'text': '讲', 'offsetMilliseconds': 700, 'durationMilliseconds': 200},
                        {'text': '剪辑', 'offsetMilliseconds': 900, 'durationMilliseconds': 600}]},
             {'offsetMilliseconds': 2600, 'durationMilliseconds': 1000, 'text': '先看口播。', 'locale': 'zh-CN',
              'confidence': 0.9, 'speaker': 2,
              'words': [{'text': '先看', 'offsetMilliseconds': 2600, 'durationMilliseconds': 400},
                        {'text': '口播', 'offsetMilliseconds': 3000, 'durationMilliseconds': 600}]}]}

FUNASR = {'properties': {'original_duration_in_milliseconds': 4200},
          'transcripts': [{'channel_id': 0, 'text': '今天讲剪辑。先看口播。', 'sentences': [
              {'begin_time': 300, 'end_time': 1500, 'text': '今天讲剪辑。', 'sentence_id': 1, 'words': [
                  {'begin_time': 300, 'end_time': 700, 'text': '今天', 'punctuation': ''},
                  {'begin_time': 700, 'end_time': 900, 'text': '讲', 'punctuation': ''},
                  {'begin_time': 900, 'end_time': 1500, 'text': '剪辑', 'punctuation': '。'}]},
              {'begin_time': 2600, 'end_time': 3600, 'text': '先看口播。', 'sentence_id': 2, 'words': [
                  {'begin_time': 2600, 'end_time': 3000, 'text': '先看', 'punctuation': ''},
                  {'begin_time': 3000, 'end_time': 3600, 'text': '口播', 'punctuation': '。'}]}]}]}


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.text = json.dumps(body)

    def json(self):
        return self._body


class FakeHttp:
    """Answers by URL substring, in order; records calls."""
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


def words_only(payload):
    return [w for w in payload['words'] if w['type'] == 'word']


class ConvertTests(unittest.TestCase):
    def test_azure_words_seconds_speakers_and_punctuation(self):
        p = tc.azure_payload(AZURE)
        w = words_only(p)
        self.assertEqual([x['text'] for x in w], ['今天', '讲', '剪辑。', '先看', '口播。'])
        self.assertEqual((w[0]['start'], w[0]['end']), (0.3, 0.7))
        self.assertEqual({x['speaker_id'] for x in w}, {'speaker_1', 'speaker_2'})
        gap = [x for x in p['words'] if x['type'] == 'spacing']
        self.assertEqual((gap[0]['start'], gap[0]['end']), (1.5, 2.6))
        self.assertEqual(p['language_code'], 'zh-CN')

    def test_funasr_words_keep_their_punctuation(self):
        p = tc.funasr_payload(FUNASR, 'fun-asr', 'zh')
        self.assertEqual([x['text'] for x in words_only(p)], ['今天', '讲', '剪辑。', '先看', '口播。'])
        self.assertEqual(p['engine'], 'dashscope:fun-asr')

    def test_attach_punct_gives_up_when_text_does_not_line_up(self):
        ws = [{'text': 'hello'}, {'text': 'world'}]
        self.assertEqual(tc.attach_punct('Hello, world!', ws), [{'text': 'hello,'}, {'text': 'world!'}])
        self.assertIs(tc.attach_punct('something else', ws), ws)

    @unittest.skipUnless(PACK.exists(), 'video-use not next to xumu')
    def test_video_use_packer_reads_the_output(self):
        spec = importlib.util.spec_from_file_location('pack_transcripts', PACK)
        pack = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pack)
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'take.json'
            f.write_text(json.dumps(tc.funasr_payload(FUNASR, 'fun-asr'), indent=2), encoding='ascii')
            _, duration, phrases = pack.pack_one_file(f, 0.5)
        self.assertEqual([p['text'].replace(' ', '') for p in phrases], ['今天讲剪辑。', '先看口播。'])   # it space-joins tokens
        self.assertAlmostEqual(duration, 3.3)


class EngineTests(unittest.TestCase):
    def test_azure_request(self):
        http = FakeHttp([('transcriptions:transcribe', [Resp(200, AZURE)])])
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(b'RIFF')
        p = tc.call_azure(f.name, 'zh', 2, http, environ={'AZURE_SPEECH_KEY': 'k', 'AZURE_SPEECH_REGION': 'eastasia'})
        Path(f.name).unlink()
        method, url, kw = http.calls[0]
        self.assertEqual(url, 'https://eastasia.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe')
        self.assertEqual(kw['params'], {'api-version': tc.AZURE_API_VERSION})
        definition = json.loads(kw['files']['definition'][1])
        self.assertEqual(definition, {'locales': ['zh-CN'], 'diarization': {'enabled': True, 'maxSpeakers': 2}})
        self.assertEqual(len(words_only(p)), 5)

    def test_funasr_with_url_polls_until_done(self):
        http = FakeHttp([
            ('/services/audio/asr/transcription', [Resp(200, {'output': {'task_id': 't1', 'task_status': 'PENDING'}})]),
            ('/api/v1/tasks/t1', [Resp(200, {'output': {'task_status': 'RUNNING'}}),
                                  Resp(200, {'output': {'task_status': 'SUCCEEDED', 'results': [
                                      {'subtask_status': 'SUCCEEDED', 'transcription_url': 'https://r.example/x.json'}]}})]),
            ('r.example', [Resp(200, FUNASR)])])
        slept = []
        p = tc.call_funasr('a.mp3', 'zh-CN', None, http, audio_url='https://my.example/a.mp3',
                           environ={'DASHSCOPE_API_KEY': 'k'}, sleep=slept.append)
        submit = http.calls[0][2]
        self.assertTrue(http.calls[0][1].startswith(tc.DASHSCOPE_DEFAULT))
        self.assertEqual(submit['json']['parameters'], {'language_hints': ['zh']})
        self.assertNotIn('X-DashScope-OssResourceResolve', submit['headers'])
        self.assertEqual(slept, [3.0])
        self.assertEqual(len(words_only(p)), 5)

    def test_funasr_temporary_upload_marks_oss_url(self):
        policy = {'data': {'upload_dir': 'dir', 'upload_host': 'https://oss.example', 'oss_access_key_id': 'a',
                           'signature': 's', 'policy': 'p', 'x_oss_object_acl': 'private', 'x_oss_forbid_overwrite': 'true'}}
        http = FakeHttp([('/api/v1/uploads', [Resp(200, policy)]), ('oss.example', [Resp(200, {})]),
                         ('/services/audio/asr/transcription', [Resp(200, {'output': {'task_id': 't2'}})]),
                         ('/api/v1/tasks/t2', [Resp(200, {'output': {'task_status': 'FAILED', 'results': [
                             {'subtask_status': 'FAILED', 'code': 'X', 'message': 'bad audio'}]}})])])
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / 'a.mp3'
            audio.write_bytes(b'ID3')
            with self.assertRaisesRegex(RuntimeError, 'bad audio'):
                tc.call_funasr(audio, None, None, http, environ={'DASHSCOPE_API_KEY': 'k'}, sleep=lambda s: None)
        submit = http.calls[2][2]
        self.assertEqual(submit['json']['input']['file_urls'], ['oss://dir/a.mp3'])
        self.assertEqual(submit['headers']['X-DashScope-OssResourceResolve'], 'enable')
        self.assertEqual(submit['json']['parameters'], {})

    def test_funasr_upload_refused_points_to_audio_url(self):
        http = FakeHttp([('/api/v1/uploads', [Resp(403, {'message': 'region'})])])
        with self.assertRaisesRegex(RuntimeError, '--audio-url'):
            tc.call_funasr('a.mp3', None, None, http, environ={'DASHSCOPE_API_KEY': 'k'})


class EstimateTests(unittest.TestCase):
    def test_costs_and_readiness_from_env_presence(self):
        est = tc.estimate(1800, environ={'DASHSCOPE_API_KEY': 'x', 'AZURE_SPEECH_KEY': 'y'}, scribe_env_file=False)
        rows = {r['engine']: r for r in est['rows']}
        self.assertTrue(rows['funasr']['ready'])
        self.assertFalse(rows['azure']['ready'])   # region or endpoint missing
        self.assertFalse(rows['elevenlabs']['ready'])
        self.assertEqual(rows['elevenlabs']['usd'], 0.11)
        self.assertEqual(rows['funasr']['usd'], 0.063)
        self.assertIsNone(rows['azure']['usd'])
        text = tc.estimate_text(est)
        self.assertIn('见官网', text)
        self.assertNotIn('x', ''.join(r['how'] for r in est['rows']))

    def test_video_use_env_key_is_flagged(self):
        est = tc.estimate(60, environ={}, scribe_env_file=True)
        self.assertTrue(next(r for r in est['rows'] if r['engine'] == 'elevenlabs')['ready'])
        self.assertIn('付费的 Scribe', est['notes'][0])
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / '.env'
            env.write_text('ELEVENLABS_API_KEY=\n', encoding='utf-8')
            self.assertFalse(tc.video_use_env_has_key(env))
            env.write_text('# x\nELEVENLABS_API_KEY="abc"\n', encoding='utf-8')
            self.assertTrue(tc.video_use_env_has_key(env))

    def test_run_needs_confirmation_and_keeps_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'edit' / 'transcripts' / 'take.json'
            out.parent.mkdir(parents=True)
            out.write_text('{}', encoding='ascii')
            a = argparse.Namespace(media=str(Path(tmp) / 'take.mp4'), edit=str(Path(tmp) / 'edit'), force=False,
                                   confirmed=False, engine='azure')
            self.assertEqual(tc.run(a, http=object()), 0)   # cached: no estimate, no upload
            self.assertEqual(out.read_text(encoding='ascii'), '{}')


class FakeSeg:
    def __init__(self, text, end, words):
        self.text, self.end = text, end
        self.words = [type('W', (), {'word': w, 'start': s, 'end': e, 'probability': 0.9})() for w, s, e in words]


class FakeWhisper:
    """The faster-whisper shape: transcribe() -> (segments, info)."""
    calls = []

    def __init__(self, model):
        self.model = model

    def transcribe(self, path, **kw):
        FakeWhisper.calls.append((path, kw))
        segs = [FakeSeg('今天讲剪辑。', 1.5, [(' 今天', 0.3, 0.7), ('讲', 0.7, 0.9), ('剪辑。', 0.9, 1.5)]),
                FakeSeg('先看口播。', 3.6, [('先看', 2.6, 3.0), ('口播。', 3.0, 3.6)])]
        return iter(segs), type('I', (), {'language': 'zh'})()


class LocalEngineTests(unittest.TestCase):
    def test_local_payload_has_scribe_shape_and_uploads_nothing(self):
        FakeWhisper.calls.clear()
        payload = tc.call_local('x.wav', None, 'small', loader=FakeWhisper, out=lambda *a, **k: None)
        self.assertEqual(payload['engine'], 'faster-whisper:small')
        self.assertEqual(payload['language_code'], 'zh')
        self.assertEqual(payload['text'], '今天讲剪辑。先看口播。')
        words = [w for w in payload['words'] if w['type'] == 'word']
        self.assertEqual([w['text'] for w in words], ['今天', '讲', '剪辑。', '先看', '口播。'])
        self.assertEqual(words[0]['start'], 0.3)
        self.assertTrue(FakeWhisper.calls[0][1]['word_timestamps'])

    def test_estimate_lists_local_with_a_time_estimate(self):
        est = tc.estimate(600, environ={'VV_WHISPER_MODEL': 'medium'}, scribe_env_file=False)
        row = next(r for r in est['rows'] if r['engine'] == 'local')
        self.assertEqual(row['model'], 'medium')
        self.assertEqual(row['minutes'], 8.0)
        self.assertEqual(row['usd'], 0)
        self.assertIn('预计约 8.0 分钟', tc.estimate_text(est))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg not on PATH')
    def test_run_local_writes_a_transcript_without_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            media = Path(d) / 'talk.wav'
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=4',
                            '-ac', '1', '-ar', '16000', str(media)], check=True)
            args = argparse.Namespace(media=str(media), edit=d, engine='local', confirmed=False, language=None,
                                      speakers=None, audio_url=None, model='fun-asr', whisper_model='small',
                                      loader=FakeWhisper, force=False)
            with mock.patch.object(tc, 'local_available', lambda: True):
                self.assertEqual(tc.run(args), 0)
            out = Path(d) / 'transcripts' / 'talk.json'
            payload = json.loads(out.read_text(encoding='ascii'))
            self.assertEqual(payload['engine'], 'faster-whisper:small')
            self.assertEqual(payload['duration'], 4.0)

if __name__ == '__main__':
    unittest.main()
