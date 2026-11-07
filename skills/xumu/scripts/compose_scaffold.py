#!/usr/bin/env python3
"""Generate a ready-to-check composition project from <edit>/visual-plan.json, so the agent only fills shot contents.

  hyperframes --edit <edit> [--out <dir>] [--force] [--preview-end <s>]
      <out>/index.html               HyperFrames root (plan width/height/fps/total length): one timed clip per shot in
                                     plan order, narration as the audio track, base_video under everything, SFX at offset
      <out>/compositions/shot-<id>.html
                                     one sub-composition per shot without a rendered file: local time starts at 0,
                                     a labelled placeholder to replace, its own paused timeline
      <out>/assets/                  plan media staged inside the project (hard link when possible, else a copy):
                                     HyperFrames refuses src paths that leave the project folder
      <out>/data.json                the same timing in seconds plus source_plan_sha256 (plan_tools.py preflight --data)
      <out>/package.json             hyperframes pinned to the verified version; npm run check / snapshot / render

Every start and duration is computed from the plan (from_frame / duration_frames / fps); nothing is hand typed.
Default out dir is <edit>/compose/hyperframes/; existing output files are never overwritten without --force
(--force rewrites index.html and the shot files too, so copy filled shots aside first).
PREVIEW_END (env, seconds) or --preview-end shortens the composition for a reference cut: HyperFrames reads the root
data-duration once at compile time and a script cannot change it, so the truncation happens here, at generation.
"""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import sys

for _stream in (sys.stdout, sys.stderr):   # Windows pipes default to the ANSI code page; the agent reads UTF-8
    if hasattr(_stream, 'reconfigure'):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_tools  # noqa: E402

HYPERFRAMES_VERSION = '0.8.230'          # verified version, see references/production.md "HyperFrames"
GSAP_SRC = 'https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js'
COMPOSITION_ID = 'main'
# Layer order (CSS z-index; HyperFrames tracks are only Studio display lanes, never layering).
Z_FILL, Z_BASE_VIDEO, Z_BACKGROUND, Z_OVERLAY = 0, 1, 1, 10
# Studio lanes, display only.
TRACK_FILL, TRACK_BASE, TRACK_BACKGROUND, TRACK_OVERLAY, TRACK_NARRATION, TRACK_SFX = 0, 1, 2, 3, 10, 11
MAX_VOLUME = 3.98                         # data-volume ceiling (+12 dB); plan gain goes to 4
ASSETS_DIR, COMPOSITIONS_DIR = 'assets', 'compositions'


def seconds(frames, fps):
    return round(frames / fps, 3)


def fmt(value):
    return f'{value:.3f}'


def slug(value):
    """File-name safe form of a shot or sfx id."""
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', value).strip('_') or 'x'


class Staging:
    """Plan media that must live inside the project folder; linked or copied when the project is written."""

    def __init__(self, root, out_dir):
        self.root, self.out_dir, self.items = root, out_dir, []

    def add(self, value, prefix):
        source = plan_tools.local_path(self.root, value)
        name = f'{prefix}-{source.name}'
        rel = f'{ASSETS_DIR}/{name}'
        self.items.append({'source': source, 'target': self.out_dir / ASSETS_DIR / name, 'src': rel})
        return rel

    def targets(self):
        return [item['target'] for item in self.items]

    def write(self, force):
        report = []
        for item in self.items:
            target = item['target']
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() or target.is_symlink():
                if not force:
                    raise FileExistsError(f'{target} exists; pass --force to overwrite')
                target.unlink()
            try:
                os.link(item['source'], target)
                how = 'hardlink'
            except OSError:                       # other drive, or links not allowed: copy instead
                shutil.copy2(item['source'], target)
                how = 'copy'
            report.append({'src': item['src'], 'from': str(item['source']), 'how': how})
        return report


