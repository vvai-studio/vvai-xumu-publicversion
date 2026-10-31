#!/usr/bin/env python3
"""Sound backend: cloned-voice narration through providers the user configured, behind one paid-call layer.

  python audio_cloud.py setup [--yes]                      # 造物社 (vvai) provider, image and music defaults
  python audio_cloud.py setup --smoke --out DIR --confirmed [--max-cost N]   # one paid line + one image, end to end
  python audio_cloud.py doctor
  python audio_cloud.py voice list [--provider P]
  python audio_cloud.py voice presets [--gender 男|女|童] [--lang 中文|英文]
  python audio_cloud.py voice audition --provider P --ids ID1,ID2 --out DIR [--text T] --confirmed [--max-cost N]
  python audio_cloud.py voice register NAME --provider P [--voice-id ID | --preset ID] [--owner WHO] [--consent TEXT] [--yes]
  python audio_cloud.py voice estimate SCRIPT [--voice NAME] [--edit EDIT] [--no-batch] [--json]
  python audio_cloud.py voice speak SCRIPT --edit EDIT [--voice NAME] [--section S1,S3] [--no-batch] --confirmed [--max-cost N]
  python audio_cloud.py voice align --edit EDIT
  python audio_cloud.py voice clone SAMPLE --name N --provider P --confirmed [--max-cost N]
  python audio_cloud.py music generate --edit EDIT --prompt TEXT [--style TAGS] [--name bgm] --confirmed [--max-cost N]
  python audio_cloud.py music check TRACK
  python audio_cloud.py music fit TRACK --len SECONDS --out OUT.wav [--start SECONDS]
  python audio_cloud.py music mix --music FITTED.wav (--video V.mp4 | --voice NARRATION.wav) --out OUT

Configuration lives in backends.local.json under "audio" (never shipped; see backends.local.example.json). Keys live
only in environment variables whose names the config gives (key_env); nothing here prints a key.

Paid-call rules (every paid command, images included: image_cloud.py shares this layer):
  1. quote first: providers with a price API return every channel's price; the cheapest channel whose 24 h success
     rate reaches budget.min_success_rate (and whose vendor is not in budget.avoid_vendors) is pinned; cheaper
     channels skipped for that reason are named in the quote;
  2. the run refuses when the quote exceeds --max-cost (default budget.confirm_over): show the quote, ask the user, rerun
     with a higher --max-cost; --confirmed is always required;
  3. a failed task is not retried on another channel: the result lists the next channels and their prices for the user;
  4. every submission is written to <edit>/audio_log.json before polling, so an interrupted run resumes the same task
     instead of paying twice; finished audio is cached by a hash of provider, model, voice, parameters and text.

Script files: Markdown with "## <section id>" headings, or JSON {"sections": [{"id", "text"}]}. Text is sent as written
(pause marks like <#0.6#> included) after the pronunciation table (config audio.voice.pronounce, then
<edit>/pronounce.json) rewrites the words it lists; captions and cue maps keep the original text.

Provider types (by API shape, not by vendor):
  lk-media-task  POST /v1/media/generate {model, prompt, params} -> GET /v1/media/status?task_id=; voices at
                 GET /v1/skills/voices. Tested live (2026-10-21, speech-2.8).
  gateway-media  multi-model gateways such as vvai造物社: POST /v1/audio/speech/async -> GET /v1/tasks/{id}; the
                 account's cloned voices at /v1/audio/voices; POST /v1/pricing-estimate + GET
                 /v1/skills/models/{m}/pricing for channel prices; lane_id pins a channel. Speech, music and images
                 tested live on 造物社 (2026-10-26).

Voices: a registered voice, else the account's cloned voices (voice list), else the platform's built-in voices
(voice presets, from references/voice-presets.json; audition, then register with --preset). Gateways charge a minimum
per call (造物社 speech-2.8: the first ~200 characters cost the same), so speak joins short sections into calls of at
least voice.batch_min_chars characters, separated by a long pause mark, and cuts the result back at those pauses;
--no-batch sends one call per section.

Music (gateway-media, e.g. Suno behind a gateway): one call usually returns two tracks and has no length parameter, so
`fit` cuts the film length (looping at a strong onset when the track is short) with fades, and `mix` puts it under
the narration with sidechain ducking and a two-pass loudness normalisation. `check` transcribes the track: no
sentences heard means instrumental. The licence text the user declares in audio.music.license goes into the record.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

for _stream in (sys.stdout, sys.stderr):   # Windows pipes default to the ANSI code page; the agent reads UTF-8
    if hasattr(_stream, 'reconfigure'):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            pass

SKILL_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = SKILL_ROOT / 'backends.local.json'
PRESETS_PATH = SKILL_ROOT / 'references' / 'voice-presets.json'
# vvai造物社: what `setup` writes. The key itself stays in the environment variable the user sets.
VVAI = {'type': 'gateway-media', 'base_url': 'https://vvai.token6688.com', 'key_env': 'VVAI_API_KEY', 'currency': '¥'}
IMAGE_DEFAULTS = {'model': 'gt-image-2.5-flare', 'defaults': {'resolution': '4K', 'quality': 'high'}}
BATCH_SEP = '<#2.0#>'   # between sections joined into one call; longer than ordinary pauses, so the cuts are findable
PAUSE = re.compile(r'<#\s*\d+(?:\.\d+)?\s*#>')
PUNCT = set('，。？！、：；,.?!:;-—…（）()“”‘’"\'「」《》·~～ \t\n')
SR = 48000


class Refused(Exception):
    """The run stopped before spending money (over budget, not confirmed, unknown voice...). Exit code 3."""


# ------------------------------------------------------------------ config
def load_config(path=CONFIG_PATH, section='audio'):
    """One section of backends.local.json: "audio" (providers, budget, voice, music) or "image" (which provider and
    model images use; providers and budget are shared from "audio")."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    return data.get(section) or {}


def budget(cfg):
    b = cfg.get('budget') or {}
    return {'confirm_over': float(b.get('confirm_over', 1.0)), 'min_success_rate': float(b.get('min_success_rate', 0.9)),
            'concurrency': int(b.get('concurrency', 3)), 'avoid_vendors': list(b.get('avoid_vendors') or [])}


def pick_voice(cfg, name=None):
    """Registered voice by name; the default (or the only one) when no name is given. Never guesses."""
    v = cfg.get('voice') or {}
    voices = v.get('voices') or {}
    if not voices:
        raise Refused('还没有登记音色。按顺序选：\n'
                      '  1. voice list：账号声纹库里自己克隆的音色，选一个 voice register；\n'
                      '  2. 声纹库是空的：voice presets 列出平台自带音色，挑几个 voice audition 试听，'
                      '再 voice register 名字 --preset 音色ID；\n'
                      '  3. 或者改用原声录音 / 不要旁白。')
    if name is None:
        name = v.get('default') or (next(iter(voices)) if len(voices) == 1 else None)
        if name is None:
            raise Refused(f'有多个音色，请指定：{", ".join(voices)}')
    if name not in voices:
        raise Refused(f'没有登记名为"{name}"的音色。可用：{", ".join(voices)}')
    entry = voices[name]
    return name, entry, provider_of(cfg, entry['provider'])


def provider_of(cfg, pname, http=None):
    p = (cfg.get('providers') or {}).get(pname)
    if not p:
        raise Refused(f'配置里没有服务商 "{pname}"')
    cls = ADAPTERS.get(p.get('type'))
    if not cls:
        raise Refused(f'服务商 "{pname}" 的 type "{p.get("type")}" 不认识；可用：{", ".join(ADAPTERS)}')
    return cls(pname, p, http)


# ------------------------------------------------------------------ http (requests, or a test double with the same calls)
def _http(http):
    if http is None:
        import requests
        return requests
    return http


def call(http, method, url, *, headers, sleep=time.sleep, tries=5, **kw):
    """One request; HTTP 429 waits Retry-After (not a failure, no channel change)."""
    timeout = kw.pop('timeout', 120)
    for _ in range(tries):
        r = getattr(http, method)(url, headers=headers, timeout=timeout, **kw)
        if r.status_code != 429:
            return r
        sleep(float((getattr(r, 'headers', None) or {}).get('Retry-After', 5)))
    return r


# Gateway error codes (造物社 API doc, 错误码) in words the user can act on.
HINTS = {
    'missing_api_key': '请求没带上密钥：确认环境变量已设置，并在设置后重开了终端和 AI 工具',
    'invalid_api_key': '密钥不对或已删除：到造物社「管理密钥」页重新复制，再设置环境变量',
    'insufficient_funds': '余额不够这一单的预冻结额：充值后重跑（失败的任务不扣费）',
    'api_key_quota_exceeded': '这把密钥的总额度用完了：在「管理密钥」页提高额度或换一把密钥',
    'api_key_inactive': '这把密钥已停用或删除：在「管理密钥」页恢复，或新建一把',
    'model_not_allowed': '这把密钥没开通这个模型：在「管理密钥」页编辑可用模型',
    'insufficient_permissions': '这把密钥没有这个接口的权限：在「管理密钥」页勾选对应权限（图片 / 音频 / 文件）',
    'content_policy_violation': '内容被安全策略拦截：改写提示词或换参考图',
    'model_not_found': '模型 ID 不存在或已下线：用 GET /v1/skills/models 查当前 ID',
    'pinned_channel_unavailable': '钉住的渠道暂时不可用：稍后重试，或重新报价换渠道',
    'likeness_consent_required': '这张真人照片在造物社还没确认肖像授权（kling-avatar 会检查）：需要照片本人在造物社确认授权后再提交；失败不扣费',
    'voice_not_found': '音色不存在、没就绪或不属于这个账号：voice list 查账号音色，或改用 voice presets 里的平台音色',
}


def fetch(http, url, sleep=time.sleep, tries=4):
    """Download a finished file; the CDN sometimes drops a connection, so a few retries before giving up (the task
    stays logged, so a later rerun still resumes instead of paying again)."""
    for k in range(tries):
        try:
            r = _http(http).get(url, timeout=300)
            if r.status_code < 400:
                return r.content
            err = f'HTTP {r.status_code}'
        except Exception as e:   # connection reset, timeout
            err = str(e)
        if k < tries - 1:
            sleep(2 * (k + 1))
    raise RuntimeError(f'下载失败（{err}）：{url}；稍后重跑同一命令会接着下载，不重复付费')


