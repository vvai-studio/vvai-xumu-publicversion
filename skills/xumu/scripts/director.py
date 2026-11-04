#!/usr/bin/env python3
"""创作板块的文件工具：三层档案（品牌 / 栏目 / 本片）、创作决策书（编剧页 + 导演页）、合并写入 project.md。

只管结构、校验、渲染与合并；内容判断（脊梁、故事线、风格方向）由总控写进 JSON。
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

SCHEMA_VERSION = 1
MODES = ('full-auto', 'semi', 'pro')
SPINES = ('narration', 'storyline', 'script', 'music', 'order')
FREEDOM = ('L0', 'L1', 'L2', 'L3')
SERIES_ACTIONS = ('reuse', 'new', 'one-off')
STATUSES = ('proposed', 'confirmed', 'edited')
MEDIA_EXT = {'.mp4', '.mov', '.mkv', '.webm', '.m4v', '.mp3', '.wav', '.m4a', '.aac', '.flac',
             '.jpg', '.jpeg', '.png', '.webp', '.heic'}
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}
TEXT_EXT = {'.md', '.txt', '.docx', '.json', '.srt'}

MODE_TEXT = {
    'full-auto': '全托：我只会在故事线、风格方向和前 60 秒参考片三处停下来问你，其余按记录的理由推进；付费、超时渲染、缺素材时另问。说"每步都问我"切到专业，说"默认通过但给我看"切到半托。',
    'semi': '半托：两页都给你看，默认通过，你可以改任何一格；后面在剪辑策略、画面方案、参考片门三处确认。说"你看着办"切到全托，说"每步都问我"切到专业。',
    'pro': '专业：两页都要你逐格确认，后面的每个确认点都停。说"你看着办"切到全托。',
}
# 画面档位（第 7 格 visual_tier）：做多少画面。和托管模式（停下来问几次）是两回事，开工时问用户一句。
VISUAL_TIERS = ('plain', 'light', 'full')
TIER_TEXT = {
    'plain': '素剪：去卡壳、变速、字幕，不加画面',
    'light': '轻包装：标题、章节卡、现成模板与组件，不做定制动画',
    'full': '精做：B-roll、定制 MG、Shotcraft 镜头；画面方案逐镜头写作用、检索与候选，动态镜头先短测',
}

# 决策书的格：编号 → (页, 标题, 必填字段, 可选字段)
GRIDS = {
    '0': ('归属', '归属', ('series_action',), ('series', 'series_confidence')),
    '1': ('编剧页', '有什么', ('inputs',), ('gaps',)),
    '2': ('编剧页', '脊梁', ('spine',), ()),
    '3': ('编剧页', '一句话', ('promise',), ()),
    '4': ('编剧页', '故事线', ('storyline',), ('recipe',)),
    '5': ('编剧页', '删留', ('target_duration',), ('must_keep', 'cut_candidates', 'opener', 'closer')),
    '6': ('导演页', '风格方向', ('style_choice',), ('style_options',)),
    '7': ('导演页', '画面与节奏', ('visual_tier', 'visual_ratio'), ('strong_motion_slots', 'evidence_segments', 'rhythm', 'avatar')),
    '8': ('导演页', '声音', ('narration',), ('music_direction', 'sfx_level', 'live_sound')),
    '9': ('导演页', '预算与自由度', ('freedom', 'mode'), ('paid_items', 'render_estimate_min')),
}

BRAND_TEMPLATE = {
    'schema_version': SCHEMA_VERSION,
    'name': '',
    'creator': {'on_camera': 'corner', 'portrait': '', 'allow_zoom': True},
    'platforms': [],
    'language': 'zh',
    'palette': {'primary': '', 'secondary': '', 'background': ''},
    'typography': {'title': '', 'body': '', 'handwriting': '', 'license': ''},
    'voice': {'kind': 'original', 'name': ''},
    'intro_outro': {'intro': 'none', 'outro': 'none'},
    'forbidden': [],
    'references': [],
}

SERIES_TEMPLATE = {
    'schema_version': SCHEMA_VERSION,
    'key': '',
    'title': '',
    'description': '',
    'content_hint': '',
    'spine': {'kind': 'narration', 'narration': 'original'},
    'audience': {'who': '', 'knowledge': '', 'goal': ''},
    'platforms': [],
    'style': {'main': '', 'assist': '', 'strength': '中', 'avoid': []},
    'edit_policy': {'cut': 'natural', 'opener': '', 'keep_stumbles': False, 'subtitles_by': 'xumu', 'pace': ''},
    'duration': {'target_s': [60, 180], 'hard_max_s': None, 'form': 'short'},
    'visual_ratio': {'person': 0.3, 'real': 0.4, 'animation': 0.3, 'strong_motion': 'opener'},
    'sound': {'music': '', 'sfx': '轻', 'live_sound': False},
    'freedom': 'L1',
    'preset': '',
}

# 合并到 project.md 的项：(标签, 取值路径, 本片格号.字段 或 None)
MERGE_ITEMS = (
    ('栏目', 'series.title', None),
    ('脊梁', 'series.spine.kind', '2.spine.kind'),
    ('一句话', None, '3.promise'),
    ('受众与目的', 'series.audience', None),
    ('平台', 'series.platforms|brand.platforms', None),
    ('主风格', 'series.style.main', '6.style_choice'),
    ('辅助风格', 'series.style.assist', None),
    ('风格强度', 'series.style.strength', None),
    ('避开清单', 'series.style.avoid', None),
    ('剪辑尺度', 'series.edit_policy.cut', None),
    ('目标时长', 'series.duration', '5.target_duration'),
    ('画面档位', None, '7.visual_tier'),
    ('画面比例', 'series.visual_ratio', '7.visual_ratio'),
    ('强动效位置', 'series.visual_ratio.strong_motion', '7.strong_motion_slots'),
    ('旁白', 'brand.voice.kind', '8.narration'),
    ('音乐方向', 'series.sound.music', '8.music_direction'),
    ('自由度', 'series.freedom', '9.freedom'),
    ('托管模式', None, '9.mode'),
    ('人像', 'brand.creator', None),
    ('品牌色', 'brand.palette', None),
    ('字体', 'brand.typography', None),
    ('禁区', 'brand.forbidden', None),
)
BEGIN = '<!-- director:begin -->'
END = '<!-- director:end -->'

# 栏目字段 → 决策书的格字段（change 时两边同步；None 表示只在栏目层）
SERIES_TO_GRID = {
    'spine.kind': '2.spine.kind',
    'spine.narration': '8.narration',
    'style.main': '6.style_choice',
    'duration.target_s': '5.target_duration',
    'visual_ratio': '7.visual_ratio',
    'sound.music': '8.music_direction',
    'sound.sfx': '8.sfx_level',
    'sound.live_sound': '8.live_sound',
    'freedom': '9.freedom',
}
SCOPES = ('one-off', 'series', 'new-series', 'brand')

# 第 7 格的数字人：默认不用。用户自己要（user_asked），或总控建议（suggested，必须写理由）且用户确认了第 7 格，
# avatar_cloud.py 才会生成。
AVATAR_OFF = {'use': False, 'source': '', 'reason': '', 'model': ''}
AVATAR_SOURCES = ('user_asked', 'suggested')

# 决策书之后的确认点：名字 → (显示名, 所在流程)。哪些必须过由托管模式决定。
GATES = {
    'edit-strategy': ('剪辑与旁白策略', '流程 1'),
    'listen': ('剪点试听合集', '流程 2'),
    'visual-plan': ('画面方案', '流程 3'),
    'reference-clip': ('参考片门（前 60～90 秒）', '流程 4'),
    'delivery': ('整片验收', '流程 5'),
}
MODE_GATES = {
    'full-auto': ('reference-clip',),
    'semi': ('edit-strategy', 'visual-plan', 'reference-clip'),
    'pro': tuple(GATES),
}
GATE_STATUS = ('pending', 'passed', 'skipped')
SKIP_MARK = '<!-- director:skip -->'


def today():
    return dt.date.today().isoformat()


def now():
    return dt.datetime.now().replace(microsecond=0).isoformat()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def deep_merge(base, override):
    out = json.loads(json.dumps(base))
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def filled(value):
    """空串、空容器、只含空值的容器都算没填。"""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(filled(v) for v in value.values())
    if isinstance(value, list):
        return any(filled(v) for v in value)
    return True


def get_path(data, dotted):
    cur = data
    for part in dotted.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def set_path(data, dotted, value):
    cur = data
    parts = dotted.split('.')
    for part in parts[:-1]:
        if not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def parse_value(text):
    """`--set k=v` 的 v：能当 JSON 读的就当 JSON（数字、true、列表），否则是字符串。"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def parse_sets(items):
    out = {}
    for item in items or []:
        key, sep, value = item.partition('=')
        if not sep or not key.strip():
            raise SystemExit(f'--set 要写成 字段=值：{item}')
        out[key.strip()] = parse_value(value.strip())
    return out


