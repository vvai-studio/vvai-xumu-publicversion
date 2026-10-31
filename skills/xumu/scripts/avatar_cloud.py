#!/usr/bin/env python3
"""Digital-human backend: one portrait photo + the narration script -> a talking-presenter video, through the provider
the user configured (造物社), behind audio_cloud's paid-call layer.

  python avatar_cloud.py check --image IMG [--out OUT.jpg]
  python avatar_cloud.py plan --edit EDIT [--model kling-v4|wan-3-0|kling-avatar] [--audio WAV] [--max-seg S]
  python avatar_cloud.py estimate --edit EDIT [--quality std|pro] [--resolution 720p|1080p] [--only 1,3]
  python avatar_cloud.py generate --edit EDIT --image IMG [--motion 小|中|大] [--extra TEXT] [--resolution R]
                                  [--quality Q] [--only 1,3] [--voice-ok "用户的原话"] [--user-asked "用户的原话"]
                                  [--skip-sample]
                                  --confirmed [--max-cost N]
  python avatar_cloud.py finish --edit EDIT [--no-align]
  python avatar_cloud.py lipsync --edit EDIT --video CLIP.mp4 --audio NEW.wav --name NAME --confirmed [--max-cost N]

Two kinds of model, chosen at plan time (default kling-v4, backup wan-3-0; config avatar.model):
  speak   kling-v4, wan-3-0. The model says the lines itself: each segment's script text goes into the prompt, and a
          short clip of the finished narration (the user's cloned voice, at most 15 s) is the voice reference. The
          voice is the model's rendering of that timbre, not the narration file. Segments follow the script sections
          from `audio_cloud.py voice speak` (tts/manifest.json), split at sentence ends to at most 30 s, and the
          requested length is the narration's length plus a little room. Tested live 2026-10-27 on a 7 s line: both
          said it word for word and kept the face (kling-v4 2.28⚡, wan-3-0 2.80⚡).
  audio   kling-avatar. The mouth follows the narration file exactly; segments are cut at pauses of the audio (up to
          300 s each). Real-person photos need the platform's likeness consent first (HTTP 403
          likeness_consent_required, not charged).

A digital human is used only when the user asked for one, or the decision doc (director.json grid 7, field avatar:
use, source user_asked|suggested, reason) suggested it with a reason and the user confirmed grid 7; generate checks
this first. A project without a decision doc needs --user-asked "the user's own words".

The narration must be final first: generate asks for the user's own words approving this version (--voice-ok),
stores them with the narration's hash in avatar/voice_review.json, and refuses when it has changed since. The first
run on a project with more than three segments sends one sample segment only (--only N), so the user can judge
gestures before paying for the rest (--skip-sample when they already have). Same paid-call rules as audio_cloud:
quote every segment, pin the balanced channel, run only under the no-confirm limit or --max-cost, log every task
before polling (an interrupted run resumes), reuse an identical earlier request, never switch channel after a failure.

finish joins the segments into avatar/final_avatar.mp4. audio models: the narration replaces the model's audio.
speak models: each take keeps its own voice, its silent tail is trimmed, and the takes are written as sections to
avatar/voice/ (manifest.json + one wav each) and aligned to the script with `audio_cloud.align(tts='avatar/voice')`,
so cue_chars.json and sections.json describe what the presenter actually says and the rest of the pipeline (cue.py,
subtitles) works unchanged. Quality check: lengths, frozen stretches, seam and contact sheets, and (with OpenCV)
stretches where speech is heard but the mouth barely moves, all into avatar/anomalies.json for covering in packaging
(presenter to a small window or off screen for those seconds) before anyone pays for a rerun. A rerun of one segment
is `generate --only N` after moving that segment's mp4 away (old takes are kept in avatar/takes/).

Prompt rules learned from talking-head generation: describe hands, head, shoulders and posture only; never the face,
mouth or expression (that tends to freeze the mouth); nothing that is not in the photo; camera fixed, background and
clothes unchanged.

lipsync re-voices an existing single-speaker clip (kling-lip-sync, at most 60 s): new words, other language.
"""
import argparse
import json
import math
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

sys.path.insert(0, str(Path(__file__).resolve().parent))   # also under python -I
import audio_cloud as ac  # noqa: E402

DEFAULTS = {'model': 'kling-v4', 'quality': 'std', 'resolution': '720p', 'lipsync_model': 'kling-lip-sync', 'min_seg': 4}
# what each model takes; speak = says the prompt's lines in the reference voice, audio = lip-syncs the given audio
MODELS = {
    'kling-v4': {'kind': 'speak', 'max_seg': 30, 'durations': list(range(3, 31)), 'resolutions': ('720p', '1080p')},
    'wan-3-0': {'kind': 'speak', 'max_seg': 30, 'durations': list(range(5, 16)) + [20, 25, 30],
                'resolutions': ('480p', '720p', '1080p')},
    'kling-avatar': {'kind': 'audio', 'max_seg': 60, 'limit': 300},
}
REF_MAX = 15.0   # voice reference length the speak models accept
LOG = 'avatar/avatar_log.json'
IMAGE_RULES = {'min_short': 300, 'good_short': 720, 'min_ratio': 0.4, 'max_ratio': 2.5, 'max_bytes': 10 * 1024 * 1024,
               'max_long': 3840}