def body(r, what):
    try:
        data = r.json()
    except ValueError:
        data = None
    if r.status_code >= 400 or data is None:
        err = (data or {}).get('error') if isinstance(data, dict) else None
        msg, hint = err, None
        if isinstance(err, dict):
            msg = err.get('message') or err.get('code')
            hint = HINTS.get(err.get('code')) or HINTS.get(err.get('type'))
        text = f'{what}: HTTP {r.status_code} {msg or getattr(r, "text", "")[:300]}'
        raise RuntimeError(text + (f'（{hint}）' if hint else ''))
    return data


# ------------------------------------------------------------------ adapters
class Adapter:
    kind = ''
    has_price_api = False
    batch_min = 0   # characters per call worth joining sections for (0 = one call per section)

    def __init__(self, name, conf, http=None):
        self.name, self.conf, self.http = name, conf, http
        self.base = conf.get('base_url', '').rstrip('/')
        self.currency = conf.get('currency', '额度')

    def key_ready(self, environ=os.environ):
        return bool(environ.get(self.conf.get('key_env', '')))

    def headers(self, environ=os.environ):
        env = self.conf.get('key_env', '')
        key = environ.get(env)
        if not key:
            raise Refused(f'服务商 "{self.name}"：环境变量 {env or "(key_env 未配置)"} 没有设置')
        return {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}

    def get(self, path, **kw):
        return call(_http(self.http), 'get', self.base + path, headers=self.headers(), **kw)

    def post(self, path, **kw):
        return call(_http(self.http), 'post', self.base + path, headers=kw.pop('headers', None) or self.headers(), **kw)

    def unit_price(self):
        """Configured price per billing unit, for providers without a price API (None = unknown)."""
        price = self.conf.get('price') or {}
        return price.get('amount'), price.get('per', 'token')


class LkMediaTask(Adapter):
    kind = 'lk-media-task'

    def list_voices(self, model='speech-2.8'):
        data = body(self.get('/v1/skills/voices', params={'model': model}), 'voice list')
        return [{'id': v['voice_id'], 'name': v.get('name'), 'status': v.get('status'),
                 'permanent': v.get('is_permanent'), 'days_left': v.get('days_left')} for v in data.get('voices', [])]

    def quote(self, model, params, text):
        amount, per = self.unit_price()
        units = billing_units(text) if per == 'token' else len(strip_pauses(text))
        price = None if amount is None else round(amount * units, 4)
        return {'channels': [{'lane': None, 'vendor': self.name, 'price': price, 'success_rate': None}],
                'units': units, 'note': '按配置的单价估算' if price is not None else '没有单价：请在配置 price 里填写，或以服务商价格表为准'}

    def submit_speech(self, model, voice_id, text, opts, lane=None):
        params = {'voice_id': voice_id, 'quality': opts.get('quality', 'hd'), 'speed': str(opts.get('speed', 1)),
                  'pitch': str(opts.get('pitch', 0)), 'emotion': opts.get('emotion', 'auto'), 'sound_effects': 'none'}
        data = body(self.post('/v1/media/generate', json={'model': model, 'prompt': text, 'params': params}), 'submit')
        return str(data['data']['task_id'])

    def poll(self, task_id):
        d = body(self.get('/v1/media/status', params={'task_id': task_id}), 'status')
        return {'final': bool(d.get('is_final')), 'ok': d.get('state') == 'success', 'url': d.get('result_url'),
                'cost': d.get('cost'), 'error': d.get('error')}

    def clone(self, sample, name, audio_url=None):
        if not audio_url:
            raise Refused('lk-media-task 的克隆接口只收公网音频地址：用 --audio-url 传一个限时签名链接')
        d = body(self.post('/v1/skills/voices/clone', json={'audio_url': audio_url, 'name': name}), 'clone')
        return {'id': d['voice_id'], 'task_id': None, 'note': '新音色 7 天内首次合成会另收激活费，之后转为永久'}


class GatewayMedia(Adapter):
    kind = 'gateway-media'
    has_price_api = True
    batch_min = 200   # 造物社 speech-2.8 bills the first ~200 characters of a call at one minimum price

    def balance(self):
        d = body(self.get('/v1/skills/balance'), 'balance')
        c = d.get('credits') or {}
        return {'available': c.get('available'), 'unit': '⚡' if c else d.get('currency'),
                'usd': d.get('available_balance')}

    def upload_file(self, path):
        """Local file -> public URL on the gateway's storage (free; inline base64 would add a transfer fee)."""
        h = self.headers()
        h.pop('Content-Type')
        with open(path, 'rb') as f:
            d = body(self.post('/v1/files', headers=h, files={'file': (Path(path).name, f)}), 'upload')
        if not d.get('url'):
            raise RuntimeError(f'上传 {Path(path).name} 没有拿到地址（平台存储失败），重试一次')
        return d['url']

    def submit_image(self, model, params, lane=None, request_id=None, modality='image'):
        req = {'model_id': model, 'modality': modality, 'params': params}
        if lane:
            req['lane_id'] = lane
        if request_id:
            req['client_request_id'] = request_id
        d = body(self.post('/api/v1/model-runtime/invoke', json=req), 'submit')
        return str(d.get('task_id') or (d.get('result') or {}).get('task_id'))

    def submit_video(self, model, params, lane=None, request_id=None):
        return self.submit_image(model, params, lane, request_id, modality='video')

    def list_voices(self, model='speech-2.8'):
        data = body(self.get('/v1/audio/voices', params={'model': model, 'limit': 100}), 'voice list')
        return [{'id': v['id'], 'name': v.get('name'), 'status': v.get('status'), 'permanent': v.get('status') == 'ready',
                 'days_left': None} for v in data.get('data', [])]

    def channel_stats(self, model):
        try:
            data = body(self.get(f'/v1/skills/models/{model}/pricing', params={'status': 'active'}), 'pricing')
        except Exception:
            return {}
        return {g.get('vendor'): (g.get('success_rate_24h') or 0) / 100 for g in data.get('channel_groups', [])}

    def quote(self, model, params, text=None):
        req = {'model': model, 'params': params, 'include_all_channels': True}
        data = body(self.post('/v1/pricing-estimate', json=req), 'pricing-estimate')
        stats = self.channel_stats(model)
        chans = data.get('channels') or [{'lane': None, 'vendor': data.get('vendor'),
                                          'effective_total_rmb': data.get('effective_total_rmb')}]
        out = [{'lane': c.get('lane'), 'vendor': c.get('vendor'), 'price': c.get('effective_total_rmb'),
                'success_rate': stats.get(c.get('vendor'))} for c in chans]
        return {'channels': out, 'units': None, 'note': f'服务商估价（{data.get("billing_mode", "")}）'}

    def submit_speech(self, model, voice_id, text, opts, lane=None):
        req = {'model': model, 'input': text, 'voice': voice_id, 'response_format': 'wav', **speech_tier(opts)}
        for k in ('speed', 'emotion', 'pitch'):
            if k in opts:
                req[k] = opts[k]
        if lane:
            req['lane_id'] = lane
        r = self.post('/v1/audio/speech/async', json=req)
        d = body(r, 'submit')
        return str(d.get('task_id') or d.get('id'))

    def poll(self, task_id):
        d = body(self.get(f'/v1/tasks/{task_id}'), 'task')
        if d.get('cdn_pending'):
            return {'final': False}
        billing = d.get('billing') or {}
        err = d.get('error')
        if isinstance(err, dict):
            err = err.get('message') or err.get('code')
        res = d.get('result') or {}
        items = (res.get('audios') or []) + (res.get('images') or []) + (res.get('videos') or []) or \
            [a for a in (d.get('data') or []) if isinstance(a, dict)]
        # original_url is the lossless file when the platform kept one; url may be a compressed copy
        urls = [a.get('original_url') or a.get('url') for a in items if a.get('original_url') or a.get('url')]
        return {'final': bool(d.get('is_final')), 'ok': d.get('status') == 'completed',
                'url': d.get('output_url') or d.get('result_url') or d.get('video_url'), 'urls': urls,
                'cost': billing.get('actual_cost_credits'), 'error': err, 'retry_offer': d.get('retry_offer'),
                'error_class': d.get('error_class'), 'refunded': bool(d.get('refunded'))}

    def submit_music(self, model, prompt, params, lane=None):
        params = dict(params)
        if lane:
            params['lane_id'] = lane
        d = body(self.post('/v1/media/generate', json={'model': model, 'prompt': prompt, 'params': params}), 'submit')
        return str((d.get('data') or d).get('task_id'))

    def clone(self, sample, name, audio_url=None):
        h = self.headers()
        h.pop('Content-Type')
        h['Idempotency-Key'] = 'xumu-' + file_hash(sample)[:24]
        with open(sample, 'rb') as f:
            r = self.post('/v1/audio/voices', headers=h, files={'file': (Path(sample).name, f)},
                          data={'model': 'speech-2.8', 'name': name})
        d = body(r, 'clone')
        return {'id': d['id'], 'task_id': d.get('task_id'), 'note': ''}


ADAPTERS = {'lk-media-task': LkMediaTask, 'gateway-media': GatewayMedia}


# ------------------------------------------------------------------ quoting
def choose_channel(channels, min_success_rate, avoid=()):
    """Balanced choice: the cheapest priced channel whose known 24 h success rate reaches the bar and whose vendor
    the user has not ruled out (unknown rates count as fine). Cheaper channels passed over are named; when no channel
    qualifies, the cheapest is used and flagged."""
    priced = sorted((c for c in channels if c.get('price') is not None), key=lambda c: c['price'])
    if not priced:
        return None, channels, []

    def fails(c):
        if c.get('vendor') in avoid:
            return '已在 avoid_vendors 里排除'
        rate = c.get('success_rate')
        return f'近 24 小时成功率只有 {rate:.0%}' if rate is not None and rate < min_success_rate else None

    good = [c for c in priced if not fails(c)]
    best = good[0] if good else priced[0]
    notes = [f'跳过更便宜的 {c["vendor"]}（{c["price"]}）：{fails(c)}' for c in priced[:priced.index(best)]]
    if not good:
        notes.append(f'没有渠道达到成功率 {min_success_rate:.0%}：先用最便宜的 {best["vendor"]}，失败后再按备选渠道问用户')
    return best, priced, notes