def slug(text):
    text = re.sub(r'[^0-9A-Za-z一-鿿]+', '-', text.strip()).strip('-').lower()
    return text or 'series'


# ---------------------------------------------------------------- 档案

def channel_dir(workspace):
    return Path(workspace) / 'channel'


def read_channel(channel):
    channel = Path(channel)
    brand_file = channel / 'brand.json'
    if not brand_file.is_file():
        raise SystemExit(f'没有频道档案：{brand_file}。先运行 director.py init --workspace <工作区>')
    brand = load(brand_file)
    series = {}
    for file in sorted((channel / 'series').glob('*.json')):
        series[file.stem] = load(file)
    return brand, series


def log_change(channel, line):
    path = Path(channel) / 'changelog.md'
    if not path.exists():
        path.write_text('# 频道档案改动日志\n\n', encoding='utf-8')
    with path.open('a', encoding='utf-8') as stream:
        stream.write(f'- {today()} {line}\n')


def cmd_init(args):
    channel = channel_dir(args.workspace)
    brand_file = channel / 'brand.json'
    if brand_file.exists() and not args.force:
        raise SystemExit(f'已有频道档案：{brand_file}（加 --force 覆盖品牌层，栏目不动）')
    brand = deep_merge(BRAND_TEMPLATE, load(args.from_json) if args.from_json else {})
    if args.name:
        brand['name'] = args.name
    if args.platform:
        brand['platforms'] = list(args.platform)
    brand['created'] = brand.get('created') or today()
    brand['updated'] = today()
    dump(brand_file, brand)
    (channel / 'series').mkdir(exist_ok=True)
    if not (channel / 'changelog.md').exists():
        (channel / 'changelog.md').write_text('# 频道档案改动日志\n\n', encoding='utf-8')
    log_change(channel, f'建档：品牌层 {brand["name"] or "(未命名)"}')
    missing = [k for k in ('name', 'platforms') if not filled(brand.get(k))]
    print(f'频道档案已建：{channel}')
    if missing:
        print('品牌层还缺：' + '、'.join(missing) + '（可用 --from 答案.json 补，或直接改 brand.json）')
    print('下一步：director.py series add --channel <channel> --key <栏目> --title <显示名>')


def cmd_series(args):
    channel = Path(args.channel)
    if args.series_cmd == 'list':
        _, series = read_channel(channel)
        if not series:
            print('还没有栏目')
        for key, item in series.items():
            print(f'{key}\t{item.get("title", "")}\t脊梁={get_path(item, "spine.kind")}\t主风格={get_path(item, "style.main") or "-"}')
        return
    read_channel(channel)  # 确认品牌层存在
    key = slug(args.key)
    file = channel / 'series' / f'{key}.json'
    if file.exists() and not args.force:
        raise SystemExit(f'栏目已存在：{file}（加 --force 覆盖）')
    base = SERIES_TEMPLATE
    if args.copy_from:
        src = channel / 'series' / f'{slug(args.copy_from)}.json'
        if not src.is_file():
            raise SystemExit(f'要复制的栏目不存在：{src}')
        base = load(src)
    item = deep_merge(base, load(args.from_json) if args.from_json else {})
    item['key'] = key
    item['title'] = args.title or item.get('title') or key
    if args.spine:
        item.setdefault('spine', {})['kind'] = args.spine
    if args.style:
        item.setdefault('style', {})['main'] = args.style
    item['created'] = item.get('created') if not args.copy_from else today()
    item['created'] = item['created'] or today()
    item['updated'] = today()
    dump(file, item)
    log_change(channel, f'新建栏目 {key}（{item["title"]}）' + (f'，复制自 {args.copy_from}' if args.copy_from else ''))
    print(f'栏目已写：{file}')


# ---------------------------------------------------------------- 清点素材

def ffprobe_facts(path):
    if not shutil.which('ffprobe'):
        return None
    try:
        out = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                             capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    try:
        info = json.loads(out.stdout or '{}')
    except json.JSONDecodeError:
        return None
    streams = info.get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), None)
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    facts = {'has_video': video is not None, 'has_audio': audio is not None}
    try:
        facts['duration_s'] = round(float(info.get('format', {}).get('duration')), 2)
    except (TypeError, ValueError):
        facts['duration_s'] = None
    if video:
        facts['width'] = video.get('width')
        facts['height'] = video.get('height')
    return facts


def speech_ratio(path, limit_s=120):
    """用 ffmpeg silencedetect 估算前 limit_s 秒里非静音的比例；没有 ffmpeg 返回 None。"""
    if not shutil.which('ffmpeg'):
        return None
    try:
        out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-t', str(limit_s), '-i', str(path),
                              '-af', 'silencedetect=n=-35dB:d=0.5', '-f', 'null', '-'],
                             capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    silence = sum(float(m) for m in re.findall(r'silence_duration: ([0-9.]+)', out.stderr))
    total = None
    times = re.findall(r'time=(\d+):(\d+):([0-9.]+)', out.stderr)
    if times:
        h, mnt, s = times[-1]
        total = int(h) * 3600 + int(mnt) * 60 + float(s)
    if not total:
        return None
    return round(max(0.0, 1 - silence / total), 2)