MOTION = {
    '小': '人物保持图片里的姿势，头部随说话自然轻点，双手放松，偶尔轻抬一下再放回原处，肩膀和身体基本不动。',
    '中': '人物保持图片里的姿势，头部随语气自然点动和轻微侧转；说到重点时单手在胸前比划或掌心朝上示意，'
          '列举时用手指计数，句与句之间双手自然落回原位。',
    '大': '人物保持图片里的姿势，手势丰富、幅度大：强调时双手张开或有力下压，列举时逐个伸出手指，'
          '说到"你"时手掌朝向镜头；身体随语气前倾或后靠，句子之间双手回到身前。',
}
FIXED = '镜头固定不推拉，背景、光线、服装与图片完全一致，不出现图片里没有的物品。'
SPEAK = '这个人正对镜头，用参考音频里的声音、普通话、自然口语的语气说："{text}" '
NO_EXTRAS = '不加字幕、不加背景音乐和音效。'
SENT_END = re.compile(r'(?<=[。！？!?；;])')


# ------------------------------------------------------------------ config
def settings(cfg, model=None):
    a = {**DEFAULTS, **(cfg.get('avatar') or {})}
    if model:
        a['model'] = model
    if a['model'] not in MODELS:
        raise ac.Refused(f'数字人模型只能是 {"、".join(MODELS)}')
    a['spec'] = MODELS[a['model']]
    if not a.get('provider'):
        gw = [n for n, p in (cfg.get('providers') or {}).items() if p.get('type') == 'gateway-media']
        if not gw:
            raise ac.Refused('没有可用的视频服务商：先运行 audio_cloud.py setup 配好造物社')
        a['provider'] = gw[0]
    return a


def provider(cfg, a, http=None):
    prov = ac.provider_of(cfg, a['provider'], http)
    if not hasattr(prov, 'submit_video'):
        raise ac.Refused(f'服务商 "{a["provider"]}"（{prov.kind}）不支持视频生成')
    return prov


def adir(edit):
    d = Path(edit) / 'avatar'
    d.mkdir(parents=True, exist_ok=True)
    return d


def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height:format=duration',
                        '-of', 'json', str(path)], capture_output=True, text=True)
    d = json.loads(r.stdout or '{}')
    v = next((s for s in d.get('streams', []) if s.get('codec_type') == 'video'), {})
    return {'width': v.get('width'), 'height': v.get('height'),
            'duration': float((d.get('format') or {}).get('duration') or 0)}


def to_mp3(src, dst, start=None, end=None):
    cut = (['-ss', f'{start:.3f}'] if start is not None else []) + (['-to', f'{end:.3f}'] if end is not None else [])
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *cut, '-i', str(src), '-ac', '1', '-ar', '44100',
                    '-c:a', 'libmp3lame', '-b:a', '192k', str(dst)], check=True)


# ------------------------------------------------------------------ image
def check_image(image, out=None):
    """Whether the photo fits the model; writes a JPEG copy (the models take jpg/png up to 10 MB)."""
    src = Path(image)
    if not src.is_file():
        raise ac.Refused(f'图片不存在：{src}')
    info = probe(src)
    w, h = info['width'] or 0, info['height'] or 0
    if not w or not h:
        raise ac.Refused(f'读不出图片尺寸：{src}')
    risks, ok = [], True
    short, ratio = min(w, h), w / h
    if short < IMAGE_RULES['min_short']:
        risks.append(f'短边只有 {short}px，模型要求至少 {IMAGE_RULES["min_short"]}px'); ok = False
    elif short < IMAGE_RULES['good_short']:
        risks.append(f'短边 {short}px 偏小，成片会糊；最好 {IMAGE_RULES["good_short"]}px 以上')
    if not IMAGE_RULES['min_ratio'] <= ratio <= IMAGE_RULES['max_ratio']:
        risks.append(f'宽高比 {ratio:.2f} 超出 0.4–2.5'); ok = False
    dst = Path(out) if out else src.with_name(src.stem + '_avatar.jpg')
    dst.parent.mkdir(parents=True, exist_ok=True)
    big = max(w, h) > IMAGE_RULES['max_long']
    if src.suffix.lower() in ('.jpg', '.jpeg') and src.stat().st_size <= IMAGE_RULES['max_bytes'] and not big:
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
    else:
        # phone photos run to 6000+ px: the output is at most 1080p, so a 4K-long-side copy loses nothing
        scale = ['-vf', f'scale={IMAGE_RULES["max_long"]}:-2' if w >= h else f'scale=-2:{IMAGE_RULES["max_long"]}'] if big else []
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), *scale, '-q:v', '2', str(dst)], check=True)
    if dst.stat().st_size > IMAGE_RULES['max_bytes']:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-vf', 'scale=-2:min(ih\\,2160)', '-q:v', '3',
                        str(dst)], check=True)
    orient = '竖屏' if h > w else '横屏' if w > h else '方形'
    return {'ok': ok, 'image': str(dst), 'size': f'{w}x{h}', 'orientation': orient, 'risks': risks,
            'aspect': '9:16' if h > w else '16:9' if w > h else '1:1',
            'note': f'成片画幅跟图片一致（{orient}）；嘴闭着、表情平静、双手在身前的图接缝最干净'}


# ------------------------------------------------------------------ plan
def cut_points(samples, sr, max_seg=60.0, min_seg=4.0, min_pause=0.3):
    """Segment boundaries (seconds, including 0 and the end) placed in the middle of pauses."""
    total = len(samples) / sr
    pauses = [((a + b) / 2, b - a) for a, b in ac.quiet_runs(samples, sr) if b - a >= min_pause and 0.05 < a and b < total - 0.05]
    cuts, cur = [0.0], 0.0
    while total - cur > max_seg:
        lo, hi = cur + min_seg, cur + max_seg
        window = [p for p in pauses if lo <= p[0] <= hi]
        late = [p for p in window if p[0] >= cur + max_seg * 0.6] or window
        if late:
            cut = max(late, key=lambda p: (p[1], p[0]))[0]   # the longest pause late in the window
        else:
            cut = hi   # no pause at all: a hard cut, flagged in the plan
        cuts.append(round(cut, 3))
        cur = cut
    if len(cuts) > 1 and total - cuts[-1] < min_seg:
        cuts.pop()   # fold a tiny tail into the previous segment
    return cuts + [round(total, 3)]


