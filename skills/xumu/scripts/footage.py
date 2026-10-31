#!/usr/bin/env python3
"""剪素材链：扫描素材切镜头并打可用度分，估音乐节拍，按故事线选段，拼粗剪预览。

  scan    每条素材：ffprobe 基本信息 → ffmpeg 场景切分 → 低分辨率抽帧算亮度 / 清晰 / 运动 / 抖动 → 静音检测算有声比例
          → （可选）人脸 → 每个镜头一个可用度分和原因 → 缩略图 + scan.json + scan.html
  beats   音乐节拍：能量包络 + 自相关估 BPM，再对齐相位，写 beats.json
  select  按 director.json 第 4 格的故事线（或总时长）从高分镜头里选段，可按节拍取整，写 picks.json
  render  按 picks 拼粗剪预览（文件名带"预览"），可垫音乐；同时写 edl_footage.json 给 cue.py 做 clip 锚点

只做粗判：分数是排除明显不能用的镜头、把好镜头排前面；最终取舍由总控看缩略图和试看决定。
"""
import argparse
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

SCAN_FPS = 2            # 抽帧率：每秒两帧，够看亮度与运动趋势
SCAN_W, SCAN_H = 160, 90
DEFAULT_SCENE = 0.30    # ffmpeg scene 阈值；越低切得越碎
DEFAULT_MIN_SHOT = 1.0  # 短于这个秒数的碎镜头并入前一个


def run(cmd, timeout=600):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)


def need(tool):
    if not shutil.which(tool):
        raise SystemExit(f'需要 {tool}，先运行 setup_env.py')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def probe(path):
    out = run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)])
    if out.returncode != 0:
        return None
    info = json.loads(out.stdout or '{}')
    streams = info.get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), None)
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    try:
        duration = float(info.get('format', {}).get('duration'))
    except (TypeError, ValueError):
        duration = None
    return {'duration': duration, 'has_video': video is not None, 'has_audio': audio is not None,
            'width': video.get('width') if video else None, 'height': video.get('height') if video else None}


# ---------------------------------------------------------------- 扫描

def scene_cuts(path, threshold):
    out = run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-an',
               '-vf', f"select='gt(scene,{threshold})',showinfo", '-f', 'null', '-'])
    return [float(t) for t in re.findall(r'pts_time:\s*([0-9.]+)', out.stderr)]


def gray_frames(path):
    import numpy as np
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-an',
                          '-vf', f'fps={SCAN_FPS},scale={SCAN_W}:{SCAN_H},format=gray', '-f', 'rawvideo', '-'],
                         capture_output=True, timeout=900)
    raw = np.frombuffer(out.stdout, dtype=np.uint8)
    n = len(raw) // (SCAN_W * SCAN_H)
    return raw[:n * SCAN_W * SCAN_H].reshape(n, SCAN_H, SCAN_W).astype(np.float32)


def frame_metrics(frames):
    """每帧：平均亮度、过暗比例、过亮比例、清晰度（梯度均值）、与上一帧的运动量。"""
    import numpy as np
    if len(frames) == 0:
        return {'luma': [], 'dark': [], 'bright': [], 'sharp': [], 'motion': []}
    luma = frames.mean(axis=(1, 2))
    dark = (frames < 16).mean(axis=(1, 2))
    bright = (frames > 240).mean(axis=(1, 2))
    gx = np.abs(np.diff(frames, axis=2)).mean(axis=(1, 2))
    gy = np.abs(np.diff(frames, axis=1)).mean(axis=(1, 2))
    sharp = (gx + gy) / 2
    motion = np.concatenate([[0.0], np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))])
    return {k: [round(float(v), 3) for v in arr] for k, arr in
            (('luma', luma), ('dark', dark), ('bright', bright), ('sharp', sharp), ('motion', motion))}


def silence_spans(path):
    out = run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-vn',
               '-af', 'silencedetect=n=-35dB:d=0.4', '-f', 'null', '-'])
    starts = [float(t) for t in re.findall(r'silence_start: ([0-9.]+)', out.stderr)]
    ends = [float(t) for t in re.findall(r'silence_end: ([0-9.]+)', out.stderr)]
    spans = list(zip(starts, ends))
    if len(starts) > len(ends):
        spans.append((starts[-1], float('inf')))
    return spans