def inventory(paths, with_speech=False):
    items = []
    for raw in paths:
        path = Path(raw)
        files = sorted(p for p in path.rglob('*') if p.is_file()) if path.is_dir() else [path]
        for file in files:
            if not file.exists():
                items.append({'path': str(file), 'kind': 'missing', 'note': '文件不存在'})
                continue
            ext = file.suffix.lower()
            if ext in TEXT_EXT:
                item = {'path': str(file), 'kind': 'text', 'bytes': file.stat().st_size}
            elif ext in MEDIA_EXT:
                is_image = ext in IMAGE_EXT
                item = {'path': str(file), 'kind': 'image' if is_image else 'media'}
                facts = ffprobe_facts(file)
                if facts and is_image:
                    # ffprobe 把静态图读成一帧视频：只留尺寸，不带时长与音视频标记
                    for key in ('width', 'height'):
                        if facts.get(key):
                            item[key] = facts[key]
                elif facts:
                    item.update(facts)
                    if facts.get('has_audio') and facts.get('has_video'):
                        item['kind'] = 'video'
                    elif facts.get('has_audio'):
                        item['kind'] = 'audio'
                    elif facts.get('has_video'):
                        item['kind'] = 'video-silent'
                    if with_speech and facts.get('has_audio'):
                        ratio = speech_ratio(file)
                        if ratio is not None:
                            item['speech_ratio'] = ratio
            else:
                continue
            item['summary'] = ''  # 总控看完后填一句话内容
            items.append(item)
    return items


def input_profile(inputs):
    """清点结果 → 有什么：讲话、无声画面、照片、文字。给脊梁判断用。"""
    kinds = [i.get('kind') for i in inputs]
    spoken = [i for i in inputs if i.get('kind') in ('video', 'audio') and (i.get('speech_ratio') is None or i['speech_ratio'] >= 0.3)]
    return {
        'spoken': len(spoken),
        'silent': kinds.count('video-silent') + kinds.count('media'),
        'images': kinds.count('image'),
        'text': kinds.count('text'),
    }


def suggest_spine(profile):
    if profile['spoken'] and not (profile['silent'] + profile['images']) > profile['spoken'] * 3:
        return 'narration', '素材里有讲话，故事线大体已在旁白里'
    if profile['silent'] or profile['images']:
        return 'storyline', '素材以无声画面或照片为主，要先找故事线' + ('；也有讲话段可作旁白' if profile['spoken'] else '')
    if profile['text']:
        return 'script', '只有文字，按文案或剧本做脊梁'
    return '', '没有可清点的素材，脊梁要问用户'


def cmd_inventory(args):
    json_file, _, _ = edit_paths(args.edit)
    doc = load(json_file)
    old = {i.get('path'): i for i in doc['grids']['1'].get('inputs') or []}
    items = inventory(args.inputs, with_speech=args.speech)
    for item in items:
        prev = old.get(item.get('path'))
        if prev and prev.get('summary'):
            item['summary'] = prev['summary']
    doc['grids']['1']['inputs'] = items
    doc['grids']['1']['status'] = 'proposed'
    profile = input_profile(items)
    kind, reason = suggest_spine(profile)
    spine = doc['grids']['2'].setdefault('spine', {})
    if not filled(spine.get('source')):
        spine['kind'] = kind or spine.get('kind', '')
        spine['reason'] = reason
    dump(json_file, doc)
    brand, series_item = channel_for(doc)
    write_md(doc, args.edit, brand, series_item)
    print(f'清点 {len(items)} 项：讲话 {profile["spoken"]}，无声画面 {profile["silent"]}，照片 {profile["images"]}，文字 {profile["text"]}')
    print(f'脊梁建议：{kind or "待定"}（{reason}）')


# ---------------------------------------------------------------- 决策书

def resolve_inherited(brand, series_item, overrides=None):
    """栏目继承品牌：同名字段栏目覆盖，platforms 为空时用品牌的；本片的一次性改动（overrides）盖在最上面。"""
    merged = {'brand': json.loads(json.dumps(brand)), 'series': json.loads(json.dumps(series_item or {}))}
    if series_item and not filled(series_item.get('platforms')):
        merged['series']['platforms'] = brand.get('platforms', [])
    for layer in ('brand', 'series'):
        for path, value in ((overrides or {}).get(layer) or {}).items():
            set_path(merged[layer], path, value)
    return merged


# ---------------------------------------------------------------- 栏目识别

WORD = re.compile(r'[A-Za-z0-9]+|[一-鿿]+')


def tokens(text):
    """英文按词，中文按相邻两字（不分词也能对上"周末出门"和"周末出门拍的"）。"""
    out = set()
    for run_ in WORD.findall(text or ''):
        if run_[0].isascii():
            out.add(run_.lower())
        else:
            out.update(run_[i:i + 2] for i in range(len(run_) - 1))
            if len(run_) == 1:
                out.add(run_)
    return out


def classify(doc, all_series, describe=''):
    """给每个栏目打分：脊梁是否合素材、描述词是否命中。分数和理由都返回，由总控或用户定夺。"""
    profile = input_profile(doc['grids']['1'].get('inputs') or [])
    spine_kind, _ = suggest_spine(profile)
    words = tokens(describe)
    ranked = []
    for key, item in all_series.items():
        score, why = 0, []
        if spine_kind and get_path(item, 'spine.kind') == spine_kind:
            score += 2
            why.append(f'脊梁 {spine_kind} 一致')
        hits = words & tokens(' '.join((item.get('title', ''), item.get('description', ''), item.get('content_hint', ''))))
        if hits:
            score += min(len(hits), 5)
            why.append('描述命中 ' + '、'.join(sorted(hits)[:6]))
        ranked.append({'series': key, 'title': item.get('title', key), 'score': score, 'why': why})
    ranked.sort(key=lambda r: -r['score'])
    if not ranked:
        return 'none', ranked
    top = ranked[0]['score']
    gap = top - (ranked[1]['score'] if len(ranked) > 1 else 0)
    confidence = 'high' if top >= 3 and gap >= 2 else 'medium' if top >= 1 else 'low'
    return confidence, ranked


def cmd_classify(args):
    json_file, _, _ = edit_paths(args.edit)
    doc = load(json_file)
    brand, all_series = read_channel(doc['channel_path'])
    confidence, ranked = classify(doc, all_series, args.describe or '')
    for row in ranked:
        print(f'{row["score"]:>2}  {row["series"]}（{row["title"]}）  ' + ('；'.join(row['why']) or '无依据'))
    print(f'把握：{confidence}')
    if not args.apply:
        return
    g0 = doc['grids']['0']
    if confidence in ('high', 'medium') and ranked:
        g0.update({'series': ranked[0]['series'], 'series_confidence': confidence, 'series_action': 'reuse'})
        doc['series'] = ranked[0]['series']
        doc.setdefault('reasons', []).append(f'归属：{ranked[0]["title"]}，' + ('；'.join(ranked[0]['why']) or '仅一个栏目'))
    else:
        g0.update({'series': None, 'series_confidence': confidence, 'series_action': 'new'})
        doc['series'] = None
        doc.setdefault('reasons', []).append('归属：没有把握匹配已有栏目，建议新建')
    g0['status'] = 'proposed'
    dump(json_file, doc)
    write_md(doc, args.edit, brand, all_series.get(doc['series'] or ''))
    print('已写入第 0 格' + ('（把握不大，请用户点一个或新建）' if confidence in ('low', 'medium') else ''))