def shot_rows(plan, root, staging):
    fps = plan['timeline']['fps']
    rows = []
    for shot in plan['shots']:
        asset = shot.get('asset') if isinstance(shot.get('asset'), dict) else None
        asset_src = None
        if asset and plan_tools.nonempty(asset.get('file')):
            try:
                if plan_tools.local_path(root, asset['file']).is_file():
                    asset_src = staging.add(asset['file'], slug(shot['id']))
            except (ValueError, OSError):
                asset_src = None
        rows.append({
            'id': shot['id'],
            'start_s': seconds(shot['from_frame'], fps),
            'duration_s': seconds(shot['duration_frames'], fps),
            'from_frame': shot['from_frame'],
            'duration_frames': shot['duration_frames'],
            'role': shot['role'],
            'route': shot['route'],
            'engine': shot.get('engine'),
            'style': shot.get('style'),
            'screen_text': shot.get('screen_text', ''),
            'inner_frames': shot.get('inner_frames', {}),
            'asset': asset_src,
            'composition': None if asset_src else f'{COMPOSITIONS_DIR}/shot-{slug(shot["id"])}.html',
        })
    return rows


def sfx_rows(plan, staging):
    fps = plan['timeline']['fps']
    by_id = plan_tools.shots_by_id(plan)
    rows = []
    for sound in plan.get('sfx', []):
        shot = by_id[sound['shot_id']]
        rows.append({
            'id': sound['id'],
            'shot_id': sound['shot_id'],
            'start_s': seconds(shot['from_frame'] + sound['offset_frames'], fps),
            'duration_s': seconds(sound['duration_frames'], fps),
            'volume': round(min(float(sound['gain']), MAX_VOLUME), 3),
            'src': staging.add(sound['file'], f'sfx-{slug(sound["id"])}'),
        })
    return rows


def build_data(plan, source_sha, shots, sfx, duration_s, preview_end, narration_src, base_src):
    timeline = plan['timeline']
    return {
        'source_plan_sha256': source_sha,
        'generated_from': 'visual-plan.json',
        'generator': 'compose_scaffold.py hyperframes',
        'hyperframes_version': HYPERFRAMES_VERSION,
        'fps': timeline['fps'],
        'width': timeline['width'],
        'height': timeline['height'],
        'total_frames': timeline['total_frames'],
        'duration_s': duration_s,
        'preview_end': preview_end,
        'narration': {'kind': plan['narration']['kind'], 'src': narration_src},
        'base_video': {'src': base_src} if base_src else None,
        'shots': shots,
        'sfx': sfx,
    }


def build_package(name, preview_end):
    cli = f'npx --yes hyperframes@{HYPERFRAMES_VERSION}'
    output = '预览.mp4' if preview_end else 'out.mp4'
    return {
        'name': name,
        'private': True,
        'description': 'HyperFrames composition generated by compose_scaffold.py from visual-plan.json',
        'scripts': {
            'check': f'{cli} check',
            'snapshot': f'{cli} snapshot',
            'render': f'{cli} render --quality delivery --output {output}',
        },
        'devDependencies': {'hyperframes': HYPERFRAMES_VERSION},
    }