def voiced_ratio(spans, start, end):
    if end <= start:
        return 0.0
    silent = 0.0
    for s, e in spans:
        silent += max(0.0, min(e, end) - max(s, start))
    return round(max(0.0, 1 - silent / (end - start)), 2)


def face_ratio(path, start, end, samples=4):
    """可选：有 OpenCV 时在几帧上找正脸，返回有脸的帧比例；没有返回 None。"""
    try:
        import cv2
    except ImportError:
        return None
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    hits = 0
    for k in range(samples):
        t = start + (end - start) * (k + 0.5) / samples
        out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-ss', f'{t:.3f}', '-i', str(path), '-frames:v', '1',
                              '-vf', 'scale=320:-2,format=gray', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                             capture_output=True, timeout=60)
        import numpy as np
        raw = np.frombuffer(out.stdout, dtype=np.uint8)
        if raw.size == 0:
            continue
        h = raw.size // 320
        img = raw[:h * 320].reshape(h, 320)
        if len(cascade.detectMultiScale(img, 1.2, 4)) > 0:
            hits += 1
    return round(hits / samples, 2)


def split_shots(duration, cuts, min_shot):
    """切点之间短于 min_shot 的碎片并入后一个镜头（双重切点里第一个才是真切点）；最后一段太短并入前一个。"""
    bounds = [0.0] + [t for t in sorted(cuts) if 0 < t < duration] + [duration]
    shots, a = [], 0.0
    for b in bounds[1:]:
        if b - a < min_shot and b < duration:
            continue               # 跳过这个切点，碎片并入下一段
        shots.append([a, b])
        a = b
    if len(shots) > 1 and shots[-1][1] - shots[-1][0] < min_shot:
        shots[-2][1] = shots[-1][1]
        shots.pop()
    return [(a, b) for a, b in shots if b - a > 0]


def summarize(values, lo, hi, skip_first=False):
    """帧级指标在 [lo, hi) 秒内的均值和方差；运动量跳过镜头第一帧（那是切点本身的跳变）。"""
    import numpy as np
    i0, i1 = int(lo * SCAN_FPS), max(int(lo * SCAN_FPS) + 1, int(hi * SCAN_FPS))
    if skip_first and i1 - i0 > 1:
        i0 += 1
    seg = np.array(values[i0:i1], dtype=np.float32)
    if seg.size == 0:
        return 0.0, 0.0
    return round(float(seg.mean()), 3), round(float(seg.var()), 3)


def score_shot(m, file_median_sharp):
    """可用度 0～100 和原因。阈值是经验值，只为排除明显不能用的镜头。"""
    score, flags = 100, []
    if m['luma'] < 40:
        score -= 30; flags.append('过暗')
    elif m['luma'] > 215:
        score -= 20; flags.append('过亮')
    if m['bright'] > 0.3:
        score -= 15; flags.append('大面积过曝')
    if file_median_sharp > 0 and m['sharp'] < 0.5 * file_median_sharp:
        score -= 20; flags.append('偏糊')
    if m['motion_var'] > 60:
        score -= 15; flags.append('抖/乱')
    if m['motion'] < 0.3:
        score -= 5; flags.append('几乎静止')
    if m['duration'] < 1.5:
        score -= 10; flags.append('太短')
    if m.get('voiced') is not None and m['voiced'] >= 0.5:
        flags.append('有声')
    if m.get('faces'):
        flags.append('有人脸')
    return max(0, score), flags