# ---------------------------------------------------------------- 改动范围

def apply_to_grid(doc, path, value):
    target = SERIES_TO_GRID.get(path)
    if not target:
        return False
    gid, _, field = target.partition('.')
    set_path(doc['grids'][gid], field, value)
    doc['grids'][gid]['status'] = 'edited'
    return True


def cmd_change(args):
    json_file, _, _ = edit_paths(args.edit)
    doc = load(json_file)
    sets = parse_sets(args.set)
    if not sets:
        raise SystemExit('给至少一个 --set 字段=值')
    channel = Path(doc['channel_path'])
    brand, all_series = read_channel(channel)
    layer = 'brand' if args.scope == 'brand' or args.layer == 'brand' else 'series'
    reason = f'（{args.reason}）' if args.reason else ''
    film = Path(args.edit).resolve().parent.name
    if args.scope == 'one-off':
        overrides = doc.setdefault('overrides', {}).setdefault(layer, {})
        for path, value in sets.items():
            overrides[path] = value
            if layer == 'series':
                apply_to_grid(doc, path, value)
        print(f'只这一期：{layer} 层 {", ".join(sets)} 改在本片，档案不动')
    elif args.scope == 'brand':
        for path, value in sets.items():
            old = get_path(brand, path)
            set_path(brand, path, value)
            log_change(channel, f'品牌层 {path}：{one_line(old)} → {one_line(value)}{reason}，由 {film} 触发')
            doc.setdefault('overrides', {}).get('brand', {}).pop(path, None)
        brand['updated'] = today()
        dump(channel / 'brand.json', brand)
        print(f'品牌层已改：{", ".join(sets)}。影响以后所有栏目的片子。')
    else:
        if layer == 'brand':
            raise SystemExit('品牌层只有 one-off / brand 两个范围')
        key = doc.get('series')
        if not key or key not in all_series:
            raise SystemExit('本片还没归属栏目，先 classify --apply 或 confirm --series-action')
        item = all_series[key]
        if args.scope == 'new-series':
            if not args.new_key:
                raise SystemExit('new-series 要给 --new-key')
            new_key = slug(args.new_key)
            if (channel / 'series' / f'{new_key}.json').exists():
                raise SystemExit(f'栏目已存在：{new_key}')
            item = json.loads(json.dumps(item))
            item['key'] = new_key
            item['title'] = args.title or new_key
            item['created'] = today()
            log_change(channel, f'新建栏目 {new_key}（{item["title"]}），复制自 {key}{reason}，由 {film} 触发')
            key = new_key
            doc['series'] = key
            doc['grids']['0'].update({'series': key, 'series_action': 'new', 'status': 'edited'})
        for path, value in sets.items():
            old = get_path(item, path)
            set_path(item, path, value)
            apply_to_grid(doc, path, value)
            doc.setdefault('overrides', {}).get('series', {}).pop(path, None)
            log_change(channel, f'栏目 {key} {path}：{one_line(old)} → {one_line(value)}{reason}，由 {film} 触发')
        item['updated'] = today()
        dump(channel / 'series' / f'{key}.json', item)
        all_series[key] = item
        print(f'栏目 {key} 已改：{", ".join(sets)}。以后这个栏目的片子都这样。')
    doc['version'] = int(doc.get('version', 1)) + 1
    dump(json_file, doc)
    write_md(doc, args.edit, brand, all_series.get(doc.get('series') or ''))


# ---------------------------------------------------------------- 确认点

def gate_table(doc):
    required = MODE_GATES.get(doc.get('mode'), MODE_GATES['semi'])
    passed = doc.get('gates') or {}
    rows = []
    for name, (title, stage) in GATES.items():
        state = passed.get(name, {})
        rows.append({'gate': name, 'title': title, 'stage': stage,
                     'required': name in required,
                     'status': state.get('status', 'pending'), 'at': state.get('at', ''), 'note': state.get('note', '')})
    return rows


def gates_open(doc):
    """还没过的必过确认点。"""
    return [r['gate'] for r in gate_table(doc) if r['required'] and r['status'] == 'pending']


def cmd_gates(args):
    json_file, _, _ = edit_paths(args.edit)
    doc = load(json_file)
    mode = doc.get('mode')
    print(f'模式 {mode}：{MODE_TEXT.get(mode, "")}')
    for row in gate_table(doc):
        flag = '必过' if row['required'] else '不必'
        mark = {'pending': '○', 'passed': '✓', 'skipped': '–'}[row['status']]
        extra = f'  {row["at"]} {row["note"]}'.rstrip() if row['status'] != 'pending' else ''
        print(f'{mark} {row["gate"]:<15} {row["title"]}（{row["stage"]}）  {flag}{extra}')
    left = gates_open(doc)
    print('还要过：' + ('、'.join(left) if left else '无'))


def cmd_gate(args):
    json_file, _, _ = edit_paths(args.edit)
    doc = load(json_file)
    if args.gate not in GATES:
        raise SystemExit(f'没有这个确认点：{args.gate}。可选：{", ".join(GATES)}')
    if args.gate_cmd == 'skip' and not args.note:
        raise SystemExit('跳过必须给 --note 说明理由（例如"沿用已确认风格的续作"）')
    doc.setdefault('gates', {})[args.gate] = {
        'status': 'passed' if args.gate_cmd == 'pass' else 'skipped',
        'at': now(), 'note': args.note or '',
    }
    doc.setdefault('reasons', []).append(f'确认点 {args.gate}：{"通过" if args.gate_cmd == "pass" else "跳过"}' + (f'，{args.note}' if args.note else ''))
    dump(json_file, doc)
    brand, series_item = channel_for(doc)
    write_md(doc, args.edit, brand, series_item)
    left = gates_open(doc)
    print(f'{args.gate} 已{"通过" if args.gate_cmd == "pass" else "跳过"}。还要过：' + ('、'.join(left) if left else '无'))


# ---------------------------------------------------------------- 旧项目迁移

def legacy_profile(project_text):
    """从旧 project.md 取"制作定位"一节的原文和能拆出的 键：值 行。"""
    lines = project_text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith('#') and '制作定位' in l), None)
    if start is None:
        return '', {}
    body = []
    for line in lines[start + 1:]:
        if line.startswith('## ') or line.startswith('# '):
            break
        body.append(line)
    text = '\n'.join(body).strip()
    hints = {}
    for raw in body:
        line = raw.strip().strip('-*|').strip()
        if not line or line.startswith('|---'):
            continue
        cells = [c.strip() for c in line.split('|') if c.strip()]
        if len(cells) >= 2 and '：' not in cells[0] and ':' not in cells[0]:
            hints.setdefault(cells[0].strip('*'), cells[1])
            continue
        for sep in ('：', ':'):
            if sep in line:
                key, value = line.split(sep, 1)
                key = key.strip().strip('*')
                if key and value.strip():
                    hints.setdefault(key, value.strip())
                break
    return text, hints