def build_shot_composition(row, width, height, fps, overlay_slot):
    """One sub-composition per shot: local time starts at 0, a labelled placeholder the agent replaces."""
    sid = html.escape(row['id'], quote=True)
    sid_js = json.dumps(row['id'], ensure_ascii=False)
    text = html.escape(row['screen_text']) or '&nbsp;'
    meta = f"{row['role']} · {row['route']}" + (f" · {row['engine']}" if row['engine'] else '') \
        + (f" · {row['style']}" if row['style'] else '')
    font_px = max(28, round(min(width, height) / 24))
    label_px = max(18, round(font_px * 0.5))
    overlay = row['role'] == 'overlay'
    inner_css = (f'position: absolute; inset: 0; display: flex; align-items: flex-start; justify-content: flex-start; '
                 f'padding: {round(height * 0.04 + overlay_slot * font_px * 4)}px {round(width * 0.04)}px 0;'
                 if overlay else 'position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;')
    card_css = f'max-width: 46%; padding: {label_px}px {font_px}px;' if overlay else f'max-width: 72%; padding: {font_px}px;'
    dur = row['duration_s']
    return f'''<!doctype html>
<!-- shot {sid}: plan frames {row["from_frame"]}..{row["from_frame"] + row["duration_frames"]} ({fmt(dur)} s), mounted by
     index.html at {fmt(row["start_s"])} s. Generated by compose_scaffold.py from visual-plan.json; times are not hand typed.
     Local time: this file's timeline starts at 0 when the shot starts; inner_frames convert with frames / {fps}.
     Sub-composition contract (hyperframes-core): everything the render needs sits inside <template>; the root is
     styled by #root; data-composition-id here, on the host in index.html and the __timelines key are the same id. -->
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <title>{sid}</title>
  </head>
  <body>
    <template>
      <style>
        #root {{ position: absolute; inset: 0; overflow: hidden; color: #f4f4f2; font-family: system-ui, sans-serif; }}
        #shot-{sid}-inner {{ {inner_css} }}
        #shot-{sid}-inner .card {{ width: 100%; {card_css} background: rgba(20, 22, 26, 0.86); border: 2px dashed #c9ccd1;
                                   border-radius: 18px; overflow: hidden; }}
        #shot-{sid}-inner .label {{ font-size: {label_px}px; color: #c9ccd1; letter-spacing: 0.04em; margin-bottom: {label_px}px; }}
        #shot-{sid}-inner .text {{ font-size: {font_px}px; line-height: 1.35; max-width: 100%; overflow-wrap: anywhere; }}
        #shot-{sid}-inner .bar {{ margin-top: {label_px}px; height: 6px; width: 100%; background: rgba(255, 255, 255, 0.14);
                                  border-radius: 3px; }}
        #shot-{sid}-bar {{ display: block; width: 100%; height: 100%; background: #5ac8fa; border-radius: 3px; transform-origin: 0 50%; }}
      </style>
      <div id="root" data-composition-id="shot-{sid}" data-width="{width}" data-height="{height}" data-duration="{fmt(dur)}">
        <div id="shot-{sid}-inner">
          <!-- FILL: replace this card with the shot content. Animate #shot-{sid}-inner or its children on the
               timeline below (local seconds, 0 = shot start); never animate the host clip in index.html. -->
          <div class="card">
            <div class="label" data-layout-ignore>{sid} · {html.escape(meta)}</div>
            <div class="text">{text}</div>
            <div class="bar"><div id="shot-{sid}-bar" class="fill"></div></div>
          </div>
        </div>
      </div>
      <script>
        (function () {{
          const DURATION = {fmt(dur)};                // from the plan: duration_frames / fps
          const INNER_FRAMES = {json.dumps(row['inner_frames'], ensure_ascii=False)};   // local frames, FPS {fps}
          const id = {sid_js};
          const el = (suffix) => document.getElementById("shot-" + id + suffix);
          const tl = gsap.timeline({{ paused: true }});
          // Placeholder motion: the card is on screen from frame 0 (no empty first frame) and a progress bar runs for
          // the whole shot, so check sees live frames and a snapshot shows how far into the shot it is.
          // FILL: replace this with the real animation (prefer fromTo; land end states before DURATION).
          tl.fromTo(el("-bar"), {{ scaleX: 0 }}, {{ scaleX: 1, duration: Math.max(0.05, DURATION - 0.04), ease: "none" }}, 0);
          window.__timelines["shot-" + id] = tl;    // registered after the build, key = data-composition-id
        }})();
      </script>
    </template>
  </body>
</html>
'''