def gate(q, limit, confirmed):
    """Stop before spending: unknown price, over the no-confirm limit, or not confirmed."""
    if q['total'] is None:
        raise Refused('费用未知，不能自动执行：给用户看服务商的价格表，用户同意后用 --max-cost 指定上限再运行')
    if q['total'] > limit:
        raise Refused(f'预计 {q["total"]} 超过上限 {limit}：先问用户，同意后加 --max-cost {q["total"]} 再运行')
    if not confirmed:
        raise Refused('未运行：付费生成需要 --confirmed')


def quote_text(q):
    lines = [f'服务商：{q["provider"]}（{q["note"]}）', f'本次：{q["count"]} 段 / 次', '',
             '| 渠道 | 单次价格 | 24 小时成功率 |', '|---|---|---|']
    for c in q['channels']:
        mark = ' ← 选用' if q['chosen'] is not None and c is q['chosen'] else ''
        rate = '—' if c.get('success_rate') is None else f'{c["success_rate"]:.0%}'
        price = '未知' if c.get('price') is None else f'{round(c["price"], 4)} {q["currency"]}'
        lines.append(f'| {c.get("vendor") or "-"}{mark} | {price} | {rate} |')
    total = '未知' if q['total'] is None else f'{round(q["total"], 4)} {q["currency"]}'
    lines += ['', f'预计合计：{total}；免确认额度 {q["limit"]}'] + [f'注意：{n}' for n in q['notes']]
    return '\n'.join(lines) + '\n'


# ------------------------------------------------------------------ text
def strip_pauses(text):
    return PAUSE.sub('', text)


def speech_tier(opts):
    """Gateway speech-2.8 calls the HD / Turbo switch `tier`; the voice defaults may say `quality` (lk-media-task's name)."""
    tier = opts.get('tier') or opts.get('quality')
    return {'tier': tier} if tier in ('hd', 'turbo') else {}


def billing_units(text):
    """MiniMax-style count seen on 棱镜 (2026-10-21): about 2 per CJK character or full-width mark, 1 otherwise."""
    return sum(2 if ord(c) > 0x2E7F else 1 for c in strip_pauses(text) if not c.isspace())


def parse_script(path):
    p = Path(path)
    raw = p.read_text(encoding='utf-8')
    if p.suffix.lower() == '.json':
        return [{'id': s['id'], 'text': s['text'].strip()} for s in json.loads(raw)['sections']]
    sections, cur = [], None
    for line in raw.splitlines():
        m = re.match(r'^##\s+(\S+)', line)
        if m:
            cur = {'id': m.group(1), 'text': ''}
            sections.append(cur)
        elif cur is not None and line.strip() and not line.lstrip().startswith('<!--'):
            cur['text'] += (' ' if cur['text'] and cur['text'][-1].isascii() and line.strip()[0].isascii() else '') + line.strip()
    if not sections:
        raise Refused(f'{path}：没有找到 "## 段落编号" 标题')
    return sections


def pronounce_table(cfg, edit=None):
    table = dict((cfg.get('voice') or {}).get('pronounce') or {})
    if edit and (Path(edit) / 'pronounce.json').exists():
        table.update(json.loads((Path(edit) / 'pronounce.json').read_text(encoding='utf-8')))
    return table


def apply_pronounce(text, table):
    """Replace listed words (longest first) outside pause marks; only the text sent to the provider changes."""
    if not table:
        return text
    parts = re.split(f'({PAUSE.pattern})', text)
    pat = re.compile('|'.join(re.escape(k) for k in sorted(table, key=len, reverse=True)))
    return ''.join(p if PAUSE.fullmatch(p) else pat.sub(lambda m: table[m.group(0)], p) for p in parts)


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def request_key(provider, model, voice_id, opts, text):
    blob = json.dumps([provider, model, voice_id, opts, text], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()[:16]


# ------------------------------------------------------------------ log (idempotency + bookkeeping)
def read_log(edit, name='audio_log.json'):
    p = Path(edit) / name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else []


def write_log(edit, entries, name='audio_log.json'):
    p = Path(edit) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(p)


# ------------------------------------------------------------------ audio files
def to_wav(src, dst):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-ac', '1', '-ar', str(SR), '-c:a', 'pcm_s16le', str(dst)],
                   check=True)


def seconds(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def build_narration(edit, sections, lead, gap):
    """Join section wavs with silence; writes tts/narration.wav and tts/manifest.json (offsets in programme seconds)."""
    tts = Path(edit) / 'tts'
    items, t = [], lead
    for s in sections:
        d = seconds(tts / f'{s["id"]}.wav')
        items.append({'id': s['id'], 'file': f'{s["id"]}.wav', 'text': s['text'], 'offset': round(t, 3), 'seconds': round(d, 3)})
        t += d + gap
    inputs, graph = [], []
    for i, it in enumerate(items):
        inputs += ['-i', str(tts / it['file'])]
        graph.append(f'[{i}:a]adelay={int(round(it["offset"] * 1000))}:all=1[a{i}]')
    graph.append(''.join(f'[a{i}]' for i in range(len(items))) + f'amix=inputs={len(items)}:normalize=0:duration=longest[o]')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(graph), '-map', '[o]',
                    '-ar', str(SR), '-ac', '1', '-c:a', 'pcm_s16le', str(tts / 'narration.wav')], check=True)
    manifest = {'lead': lead, 'gap': gap, 'sections': items, 'total': round(t - gap, 3)}
    (tts / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    return manifest


# ------------------------------------------------------------------ voice speak
class SplitError(Exception):
    """A joined call came back but could not be cut back into its sections with confidence."""


def batch_min_chars(cfg, prov, no_batch=False):
    if no_batch:
        return 0
    v = (cfg.get('voice') or {}).get('batch_min_chars')
    return prov.batch_min if v is None else int(v)


def batch_groups(jobs, min_chars, max_chars=1500):
    """Consecutive jobs grouped until each group has min_chars spoken characters (a short tail joins the last group
    when it fits under max_chars). min_chars 0 keeps one job per group."""
    if min_chars <= 0 or len(jobs) < 2:
        return [[j] for j in jobs]
    size = lambda js: sum(len(strip_pauses(j['sent'])) for j in js)
    groups, cur = [], []
    for j in jobs:
        if cur and size(cur + [j]) > max_chars:
            groups.append(cur)
            cur = []
        cur.append(j)
        if size(cur) >= min_chars:
            groups.append(cur)
            cur = []
    if cur:
        if groups and size(groups[-1] + cur) <= max_chars:
            groups[-1] += cur
        else:
            groups.append(cur)
    return groups


def chunk_job(group, tts, key_of):
    if len(group) == 1:
        return group[0]
    sent = BATCH_SEP.join(j['sent'] for j in group)
    key = key_of(sent)
    return {'section': '+'.join(j['section'] for j in group), 'sent': sent, 'key': key,
            'cache': Path(tts) / f'batch.{key}.wav', 'members': group}


def quiet_runs(samples, sr, floor_db=-38):
    """[(start, end)] of quiet stretches, from 10 ms frames below the speech level."""
    import numpy as np
    hop = int(sr * 0.01)
    n = len(samples) // hop
    if n == 0:
        return []
    db = 20 * np.log10(np.sqrt((samples[:n * hop].reshape(n, hop) ** 2).mean(axis=1)) + 1e-9)
    loud = db > max(db.max() - 45, floor_db)
    runs, i = [], 0
    while i < n:
        if not loud[i]:
            j = i
            while j < n and not loud[j]:
                j += 1
            runs.append((i * 0.01, j * 0.01))
            i = j
        i += 1
    return runs


def pause_cuts(samples, sr, parts, min_gap=1.2):
    """Cut times between `parts` joined sections: the centres of the parts-1 longest inner pauses of at least
    min_gap seconds (the joining mark is 2 s; ordinary pauses are shorter). None when there are too few."""
    end = len(samples) / sr
    inner = [(a, b) for a, b in quiet_runs(samples, sr) if b - a >= min_gap and a > 0.05 and b < end - 0.05]
    if len(inner) < parts - 1:
        return None
    chosen = sorted(sorted(inner, key=lambda r: r[1] - r[0], reverse=True)[:parts - 1])
    return [round((a + b) / 2, 3) for a, b in chosen]


def sound_span(samples, sr, pad=0.08):
    runs = quiet_runs(samples, sr)
    dur = len(samples) / sr
    start = runs[0][1] if runs and runs[0][0] == 0 else 0.0
    end = runs[-1][0] if runs and runs[-1][1] >= dur - 0.011 else dur
    if end <= start:
        return 0.0, dur
    return max(0.0, start - pad), min(dur, end + pad)


def check_pieces(pieces, counts, spread=2.5):
    """Each piece's seconds per character within `spread` times of the median: a wrong cut shows up as one piece
    far too long and its neighbour far too short."""
    rates = [(b - a) / n for (a, b), n in zip(pieces, counts) if n]
    if not rates:
        return
    med = sorted(rates)[len(rates) // 2]
    for k, ((a, b), n) in enumerate(zip(pieces, counts)):
        if n and not med / spread <= (b - a) / n <= med * spread:
            raise SplitError(f'切出的第 {k + 1} 段 {b - a:.1f} 秒，和它的 {n} 个字对不上')


def split_chunk(wav, members, sr=16000):
    """Cut a joined call back into its sections at the joining pauses; writes each member's cache wav."""
    a = load_samples(wav, sr)
    cuts = pause_cuts(a, sr, len(members))
    if cuts is None:
        raise SplitError(f'没找到足够的长停顿（需要 {len(members) - 1} 处）')
    bounds = [0.0] + cuts + [len(a) / sr]
    pieces = []
    for t0, t1 in zip(bounds, bounds[1:]):
        s0, s1 = sound_span(a[int(t0 * sr):int(t1 * sr)], sr)
        pieces.append((t0 + s0, t0 + s1))
    check_pieces(pieces, [len(script_chars(m['sent'])) for m in members])
    for (t0, t1), m in zip(pieces, members):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(wav), '-ss', f'{t0:.3f}', '-to', f'{t1:.3f}',
                        '-ac', '1', '-ar', str(SR), '-c:a', 'pcm_s16le', str(m['cache'])], check=True)