def cmd_migrate(args):
    json_file, _, project_file = edit_paths(args.edit)
    if not project_file.exists():
        raise SystemExit(f'没有旧项目记录：{project_file}')
    text = project_file.read_text(encoding='utf-8')
    if args.skip:
        if SKIP_MARK not in text:
            project_file.write_text(SKIP_MARK + '\n' + text, encoding='utf-8')
        print('已记下：这个项目按本片层处理，下次不再问要不要建档')
        return
    if json_file.exists() and not args.force:
        raise SystemExit(f'已有决策书：{json_file}，不需要迁移（重做加 --force）')
    if SKIP_MARK in text and not args.force:
        raise SystemExit('用户之前说过这个项目不建档；要改主意加 --force')
    brand, all_series = read_channel(args.channel)
    series_item = all_series.get(slug(args.series)) if args.series else None
    if args.series and series_item is None:
        raise SystemExit(f'栏目不存在：{args.series}')
    legacy_text, hints = legacy_profile(text)
    doc = {
        'schema_version': SCHEMA_VERSION, 'name': '创作决策书', 'version': 1,
        'created': now(), 'confirmed_at': None,
        'channel_path': str(Path(args.channel).resolve()),
        'series': series_item.get('key') if series_item else None,
        'mode': 'semi',
        'grids': blank_grids(brand, series_item, 'semi'),
        'reasons': ['从旧 project.md 的制作定位迁移，各格待总控按原文填、用户再确认一次'],
        'migrated': {'from': str(project_file), 'at': now(), 'profile_text': legacy_text, 'hints': hints},
    }
    if not series_item:
        doc['grids']['0'].update({'series': None, 'series_confidence': 'none', 'series_action': 'new'})
    dump(json_file, doc)
    write_md(doc, args.edit, brand, series_item)
    print(f'已从旧项目生成决策书草稿：{json_file}（标 migrated）')
    print(f'制作定位原文 {len(legacy_text)} 字，拆出 {len(hints)} 条：' + '；'.join(f'{k}={v[:20]}' for k, v in list(hints.items())[:8]))
    print('下一步：按原文填各格（update --from），给用户确认；栏目没定时先 classify 或 series add')


# ---------------------------------------------------------------- 照着这个做

def cmd_reference(args):
    json_file, _, _ = edit_paths(args.edit)
    doc = load(json_file)
    ref = args.ref
    is_url = '://' in ref
    if not is_url and not Path(ref).exists():
        raise SystemExit(f'参考不存在：{ref}')
    key = args.style_key or 'reference'
    option = {'key': key, 'ref': ref, 'frame': '', 'sample': ref if not is_url else '', 'diff': '用户给的参考，直接照做'}
    g6 = doc['grids']['6']
    g6.update({'style_options': [option], 'style_choice': key, 'status': 'proposed'})
    if args.notes:
        g6['style_notes'] = args.notes
    doc.setdefault('reasons', []).append(f'风格方向：用户给了参考 {ref}，不走推荐')
    doc['version'] = int(doc.get('version', 1)) + 1
    dump(json_file, doc)
    assets_file = Path(args.edit) / 'assets.json'
    assets = load(assets_file) if assets_file.exists() else {'sources': []}
    assets.setdefault('sources', []).append({'kind': 'style-reference', 'ref': ref, 'use': '只学画面语言、结构与节奏参数，不复制素材、字体与音乐', 'added': today()})
    dump(assets_file, assets)
    brand, series_item = channel_for(doc)
    write_md(doc, args.edit, brand, series_item)
    print(f'第 6 格已指向参考：{ref}（style_choice={key}）。拆解特征走学习模式；确认后用 change 决定是否存为栏目默认。')


def blank_grids(brand, series_item, mode):
    g = {k: {'status': 'proposed'} for k in GRIDS}
    g['0'].update({'series': series_item.get('key') if series_item else None,
                   'series_confidence': 'high' if series_item else 'none',
                   'series_action': 'reuse' if series_item else 'new'})
    g['1'].update({'inputs': [], 'gaps': []})
    spine = (series_item or {}).get('spine', {})
    g['2'].update({'spine': {'kind': spine.get('kind', ''), 'source': '', 'reason': ''}})
    g['3'].update({'promise': ''})
    g['4'].update({'storyline': []})
    dur = (series_item or {}).get('duration', {})
    g['5'].update({'must_keep': [], 'cut_candidates': [], 'opener': '', 'closer': '',
                   'target_duration': dur.get('target_s')})
    style = (series_item or {}).get('style', {})
    g['6'].update({'style_options': [], 'style_choice': style.get('main', '')})
    g['7'].update({'visual_tier': '', 'visual_ratio': (series_item or {}).get('visual_ratio'), 'strong_motion_slots': [],
                   'evidence_segments': [], 'rhythm': '', 'avatar': dict(AVATAR_OFF)})
    voice = brand.get('voice', {})
    sound = (series_item or {}).get('sound', {})
    g['8'].update({'narration': spine.get('narration') or voice.get('kind', ''), 'music_direction': sound.get('music', ''),
                   'sfx_level': sound.get('sfx', ''), 'live_sound': sound.get('live_sound', False)})
    g['9'].update({'paid_items': [], 'render_estimate_min': None,
                   'freedom': (series_item or {}).get('freedom', 'L1'), 'mode': mode})
    return g


def avatar_allowed(doc):
    """(ok, why) for generating a digital human in this project: grid 7 says use it and the user has confirmed grid 7."""
    g7 = (doc.get('grids') or {}).get('7') or {}
    av = g7.get('avatar') or {}
    if not av.get('use'):
        return False, '创作决策书第 7 格没有选用数字人：用户要数字人，或总控认为适合时，先在第 7 格写 avatar（use、source、reason）给用户确认'
    if av.get('source') not in AVATAR_SOURCES or not filled(av.get('reason')):
        return False, '第 7 格的 avatar 要写清 source（user_asked / suggested）和 reason'
    if g7.get('status') not in ('confirmed', 'edited'):
        return False, f'第 7 格（含数字人建议：{av.get("reason")}）还没经用户确认：确认后再生成'
    return True, f'{"用户要求" if av["source"] == "user_asked" else "决策书建议、用户已确认"}：{av["reason"]}'


def edit_paths(edit):
    edit = Path(edit)
    return edit / 'director.json', edit / '创作决策书.md', edit / 'project.md'


