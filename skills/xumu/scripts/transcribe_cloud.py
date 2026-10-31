#!/usr/bin/env python3
"""Cloud transcription engines beyond Video Use's built-in ElevenLabs Scribe, plus a cost estimate for all engines.

  python transcribe_cloud.py estimate <media...> [--json]
  python transcribe_cloud.py run --engine azure|funasr <media> --edit <edit> --confirmed [--language zh] [--speakers N]
                                 [--audio-url URL] [--model fun-asr] [--force]

`run` writes a Scribe-shaped transcript (words[] of type word/spacing with start/end seconds and speaker_id) to
<edit>/transcripts/<stem>.json, the same file Video Use's transcribe.py writes. Video Use then treats it as cached, and
pack_transcripts.py and voice_edit.py read it unchanged. Uploading audio costs money and sends it to a third party, so
`run` refuses to start without --confirmed: show the user `estimate` first and pass it only after they agree.

Engines (API details checked against the official docs on 2026-10-20; prices change, confirm on the pricing page):
  azure   Azure AI Speech fast transcription, synchronous, local file upload (< 5 h, < 500 MB).
          AZURE_SPEECH_KEY + AZURE_SPEECH_ENDPOINT (https://<resource>.cognitiveservices.azure.com) or AZURE_SPEECH_REGION.
  funasr  Alibaba Cloud Model Studio Fun-ASR file transcription, asynchronous. DASHSCOPE_API_KEY; host from
          DASHSCOPE_BASE_URL (default the international https://dashscope-intl.aliyuncs.com). The API takes a URL, not a
          file: pass --audio-url, or the script tries Model Studio's temporary upload (oss://, 48 h), which the docs list
          for the Beijing region only.
Neither cloud engine has been run against a live account from this repo yet; report the first real run's result.
"""
import argparse
import array
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import wave

for _stream in (sys.stdout, sys.stderr):   # Windows pipes default to the ANSI code page; the agent reads UTF-8
    if hasattr(_stream, 'reconfigure'):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            pass

AZURE_API_VERSION = '2025-10-15'
DASHSCOPE_DEFAULT = 'https://dashscope-intl.aliyuncs.com'
PUNCT = set('，。！？、；：,.!?;:…"\'“”‘’）)】」』》')
VIDEO_USE_ENV = Path(__file__).resolve().parents[2] / 'video-use' / '.env'

# usd_per_hour None = not published as a single rate; the estimate then points to the pricing page.
ENGINES = {
    'local': {'name': '本地 faster-whisper', 'env': [], 'upload': False, 'usd_per_hour': 0.0,
              'how': 'Video Use transcribe.py（未设置 ElevenLabs 密钥时）；先跑 setup_env.py --check 做冒烟测试'},
    'elevenlabs': {'name': 'ElevenLabs Scribe', 'env': ['ELEVENLABS_API_KEY'], 'upload': True, 'usd_per_hour': 0.22,
                   'how': 'Video Use transcribe.py', 'pricing': 'https://elevenlabs.io/pricing/api'},
    'azure': {'name': 'Azure 快速转录', 'env': ['AZURE_SPEECH_KEY', 'AZURE_SPEECH_ENDPOINT|AZURE_SPEECH_REGION'],
              'upload': True, 'usd_per_hour': None, 'how': 'transcribe_cloud.py run --engine azure',
              'pricing': 'https://azure.microsoft.com/pricing/details/speech/'},
    'funasr': {'name': '阿里云 Fun-ASR（国际版）', 'env': ['DASHSCOPE_API_KEY'], 'upload': True, 'usd_per_hour': 0.126,
               'how': 'transcribe_cloud.py run --engine funasr',
               'pricing': 'https://www.alibabacloud.com/help/en/model-studio/fun-asr'},
}


# ------------------------------------------------------------------ environment and estimate
def env_ready(engine, environ=os.environ):
    """True when every required variable (a|b = either one) is set. Only presence is checked, never printed."""
    return all(any(environ.get(v) for v in group.split('|')) for group in ENGINES[engine]['env'])


def video_use_env_has_key(path=VIDEO_USE_ENV):
    """Video Use reads ELEVENLABS_API_KEY from its own .env before the environment, so a key there means paid Scribe."""
    try:
        return any(line.split('=', 1)[0].strip() == 'ELEVENLABS_API_KEY' and line.split('=', 1)[1].strip()
                   for line in path.read_text(encoding='utf-8', errors='replace').splitlines() if '=' in line)
    except OSError:
        return False


