#!/usr/bin/env python3
"""Searchable index over external motion libraries (read-only references), queried in Chinese or English.

  fetch   download the read-only references into the refs dir (git clone + registry metadata; needs network)
  build   gongnyang/awesome-ai-motion index.json + HyperFrames registry item metadata
          + mg-styles-15 style prompts + Lemo-Opuscar style rules                       ->  motion-index.json
  search  Chinese or English keywords -> ranked effects, recipes, blocks and components
  show    one entry with its parameters, usage notes and local/online paths
  samples report the size of the motion samples not yet on this machine; --yes downloads them into <refs>/samples
  frames  contact sheet per sample (evenly spaced frames in one row) so a shortlisted move can be looked at

Refs dir: env XUMU_REFS, else backends.local.json "refs", else <skills dir>/_refs.
Sources:
  gn:<slug>        gongnyang effect card (definition, conveys, use/avoid, params, HyperFrames notes)  MIT
  gn-recipe:<slug> gongnyang recipe (ordered effect sequence)                                          MIT
  hf:<name>        HyperFrames registry block/component (install into a HyperFrames project)          Apache-2.0
  mg15:<id>        Vincentwei1021/mg-styles-15 style: signature features, techniques, route, reference
                   10 s film, full prompt and deterministic source (renderAt(t))                       MIT
  opus:<slug>      lemomo-ai/lemo-opuscar style (pinned revision): full rules (STYLE.md), native moves,
                   demo notes and deterministic source (render(t)); sample film online                  MIT
  sc:<style-key>   Video Shotcraft gallery preview (frames only; cards are read from the Shotcraft skill)
Samples on disk: gn clips ship with the gongnyang checkout; Shotcraft previews, mg15 films and Opuscar films
are downloaded by `samples` (sizes first, --yes to fetch).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

for _stream in (sys.stdout, sys.stderr):   # Windows pipes default to the ANSI code page; the agent reads UTF-8
    if hasattr(_stream, 'reconfigure'):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            pass

SKILL_ROOT = Path(__file__).resolve().parent.parent

PURPOSES = {'주목 끌기': '吸引注意', '설명': '解释', '비교': '对比', '순서·흐름': '顺序流程', '강조': '强调',
            '전환': '转场', '데이터 증명': '数据证据', '피드백': '反馈', '분위기': '氛围', '브랜딩': '品牌'}
MEDIA = {'설명 영상': '解说视频', '숏폼': '短视频', '스크롤덱': '滚动页', '발표': '演示', '제품 시연': '产品演示',
         '데이터 스토리': '数据故事', '웹 UI': '网页界面', '썸네일': '封面'}
FAMILIES = {'principles': '运动原理', 'entrance': '入场退场', 'emphasis': '强调', 'type': '文字', 'transitions': '转场',
            'camera': '镜头', 'data': '数据', 'ui': '界面', 'explainer': '解说图解', 'shape': '形状',
            'texture': '质感', 'generative': '生成艺术', 'depth': '空间纵深', 'loop': '循环', 'caption': '字幕'}

# Chinese query word -> terms that appear in the English/Korean source text and tags.
SYNONYMS = {
    '对比': ['compare', 'comparison', 'before', 'after', 'split', 'versus', '비교'],
    '前后': ['before', 'after', 'before-after'], '分屏': ['split', 'split-screen'],
    '因果': ['cause', 'flow', 'arrow', 'process', 'chain'], '流程': ['flow', 'flowchart', 'process', 'pipeline', 'step', 'steps', '순서·흐름'],
    '步骤': ['step', 'steps', 'stepper', 'walkthrough', 'sequence'], '顺序': ['sequence', 'stagger', 'order', '순서·흐름'],
    '列举': ['list', 'checklist', 'stagger', 'cascade'], '清单': ['checklist', 'list', 'check'],
    '数据': ['data', 'chart', 'stat', 'number', 'graph', '데이터 증명'], '数字': ['number', 'count', 'counter', 'stat', 'digits'],
    '图表': ['chart', 'graph', 'bar', 'line', 'pie', 'donut'], '增长': ['grow', 'rise', 'count-up', 'bar-grow', 'line'],
    '下降': ['decline', 'drop', 'fall'], '排名': ['rank', 'ranking', 'race'], '占比': ['pie', 'donut', 'percent', 'fraction', 'unit'],
    '地图': ['map', 'geography', 'route', 'globe', 'world'], '路线': ['route', 'path', 'map', 'flight', 'travel'],
    '时间线': ['timeline', 'chronology', 'date', 'history'], '历史': ['history', 'timeline', 'retro', 'archive', 'vintage'],
    '强调': ['emphasis', 'emphasize', 'highlight', 'accent', '강조'], '重点': ['highlight', 'emphasis', 'focus', 'spotlight'],
    '高亮': ['highlight', 'marker', 'sweep'], '标注': ['annotation', 'annotate', 'callout', 'label', 'arrow'],
    '圈注': ['circle', 'callout', 'circumscribe'], '箭头': ['arrow'], '下划线': ['underline', 'squiggle'],
    '手绘': ['hand-drawn', 'handwritten', 'hw', 'sketch', 'scribble', 'boil', 'whiteboard', 'marker', 'doodle'],
    '手写': ['handwriting', 'handwritten', 'write-on', 'write'], '白板': ['whiteboard', 'marker', 'hand-drawn', 'ink'],
    '涂鸦': ['scribble', 'doodle', 'sketch'], '粉笔': ['chalk', 'chalkboard'], '水墨': ['ink', 'ink-bleed', 'brush', 'fluid-ink'],
    '墨': ['ink'], '纸': ['paper', 'collage', 'papercut', 'page'], '拼贴': ['collage', 'cutout', 'scrapbook', 'sticker'],
    '剪纸': ['papercut', 'cutout', 'paper'], '撕纸': ['tear', 'torn', 'perforated'], '贴纸': ['sticker', 'badge', 'pop'],
    '标题': ['title', 'headline', 'titlecard', 'type'], '文字': ['text', 'type', 'typography', 'word', 'caption'],
    '大字': ['headline', 'kinetic', 'slam', 'giant', 'type'], '打字': ['typing', 'typewriter', 'typed'], '金句': ['quote', 'headline', 'kinetic'],
    '引用': ['quote', 'testimonial', 'source'], '字幕': ['caption', 'subtitle', 'karaoke', 'lower-third'],
    '人名条': ['lower-third'], '转场': ['transition', 'wipe', 'cut', '전환'], '擦除': ['wipe'], '遮罩': ['mask', 'reveal', 'iris'],
    '揭示': ['reveal', 'disclosure', 'unveil'], '入场': ['entrance', 'in', 'reveal', 'pop'], '退场': ['exit', 'out'],
    '镜头': ['camera', 'push', 'pan', 'zoom', 'dolly'], '推近': ['push-in', 'zoom', 'punch-in', 'zoom-to-detail'],
    '拉远': ['pull-back', 'unzoom', 'zoom-out'], '平移': ['pan', 'stations', 'slide'], '甩镜': ['whip', 'whip-pan'],
    '一镜到底': ['continuous', 'infinite-pan', 'one take', 'stations', 'camera-flight'], '视差': ['parallax', 'depth'],
    '纵深': ['depth', '3d', 'parallax'], '三维': ['3d', 'three', 'extrude', 'orbit', 'depth'], '立体': ['3d', 'extrude', 'extrusion'],
    '旋转': ['rotate', 'orbit', 'spin', 'turntable'], '爆炸图': ['exploded', 'layer-separation', 'assembly'],
    '等距': ['isometric'], '粒子': ['particle', 'particles'], '故障': ['glitch', 'datamosh', 'rgb'], '霓虹': ['neon', 'glow'],
    '复古': ['retro', 'vintage', 'vhs', 'crt', 'film', 'analog'], '老电视': ['crt', 'scanline', 'vhs', 'tv'],
    '胶片': ['film', 'grain', 'dust', 'gate', 'light-leak'], '颗粒': ['grain', 'noise', 'dither'], '网点': ['halftone', 'dither'],
    '像素': ['pixel', 'dither', 'pixelate', 'ascii'], '终端': ['terminal', 'code', 'ascii'], '代码': ['code', 'terminal', 'diff'],
    '界面': ['ui', 'mock-ui', 'app', 'screen', 'device'], '手机': ['phone', 'iphone', 'mobile', 'device'],
    '电脑': ['macbook', 'browser', 'desktop', 'device'], '光标': ['cursor', 'pointer'], '点击': ['click', 'tap', 'press', 'cursor'],
    '对话': ['chat', 'message', 'speech-bubble', 'conversation'], '气泡': ['bubble', 'speech-bubble'], '通知': ['notification', 'toast'],
    '社交': ['social', 'tiktok', 'instagram', 'x-post', 'reddit', 'comment'], '评论': ['comment', 'reddit', 'testimonial'],
    '角色': ['character', 'mascot', 'puppet', 'walk-cycle', 'articulation'], '人物': ['character', 'avatar', 'portrait'],
    '图标': ['icon'], '节拍': ['beat', 'rhythm', 'music'], '卡点': ['beat', 'cut'], '循环': ['loop'], '背景': ['background', 'ambient', 'gradient'],
    '渐变': ['gradient', 'mesh', 'aurora'], '光': ['light', 'glow', 'flare', 'rays', 'leak'], '玻璃': ['glass', 'liquid-glass', 'refraction'],
    '开场': ['intro', 'opener', 'hook', 'title', 'logo'], '钩子': ['hook', 'attention', '주목 끌기'], '结尾': ['outro', 'end-card', 'cta', 'close'],
    '章节': ['chapter', 'title-card', 'interstitial', 'section'], '解释': ['explainer', 'explain', '설명'], '原理': ['principle', 'explainer', 'mechanism'],
    'AI': ['ai', 'token', 'embedding', 'attention', 'chat'], '规模': ['scale', 'grid', 'unit', 'repeat', 'overwhelm'],
    '压力': ['overwhelm', 'pressure', 'pileup', 'surround'], '问题': ['problem', 'question'], '证据': ['proof', 'evidence', 'source', '데이터 증명'],
    '新闻': ['news', 'editorial', 'ticker', 'journalism'], '杂志': ['editorial', 'magazine'], '电影': ['cinematic', 'film', 'anamorphic'],
    '品牌': ['brand', 'logo', 'wordmark', '브랜딩'], '氛围': ['ambient', 'atmosphere', '분위기'], '数学': ['math', 'geometry', 'vector', 'fourier', 'plane'],
    '风格': ['style'], '综艺': ['variety', 'hanazi', 'caption'], '花字': ['hanazi', 'variety', 'caption'],
    '科普': ['explainer', 'paperclip', 'science'], '形变': ['morph', 'morphing', 'shape-morph'], '液态': ['liquid', 'metaball', 'fluid'],
    '线条': ['line', 'line-art', 'stroke', 'draw-on'], '一笔画': ['line-art', 'one-line', 'draw-on'],
    '扁平': ['flat', 'vector', 'flat-vector'], '包豪斯': ['bauhaus', 'geometric', 'konstruktion'],
}

TOKEN = re.compile(r'[a-z0-9][a-z0-9\-]*|[ㄱ-힝]+|[一-鿿]+', re.I)


def refs_config():
    try:
        return json.loads((SKILL_ROOT / 'backends.local.json').read_text(encoding='utf-8')).get('refs', {})
    except (OSError, ValueError):
        return {}


REPOS = {'awesome-ai-motion': 'https://github.com/gongnyang/awesome-ai-motion.git',
         'bang-motion': 'https://github.com/bangtutorial/bang-motion.git',
         'mg-styles-15': 'https://github.com/Vincentwei1021/mg-styles-15.git',
         'lemo-opuscar': 'https://github.com/lemomo-ai/lemo-opuscar.git'}
# Repos checked out at a fixed revision: the style keys, frames and sample hashes in library/styles match it.
PINNED = {'lemo-opuscar': '413a6bd6d78ebd3bdd5abaec9538a26867f890df'}
MEDIA_GLOBS = ['!*.mp4', '!*.webm', '!*.mov', '!*.wav', '!*.mp3', '!*.m4a', '!*.ogg', '!*.flac', '!*.png', '!*.jpg',
               '!*.jpeg', '!*.webp', '!*.gif', '!*.ttf', '!*.otf', '!*.woff', '!*.woff2', '!*.glb', '!*.hdr', '!*.exr',
               '!*.npy', '!*.bin']
# Large repos are cloned sparsely: prompts and source only, no films, HDRIs, meshes or instrument samples.
SPARSE = {'mg-styles-15': ['/prompts/', '/demos/', '/harness/', '/lib/audio/', '!/lib/audio/samples/', '/template.md',
                           '/rubric.md', '/README.md', '/README.zh-CN.md', '/LICENSE', '/assets/fonts/'],
          'lemo-opuscar': ['/styles/', '/core/', '/LICENSE', '/TECHNIQUE.md', '/DIRECTOR.md', '/README.zh-CN.md', *MEDIA_GLOBS]}
OPUS_FILMS = 'https://github.com/lemomo-ai/lemo-opuscar/releases/download/web/'
OPUS_REPO = f'https://github.com/lemomo-ai/lemo-opuscar/blob/{PINNED["lemo-opuscar"]}/'
MG15_FILMS = 'https://vincentwei1021.github.io/mg-styles-15/?lang=zh#'
MG15_REPO = 'https://github.com/Vincentwei1021/mg-styles-15/blob/main/'
CJK = re.compile(r'[\u3400-\u9fff]')
HF_RAW = 'https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry'


def refs_dir():
    if os.environ.get('XUMU_REFS'):
        return Path(os.environ['XUMU_REFS'])
    cfg = refs_config()
    if cfg.get('dir'):
        return Path(cfg['dir'])
    if cfg.get('gongnyang'):
        return Path(cfg['gongnyang']).parent
    return SKILL_ROOT.parent / '_refs'


def default_index_path():
    return Path(refs_config().get('motion_index') or refs_dir() / 'motion-index.json')


def source_paths():
    cfg, root = refs_config(), refs_dir()
    gn = Path(cfg['gongnyang']) if cfg.get('gongnyang') else root / 'awesome-ai-motion'
    hf = Path(cfg['hyperframes_registry']) if cfg.get('hyperframes_registry') else root / 'hyperframes-registry'
    mg = Path(cfg['mg_styles']) if cfg.get('mg_styles') else root / 'mg-styles-15'
    opus = Path(cfg['opuscar']) if cfg.get('opuscar') else root / 'lemo-opuscar'
    return gn, hf, mg, opus


def fetch(root):
    """Shallow-clone the reference repos and download HyperFrames registry item metadata (small JSON only)."""
    root.mkdir(parents=True, exist_ok=True)
    done = {}
    for name, url in REPOS.items():
        target = root / name
        if name in PINNED:
            rev = PINNED[name]
            if not (target / '.git').exists():
                subprocess.run(['git', 'clone', '--depth', '1', '-q', '--filter=blob:none', '--sparse', '--no-checkout', url,
                                str(target)], check=True)
            subprocess.run(['git', '-C', str(target), 'sparse-checkout', 'set', '--no-cone', *SPARSE[name]], check=True)
            subprocess.run(['git', '-C', str(target), 'fetch', '--depth', '1', '-q', 'origin', rev], check=True)
            subprocess.run(['git', '-C', str(target), 'checkout', '-q', rev], check=True)
            done[name] = f'checked out {rev[:7]} (rules and source only)'
        elif (target / '.git').exists():
            subprocess.run(['git', '-C', str(target), 'pull', '--ff-only', '-q'], check=True)
            done[name] = 'updated'
        elif name in SPARSE:
            subprocess.run(['git', 'clone', '--depth', '1', '-q', '--filter=blob:none', '--sparse', url, str(target)],
                           check=True)
            subprocess.run(['git', '-C', str(target), 'sparse-checkout', 'set', '--no-cone', *SPARSE[name]], check=True)
            done[name] = 'cloned (prompts and source only)'
        else:
            subprocess.run(['git', 'clone', '--depth', '1', '-q', url, str(target)], check=True)
            done[name] = 'cloned'
    hf = root / 'hyperframes-registry'
    (hf / 'items').mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(f'{HF_RAW}/registry.json', timeout=60) as r:
        registry = json.loads(r.read().decode('utf-8'))
    (hf / 'registry.json').write_text(json.dumps(registry, ensure_ascii=False), encoding='utf-8')
    folders = {'hyperframes:block': 'blocks', 'hyperframes:component': 'components'}
    wanted = [(folders[i['type']], i['name']) for i in registry.get('items', []) if i.get('type') in folders]

    def get(item):
        folder, name = item
        try:
            with urllib.request.urlopen(f'{HF_RAW}/{folder}/{name}/registry-item.json', timeout=60) as r:
                (hf / 'items' / f'{folder}_{name}.json').write_bytes(r.read())
            return None
        except OSError as exc:
            return f'{folder}/{name}: {exc}'

    with ThreadPoolExecutor(max_workers=16) as pool:
        failures = [f for f in pool.map(get, wanted) if f]
    done['hyperframes-registry'] = f'{len(wanted) - len(failures)}/{len(wanted)} items'
    return {'refs': str(root), 'sources': done, 'failures': failures[:10]}


def split_title(title):
    """'粗描边贴纸人科普 MG（回形针风格） Bold-outline Sticker Explainer' -> (Chinese name, English name).
    A Chinese name may end in Latin tokens that the English name repeats: '等轴 2.5D Isometric / 2.5D'."""
    last = max((m.end() for m in CJK.finditer(title)), default=0)
    if title[last:last + 1] == '）':
        last += 1
    zh, tail = title[:last].strip(), title[last:].split()
    for k in range(len(tail) - 1, 0, -1):
        extra, rest = ' '.join(tail[:k]), ' '.join(tail[k:])
        if extra in rest and not any(c.islower() for c in extra):       # acronyms only: 2.5D, HUD / FUI
            return f'{zh} {extra}', rest
    return zh, ' '.join(tail)


def parse_mg_prompt(path):
    """One mg-styles-15 prompt file -> index entry. Signature features are what the reference film is judged on."""
    text = path.read_text(encoding='utf-8')
    zh, en = split_title(text.splitlines()[0].lstrip('# ').strip())

    def section(name):
        m = re.search(rf'^# {name}[^\n]*\n(.*?)(?=^# |^```)', text, re.S | re.M)
        return m.group(1).strip() if m else ''

    film = re.search(r'\*\*原片\*\*：(.+)', text)
    route = section('Suggested technical route').split('\n(You may')[0].strip()
    signature = section('Signature features')
    origin, features, techniques = [], [], []
    for line in signature.splitlines():
        line = line.strip()
        if line.startswith('视觉特征'):
            features = [f.strip() for f in line[4:].split(',') if f.strip()]
        elif line.startswith('关键技法'):
            techniques.append(line[4:].strip())
        elif techniques:
            techniques.append(line)
        elif line:
            origin.append(line)
    output = section('Output').lstrip('- ').replace('\n  ', ' ')
    stem = path.stem
    return {
        'id': f'mg15:{stem}', 'source': 'mg-styles-15', 'kind': 'style', 'name': en, 'name_local': zh,
        'summary': ' '.join(origin), 'tags': features, 'techniques': techniques, 'route': route, 'output': output,
        'film': film.group(1).strip() if film else None, 'preview_url': MG15_FILMS + stem,
        'doc': str(path), 'source_dir': str(path.parent.parent / 'demos' / stem),
        'prompt_url': f'{MG15_REPO}prompts/{stem}.md', 'license': 'MIT',
    }


def parse_opus_style(folder):
    """One Lemo-Opuscar style folder -> index entry. Native moves are the menu a shot brief picks from."""
    meta = json.loads((folder / 'style.json').read_text(encoding='utf-8'))
    text = (folder / 'STYLE.md').read_text(encoding='utf-8')
    lead = re.search(r'^> (.+)$', text, re.M)
    moves, sections, inside = [], [], False
    for line in text.splitlines():
        if line.startswith('## '):
            sections.append(re.sub(r'^\d+\.\s*', '', line[3:]).strip())
            inside = 'native moves' in line.lower()
            continue
        m = re.match(r'^(?:[-*]|\d+\.|\|)\s*\*\*(.+?)\*\*', line.strip()) if inside else None
        if m:
            moves.append(m.group(1).strip().rstrip('.'))
    slug = meta.get('slug') or folder.name
    return {
        'id': f'opus:{slug}', 'source': 'lemo-opuscar', 'kind': 'style', 'name': meta.get('en'), 'name_local': meta.get('cn'),
        'family': meta.get('category_cn'), 'style_key': f'opuscar-{slug}', 'summary': lead.group(1).strip() if lead else '',
        'tags': moves, 'techniques': sections, 'purposes': meta.get('uses', []), 'film': meta.get('film'),
        'film_line': meta.get('line_cn') or meta.get('line'), 'preview_url': f'{OPUS_FILMS}{slug}.mp4',
        'doc': str(folder / 'STYLE.md'), 'demo_doc': str(folder / 'DEMO.md'), 'source_dir': str(folder / 'demo'),
        'prompt_url': f'{OPUS_REPO}styles/{slug}/STYLE.md', 'license': 'MIT; films and frames CC BY 4.0',
    }


def build(gn_root, hf_root, mg_root=None, opus_root=None):
    entries = []
    if gn_root:
        data = json.loads((gn_root / 'index.json').read_text(encoding='utf-8'))
        for e in data['effects']:
            card = gn_root / 'effects' / e['slug']
            clip = next((str(card / n) for n in ('clip.mp4', 'preview.gif') if (card / n).exists()), None)
            entries.append({
                'id': f'gn:{e["slug"]}', 'source': 'gongnyang', 'kind': 'effect',
                'name': e.get('en'), 'name_local': e.get('ko'), 'family': FAMILIES.get(e.get('family'), e.get('family')),
                'purposes': [PURPOSES.get(p, p) for p in e.get('purposes', [])],
                'media': [MEDIA.get(m, m) for m in e.get('media', [])],
                'tags': e.get('aka', []), 'summary': e.get('oneLiner'), 'conveys': e.get('conveys'),
                'use_when': e.get('useWhen', []), 'avoid': e.get('avoid', []), 'params': e.get('params', []),
                'ease': e.get('ease'), 'pairs_with': e.get('pairsWith', []),
                'hyperframes_note': (e.get('engines') or {}).get('hyperframes'),
                'doc': str(card / 'README.md'), 'clip': clip,
            })
        for r in data.get('recipes', []):
            slug = r.get('slug')
            entries.append({
                'id': f'gn-recipe:{slug}', 'source': 'gongnyang', 'kind': 'recipe',
                'name': r.get('en'), 'name_local': r.get('ko'),
                'summary': r.get('oneLinerEn') or r.get('oneLiner'), 'conveys': r.get('styleEn') or r.get('style'),
                'media': [MEDIA.get(m, m) for m in r.get('media', [])], 'duration': r.get('duration'),
                'steps': r.get('steps', []), 'avoid': r.get('avoid', []),
                'tags': [s.get('effect') for s in r.get('steps', []) if s.get('effect')],
                'doc': str(gn_root / 'recipes' / str(slug) / 'README.md'),
            })
    if hf_root:
        for path in sorted((hf_root / 'items').glob('*.json')):
            j = json.loads(path.read_text(encoding='utf-8'))
            folder = 'blocks' if j['type'].endswith('block') else 'components'
            entries.append({
                'id': f'hf:{j["name"]}', 'source': 'hyperframes', 'kind': folder[:-1],
                'name': j.get('title'), 'summary': j.get('description'), 'tags': j.get('tags', []),
                'controls': [c.get('name') for c in j.get('controls', []) if isinstance(c, dict)],
                'doc': f'https://github.com/heygen-com/hyperframes/tree/main/registry/{folder}/{j["name"]}',
            })
    if mg_root:
        entries += [parse_mg_prompt(path) for path in sorted((mg_root / 'prompts').glob('*.md'))]
    if opus_root:
        entries += [parse_opus_style(d) for d in sorted((opus_root / 'styles').iterdir())
                    if not d.name.startswith('_') and (d / 'style.json').is_file() and (d / 'STYLE.md').is_file()]
    sources = ('gongnyang', 'hyperframes', 'mg-styles-15', 'lemo-opuscar')
    return {'version': 1, 'counts': {s: sum(e['source'] == s for e in entries) for s in sources}, 'entries': entries}


def haystack(e):
    parts = [e['id'], e.get('name') or '', e.get('name_local') or '', e.get('family') or '', e.get('summary') or '',
             e.get('conveys') or '', ' '.join(e.get('tags', [])), ' '.join(e.get('purposes', [])),
             ' '.join(e.get('media', [])), ' '.join(e.get('use_when', []) if isinstance(e.get('use_when'), list) else []),
             ' '.join(e.get('techniques', [])), e.get('route') or '', e.get('style_key') or '']
    return ' '.join(parts).lower()


def expand(term):
    t = term.lower()
    out = {t}
    for zh, words in SYNONYMS.items():
        if zh.lower() == t or (len(t) > 1 and zh in term):
            out.update(w.lower() for w in words)
    return out


def search(index, terms, source=None, kind=None, limit=15):
    groups = [expand(t) for t in terms if t.strip()]
    rows = []
    for e in index['entries']:
        if source and e['source'] != source and not e['id'].startswith(source):
            continue
        if kind and e['kind'] != kind:
            continue
        text = haystack(e)
        tokens = set(TOKEN.findall(text))
        name = ((e.get('name') or '') + ' ' + (e.get('name_local') or '') + ' ' + e['id']).lower()
        purposes = set(e.get('purposes') or [])
        tags = ' '.join(e.get('tags', [])).lower()
        score, matched = 0.0, 0
        for group in groups:
            best, hits = 0.0, 0
            for w in group:
                # Chinese has no spaces: a CJK term of two or more characters matches as a substring.
                if w in tokens or (len(w) > 3 and w in text) or (len(w) > 1 and CJK.match(w) and w in text):
                    hits += 1
                    weight = 3.0 if (w in name or w in purposes) else (2.0 if w in tags else 1.0)
                    best = max(best, weight)
            if best:
                matched += 1
                score += best + min(2.0, 0.5 * (hits - 1))   # several synonyms hit: more specific match
        if matched:
            score += 2.0 * (matched == len(groups))
            rows.append((score, e))
    rows.sort(key=lambda r: (-r[0], r[1]['id']))
    return [{'id': e['id'], 'score': s, 'kind': e['kind'], 'name': e.get('name'), 'family': e.get('family'),
             'purposes': e.get('purposes'), 'summary': (e.get('summary') or '')[:160]} for s, e in rows[:limit]]


SC_RELEASE = 'https://api.github.com/repos/Vincentwei1021/video-shotcraft/releases/tags/gallery-media'
SC_ZIP = 'gallery-media.zip'
MG15_VIDEOS = 'https://api.github.com/repos/Vincentwei1021/mg-styles-15/contents/videos'
SAMPLE_SOURCES = ('shotcraft', 'mg15', 'opus')


def samples_dir():
    return Path(refs_config().get('samples') or refs_dir() / 'samples')


def shotcraft_root():
    try:
        roots = json.loads((SKILL_ROOT / 'backends.local.json').read_text(encoding='utf-8')).get('shotcraft', {}).get('roots', [])
    except (OSError, ValueError):
        roots = []
    for root in [*map(Path, roots), SKILL_ROOT.parent / 'video-shotcraft']:
        if (root / 'gallery' / 'api' / 'library.json').is_file():
            return root
    return None


def shotcraft_previews():
    """Shotcraft style key -> preview file name, from the gallery index (cards[].styles[].media.url)."""
    root = shotcraft_root()
    if not root:
        return {}
    lib = json.loads((root / 'gallery' / 'api' / 'library.json').read_text(encoding='utf-8'))
    out = {}
    for card in lib['cards']:
        for style in card['styles']:
            media = style.get('media')
            url = media.get('url') if isinstance(media, dict) else media
            if url:
                out[style['key']] = url.split('?')[0].rstrip('/').split('/')[-1]
    return out


def urlopen(url, headers=None, timeout=60, tries=3):
    """urlopen with retries: GitHub's CDN now and then fails a TLS handshake or resets a connection."""
    req = urllib.request.Request(url, headers={'User-Agent': 'xumu-motion-index', **(headers or {})})
    for attempt in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt == tries - 1:
                raise
        except OSError:
            if attempt == tries - 1:
                raise
        time.sleep(1 + 2 * attempt)