def cmd_propose(args):
    json_file, _, _ = edit_paths(args.edit)
    if json_file.exists() and not args.force:
        raise SystemExit(f'已有决策书：{json_file}（改内容用 --from，重来加 --force）')
    brand, all_series = read_channel(args.channel)
    series_item = None
    if args.series:
        series_item = all_series.get(slug(args.series))
        if series_item is None:
            raise SystemExit(f'栏目不存在：{args.series}。可用：{", ".join(all_series) or "(无)"}')
    elif len(all_series) == 1 and not args.no_default_series:
        series_item = next(iter(all_series.values()))
    mode = args.mode or ('full-auto' if args.first_time else 'semi')
    doc = {
        'schema_version': SCHEMA_VERSION,
        'name': '创作决策书',
        'version': 1,
        'created': now(),
        'confirmed_at': None,
        'channel_path': str(Path(args.channel).resolve()),
        'series': series_item.get('key') if series_item else None,
        'mode': mode,
        'grids': blank_grids(brand, series_item, mode),
        'reasons': [],
    }
    if args.tier:
        doc['grids']['7']['visual_tier'] = args.tier
    if args.inputs:
        doc['grids']['1']['inputs'] = inventory(args.inputs)
        if not series_item:
            kind, reason = suggest_spine(input_profile(doc['grids']['1']['inputs']))
            doc['grids']['2']['spine'].update({'kind': kind, 'reason': reason})
    if args.from_json:
        doc = apply_draft(doc, load(args.from_json))
    dump(json_file, doc)
    md = write_md(doc, args.edit, brand, series_item)
    print(f'决策书草稿已写：{json_file}')
    print(f'渲染：{md}')
    print('下一步：总控把编剧页与导演页的判断写成只含要改字段的 JSON，director.py update --from <内容.json>，再 confirm / merge')


def apply_draft(doc, draft):
    """把总控写的内容合进决策书：grids 按格深合并，顶层 mode/series/reasons 直接覆盖。"""
    for key in ('mode', 'series', 'reasons'):
        if key in draft:
            doc[key] = draft[key]
    for gid, content in (draft.get('grids') or {}).items():
        gid = str(gid)
        if gid not in GRIDS:
            raise SystemExit(f'没有第 {gid} 格')
        doc['grids'][gid] = deep_merge(doc['grids'][gid], content)
    if 'mode' in draft:
        doc['grids']['9']['mode'] = draft['mode']
    return doc


def cmd_update(args):
    json_file, _, _ = edit_paths(args.edit)
    doc = load(json_file)
    doc = apply_draft(doc, load(args.from_json))
    doc['version'] = int(doc.get('version', 1)) + 1
    dump(json_file, doc)
    brand, series_item = channel_for(doc)
    print(f'决策书已更新到 v{doc["version"]}：{json_file}')
    print(f'渲染：{write_md(doc, args.edit, brand, series_item)}')


def channel_for(doc):
    brand, all_series = read_channel(doc['channel_path'])
    return brand, all_series.get(doc.get('series') or '')


def fmt(value, indent=0):
    pad = '  ' * indent
    if value is None or value == '' or value == []:
        return pad + '（待填）'
    if isinstance(value, bool):
        return pad + ('是' if value else '否')
    if isinstance(value, (int, float, str)):
        return pad + str(value)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                head = item.get('id') or item.get('path') or item.get('key') or item.get('item') or ''
                rest = {k: v for k, v in item.items() if k not in ('id', 'path', 'key', 'item', 'status')}
                desc = '，'.join(f'{k}: {fmt(v).strip()}' for k, v in rest.items() if filled(v))
                lines.append(f'{pad}- {head}{"：" if head and desc else ""}{desc}')
            else:
                lines.append(f'{pad}- {fmt(item).strip()}')
        return '\n'.join(lines)
    if isinstance(value, dict):
        return '\n'.join(f'{pad}- {k}: {fmt(v).strip()}' for k, v in value.items())
    return pad + str(value)


STATUS_TEXT = {'proposed': '建议', 'confirmed': '已确认', 'edited': '已改'}


def render(doc, brand=None, series_item=None):
    lines = [f'# {doc.get("name", "创作决策书")} v{doc.get("version", 1)}', '']
    mode = doc.get('mode', 'semi')
    lines.append(f'> **当前模式** {MODE_TEXT.get(mode, mode)}')
    tier = (doc.get('grids', {}).get('7') or {}).get('visual_tier')
    lines.append(f'> **画面档位** {TIER_TEXT.get(tier, "还没定：开工问一句“只剪出来，还是要做画面包装？”")}')
    if brand is not None:
        lines.append(f'> 频道：{brand.get("name") or "(未命名)"}' + (f' · 栏目：{series_item.get("title")}（{series_item.get("key")}）' if series_item else ' · 栏目：未归属'))
    lines.append(f'> 生成 {doc.get("created", "")}' + (f' · 确认 {doc["confirmed_at"]}' if doc.get('confirmed_at') else ' · 未确认'))
    lines.append('')
    current_page = None
    for gid, (page, title, required, optional) in GRIDS.items():
        grid = doc['grids'].get(gid, {})
        if page != current_page:
            lines += [f'## {page}', '']
            current_page = page
        lines.append(f'### {gid}. {title}  ·  {STATUS_TEXT.get(grid.get("status"), grid.get("status"))}')
        lines.append('')
        for field in required + optional:
            if field == 'status':
                continue
            value = grid.get(field)
            mark = '' if field in optional or filled(value) else ' **（必填）**'
            rendered = fmt(value, 1)
            if '\n' in rendered or rendered.lstrip().startswith('-'):
                lines.append(f'- **{field}**{mark}')
                lines.append(rendered)
            else:
                lines.append(f'- **{field}**{mark}：{rendered.strip()}')
        lines.append('')
    lines += ['## 决策书之后的确认点', '']
    for row in gate_table(doc):
        mark = {'pending': '○', 'passed': '✓', 'skipped': '–'}[row['status']]
        lines.append(f'- {mark} {row["title"]}（{row["stage"]}）：' + ('必过' if row['required'] else '本模式不必') + (f'，{row["status"]} {row["at"]} {row["note"]}'.rstrip() if row['status'] != 'pending' else ''))
    lines.append('')
    if doc.get('migrated'):
        lines += ['## 迁移自旧项目', '', f'来源：{doc["migrated"].get("from", "")}', '', '```text', doc['migrated'].get('profile_text', ''), '```', '']
    if doc.get('reasons'):
        lines += ['## 理由记录', ''] + [f'- {r}' for r in doc['reasons']] + ['']
    lines.append('> 唯一事实源是 director.json；本文件由 director.py render 生成，改内容请改 JSON 再渲染。')
    return lines


def write_md(doc, edit, brand=None, series_item=None):
    _, md_file, _ = edit_paths(edit)
    md_file.write_text('\n'.join(render(doc, brand, series_item)) + '\n', encoding='utf-8')
    return md_file


def cmd_render(args):
    json_file, _, _ = edit_paths(args.edit)
    doc = load(json_file)
    brand, series_item = channel_for(doc)
    print(f'渲染：{write_md(doc, args.edit, brand, series_item)}')