def split_text(text, seconds, max_seg):
    """A section longer than max_seg -> pieces at sentence ends, each with its share of the section's seconds."""
    clean = ac.strip_pauses(text)
    if seconds <= max_seg:
        return [(clean, seconds)]
    parts = [p for p in SENT_END.split(clean) if p.strip()]
    chars = max(1, sum(len(p) for p in parts))
    out, cur = [], ''
    for p in parts:
        if cur and (len(cur) + len(p)) / chars * seconds > max_seg:
            out.append(cur)
            cur = ''
        cur += p
    out.append(cur)
    return [(o, round(seconds * len(o) / chars, 3)) for o in out]


def request_duration(spec, seconds):
    """Smallest allowed length with room for a slower read (the models pace themselves)."""
    need = seconds * 1.1 + 0.5
    fits = [d for d in spec['durations'] if d >= need]
    return fits[0] if fits else spec['durations'][-1]


def speak_plan(edit, a, max_seg):
    edit = Path(edit)
    man = edit / 'tts' / 'manifest.json'
    if not man.exists():
        raise ac.Refused(f'{a["model"]} 按文案说台词：先用 audio_cloud.py voice speak 生成配音（会写 tts/manifest.json）；'
                         '只有录音没有文案时用 --model kling-avatar')
    manifest = json.loads(man.read_text(encoding='utf-8'))
    narration = edit / 'tts' / 'narration.wav'
    d = adir(edit)
    ref = d / 'voice_ref.mp3'
    # the voice reference: the narration's opening (the user's cloned voice), at most 15 s
    to_mp3(narration, ref, 0, min(REF_MAX, manifest['total']))
    segs, n = [], 0
    for s in manifest['sections']:
        for text, sec in split_text(s['text'], s['seconds'], max_seg):
            n += 1
            dur = request_duration(a['spec'], sec)
            if sec > dur:
                raise ac.Refused(f'{s["id"]} 有一句约 {sec:.1f} 秒，超过 {a["model"]} 单段上限 {dur} 秒：在文案里加句号断开')
            segs.append({'n': n, 'section': s['id'], 'text': text, 'seconds': round(sec, 3), 'duration': dur})
    return {'model': a['model'], 'kind': 'speak', 'audio': str(narration), 'audio_hash': ac.file_hash(narration),
            'voice_ref': ref.name, 'voice_ref_hash': ac.file_hash(ref), 'duration': manifest['total'],
            'max_seg': max_seg, 'segments': segs, 'hard_cuts': []}


def audio_plan(edit, a, audio, max_seg, min_seg):
    src = Path(audio) if audio else Path(edit) / 'tts' / 'narration.wav'
    if not src.is_file():
        raise ac.Refused(f'没有配音：{src}。先用 audio_cloud.py voice speak 生成，或用 --audio 指定录音')
    if max_seg > a['spec']['limit']:
        raise ac.Refused(f'每段最长 {a["spec"]["limit"]} 秒（模型上限）')
    samples = ac.load_samples(src)
    cuts = cut_points(samples, 16000, max_seg, min_seg)
    d = adir(edit)
    segs, hard = [], []
    for n, (s, e) in enumerate(zip(cuts, cuts[1:]), 1):
        mp3 = d / f'seg_{n:02d}.mp3'
        to_mp3(src, mp3, s, e)
        i1 = int(e * 16000)
        if n < len(cuts) - 1 and not ac.quiet_runs(samples[max(0, i1 - 1600):i1 + 1600], 16000):
            hard.append(n)
        segs.append({'n': n, 'start': s, 'end': e, 'seconds': round(e - s, 3), 'duration': int(math.ceil(e - s)),
                     'audio': mp3.name, 'audio_hash': ac.file_hash(mp3)})
    return {'model': a['model'], 'kind': 'audio', 'audio': str(src), 'audio_hash': ac.file_hash(src),
            'duration': cuts[-1], 'max_seg': max_seg, 'segments': segs, 'hard_cuts': hard}


def make_plan(edit, audio=None, max_seg=None, min_seg=None, cfg=None, model=None):
    a = settings(cfg or {}, model)
    max_seg = float(max_seg or (cfg or {}).get('avatar', {}).get('max_seg') or a['spec']['max_seg'])
    min_seg = float(min_seg or a['min_seg'])
    if a['spec']['kind'] == 'speak':
        if audio:
            raise ac.Refused(f'{a["model"]} 自己说台词，不用 --audio；要嘴型跟录音走用 --model kling-avatar')
        plan = speak_plan(edit, a, min(max_seg, a['spec']['max_seg']))
    else:
        plan = audio_plan(edit, a, audio, max_seg, min_seg)
    (adir(edit) / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding='utf-8')
    return plan


def load_plan(edit):
    p = Path(edit) / 'avatar' / 'plan.json'
    if not p.exists():
        raise ac.Refused('还没有分段：先运行 avatar_cloud.py plan --edit …')
    plan = json.loads(p.read_text(encoding='utf-8'))
    plan.setdefault('model', 'kling-avatar')
    plan.setdefault('kind', MODELS[plan['model']]['kind'])
    src = Path(plan['audio'])
    if src.exists() and ac.file_hash(src) != plan['audio_hash']:
        raise ac.Refused('配音在分段之后改过：重新运行 plan（已生成的人物视频对不上新配音）')
    return plan


# ------------------------------------------------------------------ prompt, params, quote
def build_prompt(motion='中', extra='', text=None):
    if motion not in MOTION:
        raise ac.Refused(f'动作幅度只能是 {"、".join(MOTION)}')
    head = SPEAK.format(text=text) if text is not None else ''
    return head + MOTION[motion] + FIXED + (NO_EXTRAS if text is not None else '') + (extra.strip() if extra else '')