def api_json(url):
    with urlopen(url, {'Accept': 'application/vnd.github+json'}) as r:
        return json.loads(r.read().decode('utf-8'))


class RemoteFile(io.RawIOBase):
    """Seekable read-only view of a remote file over HTTP Range requests, so zipfile can pull single members
    out of a large archive without downloading the rest."""

    def __init__(self, url):
        with urlopen(url, {'Range': 'bytes=0-0'}) as r:
            total = (r.headers.get('Content-Range') or '').rpartition('/')[2]
            if r.status != 206 or not total.isdigit():
                raise OSError('server does not support range requests')
            self.url, self.size, self.pos = r.geturl(), int(total), 0   # the signed CDN URL after redirects

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: 0, 1: self.pos, 2: self.size}[whence] + offset
        return self.pos

    def readinto(self, buf):
        if self.pos >= self.size or not len(buf):
            return 0
        end = min(self.size, self.pos + len(buf)) - 1
        with urlopen(self.url, {'Range': f'bytes={self.pos}-{end}'}, timeout=120) as r:
            data = r.read()
        buf[:len(data)] = data
        self.pos += len(data)
        return len(data)


def remote_zip(url):
    return zipfile.ZipFile(io.BufferedReader(RemoteFile(url), buffer_size=1 << 20))