def place_members(j, tts):
    split_chunk(j['cache'], j['members'])
    for m in j['members']:
        shutil.copyfile(m['cache'], Path(tts) / f'{m["section"]}.wav')


def speak(cfg, script, edit, voice=None, only=None, confirmed=False, max_cost=None, http=None, sleep=time.sleep,
          poll_every=4.0, timeout=600, lead=0.45, gap=0.45, no_batch=False, out=print):
    name, ventry, prov = pick_voice(cfg, voice)
    prov.http = http
    b = budget(cfg)
    limit = b['confirm_over'] if max_cost is None else float(max_cost)
    model = ventry.get('model', 'speech-2.8')
    opts = {**((cfg.get('voice') or {}).get('defaults') or {}), **(ventry.get('options') or {})}
    sections = parse_script(script)
    wanted = [s for s in sections if not only or s['id'] in only]
    table = pronounce_table(cfg, edit)
    tts = Path(edit) / 'tts'
    tts.mkdir(parents=True, exist_ok=True)
    log = read_log(edit)
    jobs = []
    for s in wanted:
        sent = apply_pronounce(s['text'], table)
        key = request_key(prov.name, model, ventry['voice_id'], opts, sent)
        cached = tts / f'{s["id"]}.{key}.wav'
        if cached.exists():
            shutil.copyfile(cached, tts / f'{s["id"]}.wav')
            out(f'{s["id"]}: 原文和参数未变，复用缓存')
            continue
        jobs.append({'section': s['id'], 'sent': sent, 'key': key, 'cache': cached})
    key_of = lambda text: request_key(prov.name, model, ventry['voice_id'], opts, text)
    jobs = [chunk_job(g, tts, key_of) for g in batch_groups(jobs, batch_min_chars(cfg, prov, no_batch))]
    for j in [j for j in jobs if j.get('members') and j['cache'].exists()]:   # paid earlier, only the cut is missing
        try:
            place_members(j, tts)
        except SplitError as e:
            raise Refused(f'{j["section"]} 已生成过但切不开：{e}。整段音频在 {j["cache"]}；'
                          f'用 --no-batch --section {",".join(m["section"] for m in j["members"])} 逐段重新生成（会再付费）')
        jobs.remove(j)
        out(f'{j["section"]}: 用已生成的合并音频切段，不再付费')
    if jobs:
        q = quote_jobs(prov, model, ventry, opts, jobs, b)
        q['limit'] = limit
        out(quote_text(q))
        gate(q, limit, confirmed)
        lane = q['chosen'].get('lane') if q['chosen'] else None
        failed = run_jobs(prov, model, ventry, opts, jobs, lane, edit, log, sleep, poll_every, timeout, out)
        lines = [f'{j["section"]} 已生成（已付费）但切不开：{j["error"]}。整段音频在 {j["cache"]}；用 --no-batch --section '
                 f'{",".join(m["section"] for m in j["members"])} 逐段重新生成（会再付费），或人工切分'
                 for j in failed if j.get('paid')]
        refunded = [j for j in failed if not j.get('paid')]
        if refunded:
            alts = [c for c in q['channels'] if c is not q['chosen']]
            lines += [f'{j["section"]} 失败：{j["error"]}' for j in refunded]
            lines.append('失败的任务服务商会自动退款。没有自动换渠道；可选：')
            lines += [f'  {c.get("vendor")}（lane {c.get("lane")}）{c.get("price")} {q["currency"]}，成功率 '
                      f'{"—" if c.get("success_rate") is None else format(c["success_rate"], ".0%")}' for c in alts[:3]]
            if not alts:
                lines.append('  这个服务商没有其他渠道：稍后再试，或换另一个服务商')
        if lines:
            raise Refused('\n'.join(lines))
    missing = [s['id'] for s in sections if not (tts / f'{s["id"]}.wav').exists()]
    if missing:
        out(f'还没有音频的段落：{", ".join(missing)}（narration.wav 暂不拼接）')
        return None
    manifest = build_narration(edit, sections, lead, gap)
    spent = round(sum(e.get('cost') or 0 for e in read_log(edit) if e.get('state') == 'success'), 4)
    out(f'narration.wav：{manifest["total"]:.2f} 秒，{len(sections)} 段。本项目配音累计花费 {spent}')
    return manifest


def quote_jobs(prov, model, ventry, opts, jobs, b):
    if prov.has_price_api:
        per_job = [prov.quote(model, {'input': j['sent'], 'voice': j.get('voice_id') or ventry['voice_id'],
                                      **speech_tier(opts)}) for j in jobs]
        base = per_job[0]
        totals = {}
        for pj in per_job:
            for c in pj['channels']:
                totals.setdefault(c['lane'], {**c, 'price': 0.0})
                totals[c['lane']]['price'] = None if c['price'] is None or totals[c['lane']]['price'] is None \
                    else round(totals[c['lane']]['price'] + c['price'], 4)
        channels, note = list(totals.values()), base['note']
    else:
        pj = prov.quote(model, opts, ''.join(j['sent'] for j in jobs))
        channels, note = pj['channels'], pj['note']
    best, ordered, notes = choose_channel(channels, b['min_success_rate'], b['avoid_vendors'])
    activation = (ventry.get('activation_pending') and '这个音色还没激活：首次合成会另收激活费') or None
    return {'provider': prov.name, 'note': note, 'count': len(jobs), 'channels': ordered or channels, 'chosen': best,
            'total': None if best is None else best['price'], 'currency': prov.currency,
            'notes': notes + ([activation] if activation else [])}


def run_jobs(prov, model, ventry, opts, jobs, lane, edit, log, sleep, poll_every, timeout, out):
    """Submit (or resume) each job, poll to the end, download, convert. Returns the failed jobs."""
    by_key = {e['key']: e for e in log}
    failed = []
    for j in list(jobs):
        e = by_key.get(j['key'])
        if e and e.get('state') == 'submitted':
            j['task'] = e['task_id']
            out(f'{j["section"]}: 上次已提交（{e["task_id"]}），继续查询，不重复付费')
            continue
        try:
            j['task'] = prov.submit_speech(model, j.get('voice_id') or ventry['voice_id'], j['sent'], opts, lane)
        except RuntimeError as err:   # refused at submission (unknown voice, no balance...): nothing was charged
            j['error'] = str(err)
            failed.append(j)
            jobs = [x for x in jobs if x is not j]
            out(f'{j["section"]}: 提交被拒（未扣费）：{err}')
            continue
        entry = {'key': j['key'], 'kind': 'voice', 'section': j['section'], 'provider': prov.name, 'model': model,
                 'lane': lane, 'task_id': j['task'], 'state': 'submitted', 'at': time.strftime('%Y-%m-%d %H:%M:%S')}
        log.append(entry)
        by_key[j['key']] = entry
        write_log(edit, log)
        out(f'{j["section"]}: 已提交 {j["task"]}')
    pending, waited = list(jobs), 0.0
    while pending:
        for j in list(pending):
            st = prov.poll(j['task'])
            if not st.get('final'):
                continue
            pending.remove(j)
            e = by_key[j['key']]
            e['cost'] = st.get('cost')
            if not st.get('ok'):
                e['state'], e['error'] = 'failed', st.get('error')
                j['error'] = st.get('error') or '未知错误'
                failed.append(j)
            else:
                tts = Path(edit) / 'tts'
                raw = tts / f'{j["key"]}.download'
                raw.write_bytes(fetch(prov.http, st.get('url') or st['urls'][0], sleep))
                to_wav(raw, j['cache'])
                raw.unlink()
                e['state'], e['file'] = 'success', j['cache'].name
                out(f'{j["section"]}: 完成，花费 {st.get("cost")}')
                if j.get('members'):
                    e['members'] = [m['section'] for m in j['members']]
                    try:
                        place_members(j, tts)
                    except SplitError as err:
                        j['error'], j['paid'] = str(err), True
                        failed.append(j)
                else:
                    shutil.copyfile(j['cache'], tts / f'{j["section"]}.wav')
            write_log(edit, log)
        if pending:
            if waited >= timeout:
                raise RuntimeError(f'超时：{", ".join(j["task"] for j in pending)} 仍未完成；稍后重跑同一命令会继续查询')
            sleep(poll_every)
            waited += poll_every
    return failed


# ------------------------------------------------------------------ voice align
def voiced_chunks(samples, sr, min_gap=0.4, floor_db=-38, pad=0.05, min_len=0.25):
    """Spans of sound separated by at least min_gap of quiet; whisper drops speech after long pauses, so each span is
    transcribed on its own. Spans shorter than min_len are breaths or clicks (whisper hears them as words), dropped."""
    import numpy as np
    hop = int(sr * 0.01)
    n = len(samples) // hop
    if n == 0:
        return []
    frames = samples[:n * hop].reshape(n, hop)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    loud = db > max(db.max() - 45, floor_db)
    spans, i = [], 0
    while i < n:
        if loud[i]:
            j = i
            while j < n and (loud[j] or loud[j:j + int(min_gap / 0.01)].any()):
                j += 1
            if (j - i) * 0.01 >= min_len:
                spans.append((max(0.0, i * 0.01 - pad), min(n * 0.01, j * 0.01 + pad)))
            i = j
        i += 1
    return spans


def asr_chars(words):
    """[(char, start, end)] from ASR words: CJK characters share their word's span evenly; every letter of a Latin
    word gets the whole word span."""
    out = []
    for w in words:
        letters = [c for c in w['text'] if c not in PUNCT and not c.isspace()]
        if not letters:
            continue
        if all(c.isascii() for c in letters):
            out += [(c.lower(), w['start'], w['end']) for c in letters]
        else:
            step = (w['end'] - w['start']) / len(letters)
            out += [(c.lower(), w['start'] + k * step, w['start'] + (k + 1) * step) for k, c in enumerate(letters)]
    return out


def script_chars(text):
    return [c for c in strip_pauses(text) if c not in PUNCT and not c.isspace()]


