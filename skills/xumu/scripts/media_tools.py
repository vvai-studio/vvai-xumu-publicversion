#!/usr/bin/env python3
"""Media helpers for B-roll and delivery. Every command writes new files only (pass --force to replace).

  clips      cut named clips from long recordings: crop, speed, fixed size/fps, short GOP,
             plus first/last-frame stills and a contact sheet per clip
  cutpoint   quietest 10 ms valley near a time, for trimming web clips between words
  level      bring a clip to a target mean volume with a peak limiter (unify clips from mixed sources)
  measure    integrated loudness / true peak of a file, optionally per time range
  normalize  two-pass loudnorm of the final mix (video stream copied)
  fontcheck  characters used by the page/text files that the font cannot draw; optional woff2 subset
  deliver-check  probe the deliverable against the source footage or a delivery spec before handing it over:
             fails on a smaller frame, a changed orientation, a draft/preview file name or a missing audio track;
             warns on HDR left without tone mapping, a lower frame rate, fewer audio channels or a starved bitrate

clips spec (JSON):
  {"defaults": {"size": "1920x1080", "fps": 30, "gop": 15, "crop": null},
   "clips": {"rec_B02": {"source": "rec/01.mp4", "segments": [[236.0, 17.4, 1]], "crop": "2144:1206:328:62"}}}
  segments: [source_start_s, output_seconds, speed]; speed > 1 plays faster, < 1 slower.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr):   # Windows pipes default to the ANSI code page; the agent reads UTF-8
    if hasattr(_stream, 'reconfigure'):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            pass

FFMPEG = 'ffmpeg'


def run(cmd, capture=False):
    return subprocess.run(cmd, check=True, capture_output=capture, text=capture, encoding='utf-8' if capture else None,
                          errors='replace' if capture else None)


def guard(path, force):
    if Path(path).exists() and not force:
        raise FileExistsError(f'{path} exists; pass --force or choose a new name')


def probe_duration(path):
    out = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)], capture=True)
    return float(out.stdout.strip())


def has_video(path):
    out = run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=index', '-of', 'csv=p=0',
               str(path)], capture=True)
    return bool(out.stdout.strip())


# ------------------------------------------------------------------------------------------------ clips
def cut_clip(name, clip, defaults, out_dir, sheet_dir, force):
    size = clip.get('size', defaults.get('size', '1920x1080'))
    fps = clip.get('fps', defaults.get('fps', 30))
    gop = clip.get('gop', defaults.get('gop', 15))
    crop = clip.get('crop', defaults.get('crop'))
    target = out_dir / f'{name}.mp4'
    guard(target, force)
    chain = (f'crop={crop},' if crop else '') + f'scale={size.replace("x", ":")}:flags=lanczos,fps={fps},format=yuv420p'
    cmd, graph = [FFMPEG, '-y', '-loglevel', 'error'], []
    for k, (start, seconds, speed) in enumerate(clip['segments']):
        cmd += ['-ss', f'{start}', '-t', f'{seconds * speed}', '-i', clip['source']]
        graph.append(f'[{k}:v]setpts=(PTS-STARTPTS)/{speed},{chain}[s{k}]')
    n = len(clip['segments'])
    graph.append(''.join(f'[s{k}]' for k in range(n)) + f'concat=n={n}:v=1:a=0[v]')
    run(cmd + ['-filter_complex', ';'.join(graph), '-map', '[v]', '-c:v', 'libx264', '-crf', '18',
               '-preset', 'medium', '-g', str(gop), '-movflags', '+faststart', str(target)])
    return stills(target, sheet_dir, force)


def stills(clip_path, sheet_dir, force):
    """First and last frame (for hand-offs such as a drawn monitor) and a contact sheet of at most 30 frames."""
    first = clip_path.with_name(f'{clip_path.stem}_first.png')
    last = clip_path.with_name(f'{clip_path.stem}_last.png')
    sheet = sheet_dir / f'{clip_path.stem}_sheet.jpg'
    for path in (first, last, sheet):
        guard(path, force)
    run([FFMPEG, '-y', '-loglevel', 'error', '-i', str(clip_path), '-frames:v', '1', str(first)])
    run([FFMPEG, '-y', '-loglevel', 'error', '-sseof', '-0.1', '-i', str(clip_path), '-update', '1', '-q:v', '2',
         str(last)])
    duration = probe_duration(clip_path)
    rate = min(1.0, 30.0 / max(duration, 0.1))
    run([FFMPEG, '-y', '-loglevel', 'error', '-i', str(clip_path), '-vf', f'fps={rate:.4f},scale=384:-1,tile=6x5',
         '-frames:v', '1', str(sheet)])
    return {'clip': str(clip_path), 'seconds': round(duration, 3), 'first': str(first), 'last': str(last),
            'sheet': str(sheet), 'sheet_interval_s': round(1 / rate, 2)}


# ------------------------------------------------------------------------------------------------ audio
def mono_samples(path, rate=16000, start=None, seconds=None):
    import numpy as np
    cmd = [FFMPEG, '-loglevel', 'error']
    if start is not None:
        cmd += ['-ss', f'{max(0.0, start)}']
    if seconds is not None:
        cmd += ['-t', f'{seconds}']
    cmd += ['-i', str(path), '-vn', '-ac', '1', '-ar', str(rate), '-f', 's16le', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32)


def cutpoint(path, near, window):
    """Quietest 10 ms frames within near ± window; returns the best few, quietest first."""
    import numpy as np
    start = max(0.0, near - window)
    a = mono_samples(path, start=start, seconds=2 * window)
    hop = 160
    n = len(a) // hop
    if n == 0:
        raise ValueError('no audio in the requested window')
    rms = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1))
    db = 20 * np.log10(np.maximum(rms, 1.0) / 32768)
    order = np.argsort(db)
    picks = []
    for k in order:
        t = start + (k + 0.5) * 0.01
        if all(abs(t - p['time']) > 0.05 for p in picks):
            picks.append({'time': round(t, 3), 'db': round(float(db[k]), 1), 'distance': round(abs(t - near), 3)})
        if len(picks) == 3:
            break
    return picks


def volume_stats(path):
    out = run([FFMPEG, '-hide_banner', '-nostats', '-i', str(path), '-vn', '-af', 'volumedetect', '-f', 'null', '-'],
              capture=True)
    mean = re.search(r'mean_volume:\s*(-?[\d.]+) dB', out.stderr)
    peak = re.search(r'max_volume:\s*(-?[\d.]+) dB', out.stderr)
    if not mean or not peak:
        raise ValueError(f'no audio stats for {path}')
    return float(mean.group(1)), float(peak.group(1))


def level(src, dst, mean_target, peak_db, force):
    guard(dst, force)
    mean, peak = volume_stats(src)
    gain = mean_target - mean
    limit = 10 ** (peak_db / 20)
    cmd = [FFMPEG, '-y', '-loglevel', 'error', '-i', str(src)]
    if has_video(src):
        cmd += ['-c:v', 'copy']
    cmd += ['-af', f'volume={gain:.2f}dB,alimiter=limit={limit:.4f}:level=disabled', '-c:a', 'aac', '-b:a', '192k',
            str(dst)]
    run(cmd)
    after = volume_stats(dst)
    return {'gain_db': round(gain, 2), 'before': {'mean': mean, 'max': peak},
            'after': {'mean': after[0], 'max': after[1]}}


def ebur128(path, start=None, seconds=None):
    cmd = [FFMPEG, '-hide_banner', '-nostats']
    if start is not None:
        cmd += ['-ss', f'{start}']
    if seconds is not None:
        cmd += ['-t', f'{seconds}']
    cmd += ['-i', str(path), '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-']
    err = run(cmd, capture=True).stderr
    summary = err[err.rfind('Summary:'):]
    integrated = re.search(r'I:\s*(-?[\d.]+|-inf) LUFS', summary)
    lra = re.search(r'LRA:\s*(-?[\d.]+) LU', summary)
    peak = re.search(r'Peak:\s*(-?[\d.]+|-inf) dBFS', summary)
    value = lambda m: None if not m or m.group(1) == '-inf' else float(m.group(1))
    return {'lufs': value(integrated), 'lra': value(lra), 'true_peak_dbtp': value(peak)}


def measure(path, ranges):
    result = {'whole': ebur128(path)}
    if ranges:
        result['ranges'] = []
        for item in ranges.split(','):
            a, b = (float(x) for x in item.split('-'))
            result['ranges'].append({'from': a, 'to': b, **ebur128(path, a, b - a)})
    return result


def normalize(src, dst, target, tp, lra, force):
    guard(dst, force)
    first = run([FFMPEG, '-hide_banner', '-nostats', '-i', str(src), '-vn', '-af',
                 f'loudnorm=I={target}:TP={tp}:LRA={lra}:print_format=json', '-f', 'null', '-'], capture=True).stderr
    stats = json.loads(first[first.rfind('{'):first.rfind('}') + 1])
    second = (f'loudnorm=I={target}:TP={tp}:LRA={lra}:measured_I={stats["input_i"]}:measured_TP={stats["input_tp"]}:'
              f'measured_LRA={stats["input_lra"]}:measured_thresh={stats["input_thresh"]}:'
              f'offset={stats["target_offset"]}:linear=true')
    cmd = [FFMPEG, '-y', '-loglevel', 'error', '-i', str(src)]
    if has_video(src):
        cmd += ['-c:v', 'copy']
    cmd += ['-af', f'{second},aresample=48000', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(dst)]
    run(cmd)
    return {'pass1': {k: stats[k] for k in ('input_i', 'input_tp', 'input_lra')}, 'result': ebur128(dst)}


# ------------------------------------------------------------------------------------------------ fonts
class TextOnly(HTMLParser):
    """Visible text nodes of an HTML page (script and style bodies skipped)."""

    def __init__(self):
        super().__init__()
        self.skip, self.parts = 0, []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def used_chars(files):
    chars = set()
    for path in files:
        text = Path(path).read_text(encoding='utf-8')
        if Path(path).suffix.lower() in ('.html', '.htm'):
            parser = TextOnly()
            parser.feed(text)
            text = ''.join(parser.parts)
        chars.update(c for c in text if not c.isspace())
    return chars


def fontcheck(font, files, subset_out, force):
    try:
        from fontTools.ttLib import TTFont
    except ImportError as exc:
        raise ValueError('fontTools missing; run with: uvx --from "fonttools[woff]" python media_tools.py ...') from exc
    cmap = TTFont(font).getBestCmap()
    used = used_chars(files)
    missing = sorted(c for c in used if ord(c) not in cmap)
    result = {'used': len(used), 'missing': missing}
    if subset_out:
        guard(subset_out, force)
        try:
            import brotli  # noqa: F401  woff2 output needs it
        except ImportError as exc:
            raise ValueError('woff2 needs brotli; run with: uvx --from "fonttools[woff]" --with numpy '
                             'python media_tools.py fontcheck ...') from exc
        from fontTools import subset
        options = subset.Options()
        options.flavor = 'woff2'
        source = TTFont(font)
        subsetter = subset.Subsetter(options)
        subsetter.populate(text=''.join(sorted(c for c in used if ord(c) in cmap)))
        subsetter.subset(source)
        source.flavor = 'woff2'
        source.save(subset_out)
        result['subset'] = str(subset_out)
    return result


# ------------------------------------------------------------------------------------------------ delivery
HDR_TRANSFERS = {'smpte2084', 'arib-std-b67'}
DRAFT_MARKERS = ('草稿', '预览', 'draft', 'preview')
MIN_BITS_PER_PIXEL = 0.04  # H.264 below this per pixel per frame shows blocking on phone screens


def probe_media(path):
    out = run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], capture=True)
    return json.loads(out.stdout)


def frame_rate(value):
    if not value or value in ('0/0', 'N/A'):
        return None
    num, _, den = str(value).partition('/')
    rate = float(num) / float(den or 1)
    return round(rate, 3) if rate > 0 else None


def as_number(value, kind=float):
    try:
        return kind(value)
    except (TypeError, ValueError):
        return None


def rotation(stream):
    for item in stream.get('side_data_list') or []:
        if 'rotation' in item:
            return int(as_number(item['rotation']) or 0)
    return int(as_number((stream.get('tags') or {}).get('rotate')) or 0)


def media_facts(info):
    """Displayed size (rotation applied), fps, bitrate, duration, transfer and audio channels of a probe result."""
    streams = info.get('streams') or []
    video = next((s for s in streams if s.get('codec_type') == 'video'
                  and not (s.get('disposition') or {}).get('attached_pic')), None)
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    fmt = info.get('format') or {}
    if video is None:
        raise ValueError(f'no video stream in {fmt.get("filename", "file")}')
    width, height = int(video['width']), int(video['height'])
    if abs(rotation(video)) % 180 == 90:
        width, height = height, width
    fps = frame_rate(video.get('avg_frame_rate')) or frame_rate(video.get('r_frame_rate'))
    bitrate = as_number(video.get('bit_rate'), int) or as_number(fmt.get('bit_rate'), int)
    duration = as_number(fmt.get('duration')) or as_number(video.get('duration'))
    return {'width': width, 'height': height, 'fps': fps,
            'bitrate_mbps': round(bitrate / 1e6, 2) if bitrate else None,
            'duration_s': round(duration, 3) if duration else None,
            'color_transfer': video.get('color_transfer'), 'pix_fmt': video.get('pix_fmt'),
            'codec': video.get('codec_name'),
            'audio_channels': int(audio['channels']) if audio and audio.get('channels') else 0}


def parse_size(text):
    match = re.fullmatch(r'\s*(\d+)\s*[x×X*]\s*(\d+)\s*', text or '')
    if not match:
        raise ValueError(f'size must look like 1080x1920, got {text!r}')
    return int(match.group(1)), int(match.group(2))


def composition_gate(edit):
    """A film rendered from a composition (remotion/, hyperframes/ or a visual-plan.json in the edit folder) ships
    only after plan_tools.py preflight passed on the current plan. A plain voice_edit / ffmpeg cut is not affected."""
    edit = Path(edit)
    plan = edit / 'visual-plan.json'
    if not ((edit / 'remotion').is_dir() or (edit / 'hyperframes').is_dir() or plan.is_file()):
        return []
    record = edit / 'verify' / 'preflight.json'
    if not record.is_file():
        return ['this film is rendered from a composition but verify/preflight.json is missing: '
                'run plan_tools.py preflight <edit> --data <composition data> before rendering']
    report = json.loads(record.read_text(encoding='utf-8-sig'))
    if not report.get('ok'):
        return ['verify/preflight.json did not pass: fix the plan and run plan_tools.py preflight again']
    if not plan.is_file() or hashlib.sha256(plan.read_bytes()).hexdigest() != report.get('plan_sha256'):
        return ['visual-plan.json changed after preflight: run plan_tools.py preflight again and re-render']
    return []


# ---------------------------------------------------------------- intermediate files after delivery

CLEAN_DIR_NAMES = ('build', 'voice_segs')
CLEAN_SKIP = {'node_modules', '.git', '__pycache__', 'verify', 'transcripts'}
RECORD_EXT = ('.json', '.md', '.txt', '.html', '.py', '.mjs', '.js')


def referenced_text(edit):
    """Everything the project's records say: JSON, Markdown, scripts. A file whose name appears there is in use."""
    chunks = []
    for folder, dirs, files in os.walk(edit):
        dirs[:] = [d for d in dirs if d not in CLEAN_SKIP and d not in CLEAN_DIR_NAMES]
        for name in files:
            if name.lower().endswith(RECORD_EXT):
                try:
                    chunks.append(Path(folder, name).read_text(encoding='utf-8', errors='replace'))
                except OSError:
                    pass
    return '\n'.join(chunks)