def opus_films():
    """Opuscar slug -> (url, bytes, sha256) from the style specs, which pin the films' hashes."""
    out = {}
    for spec in sorted((SKILL_ROOT / 'library' / 'styles').glob('opuscar-*/style.json')):
        g = json.loads(spec.read_text(encoding='utf-8')).get('gallery') or {}
        if g.get('sample_url'):
            out[spec.parent.name[len('opuscar-'):]] = (g['sample_url'], g.get('sample_bytes') or 0, g.get('sample_sha256'))
    return out


def sample_plan(sources, ids=None):
    """What `samples --yes` would download: one row per file. Shotcraft's previews live in a bulk zip on its
    gallery-media release; a few named previews are read out of it one by one, the whole set comes as the zip."""
    rows, base = [], samples_dir()
    if 'shotcraft' in sources:
        previews = shotcraft_previews()
        sc_ids = {i[3:] for i in ids or () if i.startswith('sc:')}
        unknown = sc_ids - set(previews)
        if unknown:
            raise ValueError('unknown Shotcraft style keys: ' + ', '.join(sorted(unknown)))
        wanted = {previews[k] for k in sc_ids} if sc_ids else set(previews.values())
        dest = base / 'shotcraft'
        todo = {n for n in wanted if not (dest / n).is_file()}
        if todo:
            assets = api_json(SC_RELEASE)['assets']
            zipped = next((a for a in assets if a['name'] == SC_ZIP), None)
            # a single file uploaded after the zip replaces the zipped copy; older singles are superseded
            newer = {a['name']: a for a in assets if a['name'] in todo and (not zipped or a['updated_at'] > zipped['updated_at'])}
            single = {a['name']: a for a in assets}
            rest = todo - set(newer)
            if zipped and len(rest) > 20:
                rows.append({'source': 'shotcraft', 'name': SC_ZIP, 'url': zipped['browser_download_url'],
                             'bytes': zipped['size'], 'dest': str(dest), 'zip': True})
            elif zipped:   # a name the zip lacks falls back to its single upload
                # sizes from the zip's own directory (a few small range reads): the zipped previews are newer
                # and larger than the old single uploads
                with remote_zip(zipped['browser_download_url']) as z:
                    inside = {os.path.basename(i.filename): i.file_size for i in z.infolist()}
                rows += [{'source': 'shotcraft', 'name': n, 'url': zipped['browser_download_url'], 'member': n,
                          'single': single[n]['browser_download_url'] if n in single else None,
                          'bytes': inside.get(n) or (single[n]['size'] if n in single else 0), 'dest': str(dest / n)}
                         for n in sorted(rest)]
            else:
                newer.update({a['name']: a for a in assets if a['name'] in rest})
            rows += [{'source': 'shotcraft', 'name': a['name'], 'url': a['browser_download_url'], 'bytes': a['size'],
                      'dest': str(dest / a['name'])} for a in newer.values()]
    if 'mg15' in sources:
        dest = base / 'mg15'
        for f in api_json(MG15_VIDEOS):
            stem = f['name'][:-4]
            if f['name'].endswith('.mp4') and not (dest / f['name']).is_file() and (not ids or f'mg15:{stem}' in ids):
                rows.append({'source': 'mg15', 'name': f['name'], 'url': f['download_url'], 'bytes': f['size'],
                             'dest': str(dest / f['name'])})
    if 'opus' in sources:
        dest = base / 'opus'
        for slug, (url, size, sha) in opus_films().items():
            if not opus_local(slug) and (not ids or f'opus:{slug}' in ids):
                rows.append({'source': 'opus', 'name': f'{slug}.mp4', 'url': url, 'bytes': size, 'sha256': sha,
                             'dest': str(dest / f'{slug}.mp4')})
    return rows


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + '.part')
    with urlopen(url, timeout=300) as r, part.open('wb') as f:
        shutil.copyfileobj(r, f, 1 << 20)
    return part