def shot_markup(row, width, height):
    sid = html.escape(row['id'], quote=True)
    z = Z_OVERLAY if row['role'] == 'overlay' else Z_BACKGROUND
    track = TRACK_OVERLAY if row['role'] == 'overlay' else TRACK_BACKGROUND
    timing = f'data-start="{fmt(row["start_s"])}" data-duration="{fmt(row["duration_s"])}"'
    head = (f'      <!-- shot {sid}: frames {row["from_frame"]}..{row["from_frame"] + row["duration_frames"]} '
            f'({row["role"]}, {row["route"]}); times from visual-plan.json -->\n')
    if row['asset']:
        # Rendered shot file: the timed element is the <video> itself (framework-owned playback); the untimed
        # wrapper is what the agent animates. A <video data-start> must not sit inside another timed element.
        return (head +
                f'      <div id="shot-{sid}-wrap" class="layer" style="z-index: {z}">\n'
                f'        <!-- FILL (optional): animate #shot-{sid}-wrap on the main timeline, e.g. a fade on the cut -->\n'
                f'        <video id="shot-{sid}" class="clip media" src="{html.escape(row["asset"], quote=True)}" '
                f'{timing} data-track-index="{track}" muted playsinline></video>\n'
                f'      </div>\n')
    return (head +
            f'      <div id="shot-{sid}" class="clip" data-composition-id="shot-{sid}" '
            f'data-composition-src="{html.escape(row["composition"], quote=True)}" {timing} '
            f'data-track-index="{track}" data-width="{width}" data-height="{height}" style="z-index: {z}"></div>\n')


def build_html(plan, shots, sfx, duration_s, preview_end, narration_src, base_src, edit_name):
    timeline = plan['timeline']
    width, height, fps = timeline['width'], timeline['height'], timeline['fps']
    total_s = seconds(timeline['total_frames'], fps)
    full = f'data-start="0.000" data-duration="{fmt(duration_s)}"'
    body = [f'      <div id="fill" class="clip" {full} data-track-index="{TRACK_FILL}" style="z-index: {Z_FILL}"></div>\n']
    if base_src:
        body.append(f'      <!-- base_video: the finished main cut, full length, under every shot -->\n'
                    f'      <div id="base-video-wrap" class="layer" style="z-index: {Z_BASE_VIDEO}">\n'
                    f'        <video id="base-video" class="clip media" src="{html.escape(base_src, quote=True)}" '
                    f'{full} data-track-index="{TRACK_BASE}" muted playsinline></video>\n'
                    f'      </div>\n')
    for row in shots:
        body.append(shot_markup(row, width, height))
    if narration_src:
        body.append(f'      <!-- narration ({plan["narration"]["kind"]}): the only master voice; every <video> stays muted -->\n'
                    f'      <audio id="narration" src="{html.escape(narration_src, quote=True)}" {full} '
                    f'data-track-index="{TRACK_NARRATION}" data-volume="1"></audio>\n')
    for sound in sfx:
        body.append(f'      <audio id="sfx-{html.escape(sound["id"], quote=True)}" src="{html.escape(sound["src"], quote=True)}" '
                    f'data-start="{fmt(sound["start_s"])}" data-duration="{fmt(sound["duration_s"])}" '
                    f'data-track-index="{TRACK_SFX}" data-volume="{sound["volume"]}"></audio>\n')
    shots_js = json.dumps([{'id': r['id'], 'start': r['start_s'], 'duration': r['duration_s'], 'role': r['role'],
                            'video': r['asset'] is not None} for r in shots], ensure_ascii=False)
    preview_note = (f'     PREVIEW: shortened to {fmt(duration_s)} s of {fmt(total_s)} s (PREVIEW_END); '
                    f'regenerate without it for the full film.\n' if preview_end else
                    '     PREVIEW: set PREVIEW_END=<seconds> (or --preview-end) when regenerating to cut a reference '
                    'film short; HyperFrames reads the root data-duration once at compile time, so a script cannot.\n')
    return f'''<!doctype html>
<!-- Generated by compose_scaffold.py from visual-plan.json ({edit_name}); HyperFrames {HYPERFRAMES_VERSION}.
     Canvas {width}x{height} @ {fps} fps, {timeline["total_frames"]} frames = {fmt(total_s)} s: the delivery size, never smaller.
     Every data-start / data-duration below is computed from the plan (from_frame, duration_frames, fps).
     Do not hand-type times: change the plan, then regenerate (--force) or update data.json and this file together.
{preview_note}     Shots without a rendered file are sub-compositions in {COMPOSITIONS_DIR}/shot-<id>.html (local time, own timeline):
     fill the shot there. Rules kept here (hyperframes-core contract):
       - one paused GSAP timeline per composition, registered at window.__timelines[<data-composition-id>] after the build
       - animate inner containers (#shot-<id>-inner in the shot file, #shot-<id>-wrap here), never a timed clip itself
       - every <video>/<audio> has an id; videos are muted + playsinline; no play()/seek calls; no crossorigin
       - media src stays inside this folder ({ASSETS_DIR}/): HyperFrames refuses paths that leave the project
       - no Date.now / Math.random / repeat:-1; no CSS transform on a node you also tween with x/y
       - z-index per layer: fill {Z_FILL}, base video {Z_BASE_VIDEO}, background shots {Z_BACKGROUND}, overlays {Z_OVERLAY} -->
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={width}, height={height}" />
    <title>{html.escape(edit_name)} · HyperFrames composition</title>
    <script src="{GSAP_SRC}"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {width}px; height: {height}px; overflow: hidden; background: #0b0f14; }}
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; background: #0b0f14; }}
      .clip {{ position: absolute; inset: 0; }}
      .layer {{ position: absolute; inset: 0; }}            /* untimed wrapper: animate this, not the clip inside */
      #fill {{ background: #14181f; }}
      video.media {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="{COMPOSITION_ID}" data-start="0" data-width="{width}" data-height="{height}" data-fps="{fps}" data-duration="{fmt(duration_s)}">
{''.join(body)}    </div>
    <script>
      // SHOTS mirrors data.json (seconds, from the plan): use it for main-timeline timing, never retype numbers.
      const SHOTS = {shots_js};
      const el = (id) => document.getElementById(id);
      const tl = gsap.timeline({{ paused: true }});
      // FILL (optional): main-timeline motion on untimed wrappers, e.g. a cut fade on a video shot:
      //   for (const s of SHOTS.filter((s) => s.video)) tl.fromTo(el(`shot-${{s.id}}-wrap`), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.2 }}, s.start);
      // Shot-internal motion belongs in {COMPOSITIONS_DIR}/shot-<id>.html, not here.
      window.__timelines["{COMPOSITION_ID}"] = tl;
    </script>
  </body>
</html>
'''