def align_section(text, words, span, syllables=None):
    """Times for every script character. Matching characters take the ASR time; runs the ASR heard differently
    (homophones, tongue twisters) are placed on vowel peaks when the count fits, else spread evenly between the
    neighbouring matched characters. Returns (times, suspects, matched)."""
    sc = script_chars(text)
    ac = asr_chars(words)
    times = [None] * len(sc)
    sm = difflib.SequenceMatcher(None, [c.lower() for c in sc], [a[0] for a in ac], autojunk=False)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            times[a + k] = (ac[b + k][1], ac[b + k][2])
    matched = [t is not None for t in times]
    suspects, i = [], 0
    while i < len(sc):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(sc) and times[j] is None:
            j += 1
        lo = times[i - 1][1] if i > 0 else span[0]
        hi = times[j][0] if j < len(sc) else span[1]
        if hi <= lo:
            hi = lo + 0.08 * (j - i)
        peaks = [p for p in (syllables or []) if lo - 0.05 <= p < hi]
        if len(peaks) == j - i:
            edges = peaks + [hi]
            for k in range(i, j):
                times[k] = (edges[k - i], edges[k - i + 1])
        else:
            step = (hi - lo) / (j - i)
            for k in range(i, j):
                times[k] = (lo + (k - i) * step, lo + (k - i + 1) * step)
        if j - i >= 2 or any(not c.isascii() for c in sc[i:j]):
            suspects.append({'text': ''.join(sc[i:j]), 'start': round(lo, 2), 'end': round(hi, 2), 'idx': (i, j)})
        i = j
    return times, suspects, matched


def vowel_peaks(samples, sr, rise_db=-12, hold_db=-15, lead=0.08):
    """[(syllable start, peak dB)] from vowel energy: s/sh are fricatives around -20 dB, so a rise above -12 dB
    (relative to the loudest 20 ms of this stretch) marks a vowel; the consonant starts about 80 ms earlier."""
    import numpy as np
    h = int(sr * 0.02)
    n = len(samples) // h
    if n == 0:
        return []
    db = 20 * np.log10(np.sqrt((samples[:n * h].reshape(n, h) ** 2).mean(axis=1)) + 1e-9)
    db -= db.max()
    out, i = [], 0
    while i < n:
        if db[i] > rise_db and (i == 0 or db[i - 1] <= rise_db):
            j = i
            while j < n and db[j] > hold_db:
                j += 1
            out.append((max(0.0, i * 0.02 - lead), float(db[i:j].max())))
            i = j
        i += 1
    return out


def vowel_onsets(samples, sr, **kw):
    return [t for t, _ in vowel_peaks(samples, sr, **kw)]


def fit_peaks(peaks, n, max_extra=2):
    """n syllable starts from detected vowel peaks; a tone contour can split one vowel into two peaks, so up to
    max_extra of the weakest inner peaks are dropped. None when the count cannot fit."""
    peaks = list(peaks)
    if not n or not (n <= len(peaks) <= n + max_extra):
        return None
    while len(peaks) > n:
        k = min(range(1, len(peaks) - 1), key=lambda m: peaks[m][1]) if len(peaks) > 2 else len(peaks) - 1
        del peaks[k]
    return [t for t, _ in peaks]


def chunk_members(times, chunks):
    """Characters per sound chunk. A time inside the quiet before a chunk cannot be right (nothing is said there),
    so such characters belong to the chunk that follows."""
    out, prev = [], 0.0
    for c0, c1 in chunks:
        out.append([k for k, t in enumerate(times) if prev <= t[0] < c1])
        prev = c1
    return out


def refine_chunks(text, times, matched, chunks, samples, sr, min_ratio=0.8, onset_slack=0.1):
    """Two corrections per sound chunk, in place:
    - a chunk's first character starts when its sound starts (whisper often puts the first word late);
    - an all-Chinese chunk whose vowel-peak count fits its characters is placed on the peaks (more exact than ASR
      word times; this is what rescues tongue twisters). Other chunks keep ASR times.
    Returns [(start, end, character indexes)] placed on peaks while the ASR was not following (match ratio under
    min_ratio)."""
    sc = script_chars(text)
    hard = []
    for (c0, c1), idx in zip(chunks, chunk_members(times, chunks)):
        if not idx:
            continue
        if not any(sc[k].isascii() for k in idx) and len(idx) >= 3:
            starts = fit_peaks([(c0 + t, d) for t, d in vowel_peaks(samples[int(c0 * sr):int(c1 * sr)], sr)], len(idx))
            if starts is not None:
                edges = starts + [c1]
                for m, k in enumerate(idx):
                    times[k] = (edges[m], edges[m + 1])
                if sum(matched[k] for k in idx) / len(idx) < min_ratio:
                    hard.append((round(c0, 2), round(c1, 2), idx))
                continue
        first = idx[0]
        onset = c0 + 0.05   # voiced_chunks pads 50 ms of quiet in front
        if times[first][0] - onset > onset_slack or times[first][0] < onset - onset_slack:
            times[first] = (onset, max(times[first][1], onset + 0.05))
    return hard


def transcribe(model, samples, sr):
    """Word times for one stretch. The language is detected per stretch; Chinese gets a simplified-Chinese prompt
    (whisper otherwise often writes traditional characters), other languages get none."""
    lang = None
    if hasattr(model, 'detect_language'):
        try:
            lang = model.detect_language(samples)[0]
        except Exception:
            lang = None
    kw = {'language': lang} if lang else {}
    if lang in ('zh', 'yue'):
        kw = {'language': 'zh', 'initial_prompt': '以下是普通话的句子。'}
    segs, info = model.transcribe(samples, vad_filter=False, word_timestamps=True, **kw)
    return [{'text': w.word, 'start': w.start, 'end': w.end} for s in segs for w in s.words]


def load_samples(path, sr=16000):
    import numpy as np
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, np.float32)


def align(edit, whisper_model=None, out=print, tts='tts'):
    """manifest.json + section wavs -> cue_chars.json, sections.json, <tts>/align_report.md (programme seconds).
    tts names the folder holding them: tts/ for synthesised narration, avatar/voice/ when a video model spoke the lines."""
    edit = Path(edit)
    manifest = json.loads((edit / tts / 'manifest.json').read_text(encoding='utf-8'))
    if whisper_model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise Refused('本地对齐需要 faster-whisper：先运行 setup_env.py --check')
        whisper_model = WhisperModel(os.environ.get('VV_WHISPER_MODEL', 'medium'), device='cpu', compute_type='int8')
    chars, sections, report = [], [], []
    for s in manifest['sections']:
        sr = 16000
        a = load_samples(edit / tts / s['file'], sr)
        words = []
        chunks = voiced_chunks(a, sr)
        for c0, c1 in chunks:
            for w in transcribe(whisper_model, a[int(c0 * sr):int(c1 * sr)], sr):
                words.append({'text': w['text'], 'start': w['start'] + c0, 'end': w['end'] + c0})
        times, suspects, matched = align_section(s['text'], words, (0.0, s['seconds']), vowel_onsets(a, sr))
        hard = refine_chunks(s['text'], times, matched, chunks, a, sr)
        placed = {k for _, _, idx in hard for k in idx}
        notes = []
        for x in suspects:   # report final times, after the chunk corrections
            i, j = x['idx']
            if set(range(i, j)) <= placed:
                continue
            notes.append({'text': x['text'], 'start': times[i][0], 'end': times[j - 1][1]})
        sc = script_chars(s['text'])
        notes += [{'text': ''.join(sc[k] for k in idx) + '（转录跟不上，已按韵母能量峰定位，请整段试听）', 'start': c0,
                   'end': c1} for c0, c1, idx in hard]
        suspects = sorted(notes, key=lambda x: x['start'])
        off = s['offset']
        k = 0
        for c in strip_pauses(s['text']):
            if c.isspace():
                continue
            if c in PUNCT:
                t = chars[-1]['e'] if chars and chars[-1]['sec'] == s['id'] else off
                chars.append({'c': c, 't': t, 'e': t, 'sec': s['id']})
                continue
            t0, t1 = times[k]
            k += 1
            chars.append({'c': c, 't': round(float(off + t0), 3), 'e': round(float(off + t1), 3), 'sec': s['id']})
        sections.append({'id': s['id'], 'start': off, 'end': round(off + s['seconds'], 3)})
        report += [f'- {s["id"]} {off + x["start"]:.2f}–{off + x["end"]:.2f} 秒："{x["text"]}"' for x in suspects]
    (edit / 'cue_chars.json').write_text(json.dumps(chars, ensure_ascii=False), encoding='utf-8')
    (edit / 'sections.json').write_text(json.dumps(sections, ensure_ascii=False, indent=1), encoding='utf-8')
    text = ['# 合成旁白对齐核对', '',
            '下列位置转录听到的和原文不一致：可能是同音字或转录听错，也可能是真的读错。逐条试听确认。', ''] + \
           (report or ['（没有不一致的地方）'])
    (edit / tts / 'align_report.md').write_text('\n'.join(text) + '\n', encoding='utf-8')
    out(f'cue_chars.json：{sum(1 for c in chars if c["c"] not in PUNCT)} 个字；待试听疑点 {len(report)} 处（{tts}/align_report.md）')
    return chars, sections, report


# ------------------------------------------------------------------ music
MUSIC_DEFAULTS = {'mode': 'instrumental', 'operation': 'generate', 'negative_tags': 'vocals, singing, rap'}
MIX_DEFAULTS = {'duck_db': -11.0, 'ratio': 6, 'attack_ms': 40, 'release_ms': 350, 'threshold': 0.03,
                'fade_in': 0.3, 'fade_out': 2.0, 'target': -14.0, 'tp': -1.5}


def music_conf(cfg):
    m = cfg.get('music') or {}
    if not m.get('provider'):
        raise Refused('没有配置配乐服务商（audio.music.provider）：可以用用户自己有授权的音乐，或不放配乐。')
    return m