def media_seconds(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                         capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        raise SystemExit(f'ffprobe could not read the duration of {path}')


def estimate(seconds, environ=os.environ, scribe_env_file=None):
    hours = seconds / 3600
    scribe_file = video_use_env_has_key() if scribe_env_file is None else scribe_env_file
    rows = []
    for key, e in ENGINES.items():
        ready = env_ready(key, environ) or (key == 'elevenlabs' and scribe_file)
        cost = None if e['usd_per_hour'] is None else round(e['usd_per_hour'] * hours, 3)
        rows.append({'engine': key, 'name': e['name'], 'ready': ready, 'uploads': e['upload'], 'usd': cost,
                     'usd_per_hour': e['usd_per_hour'], 'how': e['how'], 'pricing': e.get('pricing')})
    notes = []
    if scribe_file:
        notes.append('video-use/.env 里有 ELEVENLABS_API_KEY：直接跑 Video Use 转录会走付费的 Scribe，即使环境变量没设。')
    return {'seconds': round(seconds, 1), 'rows': rows, 'notes': notes}


def estimate_text(est):
    lines = [f'总时长 {est["seconds"] / 60:.1f} 分钟。价格为 2026-10-20 核对的公开单价，以官网为准。', '',
             '| 引擎 | 可用 | 上传音频 | 预估费用 | 怎么跑 |', '|---|---|---|---|---|']
    for r in est['rows']:
        if r['usd'] is None:
            cost = f'见官网 {r["pricing"]}'
        elif r['usd'] == 0:
            cost = '免费'
        else:
            amount = '不到 $0.01' if r['usd'] < 0.01 else '约 $%.2f' % r['usd']
            cost = f'{amount}（${r["usd_per_hour"]}/小时）'
        ready = '冒烟测试后才知道' if r['engine'] == 'local' else '是' if r['ready'] else '否'
        lines.append(f'| {r["name"]} | {ready} | {"是" if r["uploads"] else "否"} | {cost} | {r["how"]} |')
    lines += [''] + [f'注意：{n}' for n in est['notes']]
    return '\n'.join(lines).rstrip() + '\n'


# ------------------------------------------------------------------ audio
def extract_audio(src, dest, codec_args):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(src), '-map', '0:a:0', '-vn', '-ac', '1',
                    '-ar', '16000', *codec_args, str(dest)], check=True)


def peak_dbfs(wav_path):
    peak = 0
    with wave.open(str(wav_path), 'rb') as w:
        while frames := w.readframes(1 << 16):
            samples = array.array('h', frames)
            peak = max(peak, max(samples), -min(samples))
    return 20 * math.log10(peak / 32768) if peak > 0 else float('-inf')


# ------------------------------------------------------------------ response -> Scribe-shaped words
def attach_punct(text, words):
    """Cloud word lists often drop the punctuation the phrase text has; voice_edit.py reads pauses from a word's
    trailing punctuation, so copy it back. Leaves the words untouched when they do not line up with the text."""
    out, pos = [], 0
    for w in words:
        t = w['text']
        while pos < len(text) and (text[pos].isspace() or text[pos] in PUNCT):
            pos += 1
        if text[pos:pos + len(t)].lower() != t.lower():
            return words
        pos += len(t)
        tail = ''
        while pos < len(text) and text[pos] in PUNCT:
            tail += text[pos]
            pos += 1
        out.append({**w, 'text': t + tail})
    return out


def with_spacing(words):
    """Insert Scribe-style spacing entries in the gaps between consecutive words."""
    out, prev = [], None
    for w in words:
        if prev is not None and w['start'] > prev['end']:
            out.append({'text': ' ', 'start': prev['end'], 'end': w['start'], 'type': 'spacing',
                        'speaker_id': w['speaker_id']})
        out.append(w)
        prev = w
    return out


def azure_payload(resp, language=None):
    words = []
    for ph in resp.get('phrases', []):
        spk = f'speaker_{ph["speaker"]}' if 'speaker' in ph else 'speaker_0'
        ws = [{'text': w['text'], 'start': round(w['offsetMilliseconds'] / 1000, 3),
               'end': round((w['offsetMilliseconds'] + w['durationMilliseconds']) / 1000, 3), 'type': 'word',
               'speaker_id': spk} for w in ph.get('words', [])]
        words += attach_punct(ph.get('text', ''), ws)
    text = ' '.join(p.get('text', '') for p in resp.get('combinedPhrases', []))
    locale = next((p.get('locale') for p in resp.get('phrases', []) if p.get('locale')), language)
    return {'language_code': locale, 'text': text, 'words': with_spacing(words),
            'engine': f'azure-fast-transcription:{AZURE_API_VERSION}'}