def scan_file(path, index, scene, min_shot, faces, thumbs_dir):
    import numpy as np
    info = probe(path)
    if not info or not info['has_video'] or not info['duration']:
        return {'file': str(path), 'error': '不是可读的视频', 'shots': []}
    cuts = scene_cuts(path, scene)
    frames = gray_frames(path)
    metrics = frame_metrics(frames)
    spans = silence_spans(path) if info['has_audio'] else None
    median_sharp = float(np.median(metrics['sharp'])) if metrics['sharp'] else 0.0
    shots = []
    for n, (a, b) in enumerate(split_shots(info['duration'], cuts, min_shot), 1):
        sid = f'c{index:02d}{n:02d}'
        luma, _ = summarize(metrics['luma'], a, b)
        bright, _ = summarize(metrics['bright'], a, b)
        sharp, _ = summarize(metrics['sharp'], a, b)
        motion, motion_var = summarize(metrics['motion'], a, b, skip_first=True)
        m = {'id': sid, 'file': str(path), 'start': round(a, 3), 'end': round(b, 3), 'duration': round(b - a, 3),
             'luma': luma, 'bright': bright, 'sharp': sharp, 'motion': motion, 'motion_var': motion_var,
             'voiced': voiced_ratio(spans, a, b) if spans is not None else None,
             'faces': face_ratio(path, a, b) if faces else None}
        m['score'], m['flags'] = score_shot(m, median_sharp)
        thumb = thumbs_dir / f'{sid}.jpg'
        if not thumb.exists():
            run(['ffmpeg', '-hide_banner', '-nostats', '-y', '-ss', f'{(a + b) / 2:.3f}', '-i', str(path),
                 '-frames:v', '1', '-vf', 'scale=320:-2', str(thumb)], timeout=120)
        m['thumb'] = str(thumb.relative_to(thumbs_dir.parent)) if thumb.exists() else ''
        m['summary'] = ''   # 总控看过缩略图后填一句
        shots.append(m)
    return {'file': str(path), **info, 'cuts': [round(t, 3) for t in cuts], 'shots': shots}


def write_sheet(scan, out):
    rows = []
    for f in scan['files']:
        rows.append(f'<h2>{html.escape(Path(f["file"]).name)}</h2>')
        if f.get('error'):
            rows.append(f'<p class="err">{html.escape(f["error"])}</p>')
            continue
        rows.append('<div class="grid">')
        for s in f['shots']:
            rows.append(
                f'<figure><img src="{html.escape(s["thumb"])}" alt="{s["id"]}">'
                f'<figcaption><b>{s["id"]}</b> {s["start"]:.1f}–{s["end"]:.1f}s · <b>{s["score"]}</b> 分'
                f'<br>{html.escape("、".join(s["flags"]) or "无标记")}'
                f'<br><small>亮 {s["luma"]:.0f} 清 {s["sharp"]:.1f} 动 {s["motion"]:.1f} 声 {s["voiced"] if s["voiced"] is not None else "–"}</small>'
                f'</figcaption></figure>')
        rows.append('</div>')
    page = ('<!doctype html><meta charset="utf-8"><title>素材扫描</title><style>'
            'body{font-family:system-ui,sans-serif;margin:16px;background:#111;color:#eee}'
            '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}'
            'figure{margin:0;background:#1c1c1c;padding:8px;border-radius:6px}img{width:100%;display:block;border-radius:4px}'
            'figcaption{font-size:13px;line-height:1.5;margin-top:6px}.err{color:#f66}</style>'
            f'<h1>素材扫描 · {scan["files_count"]} 个文件 · {scan["shots_count"]} 个镜头</h1>'
            '<p>分数只排除明显不能用的镜头，最终取舍看图和试看。</p>' + '\n'.join(rows))
    Path(out).write_text(page, encoding='utf-8')


def cmd_scan(args):
    need('ffmpeg'); need('ffprobe')
    edit = Path(args.edit)
    out_dir = edit / 'footage'
    scan_file_path = out_dir / 'scan.json'
    if scan_file_path.exists() and not args.force:
        raise SystemExit(f'已有扫描结果：{scan_file_path}（重扫加 --force）')
    thumbs = out_dir / 'thumbs'
    thumbs.mkdir(parents=True, exist_ok=True)
    files = []
    for raw in args.inputs:
        p = Path(raw)
        files += sorted(x for x in p.rglob('*') if x.is_file() and x.suffix.lower() in {'.mp4', '.mov', '.mkv', '.webm', '.m4v'}) if p.is_dir() else [p]
    scan = {'schema_version': 1, 'scene_threshold': args.scene, 'min_shot_s': args.min_shot, 'files': []}
    for i, f in enumerate(files, 1):
        print(f'扫描 {f.name} …', flush=True)
        scan['files'].append(scan_file(f, i, args.scene, args.min_shot, args.faces, thumbs))
    scan['files_count'] = len(scan['files'])
    scan['shots_count'] = sum(len(f['shots']) for f in scan['files'])
    dump(scan_file_path, scan)
    write_sheet(scan, out_dir / 'scan.html')
    shots = [s for f in scan['files'] for s in f['shots']]
    good = sum(1 for s in shots if s['score'] >= 70)
    print(f'{scan["files_count"]} 个文件，{scan["shots_count"]} 个镜头，{good} 个 ≥70 分；看 {out_dir / "scan.html"}')