def generate_music(cfg, edit, prompt, style=None, negative=None, name='bgm', confirmed=False, max_cost=None,
                   http=None, sleep=time.sleep, poll_every=5.0, timeout=900, check=True, out=print):
    m = music_conf(cfg)
    prov = provider_of(cfg, m['provider'], http)
    if not hasattr(prov, 'submit_music'):
        raise Refused(f'服务商 "{prov.name}"（{prov.kind}）不支持配乐')
    b = budget(cfg)
    limit = b['confirm_over'] if max_cost is None else float(max_cost)
    model = m.get('model', 'music')
    params = {**MUSIC_DEFAULTS, **(m.get('defaults') or {})}
    if style:
        params['style'] = style
    if negative is not None:
        params['negative_tags'] = negative
    key = request_key(prov.name, model, name, params, prompt)
    log = read_log(edit)
    prev = next((e for e in reversed(log) if e.get('key') == key), None)   # newest attempt (a retry follows a failure)
    mdir = Path(edit) / 'music'
    if prev and prev.get('state') == 'success' and all((mdir / f).exists() for f in prev.get('files', [])):
        out(f'同样的需求已经生成过：{", ".join(prev["files"])}（复用，不再付费）')
        return prev
    if prev and prev.get('state') == 'submitted':
        task, lane = prev['task_id'], prev.get('lane')
        out(f'上次已提交（{task}），继续查询，不重复付费')
    else:
        q = prov.quote(model, params)
        best, ordered, notes = choose_channel(q['channels'], b['min_success_rate'], b['avoid_vendors'])
        qq = {'provider': prov.name, 'note': q['note'], 'count': 1, 'channels': ordered or q['channels'], 'chosen': best,
              'total': None if best is None else best['price'], 'currency': prov.currency, 'notes': notes, 'limit': limit}
        out(quote_text(qq))
        if qq['total'] is None:
            raise Refused('费用未知，不能自动执行：给用户看价格表，同意后用 --max-cost 指定上限')
        if qq['total'] > limit:
            raise Refused(f'预计 {qq["total"]} 超过上限 {limit}：先问用户，同意后加 --max-cost {qq["total"]} 再运行')
        if not confirmed:
            raise Refused('未运行：付费生成需要 --confirmed')
        lane = best.get('lane')
        task = prov.submit_music(model, prompt, params, lane)
        prev = {'key': key, 'kind': 'music', 'name': name, 'provider': prov.name, 'model': model, 'lane': lane,
                'task_id': task, 'state': 'submitted', 'prompt': prompt, 'params': params,
                'at': time.strftime('%Y-%m-%d %H:%M:%S'), 'alternatives': [c for c in (ordered or []) if c is not best][:3]}
        log.append(prev)
        write_log(edit, log)
        out(f'已提交 {task}')
    waited = 0.0
    while True:
        st = prov.poll(task)
        if st.get('final'):
            break
        if waited >= timeout:
            raise RuntimeError(f'超时：{task} 仍未完成；稍后重跑同一命令会继续查询')
        sleep(poll_every)
        waited += poll_every
    prev['cost'] = st.get('cost')
    if not st.get('ok'):
        prev['state'], prev['error'] = 'failed', st.get('error')
        write_log(edit, log)
        alts = prev.get('alternatives') or []
        raise Refused('\n'.join([f'配乐生成失败：{st.get("error") or "未知错误"}', '失败的任务服务商会自动退款。没有自动换渠道；可选：']
                                + [f'  {c.get("vendor")}（lane {c.get("lane")}）{c.get("price")} {prov.currency}' for c in alts]
                                + ([] if alts else ['  稍后再试，或换另一个服务商'])))
    mdir.mkdir(parents=True, exist_ok=True)
    files = []
    for k, url in enumerate(st.get('urls') or [st['url']]):
        f = f'{name}_{"ABCDEFGH"[k]}.mp3'
        (mdir / f).write_bytes(fetch(prov.http, url, sleep))
        files.append(f)
    prev.update(state='success', files=files, license=m.get('license', '未声明：交付前向用户确认能否商用'))
    write_log(edit, log)
    out(f'完成：{", ".join(files)}，花费 {st.get("cost")}')
    if check:
        for f in files:
            try:
                v = vocal_check(mdir / f)
                out(f'{f}：{"没有检出人声" if not v else "检出人声：" + "；".join(v[:3])}')
            except Refused as e:
                out(str(e))
                break
    return prev


def vocal_check(track, model=None, seconds=90):
    """Sentences whisper hears in the first `seconds` of a track; [] means instrumental."""
    if model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise Refused('人声检查需要 faster-whisper（setup_env.py 会安装）；没有它请用户自己试听')
        model = WhisperModel(os.environ.get('VV_WHISPER_MODEL', 'medium'), device='cpu', compute_type='int8')
    a = load_samples(track)[:16000 * seconds]
    segs, _ = model.transcribe(a, vad_filter=False, no_speech_threshold=0.5)
    return [s.text.strip() for s in segs if s.no_speech_prob < 0.5 and len(s.text.strip()) > 3]


def first_sound(samples, sr, floor_db=-45):
    import numpy as np
    h = int(sr * 0.01)
    n = len(samples) // h
    if n == 0:
        return 0.0
    db = 20 * np.log10(np.sqrt((samples[:n * h].reshape(n, h) ** 2).mean(axis=1)) + 1e-9)
    loud = np.flatnonzero(db > max(db.max() - 40, floor_db))
    return float(loud[0] * 0.01) if len(loud) else 0.0


def loop_point(samples, sr, after):
    """A strong onset after `after` seconds to restart the track from when it is shorter than the film."""
    import numpy as np
    h = int(sr * 0.05)
    n = len(samples) // h
    e = np.sqrt((samples[:n * h].reshape(n, h) ** 2).mean(axis=1))
    rise = np.diff(e, prepend=e[0])
    lo = int(after / 0.05)
    hi = max(lo + 1, int(n * 0.6))
    k = lo + int(np.argmax(rise[lo:hi])) if hi > lo else lo
    return k * 0.05


def fit_plan(dur, length, start, loop_at, xfade=1.0):
    """Pieces [(from, to)] of the source that make `length` seconds: one cut when the track is long enough, else the
    track followed by repeats from the loop point, each joined with an xfade-second crossfade."""
    if dur - start >= length:
        return [(start, start + length)]
    pieces, have = [(start, dur)], dur - start
    while have < length:
        take = min(dur - loop_at, length - have + xfade)
        pieces.append((loop_at, loop_at + take))
        have += take - xfade
    return pieces


def fit_music(track, length, out_path, start=None, fade_in=None, fade_out=None, xfade=1.0, out=print):
    mix = MIX_DEFAULTS
    fade_in = mix['fade_in'] if fade_in is None else fade_in
    fade_out = mix['fade_out'] if fade_out is None else fade_out
    a = load_samples(track)
    dur = len(a) / 16000
    if start is None:
        start = first_sound(a, 16000)
    loop_at = loop_point(a, 16000, min(start + 4.0, dur / 3))
    pieces = fit_plan(dur, length, start, loop_at, xfade)
    graph, labels = [], []
    for k, (t0, t1) in enumerate(pieces):
        graph.append(f'[0:a]atrim={t0:.3f}:{t1:.3f},asetpts=PTS-STARTPTS[p{k}]')
        labels.append(f'p{k}')
    cur = labels[0]
    for k, lab in enumerate(labels[1:], 1):
        graph.append(f'[{cur}][{lab}]acrossfade=d={xfade}:c1=tri:c2=tri[x{k}]')
        cur = f'x{k}'
    graph.append(f'[{cur}]atrim=0:{length:.3f},afade=t=in:d={fade_in},'
                 f'afade=t=out:st={max(0.0, length - fade_out):.3f}:d={fade_out},aresample={SR}[o]')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(track), '-filter_complex', ';'.join(graph), '-map', '[o]',
                    '-ac', '2', '-c:a', 'pcm_s16le', str(out_path)], check=True)
    out(f'{Path(out_path).name}：{length:.2f} 秒，从 {start:.2f} 秒开始' +
        (f'，原曲只有 {dur:.1f} 秒，在 {loop_at:.2f} 秒处循环 {len(pieces) - 1} 次' if len(pieces) > 1 else ''))
    return {'start': start, 'pieces': pieces, 'loop_at': loop_at if len(pieces) > 1 else None}


def mix_graph(duck_db, ratio, attack_ms, release_ms, threshold, voice='[0:a]', music='[1:a]'):
    return (f'{music}volume={duck_db}dB[m];{voice}asplit=2[v][sc];'
            f'[m][sc]sidechaincompress=threshold={threshold}:ratio={ratio}:attack={attack_ms}:release={release_ms}[md];'
            f'[v][md]amix=inputs=2:duration=first:normalize=0[mix]')


def mix_music(music, out_path, video=None, voice=None, cfg=None, out=print, **override):
    """Music under the narration (ducked while it speaks), then two-pass loudness normalisation."""
    import tempfile
    sys.path.insert(0, str(Path(__file__).resolve().parent))   # also under python -I
    import media_tools
    mix ={**MIX_DEFAULTS, **((cfg or {}).get('music') or {}).get('mix', {}), **override}
    if not (video or voice):
        raise Refused('mix 需要 --video（带旁白的成片）或 --voice（旁白音频）')
    graph = mix_graph(mix['duck_db'], mix['ratio'], mix['attack_ms'], mix['release_ms'], mix['threshold'])
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / ('mix' + Path(out_path).suffix)
        cmd = ['ffmpeg', '-v', 'error', '-y', '-i', str(video or voice), '-i', str(music), '-filter_complex', graph]
        cmd += (['-map', '0:v', '-map', '[mix]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k'] if video
                else ['-map', '[mix]', '-c:a', 'pcm_s16le'])
        subprocess.run(cmd + [str(raw)], check=True)
        res = media_tools.normalize(raw, out_path, mix['target'], mix['tp'], 11, True)
    out(f'{Path(out_path).name}：{res["result"]}')
    return res


# ------------------------------------------------------------------ voice list / register / clone / doctor
def save_config_voice(name, entry, path=CONFIG_PATH):
    data = json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).exists() else {}
    voice = data.setdefault('audio', {}).setdefault('voice', {})
    voice.setdefault('voices', {})[name] = entry
    voice.setdefault('default', name)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


AUDITION_TEXT = '大家好，欢迎收看今天的视频。我们先说结论，再一步步拆开讲。'


def load_presets(path=PRESETS_PATH):
    p = Path(path)
    return json.loads(p.read_text(encoding='utf-8'))['voices'] if p.exists() else []


def presets(gender=None, lang=None, path=PRESETS_PATH):
    """Built-in platform voices (speech-2.8) that were checked live; the platform's web 音色库 has more."""
    return [v for v in load_presets(path) if (not gender or v['gender'] == gender) and (not lang or v['lang'] == lang)]