def fetch_samples(rows):
    import hashlib
    done, failed, archives = [], [], {}
    for row in rows:
        print(f'{row["source"]}: {row["name"]} ({row["bytes"] / 2 ** 20:.1f} MB)', file=sys.stderr, flush=True)
        try:
            if row.get('member'):
                if row['url'] not in archives:
                    archives[row['url']] = remote_zip(row['url'])
                z = archives[row['url']]
                info = next((i for i in z.infolist() if os.path.basename(i.filename) == row['member']), None)
                dest = Path(row['dest'])
                if not info:
                    if row.get('single'):
                        download(row['single'], dest).replace(dest)
                        done.append(row['name'])
                    else:
                        failed.append(f'{row["name"]}: not in {SC_ZIP}')
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                part = dest.with_name(dest.name + '.part')
                with z.open(info) as src, part.open('wb') as out:
                    shutil.copyfileobj(src, out, 1 << 20)
                part.replace(dest)
                done.append(row['name'])
                continue
            if row.get('zip'):
                with tempfile.TemporaryDirectory() as tmp:
                    part = download(row['url'], Path(tmp) / SC_ZIP)
                    dest = Path(row['dest'])
                    dest.mkdir(parents=True, exist_ok=True)
                    with zipfile.ZipFile(part) as z:
                        for info in z.infolist():
                            name = os.path.basename(info.filename)
                            if name.endswith('.mp4'):
                                with z.open(info) as src, (dest / name).open('wb') as out:
                                    shutil.copyfileobj(src, out, 1 << 20)
                done.append(row['name'])
                continue
            dest = Path(row['dest'])
            part = download(row['url'], dest)
            if row.get('sha256') and hashlib.sha256(part.read_bytes()).hexdigest() != row['sha256']:
                part.unlink()
                failed.append(f'{row["name"]}: hash mismatch, discarded')
                continue
            part.replace(dest)
            done.append(row['name'])
        except (OSError, zipfile.BadZipFile) as exc:
            failed.append(f'{row["name"]}: {exc} (network hiccups are common: run the same command again)')
    for z in archives.values():
        z.close()
    return done, failed