def seg_params(a, plan, s, prompt, image_url='https://example.com/avatar.jpg', audio_url='https://example.com/seg.mp3',
               quality=None, resolution=None, aspect='9:16'):
    if plan['kind'] == 'speak':
        res = resolution or a['resolution']
        if res not in a['spec']['resolutions']:
            raise ac.Refused(f'{a["model"]} 的分辨率只能是 {"、".join(a["spec"]["resolutions"])}')
        return {'mode': 'reference', 'images': [image_url], 'audios': [audio_url], 'duration': s['duration'],
                'resolution': res, 'aspect_ratio': aspect, 'prompt': prompt}
    # duration is not a kling-avatar input (the video follows the audio) but the price estimate needs it
    return {'images': [image_url], 'audios': [audio_url], 'quality': quality or a['quality'], 'prompt': prompt,
            'duration': s['duration']}


def prompt_of(plan, s, motion, extra):
    return build_prompt(motion, extra, s['text'] if plan['kind'] == 'speak' else None)


def quote(prov, a, plan, segs, motion, extra, b, limit, quality=None, resolution=None, aspect='9:16'):
    cache, total, chosen, ordered, notes, q = {}, 0.0, None, [], [], {'note': ''}
    for s in segs:
        if s['duration'] not in cache:
            cache[s['duration']] = prov.quote(a['model'], seg_params(a, plan, s, prompt_of(plan, s, motion, extra),
                                                                     quality=quality, resolution=resolution, aspect=aspect))
        q = cache[s['duration']]
        best, ordered, notes = ac.choose_channel(q['channels'], b['min_success_rate'], b['avoid_vendors'])
        if best is None:
            return {'provider': prov.name, 'note': q['note'], 'count': len(segs), 'channels': q['channels'],
                    'chosen': None, 'total': None, 'currency': prov.currency, 'notes': notes, 'limit': limit}
        chosen = chosen or best
        # every segment goes on the first segment's channel: price it there
        same = next((c for c in q['channels'] if c.get('lane') == chosen.get('lane')), best)
        total += same['price'] if same.get('price') is not None else best['price']
    return {'provider': prov.name, 'note': q['note'], 'count': len(segs), 'channels': ordered, 'chosen': chosen,
            'total': round(total, 4), 'currency': prov.currency, 'notes': notes, 'limit': limit,
            'seconds': round(sum(s['duration'] for s in segs), 1)}


def pick(segs, only):
    if not only:
        return list(segs)
    want = {int(x) for x in str(only).split(',') if x.strip()}
    return [s for s in segs if s['n'] in want]


# ------------------------------------------------------------------ voice approval
def voice_review(edit, plan, words=None):
    p = Path(edit) / 'avatar' / 'voice_review.json'
    rec = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    if words:
        rec = {'audio_hash': plan['audio_hash'], 'words': words, 'at': time.strftime('%Y-%m-%d %H:%M:%S')}
        p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
    if rec.get('audio_hash') != plan['audio_hash']:
        raise ac.Refused('提交前要用户确认这一版配音：把试听文件给用户，用户同意后用 --voice-ok "用户的原话" 重跑'
                         '（只能填用户真的说过的话；配音改过之后要重新确认）')
    return rec


# ------------------------------------------------------------------ whether to use one at all
def avatar_decision(edit, user_asked=None):
    """A digital human only when the user asked for one, or the decision doc suggested it with a reason and the user
    confirmed that grid. With a director.json, grid 7's avatar field decides; without one, the user's own words
    (--user-asked) are recorded in avatar/decision.json."""
    doc_file = Path(edit) / 'director.json'
    rec_file = Path(edit) / 'avatar' / 'decision.json'
    if doc_file.exists():
        import director
        ok, why = director.avatar_allowed(json.loads(doc_file.read_text(encoding='utf-8')))
        if not ok:
            raise ac.Refused(why)
        return why
    if user_asked:
        adir(edit)
        rec_file.write_text(json.dumps({'source': 'user_asked', 'words': user_asked, 'at': time.strftime('%Y-%m-%d %H:%M:%S')},
                                       ensure_ascii=False, indent=1), encoding='utf-8')
    if not rec_file.exists():
        raise ac.Refused('数字人只在用户要求、或决策书建议并经用户确认时才生成：这个项目没有决策书，'
                         '用户明确要数字人时用 --user-asked "用户的原话" 记下来')
    return '用户要求：' + json.loads(rec_file.read_text(encoding='utf-8'))['words']