def audition(cfg, provider, ids, out_dir, text=None, confirmed=False, max_cost=None, http=None, sleep=time.sleep,
             poll_every=4.0, timeout=600, out=print):
    """One sample line per voice, for the user to listen to before choosing; same quote and limit rules."""
    prov = provider_of(cfg, provider, http)
    b = budget(cfg)
    limit = b['confirm_over'] if max_cost is None else float(max_cost)
    model, opts, text = 'speech-2.8', (cfg.get('voice') or {}).get('defaults') or {}, text or AUDITION_TEXT
    tts = Path(out_dir) / 'tts'
    tts.mkdir(parents=True, exist_ok=True)
    jobs = []
    for vid in ids:
        key = request_key(prov.name, model, vid, opts, text)
        cached = tts / f'{vid}.{key}.wav'
        if cached.exists():
            shutil.copyfile(cached, tts / f'{vid}.wav')
            continue
        jobs.append({'section': vid, 'voice_id': vid, 'sent': text, 'key': key, 'cache': cached})
    failed = []
    if jobs:
        ventry = {'voice_id': jobs[0]['voice_id']}
        q = quote_jobs(prov, model, ventry, opts, jobs, b)
        q['limit'] = limit
        out(quote_text(q))
        gate(q, limit, confirmed)
        lane = q['chosen'].get('lane') if q['chosen'] else None
        failed = run_jobs(prov, model, ventry, opts, jobs, lane, out_dir, read_log(out_dir), sleep, poll_every, timeout,
                          out)
    names = {v['id']: v['name'] for v in load_presets()}
    for vid in ids:
        f = tts / f'{vid}.wav'
        if f.exists():
            out(f'试听 {vid}（{names.get(vid, "账号音色")}）：{f}')
    for j in failed:
        out(f'{j["section"]} 没有生成：{j["error"]}（失败不扣费；可能不是这个模型能用的音色 ID）')
    return [vid for vid in ids if (tts / f'{vid}.wav').exists()]


def register(cfg, name, provider, voice_id=None, owner=None, consent=None, yes=False, http=None, path=CONFIG_PATH,
             preset=None, out=print):
    prov = provider_of(cfg, provider, http)
    if preset:
        entry = {'provider': provider, 'model': 'speech-2.8', 'voice_id': preset, 'owner': '平台自带音色',
                 'consent': '平台预设音色，无需授权', 'preset': True}
        if preset not in {v['id'] for v in load_presets()}:
            out('注意：这个 ID 不在序幕核实过的平台音色表里；先 voice audition 试听，确认能用再登记')
        if not yes:
            raise Refused(f'将登记：{name} → {json.dumps(entry, ensure_ascii=False)}\n请用户确认后加 --yes 再运行')
        save_config_voice(name, entry, path)
        out(f'已登记 {name} → 平台音色 {preset}（写入 {Path(path).name}）')
        return entry
    found = prov.list_voices()
    match = [v for v in found if (voice_id and v['id'] == voice_id) or (not voice_id and v['name'] == name)]
    if not match:
        raise Refused(f'账号里没有找到{"音色 " + voice_id if voice_id else "名为" + name + "的音色"}。账号下的音色：'
                      + (', '.join(f'{v["name"]}({v["id"]})' for v in found) or '无'))
    v = match[0]
    entry = {'provider': provider, 'model': 'speech-2.8', 'voice_id': v['id'], 'owner': owner or '', 'consent': consent or ''}
    if v.get('status') not in (None, 'active', 'ready'):
        out(f'注意：这个音色当前状态是 {v.get("status")}')
    if not v.get('permanent'):
        entry['activation_pending'] = True
    if not yes:
        raise Refused(f'将登记：{name} → {json.dumps(entry, ensure_ascii=False)}\n请用户确认后加 --yes 再运行')
    save_config_voice(name, entry, path)
    out(f'已登记 {name} → {v["id"]}（写入 {Path(path).name}）')
    return entry


KEY_HELP = '''还没有设置造物社密钥（环境变量 {env}）。密钥由用户自己填，不要发到聊天里：
  1. 登录造物社，在「管理密钥」页新建一把密钥（只显示一次，先复制下来）；
  2. 推荐：后台运行 key_setup.py，会在浏览器打开一个本机网页，用户粘贴密钥、点保存，验证通过才保存；
     会用终端的也可以自己运行（把 sk-你的密钥 换成刚复制的；重开终端后生效）：
       Windows：setx {env} "sk-你的密钥"
       macOS：  echo 'export {env}="sk-你的密钥"' >> ~/.zshrc
  3. 然后运行 audio_cloud.py doctor 检查（网页保存的密钥不用重启就能读到）。'''


def check_models(cfg, image, pname, prov, out):
    """Free: what each default this provider serves would cost on the channel the balanced rule picks."""
    b = budget(cfg)
    rows = []
    voices = [v for v in ((cfg.get('voice') or {}).get('voices') or {}).values() if v.get('provider') == pname]
    sample = AUDITION_TEXT * 4   # ~120 characters: inside the per-call minimum, a typical joined call costs about this
    for v in voices[:1] or [{'model': 'speech-2.8', 'voice_id': 'male-qn-qingse'}]:
        rows.append(('配音', v.get('model', 'speech-2.8'), {'input': sample, 'voice': v['voice_id'],
                                                           **speech_tier((cfg.get('voice') or {}).get('defaults') or {})}))
    if (cfg.get('music') or {}).get('provider') == pname:
        rows.append(('配乐', cfg['music'].get('model', 'music'), {'mode': 'instrumental'}))
    if (image or {}).get('provider') == pname:
        rows.append(('生图', image.get('model', IMAGE_DEFAULTS['model']),
                     {'prompt': 'test', 'aspect_ratio': '16:9', **IMAGE_DEFAULTS['defaults'], **(image.get('defaults') or {})}))
    for label, model, params in rows:
        try:
            best, _, notes = choose_channel(prov.quote(model, params)['channels'], b['min_success_rate'], b['avoid_vendors'])
            rate = '—' if best.get('success_rate') is None else f'{best["success_rate"]:.0%}'
            out(f'  {label} {model}：{best["vendor"]} {round(best["price"], 4)} {prov.currency}/次，成功率 {rate}'
                + ''.join(f'；{n}' for n in notes))
        except Exception as e:
            out(f'  ✗ {label} {model} 估价失败：{e}')


def setup(path=CONFIG_PATH, yes=False, environ=os.environ, out=print):
    """Write the 造物社 provider and the image / music / voice defaults into backends.local.json, keeping everything
    already there. The key is never written: only the name of the environment variable that holds it."""
    p = Path(path)
    data = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    audio = data.setdefault('audio', {})
    changes = []
    if 'vvai' not in (audio.get('providers') or {}):
        audio.setdefault('providers', {})['vvai'] = dict(VVAI)
        changes.append(f'服务商 vvai：造物社 {VVAI["base_url"]}，密钥读环境变量 {VVAI["key_env"]}')
    if 'budget' not in audio:
        audio['budget'] = {'confirm_over': 1.0, 'min_success_rate': 0.9, 'avoid_vendors': []}
        changes.append('预算：单次预计不超过 1.0 直接执行，超过先问；只选近 24 小时成功率 ≥ 90% 的渠道')
    if 'voice' not in audio:
        audio['voice'] = {'defaults': {'tier': 'hd', 'speed': 1, 'emotion': 'auto'}, 'voices': {}}
        changes.append('配音：海螺 speech-2.8（HD），音色稍后从声纹库或平台音色里选')
    if 'music' not in audio:
        audio['music'] = {'provider': 'vvai', 'model': 'music',
                          'defaults': {'mode': 'instrumental', 'negative_tags': 'vocals, singing, rap'},
                          'license': '造物社 Suno 生成：能否商用以平台条款为准，交付前向用户确认', 'mix': {'duck_db': -11, 'target': -14}}
        changes.append('配乐：造物社 Suno，纯音乐')
    if 'image' not in data:
        data['image'] = {'provider': 'vvai', **json.loads(json.dumps(IMAGE_DEFAULTS))}
        changes.append(f'生图：{IMAGE_DEFAULTS["model"]}，4K、高质量（high）')
    if not changes:
        out('backends.local.json 里已经有造物社和各项默认设置，没有改动。')
    else:
        out('将写入 backends.local.json（已有的设置不动）：\n' + '\n'.join(f'  - {c}' for c in changes))
        if not yes:
            raise Refused('请用户确认后加 --yes 再运行')
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        out('已写入。')
    if not environ.get(VVAI['key_env']):
        out(KEY_HELP.format(env=VVAI['key_env']))
    return data