def opus_local(slug):
    for p in (samples_dir() / 'opus' / f'{slug}.mp4', media_styles() / f'opuscar-{slug}' / 'sample.mp4' if media_styles() else None):
        if p and p.is_file():
            return p
    return None


def media_styles():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import library_tools
    root = library_tools.media_root()
    return root / 'styles' if root else None


def sample_file(sid, by_id):
    """Local video for a sample id, or (None, why). A plain path to a video file is accepted too."""
    source, _, key = sid.partition(':')
    if source == 'gn':
        e = by_id.get(sid)
        if not e:
            return None, 'unknown gn id'
        return (Path(e['clip']), None) if e.get('clip') and Path(e['clip']).is_file() else (None, 'this effect has no clip')
    if source == 'sc':
        name = shotcraft_previews().get(key)
        if not name:
            return None, 'unknown Shotcraft style key (check gallery/api/library.json styles[].key)'
        p = samples_dir() / 'shotcraft' / name
        return (p, None) if p.is_file() else (None, f'not downloaded: motion_index.py samples --ids {sid} --yes')
    if source == 'mg15':
        if sid not in by_id:
            return None, 'unknown mg15 id'
        p = samples_dir() / 'mg15' / f'{key}.mp4'
        return (p, None) if p.is_file() else (None, f'not downloaded: motion_index.py samples --ids {sid} --yes')
    if source == 'opus':
        if sid not in by_id:
            return None, 'unknown opus id'
        p = opus_local(key)
        return (p, None) if p else (None, f'not downloaded: motion_index.py samples --ids {sid} --yes')
    p = Path(sid)
    return (p, None) if p.is_file() else (None, 'unknown id or missing file')