# ---------------------------------------------------------------- 节拍

def mono_pcm(path, rate=22050):
    import numpy as np
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-vn', '-ac', '1', '-ar', str(rate),
                          '-f', 's16le', '-'], capture_output=True, timeout=600)
    return np.frombuffer(out.stdout, dtype=np.int16).astype(np.float32) / 32768.0, rate


def estimate_beats(samples, rate, bpm_min=60, bpm_max=180, hop=512):
    """能量包络的正变化做起音强度，自相关选周期，再选相位；返回 bpm 与节拍时刻。"""
    import numpy as np
    n = len(samples) // hop
    if n < 8:
        return None, []
    frames = samples[:n * hop].reshape(n, hop)
    energy = np.log1p((frames ** 2).sum(axis=1) * 1000)
    onset = np.maximum(0, np.diff(energy, prepend=energy[0]))
    onset -= onset.mean()
    fps = rate / hop
    lag_min, lag_max = int(fps * 60 / bpm_max), int(fps * 60 / bpm_min)
    ac = np.correlate(onset, onset, mode='full')[len(onset) - 1:]
    if lag_max >= len(ac):
        lag_max = len(ac) - 1
    if lag_max <= lag_min:
        return None, []
    lag = lag_min + int(np.argmax(ac[lag_min:lag_max + 1]))

    def peak_near(center):
        lo, hi = max(lag_min, center - 1), min(len(ac) - 1, center + 1)
        return lo + int(np.argmax(ac[lo:hi + 1]))

    # 自相关常把一拍认成两拍（60 当 120 的一半）；半周期附近也够强时取快的那个
    while lag // 2 >= lag_min:
        half = peak_near(lag // 2)
        if ac[half] < 0.6 * ac[lag]:
            break
        lag = half
    # 真实周期不一定是整数帧：用峰两侧做抛物线插值
    if 1 <= lag < len(ac) - 1:
        y0, y1, y2 = float(ac[lag - 1]), float(ac[lag]), float(ac[lag + 1])
        denom = y0 - 2 * y1 + y2
        lag_f = lag + (0.5 * (y0 - y2) / denom if denom else 0.0)
    else:
        lag_f = float(lag)
    period = lag_f / fps
    best_phase, best_sum = 0, -1e9
    for ph in range(lag):
        idx = np.arange(ph, len(onset), lag)
        s = float(onset[idx].sum())
        if s > best_sum:
            best_sum, best_phase = s, ph
    times = [round(float(t), 3) for t in np.arange(best_phase / fps, len(samples) / rate, period)]
    return round(60 / period, 1), times


def cmd_beats(args):
    need('ffmpeg')
    samples, rate = mono_pcm(args.music)
    bpm, times = estimate_beats(samples, rate, args.bpm_min, args.bpm_max)
    if not times:
        raise SystemExit('音乐太短或没读到音频')
    dump(Path(args.edit) / 'beats.json', {'music': str(args.music), 'bpm': bpm, 'period': round(60 / bpm, 4), 'times': times})
    print(f'{bpm} BPM，{len(times)} 拍，写入 beats.json（{Path(args.edit) / "beats.json"}）')


# ---------------------------------------------------------------- 选段

def all_shots(scan):
    return [s for f in scan['files'] for s in f.get('shots', [])]


def segments_from_director(edit):
    path = Path(edit) / 'director.json'
    if not path.exists():
        return []
    doc = load(path)
    story = (doc.get('grids', {}).get('4') or {}).get('storyline') or []
    return [{'id': s.get('id', f'S{i}'), 'goal': s.get('goal', ''), 'refs': s.get('source_refs') or [],
             'seconds': float(s.get('est_duration') or 0)} for i, s in enumerate(story, 1)]


def candidates_for(segment, shots):
    """source_refs 点名了镜头 id 就用那些；点名了文件就限定到那些文件；都没有就全部。"""
    refs = [str(r) for r in segment.get('refs') or []]
    by_id = [s for s in shots if s['id'] in refs]
    if by_id:
        return by_id
    by_file = [s for s in shots if any(r and r in s['file'] for r in refs)]
    return by_file or shots


def pick(shots, segments, max_shot, min_score, period=None, lead=0.2, order='time'):
    used, result = set(), []
    for seg in segments:
        pool = [s for s in candidates_for(seg, shots) if s['id'] not in used and s['score'] >= min_score]
        pool.sort(key=lambda s: -s['score'])
        need_s, clips = seg['seconds'] or 0, []
        for s in pool:
            if need_s and sum(c['dur'] for c in clips) >= need_s:
                break
            avail = s['duration'] - 2 * lead
            if avail < 0.6:
                continue
            dur = min(avail, max_shot)
            if period:
                dur = max(period, round(dur / period) * period)
                if dur > avail:
                    dur = max(period, (avail // period) * period)
                    if dur > avail:
                        continue
            clips.append({'id': s['id'], 'file': s['file'], 'in': round(s['start'] + lead, 3),
                          'out': round(s['start'] + lead + dur, 3), 'dur': round(dur, 3), 'score': s['score']})
            used.add(s['id'])
        if order == 'time':
            clips.sort(key=lambda c: (c['file'], c['in']))
        total = round(sum(c['dur'] for c in clips), 3)
        result.append({'segment': seg['id'], 'goal': seg.get('goal', ''), 'target_s': seg['seconds'], 'total_s': total,
                       'short_by_s': round(max(0.0, (seg['seconds'] or 0) - total), 3), 'clips': clips})
    return result


def cmd_select(args):
    edit = Path(args.edit)
    scan = load(edit / 'footage' / 'scan.json')
    shots = all_shots(scan)
    if args.from_json:
        picks = load(args.from_json)
        by_id = {s['id']: s for s in shots}
        for seg in picks:
            for c in seg['clips']:
                s = by_id.get(c['id'])
                if s is None:
                    raise SystemExit(f'镜头不存在：{c["id"]}')
                c.setdefault('file', s['file'])
                c.setdefault('in', s['start']); c.setdefault('out', s['end'])
                c['dur'] = round(c['out'] - c['in'], 3)
            seg['total_s'] = round(sum(c['dur'] for c in seg['clips']), 3)
    else:
        segments = segments_from_director(edit)
        if not segments:
            segments = [{'id': 'ALL', 'goal': '', 'refs': [], 'seconds': args.total or 60}]
        period = None
        if args.music:
            beats = edit / 'beats.json'
            if not beats.exists():
                raise SystemExit('先 footage.py beats 生成 beats.json')
            period = load(beats)['period']
        picks = pick(shots, segments, args.max_shot, args.min_score, period, order=args.order)
    dump(edit / 'footage' / 'picks.json', picks)
    for seg in picks:
        line = f'{seg["segment"]:<6} {len(seg["clips"])} 段 {seg["total_s"]}s'
        if seg.get('target_s'):
            line += f' / 目标 {seg["target_s"]}s' + (f'（缺 {seg["short_by_s"]}s）' if seg.get('short_by_s') else '')
        print(line + '：' + ' '.join(c['id'] for c in seg['clips']))
    print(f'写入 {edit / "footage" / "picks.json"}；改选段直接改这个文件再 render')


# ---------------------------------------------------------------- 粗剪

def cmd_render(args):
    need('ffmpeg')
    edit = Path(args.edit)
    picks = load(edit / 'footage' / 'picks.json')
    scan = load(edit / 'footage' / 'scan.json')
    has_audio = {f['file']: f.get('has_audio', False) for f in scan['files']}
    w, h = (int(x) for x in args.size.lower().split('x'))
    out = Path(args.out) if args.out else edit / 'build' / '粗剪_预览.mp4'
    if out.exists() and not args.force:
        raise SystemExit(f'已有 {out}（覆盖加 --force）')
    out.parent.mkdir(parents=True, exist_ok=True)
    clips = [dict(c, segment=seg['segment']) for seg in picks for c in seg['clips']]
    if not clips:
        raise SystemExit('picks.json 里没有镜头')
    cmd, filters, t = ['ffmpeg', '-hide_banner', '-nostats', '-y'], [], 0.0
    edl = []
    for i, c in enumerate(clips):
        cmd += ['-ss', f'{c["in"]:.3f}', '-to', f'{c["out"]:.3f}', '-i', c['file']]
        filters.append(f'[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={args.fps},format=yuv420p[v{i}]')
        if args.keep_audio and has_audio.get(c['file']):
            filters.append(f'[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]')
        else:
            filters.append(f'anullsrc=r=48000:cl=stereo,atrim=0:{c["dur"]:.3f}[a{i}]')
        edl.append({'id': c['id'], 'segment': c['segment'], 'file': c['file'], 'in': c['in'], 'out': c['out'],
                    'start': round(t, 3), 'end': round(t + c['dur'], 3)})
        t += c['dur']
    n = len(clips)
    filters.append(''.join(f'[v{i}][a{i}]' for i in range(n)) + f'concat=n={n}:v=1:a=1[vc][ac]')
    maps = ['-map', '[vc]']
    if args.music:
        cmd += ['-i', str(args.music)]
        filters.append(f'[{n}:a]atrim=0:{t:.3f},afade=t=out:st={max(0, t - 1):.3f}:d=1,volume={args.music_db}dB[m]')
        filters.append('[ac][m]amix=inputs=2:duration=first:normalize=0[mix]')
        maps += ['-map', '[mix]']
    else:
        maps += ['-map', '[ac]']
    cmd += ['-filter_complex', ';'.join(filters)] + maps + ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
                                                            '-c:a', 'aac', '-shortest', str(out)]
    res = run(cmd, timeout=3600)
    if res.returncode != 0:
        raise SystemExit('ffmpeg 失败：\n' + res.stderr[-2000:])
    dump(edit / 'edl_footage.json', {'fps': args.fps, 'size': args.size, 'total_seconds': round(t, 3),
                                     'music': str(args.music) if args.music else None, 'clips': edl})
    print(f'粗剪预览：{out}（{t:.1f}s，{n} 段）；edl_footage.json 已写，cue.py 可用 {{"clip": "<id>"}} 锚点')


# ---------------------------------------------------------------- CLI

def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('scan', help='切镜头、打分、缩略图')
    p.add_argument('--edit', required=True)
    p.add_argument('--inputs', nargs='+', required=True, help='视频文件或目录')
    p.add_argument('--scene', type=float, default=DEFAULT_SCENE)
    p.add_argument('--min-shot', type=float, default=DEFAULT_MIN_SHOT)
    p.add_argument('--faces', action='store_true', help='有 OpenCV 时找人脸')
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser('beats', help='音乐节拍 → beats.json')
    p.add_argument('--edit', required=True)
    p.add_argument('--music', required=True)
    p.add_argument('--bpm-min', type=int, default=60)
    p.add_argument('--bpm-max', type=int, default=180)
    p.set_defaults(func=cmd_beats)

    p = sub.add_parser('select', help='按故事线选段 → picks.json')
    p.add_argument('--edit', required=True)
    p.add_argument('--from', dest='from_json', help='总控或用户手选的 picks（只需 segment + clips[].id，可带 in/out）')
    p.add_argument('--max-shot', type=float, default=6.0, help='单段最长秒数')
    p.add_argument('--min-score', type=int, default=50)
    p.add_argument('--total', type=float, help='没有故事线时的总时长')
    p.add_argument('--music', action='store_true', help='段长按 beats.json 的节拍取整')
    p.add_argument('--order', choices=('time', 'score'), default='time', help='段内按素材时间顺序（默认）还是分数')
    p.set_defaults(func=cmd_select)

    p = sub.add_parser('render', help='拼粗剪预览 → build/粗剪_预览.mp4 + edl_footage.json')
    p.add_argument('--edit', required=True)
    p.add_argument('--size', default='1080x1920')
    p.add_argument('--fps', type=int, default=30)
    p.add_argument('--keep-audio', action='store_true', help='保留素材现场声')
    p.add_argument('--music', help='垫一首音乐')
    p.add_argument('--music-db', type=float, default=-14.0)
    p.add_argument('--out')
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_render)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