def clean_candidates(edit):
    """Intermediate renders (build/, voice_segs/) no record refers to, largest first. Referenced = its file name
    appears in any JSON / Markdown / script of the project, so the delivered cut and anything a plan or log
    points at stays; the five earlier 1080p exports and the per-segment caches go."""
    edit = Path(edit).resolve()
    records = referenced_text(edit)
    rows, kept = [], []
    for folder, dirs, files in os.walk(edit):
        dirs[:] = [d for d in dirs if d not in CLEAN_SKIP]
        if not any(part in CLEAN_DIR_NAMES for part in Path(folder).relative_to(edit).parts):
            continue
        for name in files:
            item = Path(folder, name)
            size = item.stat().st_size
            rel = item.relative_to(edit).as_posix()
            (kept if name in records else rows).append({'file': rel, 'mb': round(size / 1e6, 1)})
    rows.sort(key=lambda r: -r['mb'])
    return rows, kept


def clean(edit, yes=False):
    rows, kept = clean_candidates(edit)
    total = round(sum(r['mb'] for r in rows), 1)
    deleted = 0
    if yes:
        for r in rows:
            (Path(edit).resolve() / r['file']).unlink()
            deleted += 1
    return {'candidates': rows, 'total_mb': total, 'kept_referenced': len(kept), 'deleted': deleted,
            'note': 'deleted' if yes else 'nothing deleted: show this list to the user, rerun with --yes after their OK'}