def probe_duration(path):
    res = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                         capture_output=True, text=True, timeout=60)
    try:
        return float(res.stdout.strip())
    except ValueError:
        return None


def contact_sheet(video, out, n=6, height=240):
    """n frames at the middle of n equal slices (skips the black first frame), tiled in one row."""
    dur = probe_duration(video)
    if not dur:
        raise ValueError(f'cannot read duration: {video}')
    step = dur / n
    # first frame at or after step/2, then each frame at least one step after the last picked one
    pick = f"if(isnan(prev_selected_t),gte(t,{step / 2:.3f}),gte(t-prev_selected_t,{step * 0.98:.3f}))"
    vf = f"select='{pick}',scale=-2:{height},tile={n}x1"
    res = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(video), '-vf', vf,
                          '-frames:v', '1', '-q:v', '3', str(out)], capture_output=True, text=True, timeout=120)
    if res.returncode or not out.is_file():
        raise ValueError(f'ffmpeg failed on {video}: {res.stderr.strip()[-200:]}')
    return [round(step / 2 + k * step, 2) for k in range(n)], round(dur, 2)


def stack_sheets(sheets, out):
    """Several one-row sheets stacked into one image (padded to the widest), so one look covers a shortlist."""
    widths = []
    for s in sheets:
        res = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width',
                              '-of', 'csv=p=0', str(s)], capture_output=True, text=True, timeout=60)
        widths.append(int(res.stdout.strip()))
    w = max(widths) + max(widths) % 2
    args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y']
    for s in sheets:
        args += ['-i', str(s)]
    chain = ''.join(f'[{i}:v]pad={w}:ih:0:0:color=0x202020,pad=iw:ih+8:0:0:color=0x202020[r{i}];' for i in range(len(sheets)))
    chain += ''.join(f'[r{i}]' for i in range(len(sheets))) + f'vstack=inputs={len(sheets)}'
    if len(sheets) == 1:
        chain = f'[0:v]pad={w}:ih:0:0:color=0x202020'
    subprocess.run([*args, '-filter_complex', chain, '-frames:v', '1', '-q:v', '3', str(out)], check=True,
                   capture_output=True, timeout=120)