def validate(doc, ready=False):
    errors = []
    if doc.get('schema_version') != SCHEMA_VERSION:
        errors.append('schema_version 不对')
    if doc.get('mode') not in MODES:
        errors.append(f'mode 必须是 {MODES}')
    grids = doc.get('grids', {})
    for gid, (page, title, required, _) in GRIDS.items():
        grid = grids.get(gid)
        if grid is None:
            errors.append(f'缺第 {gid} 格（{title}）')
            continue
        if grid.get('status') not in STATUSES:
            errors.append(f'第 {gid} 格 status 必须是 {STATUSES}')
        if ready:
            for field in required:
                if not filled(grid.get(field)):
                    errors.append(f'第 {gid} 格（{title}）缺 {field}')
            if grid.get('status') == 'proposed':
                errors.append(f'第 {gid} 格（{title}）还没确认')
    g0 = grids.get('0', {})
    if g0.get('series_action') not in SERIES_ACTIONS:
        errors.append(f'第 0 格 series_action 必须是 {SERIES_ACTIONS}')
    spine = (grids.get('2') or {}).get('spine') or {}
    if ready and spine.get('kind') not in SPINES:
        errors.append(f'第 2 格 spine.kind 必须是 {SPINES}')
    g9 = grids.get('9', {})
    if g9.get('freedom') not in FREEDOM:
        errors.append(f'第 9 格 freedom 必须是 {FREEDOM}')
    if g9.get('mode') != doc.get('mode'):
        errors.append('第 9 格 mode 与顶层 mode 不一致')
    tier = (grids.get('7') or {}).get('visual_tier')
    if filled(tier) and tier not in VISUAL_TIERS:
        errors.append(f'第 7 格 visual_tier 必须是 {VISUAL_TIERS}（素剪 / 轻包装 / 精做）')
    av = (grids.get('7') or {}).get('avatar') or {}
    if av.get('use'):
        if av.get('source') not in AVATAR_SOURCES:
            errors.append(f'第 7 格 avatar.source 必须是 {AVATAR_SOURCES}（用户要的，还是总控建议的）')
        if not filled(av.get('reason')):
            errors.append('第 7 格用数字人要写 avatar.reason：为什么这条片子适合数字人出镜')
    if ready:
        for seg in (grids.get('4') or {}).get('storyline') or []:
            if not filled(seg.get('id')) or not filled(seg.get('goal')):
                errors.append(f'故事线每段都要 id 和 goal：{seg}')
    return errors


def cmd_check(args):
    json_file, _, _ = edit_paths(args.edit)
    errors = validate(load(json_file), args.ready)
    for err in errors:
        print('✗ ' + err)
    if errors:
        raise SystemExit(1)
    print('✓ 决策书结构正确' + ('，可以合并' if args.ready else ''))


def cmd_confirm(args):
    json_file, _, _ = edit_paths(args.edit)
    doc = load(json_file)
    targets = list(GRIDS) if args.all else [g.strip() for g in (args.grids or '').split(',') if g.strip()]
    if not targets:
        raise SystemExit('给 --all 或 --grids 0,3,6')
    for gid in targets:
        if gid not in GRIDS:
            raise SystemExit(f'没有第 {gid} 格')
        doc['grids'][gid]['status'] = 'edited' if args.edited else 'confirmed'
    if args.mode:
        doc['mode'] = args.mode
        doc['grids']['9']['mode'] = args.mode
    if args.series_action:
        doc['grids']['0']['series_action'] = args.series_action
    if all(g.get('status') != 'proposed' for g in doc['grids'].values()):
        doc['confirmed_at'] = now()
    dump(json_file, doc)
    brand, series_item = channel_for(doc)
    write_md(doc, args.edit, brand, series_item)
    print(f'已确认第 {", ".join(targets)} 格' + ('；整份决策书已确认' if doc.get('confirmed_at') else ''))


# ---------------------------------------------------------------- 合并到 project.md

LAYER_TEXT = {'film': '本片', 'series': '栏目', 'brand': '品牌', 'none': '待定'}


def overridden(overrides, option):
    """option 形如 series.style.main；本片一次性改动里有这条（或它的上级 / 下级）就算改过。"""
    layer, _, path = option.partition('.')
    for key in ((overrides or {}).get(layer) or {}):
        if key == path or key.startswith(path + '.') or path.startswith(key + '.'):
            return True
    return False


def resolve_items(doc, brand, series_item):
    layers = resolve_inherited(brand, series_item, doc.get('overrides'))
    rows = []
    for label, inherited_path, film_path in MERGE_ITEMS:
        inherited, inherited_layer, status = None, 'none', ''
        for option in (inherited_path or '').split('|'):
            candidate = get_path(layers, option) if option else None
            if filled(candidate):
                inherited, inherited_layer = candidate, option.split('.')[0]
                if overridden(doc.get('overrides'), option):
                    inherited_layer, status = 'film', STATUS_TEXT['edited']
                break
        value, layer = inherited, inherited_layer
        if film_path:
            gid, _, field = film_path.partition('.')
            grid = doc['grids'].get(gid, {})
            candidate = get_path(grid, field)
            if filled(candidate):
                status = STATUS_TEXT.get(grid.get('status'), '')
                # 和继承值一样的，仍算继承，只带上本片的确认状态
                value, layer = candidate, ('film' if candidate != inherited else inherited_layer)
        rows.append((label, value, layer, status))
    return rows


def one_line(value):
    if isinstance(value, dict):
        return '；'.join(f'{k} {one_line(v)}' for k, v in value.items() if filled(v)) or '待定'
    if isinstance(value, list):
        return '、'.join(one_line(v) for v in value) or '待定'
    if isinstance(value, bool):
        return '是' if value else '否'
    if value is None or value == '':
        return '待定'
    return str(value).replace('\n', ' ').replace('|', '/')


def merged_section(doc, brand, series_item):
    lines = [BEGIN, '',
             f'当前模式 {MODE_TEXT.get(doc.get("mode"), doc.get("mode"))}', '',
             f'决策书：`director.json` v{doc.get("version", 1)}' + ('（已确认 ' + doc['confirmed_at'] + '）' if doc.get('confirmed_at') else '（未全部确认）'),
             '', '| 项 | 值 | 来自 | 状态 |', '|---|---|---|---|']
    for label, value, layer, status in resolve_items(doc, brand, series_item):
        lines.append(f'| {label} | {one_line(value)} | {LAYER_TEXT[layer]} | {status or ("继承" if layer in ("series", "brand") else "")} |')
    # 本片格里是继承值时也写明，免得读者以为是本期特意定的
    g4 = doc['grids'].get('4', {}).get('storyline') or []
    if g4:
        lines += ['', '故事线：'] + [f'- {seg.get("id", "")} {seg.get("beat", "")}：{seg.get("goal", "")}' for seg in g4]
    g1 = doc['grids'].get('1', {}).get('gaps') or []
    if g1:
        lines += ['', '缺口：'] + [f'- {one_line(g)}' for g in g1]
    gates = [f'{ {"pending": "○", "passed": "✓", "skipped": "–"}[r["status"]] } {r["title"]}' for r in gate_table(doc) if r['required']]
    lines += ['', '确认点：' + '；'.join(gates)]
    lines += ['', END]
    return '\n'.join(lines)