# ------------------------------------------------------------------ generate
def generate(cfg, edit, image, quality=None, motion='中', extra='', only=None, voice_ok=None, skip_sample=False,
             confirmed=False, max_cost=None, http=None, sleep=time.sleep, poll_every=10.0, timeout=3600, out=print,
             resolution=None, user_asked=None):
    why = avatar_decision(edit, user_asked)
    plan = load_plan(edit)
    a = settings(cfg, plan['model'])
    prov = provider(cfg, a, http)
    review = voice_review(edit, plan, voice_ok)
    b = ac.budget(cfg)
    limit = b['confirm_over'] if max_cost is None else float(max_cost)
    d = adir(edit)
    img = check_image(image, d / 'image.jpg')
    if not img['ok']:
        raise ac.Refused('图片不能用：' + '；'.join(img['risks']))
    img_hash = ac.file_hash(d / 'image.jpg')
    log = ac.read_log(edit, LOG)
    opts = {'quality': quality or a['quality']} if plan['kind'] == 'audio' else {'resolution': resolution or a['resolution']}
    todo, waiting = [], []
    for s in pick(plan['segments'], only):
        prompt = prompt_of(plan, s, motion, extra)
        sound = s.get('audio_hash') or plan['voice_ref_hash']
        s['key'] = ac.request_key(prov.name, a['model'], img_hash, {**opts, 'prompt': prompt, 'duration': s['duration']}, sound)
        done = d / f'seg_{s["n"]:02d}.mp4'
        prev = next((e for e in reversed(log) if e.get('key') == s['key']), None)
        if prev and prev.get('state') == 'success' and done.exists():
            out(f'第 {s["n"]} 段已生成过（复用，不再付费）')
        elif prev and prev.get('state') == 'submitted':
            out(f'第 {s["n"]} 段上次已提交（{prev["task_id"]}），继续查询')
            waiting.append((s, prev))
        else:
            todo.append(s)
    ever = any(e.get('state') == 'success' and e.get('kind') == 'avatar' for e in log)
    if todo and not ever and not only and not skip_sample and len(plan['segments']) > 3:
        pick_n = max(plan['segments'], key=lambda s: s['seconds'])['n']
        raise ac.Refused(f'共 {len(plan["segments"])} 段，还没有跑过样段：先只跑一段看动作幅度和手势，'
                         f'例如 --only {pick_n}；用户看过、说可以再全量（或用户已经说过不用看样段时加 --skip-sample）')
    if todo:
        q = quote(prov, a, plan, todo, motion, extra, b, limit, opts.get('quality'), opts.get('resolution'), img['aspect'])
        out(ac.quote_text(q) + f'{a["model"]}：{len(todo)} 段，合计请求 {q.get("seconds")} 秒；'
            f'{"画质 " + opts["quality"] if "quality" in opts else opts["resolution"]}，动作幅度 {motion}')
        ac.gate(q, limit, confirmed)
        image_url = prov.upload_file(d / 'image.jpg')
        ref_url = prov.upload_file(d / plan['voice_ref']) if plan['kind'] == 'speak' else None
        attempt = len(log)
        for s in todo:
            audio_url = ref_url or prov.upload_file(d / s['audio'])
            params = seg_params(a, plan, s, prompt_of(plan, s, motion, extra), image_url, audio_url,
                                opts.get('quality'), opts.get('resolution'), img['aspect'])
            try:
                task = prov.submit_video(a['model'], params, q['chosen'].get('lane'), request_id=f'xumu-av-{s["key"]}-{attempt}')
            except RuntimeError as e:   # refused before any charge (e.g. likeness consent, balance): say why, stop
                raise ac.Refused(f'第 {s["n"]} 段没有提交成功（未扣费）：{e}')
            attempt += 1
            entry = {'key': s['key'], 'kind': 'avatar', 'segment': s['n'], 'provider': prov.name, 'model': a['model'],
                     'lane': q['chosen'].get('lane'), 'task_id': task, 'state': 'submitted', 'seconds': s['seconds'],
                     'duration': s['duration'], **opts, 'motion': motion, 'prompt': params['prompt'],
                     'voice_ok': review.get('words'), 'why': why, 'alternatives': [c for c in q['channels'] if c is not q['chosen']][:3],
                     'at': time.strftime('%Y-%m-%d %H:%M:%S')}
            log.append(entry)
            ac.write_log(edit, log, LOG)
            out(f'第 {s["n"]} 段已提交 {task}（{s["duration"]} 秒）')
            waiting.append((s, entry))
    failed = []
    waited = 0.0
    while waiting:
        for s, e in list(waiting):
            st = prov.poll(e['task_id'])
            if not st.get('final'):
                continue
            waiting.remove((s, e))
            e['cost'] = st.get('cost')
            if not st.get('ok'):
                e['state'], e['error'] = 'failed', st.get('error')
                failed.append((s, e))
            else:
                dst = d / f'seg_{s["n"]:02d}.mp4'
                if dst.exists():   # an earlier take: keep it
                    takes = d / 'takes'
                    takes.mkdir(exist_ok=True)
                    dst.replace(takes / f'seg_{s["n"]:02d}_{time.strftime("%Y%m%d%H%M%S")}.mp4')
                dst.write_bytes(ac.fetch(prov.http, (st.get('urls') or [st['url']])[0], sleep))
                e['state'], e['file'] = 'success', dst.name
                out(f'第 {s["n"]} 段完成：{dst.name}（{probe(dst)["duration"]:.2f} 秒），花费 {st.get("cost")}')
            ac.write_log(edit, log, LOG)
        if waiting:
            if waited >= timeout:
                raise RuntimeError('超时：仍有段未完成；稍后重跑同一命令会继续查询，不重复付费')
            sleep(poll_every)
            waited += poll_every
    if failed:
        lines = [f'第 {s["n"]} 段失败：{e.get("error") or "未知错误"}' for s, e in failed]
        alts = failed[0][1].get('alternatives') or []
        lines += ['失败的任务不扣费。没有自动换渠道；可选：'] + \
                 [f'  {c.get("vendor")}（lane {c.get("lane")}）{c.get("price")} {prov.currency}' for c in alts] + \
                 ([] if alts else ['  稍后再试；同一段连续两次失败时，换一张图或改动作描述']) + \
                 (['  或换备选模型：plan --model wan-3-0 重新分段'] if a['model'] == 'kling-v4' else [])
        raise ac.Refused('\n'.join(lines))
    missing = [s['n'] for s in plan['segments'] if not (d / f'seg_{s["n"]:02d}.mp4').exists()]
    spent = round(sum(e.get('cost') or 0 for e in ac.read_log(edit, LOG) if e.get('state') == 'success'), 4)
    out(('还没生成的段：' + '、'.join(map(str, missing))) if missing else '全部段已生成：运行 finish 拼接与质检')
    out(f'本项目数字人累计花费 {spent}')
    return {'missing': missing, 'spent': spent}