def frames(index, ids, out_dir, n=6, height=240, per_image=6):
    started = time.monotonic()
    by_id = {e['id']: e for e in index['entries']}
    out_dir.mkdir(parents=True, exist_ok=True)
    sheets, missing = [], []
    for sid in ids:
        video, why = sample_file(sid, by_id)
        if not video:
            missing.append({'id': sid, 'reason': why})
            continue
        sheet = out_dir / (re.sub(r'[^\w.-]+', '_', sid) + '.jpg')
        try:
            times, dur = contact_sheet(video, sheet, n, height)
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            missing.append({'id': sid, 'reason': str(exc)})
            continue
        sheets.append({'id': sid, 'video': str(video), 'duration_s': dur, 'times_s': times, 'sheet': str(sheet)})
    combined = []
    for k in range(0, len(sheets), per_image):
        group = sheets[k:k + per_image]
        target = out_dir / f'refs_sheet_{k // per_image + 1}.jpg'
        stack_sheets([Path(s['sheet']) for s in group], target)
        combined.append({'file': str(target), 'rows': [s['id'] for s in group]})
    return {'sheets': sheets, 'combined': combined, 'missing': missing, 'seconds': round(time.monotonic() - started, 1)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--index', type=Path, help='default: <refs dir>/motion-index.json')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('fetch')
    p.add_argument('--dest', type=Path, help='default: env XUMU_REFS or <skills dir>/_refs')
    p = sub.add_parser('build')
    p.add_argument('--gongnyang', type=Path)
    p.add_argument('--hyperframes', type=Path, help='dir with items/*.json (registry-item metadata)')
    p.add_argument('--mg-styles', type=Path, help='mg-styles-15 checkout (prompts/*.md)')
    p.add_argument('--opuscar', type=Path, help='lemo-opuscar checkout (styles/<slug>/STYLE.md)')
    p.add_argument('--force', action='store_true')
    p = sub.add_parser('search')
    p.add_argument('terms', nargs='+')
    p.add_argument('--source', choices=['gongnyang', 'hyperframes', 'mg-styles-15', 'lemo-opuscar', 'gn', 'gn-recipe', 'hf',
                                        'mg15', 'opus'])
    p.add_argument('--kind', choices=['effect', 'recipe', 'block', 'component', 'style'])
    p.add_argument('--limit', type=int, default=15)
    p = sub.add_parser('show')
    p.add_argument('ids', nargs='+')
    p = sub.add_parser('samples')
    p.add_argument('--source', nargs='+', choices=SAMPLE_SOURCES, help='default: all three')
    p.add_argument('--ids', nargs='+', help='only these sc:/mg15:/opus: samples (a shortlist; Shotcraft previews are '
                                            'read one by one out of its bulk zip)')
    p.add_argument('--yes', action='store_true', help='download; without it only report sizes')
    p = sub.add_parser('frames')
    p.add_argument('ids', nargs='+', help='gn:/sc:/mg15:/opus: ids or a path to a video')
    p.add_argument('--out', type=Path, required=True, help='folder for the sheets, e.g. <edit>/verify/refs')
    p.add_argument('--n', type=int, default=6, help='frames per sample (default 6)')
    p.add_argument('--height', type=int, default=240)
    args = parser.parse_args(argv)
    index_path = args.index or default_index_path()
    try:
        if args.command == 'fetch':
            result = fetch(args.dest or refs_dir())
        elif args.command == 'build':
            default_gn, default_hf, default_mg, default_opus = source_paths()
            gn = args.gongnyang or (default_gn if (default_gn / 'index.json').exists() else None)
            hf = args.hyperframes or (default_hf if (default_hf / 'items').is_dir() else None)
            mg = args.mg_styles or (default_mg if (default_mg / 'prompts').is_dir() else None)
            opus = args.opuscar or (default_opus if (default_opus / 'styles').is_dir() else None)
            if not gn and not hf and not mg and not opus:
                raise ValueError(f'no reference sources under {refs_dir()}; run: motion_index.py fetch')
            index = build(gn, hf, mg, opus)
            with index_path.open('w' if args.force else 'x', encoding='utf-8') as stream:
                json.dump(index, stream, ensure_ascii=False)
            result = {'index': str(index_path), 'counts': index['counts'], 'entries': len(index['entries'])}
        elif args.command == 'samples':
            prefix = {'sc': 'shotcraft', 'mg15': 'mg15', 'opus': 'opus'}
            if args.ids and any(i.split(':')[0] not in prefix for i in args.ids):
                raise ValueError('--ids takes sc:, mg15: or opus: ids (gn clips are already local)')
            sources = args.source or ({prefix[i.split(':')[0]] for i in args.ids} if args.ids else SAMPLE_SOURCES)
            rows = sample_plan(set(sources), set(args.ids or []))
            result = {'dir': str(samples_dir()), 'files': len(rows), 'mb': round(sum(r['bytes'] for r in rows) / 2 ** 20),
                      'by_source': {s: round(sum(r['bytes'] for r in rows if r['source'] == s) / 2 ** 20)
                                    for s in SAMPLE_SOURCES if any(r['source'] == s for r in rows)}}
            if args.yes:
                done, failed = fetch_samples(rows)
                if any(r.get('zip') for r in rows):      # names the bulk zip did not carry
                    rest = sample_plan({'shotcraft'})
                    more, fail2 = fetch_samples(rest)
                    done, failed = done + more, failed + fail2
                result.update(downloaded=len(done), failed=failed)
            else:
                result['next'] = 'add --yes to download'
        else:
            index = json.loads(index_path.read_text(encoding='utf-8'))
            if args.command == 'search':
                source = {'gn': 'gn:', 'gn-recipe': 'gn-recipe:', 'hf': 'hf:', 'mg15': 'mg15:', 'opus': 'opus:'}.get(args.source,
                                                                                                         args.source)
                result = {'results': search(index, args.terms, source, args.kind, args.limit)}
            elif args.command == 'frames':
                result = frames(index, args.ids, args.out, args.n, args.height)
            else:
                by_id = {e['id']: e for e in index['entries']}
                missing = [i for i in args.ids if i not in by_id]
                if missing:
                    raise ValueError(f'unknown ids: {", ".join(missing)}')
                result = {'entries': [by_id[i] for i in args.ids]}
        print(json.dumps({'ok': True, **result}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(json.dumps({'ok': False, 'errors': [str(exc)]}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