def deliver_check(final, source=None, spec=None, probe=None):
    """Compare the deliverable with the source footage (the default spec) or an explicit WxH spec."""
    probe = probe or probe_media
    if not source and not spec:
        raise ValueError('pass --source (the original footage) or --spec WxH')
    out = media_facts(probe(final))
    src = media_facts(probe(source)) if source else None
    need = parse_size(spec) if spec else (src['width'], src['height'])
    errors, warnings = [], []

    name = Path(final).name.lower()
    marker = next((m for m in DRAFT_MARKERS if m in name), None)
    if marker:
        errors.append(f'file name marks a draft/preview render ("{marker}"); render the final instead of shipping it')
    if need[0] != need[1] and (need[0] > need[1]) != (out['width'] > out['height']):
        errors.append(f'orientation changed: deliverable {out["width"]}x{out["height"]}, '
                      f'required {need[0]}x{need[1]}')
    elif min(out['width'], out['height']) < min(need) or max(out['width'], out['height']) < max(need):
        errors.append(f'resolution dropped: deliverable {out["width"]}x{out["height"]}, required at least '
                      f'{need[0]}x{need[1]} ({"spec" if spec else "source"})')
    if out['audio_channels'] == 0:
        errors.append('deliverable has no audio track')
    if out['fps'] and out['bitrate_mbps']:
        bpp = out['bitrate_mbps'] * 1e6 / (out['width'] * out['height'] * out['fps'])
        if bpp < MIN_BITS_PER_PIXEL:
            warnings.append(f'video bitrate {out["bitrate_mbps"]} Mbps is {bpp:.3f} bits/pixel/frame '
                            f'(< {MIN_BITS_PER_PIXEL}): looks like a draft-grade encode')
    if src:
        if src['color_transfer'] in HDR_TRANSFERS and out['color_transfer'] in HDR_TRANSFERS:
            warnings.append(f'source is HDR ({src["color_transfer"]}) and the deliverable is still tagged '
                            f'{out["color_transfer"]}: tone-map to BT.709 SDR unless HDR delivery was agreed')
        if src['fps'] and out['fps'] and out['fps'] < src['fps'] - 0.5:
            warnings.append(f'frame rate dropped: {src["fps"]} -> {out["fps"]} fps')
        if out['audio_channels'] and out['audio_channels'] < src['audio_channels']:
            warnings.append(f'audio channels dropped: {src["audio_channels"]} -> {out["audio_channels"]}')
        if src['duration_s'] and out['duration_s'] and out['duration_s'] < src['duration_s']:
            warnings.append(f'duration {out["duration_s"]} s vs source {src["duration_s"]} s: '
                            'confirm the difference is the agreed edit, not a truncated render')
    return {'ok': not errors, 'deliverable': {'file': str(final), **out},
            'source': {'file': str(source), **src} if src else None,
            'required_size': f'{need[0]}x{need[1]}', 'errors': errors, 'warnings': warnings}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--force', action='store_true', help='replace existing outputs')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('clips')
    p.add_argument('spec', type=Path)
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--sheet-dir', type=Path, help='default: <out-dir>/sheets')
    p.add_argument('--only', nargs='*')
    p = sub.add_parser('stills')
    p.add_argument('clips', nargs='+', type=Path)
    p.add_argument('--sheet-dir', type=Path, required=True)
    p = sub.add_parser('cutpoint')
    p.add_argument('media', type=Path)
    p.add_argument('--near', type=float, required=True)
    p.add_argument('--window', type=float, default=0.4)
    p = sub.add_parser('level')
    p.add_argument('src', type=Path)
    p.add_argument('dst', type=Path)
    p.add_argument('--mean', type=float, default=-19.0)
    p.add_argument('--peak', type=float, default=-1.5)
    p = sub.add_parser('measure')
    p.add_argument('media', type=Path)
    p.add_argument('--ranges', help='e.g. 0-26.4,26.4-60')
    p = sub.add_parser('normalize')
    p.add_argument('src', type=Path)
    p.add_argument('dst', type=Path)
    p.add_argument('--target', type=float, default=-16.0)
    p.add_argument('--tp', type=float, default=-1.5)
    p.add_argument('--lra', type=float, default=11.0)
    p = sub.add_parser('fontcheck')
    p.add_argument('--font', type=Path, required=True)
    p.add_argument('files', nargs='+', type=Path)
    p.add_argument('--subset', type=Path, help='write a woff2 subset of the used characters')
    p = sub.add_parser('clean', help='intermediate renders in build/ and voice_segs/ that no record refers to; '
                                     'lists sizes, deletes only with --yes after the user agreed')
    p.add_argument('--edit', type=Path, required=True)
    p.add_argument('--yes', action='store_true', help='the user agreed to delete the listed files')
    p = sub.add_parser('deliver-check')
    p.add_argument('deliverable', type=Path)
    p.add_argument('--source', type=Path, help='original footage; its size is the default delivery spec')
    p.add_argument('--spec', help='delivery size WxH, e.g. 1080x1920 (overrides the source size)')
    p.add_argument('--report', type=Path, help='also write the JSON report here, e.g. verify/deliver_check.json')
    p.add_argument('--edit', type=Path, help='edit folder: a composition-rendered film also needs a current '
                                             'verify/preflight.json (plan_tools.py preflight)')
    args = parser.parse_args(argv)
    try:
        if args.command == 'clips':
            spec = json.loads(args.spec.read_text(encoding='utf-8'))
            args.out_dir.mkdir(parents=True, exist_ok=True)
            sheet_dir = args.sheet_dir or args.out_dir / 'sheets'
            sheet_dir.mkdir(parents=True, exist_ok=True)
            names = args.only or list(spec['clips'])
            result = {'clips': [cut_clip(n, spec['clips'][n], spec.get('defaults', {}), args.out_dir, sheet_dir,
                                         args.force) for n in names]}
        elif args.command == 'stills':
            args.sheet_dir.mkdir(parents=True, exist_ok=True)
            result = {'clips': [stills(c, args.sheet_dir, args.force) for c in args.clips]}
        elif args.command == 'cutpoint':
            result = {'candidates': cutpoint(args.media, args.near, args.window)}
        elif args.command == 'level':
            result = level(args.src, args.dst, args.mean, args.peak, args.force)
        elif args.command == 'measure':
            result = measure(args.media, args.ranges)
        elif args.command == 'normalize':
            result = normalize(args.src, args.dst, args.target, args.tp, args.lra, args.force)
        elif args.command == 'clean':
            result = clean(args.edit, args.yes)
        elif args.command == 'deliver-check':
            if args.report:
                guard(args.report, args.force)
            report = deliver_check(args.deliverable, args.source, args.spec)
            if args.edit:
                gate = composition_gate(args.edit)
                report['errors'] += gate
                report['ok'] = report['ok'] and not gate
            text = json.dumps(report, ensure_ascii=False, indent=2)
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(text + '\n', encoding='utf-8')
            print(text)
            return 0 if report['ok'] else 1
        else:
            result = fontcheck(args.font, args.files, args.subset, args.force)
            if result['missing']:
                print(json.dumps({'ok': False, **result}, ensure_ascii=False, indent=2))
                return 1
        print(json.dumps({'ok': True, **result}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(json.dumps({'ok': False, 'errors': [str(exc)]}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