# ------------------------------------------------------------------ finish + QC
def _frames(video, times, out_path, width=320):
    tiles = []
    tmp = Path(out_path).with_suffix('')
    tmp.mkdir(exist_ok=True)
    for k, t in enumerate(times):
        f = tmp / f'{k:03d}.jpg'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{max(0, t):.3f}', '-i', str(video), '-frames:v', '1',
                        '-vf', f'scale={width}:-2', str(f)], check=False)
        if f.exists():
            tiles.append(f)
    if tiles:
        cols = min(6, len(tiles))
        rows = math.ceil(len(tiles) / cols)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', '1', '-i', str(tmp / '%03d.jpg'),
                        '-vf', f'tile={cols}x{rows}', '-frames:v', '1', str(out_path)], check=False)
    shutil.rmtree(tmp, ignore_errors=True)
    return str(out_path) if Path(out_path).exists() else None


def freezes(video, min_s=2.0):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(video), '-vf', f'freezedetect=n=-60dB:d={min_s}',
                        '-map', '0:v', '-f', 'null', '-'], capture_output=True, text=True)
    starts = [float(l.split('freeze_start: ')[1]) for l in r.stderr.splitlines() if 'freeze_start' in l]
    ends = [float(l.split('freeze_end: ')[1]) for l in r.stderr.splitlines() if 'freeze_end' in l]
    return [(s, e) for s, e in zip(starts, ends + [None] * (len(starts) - len(ends)))]


def mouth_check(video, audio, fps=5):
    """Stretches (>= 3 s) where the speech is loud but the lower face barely changes. None without OpenCV."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    try:   # a stub or partial cv2 (other packages sometimes bring one) means: not run
        det = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        cap = cv2.VideoCapture(str(video))
    except AttributeError:
        return None
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, int(round(src_fps / fps)))
    box, prev, motion, i = None, None, [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            g = cv2.cvtColor(cv2.resize(frame, None, fx=0.5, fy=0.5), cv2.COLOR_BGR2GRAY)
            if box is None or i % (step * 25) == 0:
                faces = det.detectMultiScale(g, 1.2, 5, minSize=(40, 40))
                if len(faces):
                    box = max(faces, key=lambda f: f[2] * f[3])
            if box is not None:
                x, y, w, h = box
                roi = cv2.resize(g[y + h * 2 // 3:y + h, x + w // 4:x + w * 3 // 4], (64, 32)).astype('float32')
                motion.append(float(np.abs(roi - prev).mean()) if prev is not None else 0.0)
                prev = roi
            else:
                motion.append(None)
        i += 1
    cap.release()
    samples = ac.load_samples(audio)
    hop = 16000 // fps
    n = min(len(motion), len(samples) // hop)
    if n < fps * 3:
        return []
    db = 20 * np.log10(np.sqrt((samples[:n * hop].reshape(n, hop) ** 2).mean(axis=1)) + 1e-9)
    speaking = db > db.max() - 30
    m = np.array([v if v is not None else np.nan for v in motion[:n]])
    talk = m[speaking & ~np.isnan(m)]
    if not len(talk):
        return []
    floor = np.median(talk) * 0.45
    out, start = [], None
    for k in range(n):
        bad = speaking[k] and not np.isnan(m[k]) and m[k] < floor
        if bad and start is None:
            start = k
        if not bad and start is not None:
            if (k - start) / fps >= 3:
                out.append((round(start / fps, 2), round(k / fps, 2)))
            start = None
    if start is not None and (n - start) / fps >= 3:
        out.append((round(start / fps, 2), round(n / fps, 2)))
    return out


def speech_end(wav, pad=0.35):
    """Where a take's speech stops (plus a short tail), from its own audio."""
    samples = ac.load_samples(wav)
    dur = len(samples) / 16000
    runs = ac.quiet_runs(samples, 16000)
    end = runs[-1][0] if runs and runs[-1][1] >= dur - 0.011 else dur
    return min(dur, end + pad)