def funasr_payload(result, model, language=None):
    words, texts = [], []
    for tr in result.get('transcripts', []):
        texts.append(tr.get('text', ''))
        for s in tr.get('sentences', []):
            spk = f'speaker_{s["speaker_id"]}' if 'speaker_id' in s else 'speaker_0'
            for w in s.get('words', []):
                words.append({'text': w['text'] + (w.get('punctuation') or ''), 'start': round(w['begin_time'] / 1000, 3),
                              'end': round(w['end_time'] / 1000, 3), 'type': 'word', 'speaker_id': spk})
    return {'language_code': language, 'text': ''.join(texts), 'words': with_spacing(words), 'engine': f'dashscope:{model}'}


# ------------------------------------------------------------------ engines (http = the requests module, or a test double)
def azure_locale(language):
    return {'zh': 'zh-CN', 'en': 'en-US', 'ja': 'ja-JP', 'ko': 'ko-KR'}.get(language, language)


def call_azure(audio, language, speakers, http, environ=os.environ):
    base = environ.get('AZURE_SPEECH_ENDPOINT') or f'https://{environ["AZURE_SPEECH_REGION"]}.api.cognitive.microsoft.com'
    definition = {}
    if language:
        definition['locales'] = [azure_locale(language)]
    if speakers and speakers > 1:
        definition['diarization'] = {'enabled': True, 'maxSpeakers': speakers}
    with open(audio, 'rb') as f:
        r = http.post(f'{base.rstrip("/")}/speechtotext/transcriptions:transcribe',
                      params={'api-version': AZURE_API_VERSION},
                      headers={'Ocp-Apim-Subscription-Key': environ['AZURE_SPEECH_KEY']},
                      files={'audio': (Path(audio).name, f), 'definition': (None, json.dumps(definition))},
                      timeout=3600)
    if r.status_code != 200:
        raise RuntimeError(f'Azure returned {r.status_code}: {r.text[:500]}')
    return azure_payload(r.json(), language)


def dashscope_upload(audio, model, http, base, key):
    """Model Studio temporary storage: getPolicy, then a form POST to OSS. Returns an oss:// URL valid for 48 h."""
    r = http.get(f'{base}/api/v1/uploads', params={'action': 'getPolicy', 'model': model},
                 headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f'temporary upload is not available here ({r.status_code}: {r.text[:300]}); '
                           'upload the audio somewhere reachable and pass --audio-url')
    d = r.json()['data']
    name = Path(audio).name
    k = f'{d["upload_dir"]}/{name}'
    with open(audio, 'rb') as f:
        up = http.post(d['upload_host'], files={
            'OSSAccessKeyId': (None, d['oss_access_key_id']), 'Signature': (None, d['signature']),
            'policy': (None, d['policy']), 'x-oss-object-acl': (None, d['x_oss_object_acl']),
            'x-oss-forbid-overwrite': (None, d['x_oss_forbid_overwrite']), 'key': (None, k),
            'success_action_status': (None, '200'), 'file': (name, f)}, timeout=1800)
    if up.status_code != 200:
        raise RuntimeError(f'OSS upload failed ({up.status_code}): {up.text[:300]}')
    return f'oss://{k}'