def cmd_merge(args):
    json_file, _, project_file = edit_paths(args.edit)
    doc = load(json_file)
    errors = validate(doc, ready=not args.draft)
    if errors:
        for err in errors:
            print('✗ ' + err)
        raise SystemExit('决策书还不能合并（草稿先看一眼可加 --draft）')
    brand, series_item = channel_for(doc)
    section = merged_section(doc, brand, series_item)
    project_file = Path(args.project) if args.project else project_file
    heading = '## 制作定位'
    if project_file.exists():
        text = project_file.read_text(encoding='utf-8')
        if BEGIN in text and END in text:
            text = text[:text.index(BEGIN)] + section + text[text.index(END) + len(END):]
        elif heading in text:
            idx = text.index(heading) + len(heading)
            text = text[:idx] + '\n\n' + section + '\n' + text[idx:]
        else:
            text = text.rstrip('\n') + f'\n\n{heading}\n\n{section}\n'
    else:
        text = f'# {Path(args.edit).resolve().parent.name}\n\n{heading}\n\n{section}\n'
    project_file.write_text(text, encoding='utf-8')
    print(f'制作定位已写入：{project_file}')


# ---------------------------------------------------------------- CLI

def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('init', help='建频道档案（品牌层）')
    p.add_argument('--workspace', required=True)
    p.add_argument('--name')
    p.add_argument('--platform', action='append')
    p.add_argument('--from', dest='from_json', help='答案 JSON，按品牌层字段')
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_init)

    p = sub.add_parser('series', help='栏目层')
    s = p.add_subparsers(dest='series_cmd', required=True)
    a = s.add_parser('add')
    a.add_argument('--channel', required=True)
    a.add_argument('--key', required=True)
    a.add_argument('--title')
    a.add_argument('--spine', choices=SPINES)
    a.add_argument('--style', help='主风格 key')
    a.add_argument('--copy-from', help='复制已有栏目再改')
    a.add_argument('--from', dest='from_json')
    a.add_argument('--force', action='store_true')
    ls = s.add_parser('list')
    ls.add_argument('--channel', required=True)
    p.set_defaults(func=cmd_series)

    p = sub.add_parser('propose', help='生成决策书草稿（继承档案 + 清点素材）')
    p.add_argument('--edit', required=True)
    p.add_argument('--channel', required=True)
    p.add_argument('--series')
    p.add_argument('--no-default-series', action='store_true', help='只有一个栏目时也不自动归属')
    p.add_argument('--inputs', nargs='*', help='素材文件或目录')
    p.add_argument('--mode', choices=MODES)
    p.add_argument('--first-time', action='store_true', help='新手首次：默认全托')
    p.add_argument('--tier', choices=VISUAL_TIERS, help='画面档位：plain 素剪 / light 轻包装 / full 精做')
    p.add_argument('--from', dest='from_json', help='总控写好的内容，按 grids 合并')
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_propose)

    p = sub.add_parser('inventory', help='重新清点素材写进第 1 格，并给脊梁建议')
    p.add_argument('--edit', required=True)
    p.add_argument('--inputs', nargs='+', required=True)
    p.add_argument('--speech', action='store_true', help='用 ffmpeg 静音检测估每条素材的非静音比例（有配乐时偏高，只是粗判）')
    p.set_defaults(func=cmd_inventory)

    p = sub.add_parser('classify', help='按素材与描述给栏目打分；--apply 写进第 0 格')
    p.add_argument('--edit', required=True)
    p.add_argument('--describe', help='用户对这期的一句话描述')
    p.add_argument('--apply', action='store_true')
    p.set_defaults(func=cmd_classify)

    p = sub.add_parser('change', help='改栏目级或品牌级字段，先定范围')
    p.add_argument('--edit', required=True)
    p.add_argument('--scope', choices=SCOPES, required=True, help='one-off 只这一期 / series 以后都这样 / new-series 新开栏目 / brand 改品牌层')
    p.add_argument('--layer', choices=('series', 'brand'), default='series')
    p.add_argument('--set', action='append', help='字段=值，如 style.main=chalkboard 或 duration.target_s=[60,90]')
    p.add_argument('--new-key', help='new-series 的栏目 key')
    p.add_argument('--title', help='new-series 的显示名')
    p.add_argument('--reason', help='用户原话或理由，写进日志')
    p.set_defaults(func=cmd_change)

    p = sub.add_parser('reference', help='"照着这个做"：参考直接成为第 6 格唯一方向')
    p.add_argument('--edit', required=True)
    p.add_argument('--ref', required=True, help='链接或本地文件')
    p.add_argument('--style-key', help='最接近的风格目录 key')
    p.add_argument('--notes', help='与目录风格的差异')
    p.set_defaults(func=cmd_reference)

    p = sub.add_parser('gates', help='按托管模式列出决策书之后要过的确认点')
    p.add_argument('--edit', required=True)
    p.set_defaults(func=cmd_gates)

    p = sub.add_parser('gate', help='记录一个确认点通过或跳过')
    g = p.add_subparsers(dest='gate_cmd', required=True)
    for name, help_text in (('pass', '用户确认通过'), ('skip', '按规则跳过（必须 --note）')):
        gp = g.add_parser(name, help=help_text)
        gp.add_argument('gate', choices=tuple(GATES))
        gp.add_argument('--edit', required=True)
        gp.add_argument('--note')
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser('migrate', help='旧项目：从 project.md 的制作定位生成决策书草稿')
    p.add_argument('--edit', required=True)
    p.add_argument('--channel', help='频道档案目录；--skip 时不需要')
    p.add_argument('--series', help='归到哪个栏目')
    p.add_argument('--skip', action='store_true', help='用户说不建档：记下来，下次不再问')
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_migrate)

    p = sub.add_parser('update', help='把总控写的内容合进决策书并重渲')
    p.add_argument('--edit', required=True)
    p.add_argument('--from', dest='from_json', required=True)
    p.set_defaults(func=cmd_update)

    p = sub.add_parser('render', help='JSON → 创作决策书.md')
    p.add_argument('--edit', required=True)
    p.set_defaults(func=cmd_render)

    p = sub.add_parser('check', help='结构校验；--ready 要求全部确认且必填齐')
    p.add_argument('--edit', required=True)
    p.add_argument('--ready', action='store_true')
    p.set_defaults(func=cmd_check)

    p = sub.add_parser('confirm', help='记录用户确认')
    p.add_argument('--edit', required=True)
    p.add_argument('--all', action='store_true')
    p.add_argument('--grids', help='逗号分隔的格号，如 0,4,6')
    p.add_argument('--edited', action='store_true', help='标为用户改过而不是原样确认')
    p.add_argument('--mode', choices=MODES)
    p.add_argument('--series-action', choices=SERIES_ACTIONS)
    p.set_defaults(func=cmd_confirm)

    p = sub.add_parser('merge', help='三层合并，写 project.md 的制作定位')
    p.add_argument('--edit', required=True)
    p.add_argument('--project', help='默认 <edit>/project.md')
    p.add_argument('--draft', action='store_true', help='未确认也先写一版草稿')
    p.set_defaults(func=cmd_merge)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