def finish(edit, align=True, whisper_model=None, out=print):
    plan = load_plan(edit)
    d = adir(edit)
    segs = plan['segments']
    missing = [s['n'] for s in segs if not (d / f'seg_{s["n"]:02d}.mp4').exists()]
    if missing:
        raise ac.Refused('还有段没生成：' + '、'.join(map(str, missing)))
    first = probe(d / 'seg_01.mp4')
    w, h = first['width'], first['height']
    qc, fixed = [], d / 'fixed'
    fixed.mkdir(exist_ok=True)
    speak = plan['kind'] == 'speak'
    voice = d / 'voice'
    if speak:
        shutil.rmtree(voice, ignore_errors=True)
        voice.mkdir()
    sections, offset = [], 0.0
    for s in segs:
        src = d / f'seg_{s["n"]:02d}.mp4'
        got = probe(src)['duration']
        if speak:
            wav = voice / f'seg_{s["n"]:02d}_full.wav'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-vn', '-ac', '1', '-ar', str(ac.SR),
                            '-c:a', 'pcm_s16le', str(wav)], check=True)
            length = round(speech_end(wav), 3)
            # the model paces itself: compare its read with the narration's length for the same text
            ratio = round(length / s['seconds'], 2) if s['seconds'] else None
            qc.append({'segment': s['n'], 'requested_s': s['duration'], 'video_s': round(got, 3), 'speech_s': length,
                       'narration_s': s['seconds'], 'pace': ratio,
                       'status': 'passed' if length < got - 0.05 and ratio and 0.6 <= ratio <= 1.5 else 'needs_fix'})
            sid = f'A{s["n"]:02d}'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(wav), '-t', f'{length:.3f}', str(voice / f'{sid}.wav')],
                           check=True)
            wav.unlink()
            sections.append({'id': sid, 'file': f'{sid}.wav', 'text': s['text'], 'offset': round(offset, 3),
                             'seconds': length})
            offset += length
            vf = f'scale={w}:{h},fps=30'
        else:
            length = s['seconds']
            diff = round(got - length, 3)
            qc.append({'segment': s['n'], 'audio_s': length, 'video_s': round(got, 3), 'diff_s': diff,
                       'status': 'passed' if abs(diff) <= 0.15 else 'needs_fix'})
            # exact segment length: trim a longer take, hold the last frame of a shorter one
            vf = f'scale={w}:{h},fps=30,tpad=stop_mode=clone:stop_duration=2'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-an', '-vf', vf, '-t', f'{length:.3f}',
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16', '-pix_fmt', 'yuv420p',
                        str(fixed / src.name)], check=True)
    if speak:
        programme = voice / 'narration.wav'
        lst_a = voice / 'list.txt'
        lst_a.write_text(''.join(f"file '{(voice / x['file']).as_posix()}'\n" for x in sections), encoding='utf-8')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst_a), '-c:a', 'pcm_s16le',
                        str(programme)], check=True)
        lst_a.unlink()
        (voice / 'manifest.json').write_text(json.dumps({'lead': 0.0, 'gap': 0.0, 'sections': sections,
                                                         'total': round(offset, 3), 'source': plan['model']},
                                                        ensure_ascii=False, indent=1), encoding='utf-8')
    else:
        programme = Path(plan['audio'])
    lst = fixed / 'list.txt'
    lst.write_text(''.join(f"file '{(fixed / f'seg_{s['n']:02d}.mp4').as_posix()}'\n" for s in segs), encoding='utf-8')
    final = d / 'final_avatar.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-i', str(programme),
                    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', str(final)],
                   check=True)
    shutil.rmtree(fixed, ignore_errors=True)
    total = probe(final)['duration']
    bounds = [x['offset'] for x in sections[1:]] if speak else [s['end'] for s in segs[:-1]]
    seam_img = _frames(final, [t + o for t in bounds for o in (-0.2, 0.05)], d / 'seams.jpg') if bounds else None
    contact = _frames(final, [k * 2.0 + 1 for k in range(int(total // 2))][:60], d / 'contact.jpg', 240)
    anomalies = [{'start': round(s, 2), 'end': round(e if e is not None else total, 2), 'type': 'freeze',
                  'detail': '画面静止超过 2 秒'} for s, e in freezes(final)]
    mouth = mouth_check(final, programme)
    anomalies += [{'start': s, 'end': e, 'type': 'mouth_still', 'detail': '有声音但嘴几乎不动'} for s, e in (mouth or [])]
    aligned = 'n/a'
    if speak:
        if not align:
            aligned = 'not_run（--no-align）'
        else:
            try:
                _, _, report = ac.align(edit, whisper_model, out, tts='avatar/voice')
                aligned = f'run：疑点 {len(report)} 处（avatar/voice/align_report.md）'
            except ac.Refused as e:
                aligned = f'not_run（{e}）'
    report = {'video': str(final), 'model': plan['model'], 'duration': round(total, 3), 'size': f'{w}x{h}',
              'segments': qc, 'seam_sheet': seam_img, 'contact_sheet': contact, 'align': aligned,
              'mouth_check': 'not_run（OpenCV 不可用）' if mouth is None else 'run', 'anomalies': len(anomalies),
              'unverified': ['口型是否逐字对准', '手势自然不自然', '接缝处动作是否跳'] +
                            (['音色像不像本人的克隆声音', '每段之间音色是否一致'] if speak else [])}
    (d / 'qc.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    (d / 'anomalies.json').write_text(json.dumps({'duration': round(total, 3), 'anomalies': anomalies},
                                                 ensure_ascii=False, indent=1), encoding='utf-8')
    bad = [q for q in qc if q['status'] != 'passed']
    out(f'final_avatar.mp4：{total:.2f} 秒，{w}x{h}，{len(segs)} 段（{plan["model"]}）；' +
        ('人声是模型说的，逐字时间按它重新对齐' if speak else '原声已换回配音原文件'))
    out(f'长度核对：{len(qc) - len(bad)}/{len(qc)} 段通过' + (f'（要看的段：{", ".join(str(q["segment"]) for q in bad)}）' if bad else ''))
    if speak:
        out(f'逐字对齐：{aligned}')
    out(f'异常时间段 {len(anomalies)} 处 → avatar/anomalies.json；接缝图 {seam_img or "无"}，总览图 {contact or "无"}')
    out('需要用户播放确认：' + '、'.join(report['unverified']))
    return report


# ------------------------------------------------------------------ lipsync
def lipsync(cfg, edit, video, audio, name, confirmed=False, max_cost=None, http=None, sleep=time.sleep,
            poll_every=10.0, timeout=3600, out=print):
    a = settings(cfg)
    prov = provider(cfg, a, http)
    b = ac.budget(cfg)
    limit = b['confirm_over'] if max_cost is None else float(max_cost)
    vsec, asec = probe(video)['duration'], probe(audio)['duration']
    if vsec > 60 or asec > 60:
        raise ac.Refused('对口型每次最长 60 秒：先把视频和新音频在同一停顿处切成多段')
    model = a['lipsync_model']
    params = {'videos': ['https://example.com/clip.mp4'], 'audios': ['https://example.com/new.mp3'],
              'video_total_duration_sec': round(vsec, 2), 'duration': int(math.ceil(vsec))}
    key = ac.request_key(prov.name, model, ac.file_hash(video), {'name': name}, ac.file_hash(audio))
    d = adir(edit)
    dst = d / f'{name}.mp4'
    log = ac.read_log(edit, LOG)
    prev = next((e for e in reversed(log) if e.get('key') == key), None)
    if prev and prev.get('state') == 'success' and dst.exists():
        out(f'同样的对口型已经做过：{dst.name}（复用，不再付费）')
        return prev
    if not (prev and prev.get('state') == 'submitted'):
        q = prov.quote(model, params)
        best, ordered, notes = ac.choose_channel(q['channels'], b['min_success_rate'], b['avoid_vendors'])
        qq = {'provider': prov.name, 'note': q['note'], 'count': 1, 'channels': ordered or q['channels'], 'chosen': best,
              'total': None if best is None else best['price'], 'currency': prov.currency, 'notes': notes, 'limit': limit}
        out(ac.quote_text(qq))
        ac.gate(qq, limit, confirmed)
        mp3 = d / f'{name}_audio.mp3'
        to_mp3(audio, mp3)
        params.update(videos=[prov.upload_file(video)], audios=[prov.upload_file(mp3)])
        try:
            task = prov.submit_video(model, params, best.get('lane'), request_id=f'xumu-ls-{key}-{len(log)}')
        except RuntimeError as e:
            raise ac.Refused(f'没有提交成功（未扣费）：{e}')
        prev = {'key': key, 'kind': 'lipsync', 'name': name, 'provider': prov.name, 'model': model, 'lane': best.get('lane'),
                'task_id': task, 'state': 'submitted', 'at': time.strftime('%Y-%m-%d %H:%M:%S')}
        log.append(prev)
        ac.write_log(edit, log, LOG)
        out(f'已提交 {task}')
    waited = 0.0
    while True:
        st = prov.poll(prev['task_id'])
        if st.get('final'):
            break
        if waited >= timeout:
            raise RuntimeError('超时：稍后重跑同一命令会继续查询，不重复付费')
        sleep(poll_every)
        waited += poll_every
    prev['cost'] = st.get('cost')
    if not st.get('ok'):
        prev['state'], prev['error'] = 'failed', st.get('error')
        ac.write_log(edit, log, LOG)
        raise ac.Refused(f'对口型失败：{st.get("error")}（不扣费，没有自动换渠道）')
    dst.write_bytes(ac.fetch(prov.http, (st.get('urls') or [st['url']])[0], sleep))
    prev.update(state='success', file=dst.name)
    ac.write_log(edit, log, LOG)
    out(f'完成：{dst.name}，花费 {st.get("cost")}')
    return prev


# ------------------------------------------------------------------ cli
def main(argv=None, cfg=None, http=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('check'); p.add_argument('--image', required=True); p.add_argument('--out')
    p = sub.add_parser('plan'); p.add_argument('--edit', required=True); p.add_argument('--audio')
    p.add_argument('--model', choices=list(MODELS)); p.add_argument('--max-seg', type=float); p.add_argument('--min-seg', type=float)
    p = sub.add_parser('estimate'); p.add_argument('--edit', required=True); p.add_argument('--quality')
    p.add_argument('--resolution'); p.add_argument('--motion', default='中'); p.add_argument('--extra', default='')
    p.add_argument('--only'); p.add_argument('--aspect', default='9:16')
    p = sub.add_parser('generate'); p.add_argument('--edit', required=True); p.add_argument('--image', required=True)
    p.add_argument('--quality'); p.add_argument('--resolution'); p.add_argument('--motion', default='中')
    p.add_argument('--extra', default=''); p.add_argument('--only'); p.add_argument('--voice-ok')
    p.add_argument('--user-asked'); p.add_argument('--skip-sample', action='store_true')
    p.add_argument('--confirmed', action='store_true'); p.add_argument('--max-cost', type=float)
    p = sub.add_parser('finish'); p.add_argument('--edit', required=True); p.add_argument('--no-align', action='store_true')
    p = sub.add_parser('lipsync'); p.add_argument('--edit', required=True); p.add_argument('--video', required=True)
    p.add_argument('--audio', required=True); p.add_argument('--name', required=True)
    p.add_argument('--confirmed', action='store_true'); p.add_argument('--max-cost', type=float)
    a = ap.parse_args(argv)
    cfg = ac.load_config() if cfg is None else cfg
    try:
        if a.cmd == 'check':
            print(json.dumps(check_image(a.image, a.out), ensure_ascii=False, indent=1))
        elif a.cmd == 'plan':
            plan = make_plan(a.edit, a.audio, a.max_seg, a.min_seg, cfg, a.model)
            print(f'{plan["model"]}：{len(plan["segments"])} 段，配音共 {plan["duration"]:.1f} 秒：' +
                  '，'.join(f'{s["n"]}）{s["seconds"]:.1f}s→请求 {s["duration"]}s' for s in plan['segments']))
            if plan['hard_cuts']:
                print(f'注意：第 {"、".join(map(str, plan["hard_cuts"]))} 段的结尾不在停顿上（找不到停顿，硬切），接缝要重点看')
        elif a.cmd == 'estimate':
            plan = load_plan(a.edit)
            s = settings(cfg, plan['model'])
            prov = provider(cfg, s, http)
            b = ac.budget(cfg)
            segs = pick(plan['segments'], a.only)
            print(ac.quote_text(quote(prov, s, plan, segs, a.motion, a.extra, b, b['confirm_over'], a.quality,
                                      a.resolution, a.aspect)), end='')
        elif a.cmd == 'generate':
            generate(cfg, a.edit, a.image, a.quality, a.motion, a.extra, a.only, a.voice_ok, a.skip_sample,
                     a.confirmed, a.max_cost, http, resolution=a.resolution, user_asked=a.user_asked)
        elif a.cmd == 'finish':
            finish(a.edit, align=not a.no_align)
        else:
            lipsync(cfg, a.edit, a.video, a.audio, a.name, a.confirmed, a.max_cost, http)
    except ac.Refused as e:
        print(str(e))
        return 3
    return 0


if __name__ == '__main__':
    import key_setup
    key_setup.load_user_env()   # a key saved after this terminal or agent host started
    sys.exit(main())