def call_funasr(audio, language, speakers, http, model='fun-asr', audio_url=None, environ=os.environ,
                sleep=time.sleep, poll=3.0, timeout=3600):
    base = (environ.get('DASHSCOPE_BASE_URL') or DASHSCOPE_DEFAULT).rstrip('/')
    key = environ['DASHSCOPE_API_KEY']
    url = audio_url or dashscope_upload(audio, model, http, base, key)
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'X-DashScope-Async': 'enable'}
    if url.startswith('oss://'):
        headers['X-DashScope-OssResourceResolve'] = 'enable'
    params = {}   # the Singapore host fails recognition when parameters is missing, so always send the object
    if language:
        params['language_hints'] = [language.split('-')[0]]
    if speakers and speakers > 1:
        params.update(diarization_enabled=True, speaker_count=speakers)
    r = http.post(f'{base}/api/v1/services/audio/asr/transcription', headers=headers, timeout=60,
                  json={'model': model, 'input': {'file_urls': [url]}, 'parameters': params})
    if r.status_code != 200:
        raise RuntimeError(f'Fun-ASR submit returned {r.status_code}: {r.text[:500]}')
    task = r.json()['output']['task_id']
    waited = 0.0
    while True:
        q = http.get(f'{base}/api/v1/tasks/{task}', headers={'Authorization': f'Bearer {key}'}, timeout=60).json()
        status = q['output']['task_status']
        if status not in ('PENDING', 'RUNNING'):
            break
        if waited >= timeout:
            raise RuntimeError(f'Fun-ASR task {task} still {status} after {timeout:.0f} s')
        sleep(poll)
        waited += poll
    sub = (q['output'].get('results') or [{}])[0]
    if status != 'SUCCEEDED' or sub.get('subtask_status') != 'SUCCEEDED':
        raise RuntimeError(f'Fun-ASR task {task} {status}: {sub.get("code", "")} {sub.get("message", "")}'.strip())
    result = http.get(sub['transcription_url'], timeout=120).json()
    return funasr_payload(result, model, language)


# ------------------------------------------------------------------ commands
def run(args, http=None):
    media = Path(args.media).resolve()
    out = Path(args.edit).resolve() / 'transcripts' / f'{media.stem}.json'
    if out.exists() and not args.force:
        print(f'cached: {out} (--force to replace)')
        return 0
    if not args.confirmed:
        print(estimate_text(estimate(media_seconds(media))))
        print('未运行：转录会上传音频并产生费用。把上表给用户看，用户同意后加 --confirmed 再运行。')
        return 3
    if not env_ready(args.engine):
        missing = ' + '.join(ENGINES[args.engine]['env'])
        raise SystemExit(f'{args.engine}: set {missing} in the environment first (never in a file in this repo)')
    if http is None:
        import requests as http
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / f'{media.stem}.wav'
        extract_audio(media, wav, ['-c:a', 'pcm_s16le'])
        peak = peak_dbfs(wav)
        if peak < -60:
            raise SystemExit(f'{media.name}: the first audio track is silent (peak {peak:.1f} dBFS); not uploading')
        t0 = time.time()
        if args.engine == 'azure':
            payload = call_azure(wav, args.language, args.speakers, http)
        else:
            mp3 = Path(tmp) / f'{media.stem}.mp3'   # 16 kHz mono MP3: about 20 MB an hour, under upload size caps
            extract_audio(media, mp3, ['-c:a', 'libmp3lame', '-b:a', '48k'])
            payload = call_funasr(mp3, args.language, args.speakers, http, model=args.model, audio_url=args.audio_url)
    payload['duration'] = round(media_seconds(media), 3)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding='ascii')   # ASCII-escaped: pack_transcripts reads with the locale codec
    n = sum(1 for w in payload['words'] if w['type'] == 'word')
    print(f'saved: {out} ({n} words, {payload["engine"]}, {time.time() - t0:.0f} s)')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('estimate', help='duration and expected cost per engine; uploads nothing')
    p.add_argument('media', nargs='+')
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('run', help='transcribe one file with a cloud engine')
    p.add_argument('--engine', choices=['azure', 'funasr'], required=True)
    p.add_argument('media')
    p.add_argument('--edit', required=True, help='edit directory; writes transcripts/<stem>.json')
    p.add_argument('--confirmed', action='store_true', help='the user agreed to the upload and the cost')
    p.add_argument('--language', help='e.g. zh, en, zh-CN; omit to auto-detect')
    p.add_argument('--speakers', type=int, help='number of speakers when more than one (enables diarization)')
    p.add_argument('--audio-url', help='funasr: an HTTP(S) or oss:// URL of the audio instead of a temporary upload')
    p.add_argument('--model', default='fun-asr', help='funasr model id (default fun-asr)')
    p.add_argument('--force', action='store_true', help='replace an existing transcript')
    a = ap.parse_args(argv)
    if a.cmd == 'estimate':
        if not shutil.which('ffprobe'):
            raise SystemExit('ffprobe not found; run setup_env.py --check')
        est = estimate(sum(media_seconds(m) for m in a.media))
        print(json.dumps(est, ensure_ascii=False, indent=2) if a.json else estimate_text(est), end='')
        return 0
    return run(a)


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))   # also under python -I
    import key_setup
    key_setup.load_user_env()   # a key saved after this terminal or agent host started
    sys.exit(main())