def write_text(path, text, force):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w' if force else 'x', encoding='utf-8') as stream:
        stream.write(text)


def scaffold_hyperframes(edit, out_dir=None, force=False, preview_end=None):
    edit = Path(edit).resolve()
    plan_file = edit / 'visual-plan.json'
    if not plan_file.is_file():
        raise ValueError(f'no visual-plan.json in {edit}: write the picture plan first')
    raw = plan_file.read_bytes()
    plan = json.loads(raw.decode('utf-8-sig'), parse_constant=plan_tools.reject_constant)
    source_sha = hashlib.sha256(raw).hexdigest()
    root = plan_file.parent
    errors = plan_tools.validate(plan, root)
    if errors:
        return {'ok': False, 'errors': [f'visual-plan.json: {e}' for e in errors]}
    out_dir = Path(out_dir).resolve() if out_dir else edit / 'compose' / 'hyperframes'

    timeline = plan['timeline']
    fps, width, height = timeline['fps'], timeline['width'], timeline['height']
    total_s = seconds(timeline['total_frames'], fps)
    if preview_end is None:
        env = os.environ.get('PREVIEW_END', '').strip()
        preview_end = float(env) if env else None
    if preview_end is not None and not preview_end > 0:
        raise ValueError('PREVIEW_END / --preview-end must be a positive number of seconds')
    duration_s = round(min(total_s, preview_end), 3) if preview_end else total_s
    preview_end = preview_end if preview_end and preview_end < total_s else None

    staging = Staging(root, out_dir)
    narration_src = None
    if plan['narration']['kind'] != 'none' and plan_tools.nonempty(plan['narration'].get('file')):
        narration_src = staging.add(plan['narration']['file'], 'narration')
    base_src = staging.add(plan['base_video']['file'], 'base') if plan.get('base_video') else None
    shots = shot_rows(plan, root, staging)
    sfx = sfx_rows(plan, staging)
    for item in staging.items:
        if not item['source'].is_file():
            return {'ok': False, 'errors': [f'{item["source"]}: file does not exist']}

    files = {out_dir / 'index.html': build_html(plan, shots, sfx, duration_s, preview_end, narration_src, base_src, edit.name)}
    overlay_slot = 0
    for row in shots:
        if row['composition']:
            files[out_dir / row['composition']] = build_shot_composition(row, width, height, fps, overlay_slot)
            overlay_slot += row['role'] == 'overlay'
    data = build_data(plan, source_sha, shots, sfx, duration_s, preview_end, narration_src, base_src)
    package = build_package(f'{edit.name}-hyperframes'.lower().replace(' ', '-'), preview_end)
    files[out_dir / 'data.json'] = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    files[out_dir / 'package.json'] = json.dumps(package, ensure_ascii=False, indent=2) + '\n'

    existing = [str(p) for p in list(files) + staging.targets() if p.exists()]
    if existing and not force:
        return {'ok': False, 'errors': [f'{p} exists; pass --force to overwrite' for p in existing]}
    for path, text in files.items():
        write_text(path, text, force)
    staged = staging.write(force)

    cli = f'npx --yes hyperframes@{HYPERFRAMES_VERSION}'
    until = duration_s if preview_end else None
    if hasattr(plan_tools, 'snapshot_times'):       # the stills list preflight expects (every join, end and middle)
        at = ','.join(str(t['t']) for t in plan_tools.snapshot_times(plan, until))
    else:
        marks = sorted({round(min(r['start_s'] + 0.1, duration_s - 0.05), 3) for r in shots if r['start_s'] < duration_s})
        at = ','.join(fmt(m) for m in marks) or fmt(max(0.0, duration_s / 2))
    tools = Path(__file__).resolve().parent
    stills = f'python "{tools / "plan_tools.py"}" snapshots "{plan_file}"' + (f' --until {fmt(until)}' if until else '')
    return {
        'ok': True,
        'out': str(out_dir),
        'files': [p.relative_to(out_dir).as_posix() for p in files],
        'assets': staged,
        'shots': len(shots),
        'placeholders': sum(1 for r in shots if r['composition']),
        'videos': sum(1 for r in shots if r['asset']) + (1 if base_src else 0),
        'audio': (1 if narration_src else 0) + len(sfx),
        'duration_s': duration_s,
        'total_s': total_s,
        'preview_end': preview_end,
        'source_plan_sha256': source_sha,
        'next': [
            f'cd "{out_dir}"',
            f'{cli} check',
            stills,
            f'{cli} snapshot --at {at}',
            f'{stills} --frames-dir "{out_dir / ".hyperframes" / "artifacts" / "snapshots"}"',
            f'python "{tools / "plan_tools.py"}" preflight "{edit}" --data "{out_dir / "data.json"}"',
            f'{cli} render --quality delivery --output {"预览.mp4" if preview_end else "out.mp4"}',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    hf = sub.add_parser('hyperframes', help='HyperFrames project skeleton from visual-plan.json')
    hf.add_argument('--edit', type=Path, required=True, help='edit directory holding visual-plan.json')
    hf.add_argument('--out', type=Path, help='output directory (default <edit>/compose/hyperframes)')
    hf.add_argument('--force', action='store_true', help='overwrite the generated files and staged assets')
    hf.add_argument('--preview-end', type=float, help='cut the composition at this many seconds (reference film)')
    args = parser.parse_args(argv)
    try:
        report = scaffold_hyperframes(args.edit, args.out, args.force, args.preview_end)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report = {'ok': False, 'errors': [f'{type(exc).__name__}: {exc}']}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