def smoke(cfg, image, out_dir, confirmed=False, max_cost=None, http=None, sleep=time.sleep, out=print):
    """One paid sample line and one image, to prove the whole chain before a real project."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))   # also under python -I
    import image_cloud
    voices = (cfg.get('voice') or {}).get('voices') or {}
    v = voices.get((cfg.get('voice') or {}).get('default')) or next(iter(voices.values()), None)
    provider = v['provider'] if v else (image or {}).get('provider', 'vvai')
    heard = audition(cfg, provider, [v['voice_id'] if v else 'male-qn-qingse'], out_dir, confirmed=confirmed,
                     max_cost=max_cost, http=http, sleep=sleep, out=out)
    rec = image_cloud.generate(cfg, image, out_dir, 'smoke', '一张简洁的桌面俯拍照片，木桌上放着笔记本电脑和一杯咖啡，自然光',
                               confirmed=confirmed, max_cost=max_cost, http=http, sleep=sleep, out=out)
    out(f'试跑完成：配音 {"成功" if heard else "失败"}，图片 {", ".join(rec.get("files") or [])}')
    return heard, rec


def doctor(cfg, http=None, environ=os.environ, out=print, image=None):
    ok = True
    if not cfg:
        out('没有 audio 配置：运行 audio_cloud.py setup 写入造物社的默认设置（或复制 backends.local.example.json 自己填）。'
            '没有配音接口时，可以自己录音（推荐）或不要旁白。')
        if not environ.get(VVAI['key_env']):
            out(KEY_HELP.format(env=VVAI['key_env']))
        return False
    for tool in ('ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            out(f'✗ 找不到 {tool}：运行 setup_env.py --check')
            ok = False
    for pname in cfg.get('providers') or {}:
        try:
            prov = provider_of(cfg, pname, http)
        except Refused as e:
            out(f'✗ {e}')
            ok = False
            continue
        if not prov.key_ready(environ):
            out(f'✗ {pname}：环境变量 {prov.conf.get("key_env")} 没有设置')
            if prov.conf.get('key_env') == VVAI['key_env']:
                out(KEY_HELP.format(env=VVAI['key_env']))
            ok = False
            continue
        try:
            n = len(prov.list_voices())
            out(f'✓ {pname}（{prov.kind}）：连通，账号声纹库 {n} 个音色'
                + ('（空：可以用 voice presets 里的平台音色）' if n == 0 and prov.has_price_api else ''))
        except Exception as e:
            out(f'✗ {pname}：查询音色失败 {e}')
            ok = False
            continue
        if prov.has_price_api:
            try:
                bal = prov.balance()
                out(f'  可用余额：{bal["available"]} {bal["unit"]}（{bal["usd"]}）')
            except Exception as e:
                out(f'  · 查余额失败：{e}')
            check_models(cfg, image, pname, prov, out)
    voices = (cfg.get('voice') or {}).get('voices') or {}
    for name, v in voices.items():
        flag = '（未激活：首次合成会收激活费）' if v.get('activation_pending') else ''
        out(f'  音色 {name} → {v.get("provider")} {v.get("voice_id")} {flag}')
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        out('· 本地对齐需要 faster-whisper（setup_env.py 会安装）；没有它只能生成，不能自动对齐')
    out(f'免确认额度：{budget(cfg)["confirm_over"]}')
    return ok


def clone(cfg, sample, name, provider, confirmed=False, max_cost=None, audio_url=None, http=None, sleep=time.sleep,
          out=print):
    prov = provider_of(cfg, provider, http)
    limit = budget(cfg)['confirm_over'] if max_cost is None else float(max_cost)
    price = (prov.conf.get('clone_price'))
    out(f'克隆：{Path(sample).name} → {provider}，名称 {name}；费用 {price if price is not None else "以服务商价格表为准"}')
    out('样本会上传到所配置的服务商。只克隆本人或已取得书面授权的声音。')
    if price is None or float(price) > limit:
        if max_cost is None:
            raise Refused('克隆费用未知或超过免确认额度：先问用户，同意后用 --max-cost 指定上限')
    if not confirmed:
        raise Refused('未运行：克隆需要 --confirmed')
    r = prov.clone(sample, name, audio_url)
    if r.get('task_id'):
        for _ in range(150):
            st = body(prov.get(f'/v1/tasks/{r["task_id"]}'), 'clone task')
            if st.get('is_final'):
                if st.get('status') != 'completed':
                    raise RuntimeError(f'克隆失败：{st.get("error")}')
                break
            sleep(4)
    out(f'克隆完成：{r["id"]}。{r["note"]} 用 voice register {name} --provider {provider} --voice-id {r["id"]} 登记')
    return r


# ------------------------------------------------------------------ cli
def main(argv=None, cfg=None, http=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('doctor', help='check config, keys (presence only), balance, channel prices; free')
    p = sub.add_parser('setup', help='write the 造物社 defaults into backends.local.json; --smoke runs one paid check')
    p.add_argument('--yes', action='store_true'); p.add_argument('--smoke', action='store_true')
    p.add_argument('--out', default='xumu-smoke'); p.add_argument('--confirmed', action='store_true')
    p.add_argument('--max-cost', type=float)
    v = sub.add_parser('voice').add_subparsers(dest='vcmd', required=True)
    p = v.add_parser('list'); p.add_argument('--provider')
    p = v.add_parser('presets'); p.add_argument('--gender', choices=['男', '女', '童']); p.add_argument('--lang')
    p = v.add_parser('audition'); p.add_argument('--provider', required=True); p.add_argument('--ids', required=True)
    p.add_argument('--out', required=True); p.add_argument('--text'); p.add_argument('--confirmed', action='store_true')
    p.add_argument('--max-cost', type=float)
    p = v.add_parser('register'); p.add_argument('name'); p.add_argument('--provider', required=True)
    p.add_argument('--voice-id'); p.add_argument('--preset', help='a built-in platform voice id (voice presets)')
    p.add_argument('--owner'); p.add_argument('--consent'); p.add_argument('--yes', action='store_true')
    for nm in ('estimate', 'speak'):
        p = v.add_parser(nm); p.add_argument('script'); p.add_argument('--voice'); p.add_argument('--edit')
        p.add_argument('--section', help='comma-separated section ids (default: all)')
        p.add_argument('--no-batch', action='store_true', help='one call per section (no joining)')
        if nm == 'speak':
            p.add_argument('--confirmed', action='store_true'); p.add_argument('--max-cost', type=float)
            p.add_argument('--lead', type=float, default=0.45); p.add_argument('--gap', type=float, default=0.45)
        else:
            p.add_argument('--json', action='store_true')
    p = v.add_parser('align'); p.add_argument('--edit', required=True)
    p = v.add_parser('clone'); p.add_argument('sample'); p.add_argument('--name', required=True)
    p.add_argument('--provider', required=True); p.add_argument('--confirmed', action='store_true')
    p.add_argument('--max-cost', type=float); p.add_argument('--audio-url')
    mu = sub.add_parser('music').add_subparsers(dest='mcmd', required=True)
    p = mu.add_parser('generate'); p.add_argument('--edit', required=True); p.add_argument('--prompt', required=True)
    p.add_argument('--style'); p.add_argument('--negative'); p.add_argument('--name', default='bgm')
    p.add_argument('--confirmed', action='store_true'); p.add_argument('--max-cost', type=float)
    p.add_argument('--no-check', action='store_true')
    p = mu.add_parser('check'); p.add_argument('track')
    p = mu.add_parser('fit'); p.add_argument('track'); p.add_argument('--len', type=float, required=True)
    p.add_argument('--out', required=True); p.add_argument('--start', type=float)
    p.add_argument('--fade-in', type=float); p.add_argument('--fade-out', type=float)
    p = mu.add_parser('mix'); p.add_argument('--music', required=True); p.add_argument('--out', required=True)
    p.add_argument('--video'); p.add_argument('--voice'); p.add_argument('--duck-db', type=float)
    p.add_argument('--target', type=float)
    a = ap.parse_args(argv)
    cfg = load_config() if cfg is None else cfg
    try:
        if a.cmd == 'doctor':
            return 0 if doctor(cfg, http, image=load_config(section='image')) else 1
        if a.cmd == 'setup':
            if a.smoke:
                smoke(cfg, load_config(section='image'), a.out, a.confirmed, a.max_cost, http)
            else:
                setup(yes=a.yes)
            return 0
        if a.cmd == 'music':
            if a.mcmd == 'generate':
                generate_music(cfg, a.edit, a.prompt, a.style, a.negative, a.name, a.confirmed, a.max_cost, http,
                               check=not a.no_check)
            elif a.mcmd == 'check':
                v = vocal_check(a.track)
                print('没有检出人声' if not v else '检出人声：' + '；'.join(v))
            elif a.mcmd == 'fit':
                fit_music(a.track, a.len, a.out, a.start, a.fade_in, a.fade_out)
            else:
                over = {k: v for k, v in (('duck_db', a.duck_db), ('target', a.target)) if v is not None}
                mix_music(a.music, a.out, a.video, a.voice, cfg, **over)
            return 0
        if a.vcmd == 'list':
            names = [a.provider] if a.provider else list(cfg.get('providers') or {})
            for pn in names:
                for x in provider_of(cfg, pn, http).list_voices():
                    print(f'{pn}\t{x["name"]}\t{x["id"]}\t{x["status"]}\t{"永久" if x.get("permanent") else ""}')
            return 0
        if a.vcmd == 'presets':
            rows = presets(a.gender, a.lang)
            for x in rows:
                print(f'{x["id"]}\t{x["name"]}\t{x["gender"]}\t{x["lang"]}\t{x.get("note", "")}')
            print(f'共 {len(rows)} 个（序幕核实过的常用平台音色；造物社网页「音色库」里还有更多，ID 同样可用）')
            return 0
        if a.vcmd == 'audition':
            audition(cfg, a.provider, a.ids.split(','), a.out, a.text, a.confirmed, a.max_cost, http)
            return 0
        if a.vcmd == 'register':
            register(cfg, a.name, a.provider, a.voice_id, a.owner, a.consent, a.yes, http, preset=a.preset)
            return 0
        if a.vcmd == 'estimate':
            name, ventry, prov = pick_voice(cfg, a.voice)
            prov.http = http
            model = ventry.get('model', 'speech-2.8')
            opts = {**((cfg.get('voice') or {}).get('defaults') or {}), **(ventry.get('options') or {})}
            secs = [s for s in parse_script(a.script) if not a.section or s['id'] in a.section.split(',')]
            table = pronounce_table(cfg, a.edit)
            jobs = [{'section': s['id'], 'sent': apply_pronounce(s['text'], table)} for s in secs]
            key_of = lambda text: request_key(prov.name, model, ventry['voice_id'], opts, text)
            jobs = [chunk_job(g, Path(a.edit or '.') / 'tts', key_of)
                    for g in batch_groups(jobs, batch_min_chars(cfg, prov, a.no_batch))]
            q = quote_jobs(prov, model, ventry, opts, jobs, budget(cfg))
            q['limit'] = budget(cfg)['confirm_over']
            print(json.dumps(q, ensure_ascii=False, indent=1, default=str) if a.json else quote_text(q), end='')
            return 0
        if a.vcmd == 'speak':
            if not a.edit:
                raise Refused('speak 需要 --edit')
            speak(cfg, a.script, a.edit, a.voice, a.section.split(',') if a.section else None, a.confirmed, a.max_cost,
                  http, lead=a.lead, gap=a.gap, no_batch=a.no_batch)
            return 0
        if a.vcmd == 'align':
            align(a.edit)
            return 0
        if a.vcmd == 'clone':
            clone(cfg, a.sample, a.name, a.provider, a.confirmed, a.max_cost, a.audio_url, http)
            return 0
    except Refused as e:
        print(str(e))
        return 3
    return 0


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))   # also under python -I
    import key_setup
    key_setup.load_user_env()   # a key saved after this terminal or agent host started
    sys.exit(main())
