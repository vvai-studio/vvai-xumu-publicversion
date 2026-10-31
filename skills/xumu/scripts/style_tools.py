#!/usr/bin/env python3
"""风格规范与合规检查。

  sync-catalog   从 references/style-catalog.md 生成或补齐 library/styles/<key>/style.json（已有的不覆盖）
  list / show    看有哪些规范、某条写了什么
  set            改规范里的字段（例如补色板）：set whiteboard-world spec.palette='["#ffffff","#2b2b2b"]'
  check          按决策书的自由度与主风格检查 visual-plan.json；可选对渲染静帧做色板比对；报告写进 verify/

规范是"锁住什么"的清单：时序与可读性、风格标志动作、禁用项锁死；色板、字体、插画这些放开给频道档案。
分数之外的判断（像不像这种风格）仍靠看帧。
"""
import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys

SKILL = Path(__file__).resolve().parent.parent
CATALOG = SKILL / 'references' / 'style-catalog.md'
STYLES = SKILL / 'library' / 'styles'
TEMPLATES = SKILL / 'assets' / 'templates'
STRENGTH = {'克制': 0, '中': 1, '强': 2}
FREEDOM = ('L0', 'L1', 'L2', 'L3')
CUSTOM_SHARE_L2 = 0.2
# 大类 → 默认动作档位上限（规范里可改）
FAMILY_STRENGTH = {'A': '中', 'B': '中', 'C': '中', 'D': '强', 'E': '中', 'F': '强', 'G': '强', 'H': '中', 'I': '强', 'J': '中', 'K': '中'}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


# ---------------------------------------------------------------- 目录 → 规范

def parse_catalog(text):
    """每一行 `| `key` 名 **标签** | 观感 | 标志动作 | 适合内容 | 实现 |` → dict；组合方式只有两列。"""
    family, rows = '', []
    for line in text.splitlines():
        m = re.match(r'^## ([A-Z])\. (.+)$', line.strip())
        if m:
            family = f'{m.group(1)}. {m.group(2)}'
            continue
        if not line.startswith('| `'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        head = cells[0]
        key = re.search(r'`([^`]+)`', head).group(1)
        tags = re.findall(r'\*\*(.+?)\*\*', head)
        name = re.sub(r'`[^`]+`', '', head)
        name = re.sub(r'\*\*.+?\*\*', '', name)
        name = re.sub(r'（\[.*?\]\(.*?\)）|\(\[.*?\]\(.*?\)\)', '', name).strip(' ·')
        row = {'key': key, 'name': name, 'family': family, 'tags': [t.strip(' ·') for t in tags]}
        if len(cells) >= 5:
            row.update({'kind': 'style', 'look': cells[1], 'signature': cells[2], 'fits': cells[3], 'implementation': cells[4]})
        else:
            row.update({'kind': 'combo', 'look': '', 'signature': '', 'fits': '', 'implementation': cells[1] if len(cells) > 1 else ''})
        rows.append(row)
    return rows


def spec_from_row(row):
    impl = row.get('implementation', '')
    reference = re.findall(r'(?:mg15|opus):[\w-]+', impl)
    components = re.findall(r'(?:gn|hf|gn-recipe):[\w-]+', impl)
    template = TEMPLATES / row['key']
    letter = row['family'][:1]
    moves = [s.strip() for s in re.split(r'[；;，,]', row.get('signature', '')) if s.strip()]
    return {
        'schema_version': 1,
        'key': row['key'], 'name': row['name'], 'family': row['family'], 'kind': row['kind'],
        'look': row.get('look', ''), 'signature': row.get('signature', ''), 'fits': row.get('fits', ''),
        'implementation': impl, 'tags': row['tags'],
        'template': str(template.relative_to(SKILL)).replace('\\', '/') if template.is_dir() else None,
        'reference': reference[0] if reference else None,
        'needs_assets': '需素材' in row['tags'] or '需素材' in impl,
        'components': components,
        'spec': {
            'palette': [],
            'fonts': {'title': '', 'body': '', 'handwriting': ''},
            'strength_max': FAMILY_STRENGTH.get(letter, '中'),
            'max_chars_per_s': 4.0,
            'min_dwell_s': 1.2,
            'signature_moves': moves,
            'forbidden': [],
            'notes': '',
        },
        'gallery': {'frame': '', 'sample': '', 'frame_kind': ''},
        'verified_in': [],
    }


def cmd_sync(args):
    catalog = Path(args.catalog) if args.catalog else CATALOG
    out = Path(args.out) if args.out else STYLES
    rows = parse_catalog(catalog.read_text(encoding='utf-8'))
    created, updated, kept = [], [], []
    for row in rows:
        file = out / row['key'] / 'style.json'
        fresh = spec_from_row(row)
        if file.exists() and not args.force:
            current = load(file)
            changed = False
            # 目录文字变了就跟着更新描述性字段；spec / gallery / verified_in 是人填的，不动
            for field in ('name', 'family', 'look', 'signature', 'fits', 'implementation', 'tags', 'template', 'reference', 'needs_assets', 'components'):
                if current.get(field) != fresh[field]:
                    current[field] = fresh[field]
                    changed = True
            # 标志动作从目录拆出来，也跟着目录走；想自己写就加 spec.signature_moves_custom=true
            if not current.get('spec', {}).get('signature_moves_custom') and current.get('spec', {}).get('signature_moves') != fresh['spec']['signature_moves']:
                current.setdefault('spec', {})['signature_moves'] = fresh['spec']['signature_moves']
                changed = True
            if changed:
                dump(file, current)
                updated.append(row['key'])
            else:
                kept.append(row['key'])
        else:
            dump(file, fresh)
            created.append(row['key'])
    print(f'{len(rows)} 条：新建 {len(created)}，更新描述 {len(updated)}，不变 {len(kept)}；目录 {out}')
    if created:
        print('新建：' + ' '.join(created))


def all_specs(root=None):
    root = Path(root) if root else STYLES
    return {p.parent.name: load(p) for p in sorted(root.glob('*/style.json'))}


def cmd_list(args):
    specs = all_specs(args.root)
    for key, s in specs.items():
        marks = []
        if s.get('template'):
            marks.append('模板')
        if s.get('reference'):
            marks.append('参考片')
        if s['spec'].get('palette'):
            marks.append('色板')
        if s.get('gallery', {}).get('frame'):
            marks.append('代表帧')
        print(f'{key:<22} {s["family"][:1]} {s["name"]:<14} {"、".join(marks)}')
    print(f'{len(specs)} 条')


def cmd_show(args):
    s = all_specs(args.root).get(args.key)
    if not s:
        raise SystemExit(f'没有这条规范：{args.key}')
    print(json.dumps(s, ensure_ascii=False, indent=2))


def parse_value(text):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def cmd_set(args):
    root = Path(args.root) if args.root else STYLES
    file = root / args.key / 'style.json'
    if not file.exists():
        raise SystemExit(f'没有这条规范：{file}')
    s = load(file)
    for item in args.set:
        path, sep, value = item.partition('=')
        if not sep:
            raise SystemExit(f'--set 要写成 字段=值：{item}')
        cur = s
        parts = path.strip().split('.')
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = parse_value(value.strip())
    dump(file, s)
    print(f'{args.key} 已改：{", ".join(i.split("=")[0] for i in args.set)}')


# ---------------------------------------------------------------- 检查

def have_numpy():
    try:
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


def hex_rgb(value):
    v = value.lstrip('#')
    if len(v) == 3:
        v = ''.join(c * 2 for c in v)
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def frame_palette_share(image, palette, tolerance=60.0):
    """静帧里离色板任一色不超过 tolerance（RGB 欧氏距离）的像素比例；近白近黑算中性不计。"""
    import numpy as np
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(image), '-vf', 'scale=64:36', '-f', 'rawvideo',
                          '-pix_fmt', 'rgb24', '-'], capture_output=True, timeout=60)
    raw = np.frombuffer(out.stdout, dtype=np.uint8)
    if raw.size < 3:
        return None
    px = raw[:raw.size // 3 * 3].reshape(-1, 3).astype(np.float32)
    luma = px.mean(axis=1)
    neutral = (luma > 235) | (luma < 20)
    colored = px[~neutral]
    if colored.shape[0] == 0:
        return 1.0
    pal = np.array([hex_rgb(c) for c in palette], dtype=np.float32)
    d = np.sqrt(((colored[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)).min(axis=1)
    return round(float((d <= tolerance).mean()), 3)


def shot_is_custom(shot, specs):
    """没有模板也没有参考片源码的 mg、3D、外部生成，都算定制。"""
    route = shot.get('route')
    if route in ('three', 'external'):
        return True
    if route in ('mg', 'illustration'):
        spec = specs.get(shot.get('style', ''))
        return not (spec and (spec.get('template') or spec.get('reference')))
    return False


def check_plan(plan, specs, freedom, main_style, assist_style=None, forbidden=(), fps=None):
    errors, warnings = [], []
    shots = plan.get('shots', [])
    fps = fps or plan.get('timeline', {}).get('fps', 30)
    allowed_styles = {s for s in (main_style, assist_style) if s}
    main_spec = specs.get(main_style or '', {})
    spec = main_spec.get('spec', {})
    if main_style and not main_spec:
        warnings.append(f'主风格 {main_style} 没有规范文件，先 style_tools.py sync-catalog')
    custom = []
    for shot in shots:
        sid = shot.get('id', '?')
        style = shot.get('style')
        route = shot.get('route')
        if style and allowed_styles and style not in allowed_styles and shot.get('role') != 'overlay':
            errors.append(f'{sid}: 风格 {style} 不在主风格 / 辅助风格里（{"、".join(sorted(allowed_styles))}）')
        is_custom = shot_is_custom(shot, specs)
        if is_custom:
            custom.append(sid)
        if freedom == 'L0':
            if route in ('mg', 'illustration') and not (specs.get(style or '', {}).get('template')):
                errors.append(f'{sid}: L0 只能用有模板的风格做 {route}，{style or "(无风格)"} 没有模板')
            elif route in ('three', 'external'):
                errors.append(f'{sid}: L0 不允许 {route}')
        elif freedom == 'L1' and is_custom:
            errors.append(f'{sid}: L1 不允许从零定制（{route}，{style or "(无风格)"} 既无模板也无参考片源码）')
        text = ' '.join(str(shot.get(k, '')) for k in ('purpose', 'screen_text', 'quote')) + ' ' + json.dumps(shot.get('props', {}), ensure_ascii=False)
        for word in forbidden:
            if word and word in text:
                errors.append(f'{sid}: 出现禁用项"{word}"')
        screen = str(shot.get('screen_text') or '')
        chars = len(re.sub(r'\s', '', screen))
        seconds = (shot.get('duration_frames') or 0) / fps
        if chars and seconds > 0:
            rate = chars / seconds
            if rate > spec.get('max_chars_per_s', 4.0):
                warnings.append(f'{sid}: 屏幕文字 {chars} 字在 {seconds:.1f} 秒内，{rate:.1f} 字/秒 超过 {spec.get("max_chars_per_s", 4.0)}')
            if seconds < spec.get('min_dwell_s', 1.2):
                warnings.append(f'{sid}: 带文字的镜头只有 {seconds:.1f} 秒，短于最短停留 {spec.get("min_dwell_s", 1.2)}')
        strength = (shot.get('props') or {}).get('strength') or shot.get('motion')
        if strength in STRENGTH and STRENGTH[strength] > STRENGTH.get(spec.get('strength_max', '强'), 2):
            warnings.append(f'{sid}: 动作档位 {strength} 超过 {main_style} 的上限 {spec.get("strength_max")}')
    if freedom == 'L2' and shots:
        limit = math.ceil(len(shots) * CUSTOM_SHARE_L2)
        if len(custom) > limit:
            errors.append(f'L2 定制镜头 {len(custom)} 个超过两成（{len(shots)} 个镜头最多 {limit}）：{", ".join(custom)}')
    return errors, warnings, custom


def cmd_check(args):
    edit = Path(args.edit) if args.edit else None
    specs = all_specs(args.root)
    freedom, main_style, assist, forbidden = args.freedom, args.style, args.assist, list(args.forbid or [])
    if edit and (edit / 'director.json').exists():
        doc = load(edit / 'director.json')
        freedom = freedom or doc['grids']['9'].get('freedom')
        main_style = main_style or doc['grids']['6'].get('style_choice')
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import director
            brand, series_item = director.channel_for(doc)
            layers = director.resolve_inherited(brand, series_item, doc.get('overrides'))
            assist = assist or layers['series'].get('style', {}).get('assist')
            forbidden += list(layers['series'].get('style', {}).get('avoid') or []) + list(layers['brand'].get('forbidden') or [])
        except (SystemExit, OSError, KeyError):
            pass
    freedom = freedom or 'L1'
    if freedom not in FREEDOM:
        raise SystemExit(f'自由度必须是 {FREEDOM}')
    plan_path = Path(args.plan) if args.plan else (edit / 'visual-plan.json' if edit else None)
    if not plan_path or not plan_path.exists():
        raise SystemExit('给 --plan，或 --edit 下要有 visual-plan.json')
    plan = load(plan_path)
    forbidden = [w for w in dict.fromkeys(forbidden) if w]
    errors, warnings, custom = check_plan(plan, specs, freedom, main_style, assist, forbidden)
    frames = []
    palette = specs.get(main_style or '', {}).get('spec', {}).get('palette') or []
    if args.frames:
        if not palette:
            warnings.append(f'{main_style} 的规范还没填色板，跳过静帧比对')
        elif not shutil.which('ffmpeg'):
            warnings.append('没有 ffmpeg，跳过静帧比对')
        elif not have_numpy():
            warnings.append('没有 numpy，跳过静帧比对（setup_env.py 会装）')
        else:
            for img in sorted(Path(args.frames).rglob('*')):
                if img.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
                    continue
                share = frame_palette_share(img, palette)
                frames.append({'frame': str(img), 'palette_share': share})
                if share is not None and share < args.palette_min:
                    warnings.append(f'{img.name}: 只有 {share:.0%} 的有色像素在色板附近（下限 {args.palette_min:.0%}）')
    report = {'freedom': freedom, 'main_style': main_style, 'assist_style': assist, 'forbidden': forbidden,
              'shots': len(plan.get('shots', [])), 'custom_shots': custom,
              'errors': errors, 'warnings': warnings, 'frames': frames, 'ok': not errors and not (args.strict and warnings)}
    if edit:
        verify = edit / 'verify'
        verify.mkdir(exist_ok=True)
        dump(verify / 'style-check.json', report)
        lines = [f'# 风格合规检查', '', f'自由度 {freedom} · 主风格 {main_style or "(未定)"}' + (f' · 辅助 {assist}' if assist else ''),
                 f'镜头 {report["shots"]} 个，定制 {len(custom)} 个' + (f'：{", ".join(custom)}' if custom else ''), '']
        lines += ['## 不通过', ''] + ([f'- {e}' for e in errors] or ['- 无']) + ['', '## 提醒', ''] + ([f'- {w}' for w in warnings] or ['- 无']) + ['']
        if frames:
            lines += ['## 静帧色板', ''] + [f'- {Path(f["frame"]).name}: {f["palette_share"]}' for f in frames] + ['']
        (verify / 'style-check.md').write_text('\n'.join(lines), encoding='utf-8')
    for e in errors:
        print('✗ ' + e)
    for w in warnings:
        print('! ' + w)
    print(f'自由度 {freedom}，主风格 {main_style or "(未定)"}，{report["shots"]} 个镜头，定制 {len(custom)} 个' + ('，通过' if report['ok'] else '，不通过'))
    if not report['ok']:
        raise SystemExit(1)


# ---------------------------------------------------------------- 参考片库：媒体目录

def media_root(explicit=None):
    """代表帧、样片、参考片媒体的根目录：--media > XUMU_LIBRARY_MEDIA > backends.local.json learning.media_root。"""
    if explicit:
        return Path(explicit)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import library_tools
    root = library_tools.media_root()
    if root is None:
        raise SystemExit('没有媒体目录：给 --media，或设 XUMU_LIBRARY_MEDIA / backends.local.json 的 learning.media_root')
    return root


def tokens(text):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import director
    return director.tokens(text)


def frame_path(spec, media=None):
    """gallery.frame 的绝对路径：assets/ 开头的随 Skill 发布（示意帧小图），其余在媒体目录（真帧、参考片）。"""
    frame = (spec.get('gallery') or {}).get('frame') or ''
    if not frame:
        return ''
    if frame.startswith('assets/'):
        return str(SKILL / frame)
    return str(Path(media) / frame) if media else frame


# ---------------------------------------------------------------- 推荐

def recently_replaced(changelog):
    """频道日志里最近被换掉的风格（style.main：A → B 的 A），推荐时往后排。"""
    path = Path(changelog) if changelog else None
    if not path or not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding='utf-8').splitlines()[-30:]:
        m = re.search(r'style\.main：([\w-]+) → ([\w-]+)', line)
        if m:
            out.add(m.group(1))
    return out


def recommend(specs, query, tone=None, n=3, avoid=(), replaced=(), media=None):
    """按内容描述与语气给出 n 个拉开差别的风格：不同大类、有图优先。返回带分数与理由的列表。"""
    words = tokens(query)
    tone_level = STRENGTH.get(tone) if tone else None
    ranked = []
    for key, s in specs.items():
        if s.get('kind') == 'combo' or key in avoid:
            continue
        hits = words & tokens(' '.join((s.get('name', ''), s.get('fits', ''), s.get('look', ''))))
        score, why = min(len(hits), 6), []
        if hits:
            why.append('匹配 ' + '、'.join(sorted(hits)[:5]))
        if tone_level is not None:
            smax = STRENGTH.get(s.get('spec', {}).get('strength_max', '中'), 1)
            if smax <= tone_level:
                score += 1
            else:
                score -= 2
                why.append(f'动作上限 {s["spec"].get("strength_max")} 比要的 {tone} 强')
        if s.get('template'):
            score += 2; why.append('有模板')
        elif s.get('reference'):
            score += 1; why.append('有参考片')
        if s.get('gallery', {}).get('frame'):
            score += 1
        if key in replaced:
            score -= 3; why.append('最近刚换掉')
        ranked.append({'key': key, 'name': s.get('name', key), 'family': s.get('family', ''), 'score': score, 'why': why,
                       'frame': frame_path(s, media),
                       'frame_kind': s.get('gallery', {}).get('frame_kind', ''),
                       'sample': s.get('gallery', {}).get('sample') or s.get('gallery', {}).get('sample_url', '')})
    ranked.sort(key=lambda r: (-r['score'], r['key']))
    picks, families = [], set()
    for r in ranked:
        if r['family'] in families:
            continue
        picks.append(r)
        families.add(r['family'])
        if len(picks) >= n:
            break
    return picks, ranked


def cmd_recommend(args):
    specs = all_specs(args.root)
    query = ' '.join(filter(None, [args.query, args.content, args.platform]))
    avoid, replaced, media = set(args.avoid or []), set(), None
    doc = None
    if args.edit and (Path(args.edit) / 'director.json').exists():
        doc = load(Path(args.edit) / 'director.json')
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import director
            brand, series_item = director.channel_for(doc)
            if series_item:
                query += ' ' + ' '.join((series_item.get('title', ''), series_item.get('description', ''), series_item.get('content_hint', '')))
                avoid |= set(series_item.get('style', {}).get('avoid') or [])
            replaced = recently_replaced(Path(doc['channel_path']) / 'changelog.md')
            query += ' ' + (doc['grids']['3'].get('promise') or '')
        except (SystemExit, OSError, KeyError):
            pass
    try:
        media = media_root(args.media)
    except SystemExit:
        media = None
    picks, ranked = recommend(specs, query, args.tone, args.n, avoid, replaced, media)
    if not picks:
        raise SystemExit('没有可推荐的风格；先 sync-catalog')
    for r in picks:
        print(f'{r["score"]:>2}  {r["key"]:<20} {r["name"]}（{r["family"]}）  ' + ('；'.join(r['why']) or '—')
              + (f'\n    代表帧 {r["frame"]}' + (f'（{r["frame_kind"]}）' if r['frame_kind'] else '') if r['frame'] else '\n    代表帧：无，首次使用现场渲染一张效果草稿'))
    if args.json:
        print(json.dumps(picks, ensure_ascii=False, indent=2))
    if args.apply and doc is not None:
        options = [{'key': r['key'], 'frame': r['frame'], 'sample': r['sample'], 'diff': f'{r["name"]}：{r["why"][0] if r["why"] else ""}'} for r in picks]
        doc['grids']['6'].update({'style_options': options, 'status': 'proposed'})
        if not doc['grids']['6'].get('style_choice'):
            doc['grids']['6']['style_choice'] = ''
        doc.setdefault('reasons', []).append('风格方向：按内容与语气推荐 ' + '、'.join(r['key'] for r in picks))
        dump(Path(args.edit) / 'director.json', doc)
        import director
        brand, series_item = director.channel_for(doc)
        director.write_md(doc, args.edit, brand, series_item)
        print('已写入决策书第 6 格（三个方向，待用户点一个）')


# ---------------------------------------------------------------- 学习：参考片 → 特征、关键帧、样片

def dominant_colors(path, n=6, step=32):
    """每秒一帧缩到 64×36（静帧直接缩），按 step 量化后数最多的颜色；返回十六进制列表（含白黑，白底风格要靠它）。"""
    import numpy as np
    still = Path(path).suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp')
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-an', '-vf', 'scale=64:36' if still else 'fps=1,scale=64:36',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, timeout=600)
    raw = np.frombuffer(out.stdout, dtype=np.uint8)
    if raw.size < 3:
        return []
    px = raw[:raw.size // 3 * 3].reshape(-1, 3)
    q = (px // step) * step + step // 2
    keys, counts = np.unique(q, axis=0, return_counts=True)
    order = np.argsort(-counts)
    total = counts.sum()
    colors = []
    for i in order[:n]:
        if counts[i] / total < 0.02:
            break
        r, g, b = (int(v) for v in keys[i])
        colors.append('#%02x%02x%02x' % (min(r, 255), min(g, 255), min(b, 255)))
    return colors


def cmd_learn(args):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import footage
    footage.need('ffmpeg'); footage.need('ffprobe')
    src = Path(args.ref)
    if not src.is_file():
        raise SystemExit(f'参考片不存在：{src}')
    root = Path(args.root) if args.root else STYLES
    key = args.key
    spec_file = root / key / 'style.json'
    if not spec_file.exists():
        if not args.title:
            raise SystemExit(f'{key} 不是目录里的风格；新风格要给 --title，并先在 style-catalog.md 加条目')
        spec = {'schema_version': 1, 'key': key, 'name': args.title, 'family': 'X. 用户新增', 'kind': 'style',
                'look': '', 'signature': '', 'fits': '', 'implementation': '', 'tags': ['用户新增'], 'template': None,
                'reference': None, 'needs_assets': False, 'components': [],
                'spec': {'palette': [], 'fonts': {'title': '', 'body': '', 'handwriting': ''}, 'strength_max': '中',
                         'max_chars_per_s': 4.0, 'min_dwell_s': 1.2, 'signature_moves': [], 'forbidden': [], 'notes': ''},
                'gallery': {'frame': '', 'sample': '', 'frame_kind': ''}, 'verified_in': []}
    else:
        spec = load(spec_file)
    media = media_root(args.media)
    refs_dir = media / 'styles' / key / 'refs'
    refs_dir.mkdir(parents=True, exist_ok=True)
    index_file = media / 'styles' / key / 'refs.json'
    index = load(index_file) if index_file.exists() else {'key': key, 'refs': []}
    n = len(index['refs']) + 1
    out_dir = refs_dir / f'{n:02d}'
    out_dir.mkdir(exist_ok=True)
    info = footage.probe(src) or {}
    duration = info.get('duration') or 0
    cuts = footage.scene_cuts(src, args.scene)
    metrics = footage.frame_metrics(footage.gray_frames(src))
    import numpy as np
    motion = float(np.mean(metrics['motion'][1:])) if len(metrics['motion']) > 1 else 0.0
    luma = float(np.mean(metrics['luma'])) if metrics['luma'] else 0.0
    cuts_per_min = round(len(cuts) / duration * 60, 1) if duration else 0.0
    strength = '强' if cuts_per_min >= 30 or motion >= 8 else '克制' if cuts_per_min <= 8 and motion < 3 else '中'
    palette = dominant_colors(src)
    keyframes = []
    for k in range(args.keyframes):
        t = duration * (k + 0.5) / args.keyframes
        kf = out_dir / f'kf_{k + 1:02d}.jpg'
        footage.run(['ffmpeg', '-hide_banner', '-nostats', '-y', '-ss', f'{t:.3f}', '-i', str(src), '-frames:v', '1', '-vf', 'scale=640:-2', str(kf)], timeout=120)
        if kf.exists():
            keyframes.append(str(kf.relative_to(media)).replace('\\', '/'))
    sample = out_dir / 'sample.mp4'
    start = max(0.0, duration / 2 - 5)
    footage.run(['ffmpeg', '-hide_banner', '-nostats', '-y', '-ss', f'{start:.3f}', '-t', '10', '-i', str(src), '-vf', 'scale=-2:540',
                 '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-an', str(sample)], timeout=600)
    entry = {'n': n, 'source': args.source or str(src), 'note': args.note or '', 'duration_s': round(duration, 1),
             'cuts_per_min': cuts_per_min, 'motion_mean': round(motion, 2), 'luma_mean': round(luma, 1),
             'strength_hint': strength, 'palette': palette, 'keyframes': keyframes,
             'sample': str(sample.relative_to(media)).replace('\\', '/') if sample.exists() else '',
             'license': '只学画面语言、结构与节奏参数；不复制素材、字体与音乐', 'added': __import__('datetime').date.today().isoformat()}
    dump(out_dir / 'meta.json', entry)
    index['refs'].append(entry)
    dump(index_file, index)
    changed = []
    if not spec['spec'].get('palette') and palette:
        spec['spec']['palette'] = palette
        spec['spec']['palette_status'] = 'draft'
        changed.append('色板（draft）')
    if not spec.get('gallery', {}).get('frame') and keyframes:
        mid = keyframes[len(keyframes) // 2]
        spec['gallery'] = {'frame': mid, 'sample': entry['sample'], 'frame_kind': 'reference'}
        changed.append('代表帧（reference，仅本机）')
    spec['learned'] = {'refs': n, 'cuts_per_min': cuts_per_min, 'motion_mean': round(motion, 2), 'strength_hint': strength}
    dump(spec_file, spec)
    print(f'{key} 第 {n} 份参考：{duration:.0f}s，{len(cuts)} 个切点（{cuts_per_min}/分钟），运动 {motion:.1f}，亮度 {luma:.0f} → 动作档位提示 {strength}')
    print(f'色板 {" ".join(palette) or "无"}；关键帧 {len(keyframes)} 张，样片 {"有" if sample.exists() else "无"}；存 {out_dir}')
    print('规范更新：' + ('、'.join(changed) if changed else '无（已有色板与代表帧）') + '；特征存 refs.json，不进仓库')


# ---------------------------------------------------------------- 画廊：示意帧、索引页

def concept_prompt(spec, aspect):
    orient = '竖屏 9:16' if aspect == '9:16' else '横屏 16:9'
    return (f'一支{spec["name"]}风格解说视频的一帧截图，{orient}。画面观感：{spec.get("look") or spec["name"]}。'
            f'正在发生的动作：{spec.get("signature") or "画面元素按节奏登场"}。内容示意：{spec.get("fits") or "知识讲解"}。'
            '像真实的视频成片截图，有少量中文标题文字"示例"，构图完整，无水印、无 logo、不出现真实品牌、不画人脸特写。')


def cmd_gallery(args):
    specs_root = Path(args.root) if args.root else STYLES
    specs = all_specs(specs_root)
    media = media_root(args.media)
    if args.gallery_cmd == 'html':
        write_gallery_html(specs, media, Path(args.out) if args.out else media / 'styles' / 'index.html')
        return
    if args.gallery_cmd == 'pack':
        cmd_gallery_pack(specs_root, specs, media)
        return
    if args.gallery_cmd == 'sample':
        cmd_gallery_sample(specs_root, specs, media, args.keys, args.yes)
        return
    if args.gallery_cmd == 'set':
        s = specs.get(args.key)
        if not s:
            raise SystemExit(f'没有这条规范：{args.key}')
        s['gallery'] = {'frame': args.frame, 'sample': args.sample or s.get('gallery', {}).get('sample', ''), 'frame_kind': args.kind}
        dump(specs_root / args.key / 'style.json', s)
        print(f'{args.key} 代表帧 → {args.frame}（{args.kind}）')
        return
    keys = [k for k in (args.keys or specs) if specs.get(k, {}).get('kind') != 'combo']
    if not args.force:
        keys = [k for k in keys if not specs[k].get('gallery', {}).get('frame')]
    if not keys:
        print('没有要生成的：都已有代表帧（--force 重做）')
        return
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import audio_cloud as ac
    import image_cloud
    cfg = ac.load_config()
    icfg = dict(ac.load_config(section='image'))
    over = {'resolution': args.resolution, 'quality': args.quality}
    gen_dir = media / 'styles' / '_generated'
    gen_dir.mkdir(parents=True, exist_ok=True)
    if args.gallery_cmd == 'estimate':
        try:
            prov, model = image_cloud.provider(cfg, icfg)
            b = ac.budget(cfg)
            params = image_cloud.image_params(icfg, concept_prompt(specs[keys[0]], args.aspect), args.aspect, 1, [], over)
            q = image_cloud.quote(prov, model, params, b, b['confirm_over'], 1)
        except ac.Refused as e:
            raise SystemExit(str(e))
        print(ac.quote_text(q), end='')
        print(f'共 {len(keys)} 张：' + ' '.join(keys))
        return
    done, failed, total_cost = [], [], 0.0
    workers = max(1, int(args.jobs or ac.budget(cfg)['concurrency']))

    def one(key):
        # 每个风格自己的 edit 目录：计费日志互不打架，重跑时各自复用
        spec = specs[key]
        quiet = []
        try:
            res = image_cloud.generate(cfg, icfg, str(gen_dir / key), key, concept_prompt(spec, args.aspect), args.aspect, 1, [], over,
                                       False, args.confirmed, args.max_cost, out=quiet.append)
        except ac.Refused as e:
            return key, None, str(e)
        files = res.get('files') or []
        if not files:
            return key, None, '\n'.join(quiet)
        src = gen_dir / key / 'images' / files[0]
        dst_dir = media / 'styles' / key
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f'concept{src.suffix}'
        shutil.copyfile(src, dst)
        packed = pack_frame(src, key)
        spec['gallery'] = {'frame': packed or str(dst.relative_to(media)).replace('\\', '/'),
                           'sample': spec.get('gallery', {}).get('sample', ''), 'frame_kind': 'concept',
                           'original': str(dst.relative_to(media)).replace('\\', '/')}
        dump(specs_root / key / 'style.json', spec)
        return key, res, '\n'.join(quiet)

    from concurrent.futures import ThreadPoolExecutor, as_completed
    print(f'{len(keys)} 张，{workers} 路并发')
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, key): key for key in keys}
        for fut in as_completed(futures):
            key, res, text = fut.result()
            if res is None:
                failed.append(key)
                print(f'✗ {key}：{text.strip().splitlines()[0] if text.strip() else "没出图"}')
                continue
            try:
                total_cost += float(res.get('cost') or 0)
            except (TypeError, ValueError):
                pass
            done.append(key)
            print(f'✓ {key}（{len(done)}/{len(keys)}）花费 {res.get("cost")}')
    write_gallery_html(all_specs(specs_root), media, media / 'styles' / 'index.html')
    print(f'生成 {len(done)} 张，失败 {len(failed)} 张' + (f'：{" ".join(failed)}' if failed else '') + f'，本次花费约 {total_cost:.2f}；索引 {media / "styles" / "index.html"}')


GALLERY_ASSETS = SKILL / 'assets' / 'gallery'


def pack_frame(src, key, width=640):
    """示意帧缩成 640 宽的 JPEG 放进 assets/gallery/，随 Skill 发布（约 60KB 一张）；原图留在媒体目录。"""
    if not shutil.which('ffmpeg'):
        return ''
    GALLERY_ASSETS.mkdir(parents=True, exist_ok=True)
    dst = GALLERY_ASSETS / f'{key}.jpg'
    res = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-y', '-i', str(src), '-vf', f'scale={width}:-2', '-q:v', '4', str(dst)],
                         capture_output=True, timeout=120)
    return f'assets/gallery/{key}.jpg' if res.returncode == 0 and dst.exists() else ''


def cmd_gallery_pack(specs_root, specs, media):
    """把媒体目录里已有的示意帧补打包进 assets/gallery/（给生成时没打包的、或换过机器的）。"""
    n = 0
    for key, s in specs.items():
        g = s.get('gallery') or {}
        if g.get('frame_kind') != 'concept' or (g.get('frame') or '').startswith('assets/'):
            continue
        src = media / (g.get('original') or g.get('frame') or '')
        if not src.is_file():
            continue
        packed = pack_frame(src, key)
        if packed:
            g.update({'original': str(src.relative_to(media)).replace('\\', '/'), 'frame': packed})
            s['gallery'] = g
            dump(specs_root / key / 'style.json', s)
            n += 1
    print(f'打包 {n} 张到 {GALLERY_ASSETS}')


def cmd_gallery_sample(specs_root, specs, media, keys, yes):
    """有 gallery.sample_url 的风格（开源风格包）：把样片下到媒体目录并核对哈希。不加 --yes 只报大小。"""
    import hashlib
    import urllib.request
    todo = [k for k in keys if (specs.get(k, {}).get('gallery') or {}).get('sample_url')]
    missing = [k for k in keys if k not in todo]
    if missing:
        print('没有在线样片：' + ' '.join(missing))
    todo = [k for k in todo if not (media / 'styles' / k / 'sample.mp4').is_file()]
    if not todo:
        print('没有要下载的样片')
        return
    total = sum(specs[k]['gallery'].get('sample_bytes') or 0 for k in todo)
    for k in todo:
        g = specs[k]['gallery']
        print(f'{k:<32} {(g.get("sample_bytes") or 0) / 2 ** 20:5.1f} MB  {g["sample_url"]}')
    print(f'共 {len(todo)} 条，约 {total / 2 ** 20:.0f} MB，存 {media / "styles"}/<key>/sample.mp4')
    if not yes:
        print('确认后加 --yes 下载')
        return
    for k in todo:
        g = specs[k]['gallery']
        dst = media / 'styles' / k / 'sample.mp4'
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix('.part')
        with urllib.request.urlopen(g['sample_url'], timeout=120) as r, tmp.open('wb') as f:
            shutil.copyfileobj(r, f)
        digest = hashlib.sha256(tmp.read_bytes()).hexdigest()
        if g.get('sample_sha256') and digest != g['sample_sha256']:
            tmp.unlink()
            print(f'✗ {k}：哈希不符，已丢弃')
            continue
        tmp.replace(dst)
        g['sample'] = str(dst.relative_to(media)).replace('\\', '/')
        dump(specs_root / k / 'style.json', specs[k])
        print(f'✓ {k}')


def write_gallery_html(specs, media, out):
    import html as h
    cards, families = [], {}
    for key, s in specs.items():
        if s.get('kind') == 'combo':
            continue
        families.setdefault(s.get('family', ''), []).append((key, s))
    for fam in sorted(families):
        cards.append(f'<h2>{h.escape(fam)}</h2><div class="grid">')
        for key, s in families[fam]:
            g = s.get('gallery', {})
            frame = frame_path(s, media)
            if frame:
                try:
                    frame = Path(frame).resolve().relative_to(Path(out).resolve().parent).as_posix()
                except ValueError:
                    frame = Path(frame).resolve().as_uri()
            img = f'<img src="{h.escape(frame)}" alt="{key}">' if frame else '<div class="none">暂无代表帧<br><small>首次使用时现场渲染</small></div>'
            kind = {'render': '真帧', 'concept': '示意', 'reference': '参考片'}.get(g.get('frame_kind', ''), '')
            pal = ''.join(f'<i style="background:{h.escape(c)}"></i>' for c in s.get('spec', {}).get('palette') or [])
            marks = '、'.join(m for m, ok in (('模板', s.get('template')), ('参考片', s.get('reference'))) if ok)
            cards.append(f'<figure data-key="{key}">{img}<figcaption><b>{key}</b> {h.escape(s.get("name", ""))}'
                         f'{" · " + kind if kind else ""}{" · " + marks if marks else ""}<br><small>{h.escape(s.get("fits", ""))}</small>'
                         f'<div class="pal">{pal}</div></figcaption></figure>')
        cards.append('</div>')
    page = ('<!doctype html><meta charset="utf-8"><title>风格画廊</title><style>'
            'body{font-family:system-ui,sans-serif;margin:16px;background:#111;color:#eee}'
            '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}'
            'figure{margin:0;background:#1c1c1c;padding:8px;border-radius:6px}img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;border-radius:4px}'
            '.none{aspect-ratio:16/9;display:flex;align-items:center;justify-content:center;text-align:center;background:#2a2a2a;border-radius:4px;color:#888}'
            'figcaption{font-size:13px;line-height:1.5;margin-top:6px}.pal i{display:inline-block;width:18px;height:12px;margin:4px 2px 0 0;border-radius:2px;border:1px solid #333}</style>'
            '<h1>风格画廊</h1><p>示意 = 生图示意板，真帧 = 实际成片，参考片 = 用户给的参考（仅本机）。推荐时从不同大类各出一个。</p>' + '\n'.join(cards))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(page, encoding='utf-8')
    print(f'画廊：{out}')


# ---------------------------------------------------------------- CLI

def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('sync-catalog', help='从风格目录生成 / 补齐规范')
    p.add_argument('--catalog')
    p.add_argument('--out')
    p.add_argument('--force', action='store_true', help='连 spec / gallery 一起重置')
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser('list')
    p.add_argument('--root')
    p.set_defaults(func=cmd_list)

    p = sub.add_parser('show')
    p.add_argument('key')
    p.add_argument('--root')
    p.set_defaults(func=cmd_show)

    p = sub.add_parser('set', help='改规范字段')
    p.add_argument('key')
    p.add_argument('--set', action='append', required=True, help="字段=值，如 spec.palette='[\"#fff\",\"#2b2b2b\"]'")
    p.add_argument('--root')
    p.set_defaults(func=cmd_set)

    p = sub.add_parser('check', help='自由度与风格合规检查')
    p.add_argument('--edit', help='读 director.json 的自由度与主风格，报告写 verify/')
    p.add_argument('--plan', help='默认 <edit>/visual-plan.json')
    p.add_argument('--freedom', choices=FREEDOM)
    p.add_argument('--style', help='主风格 key（默认从决策书第 6 格读）')
    p.add_argument('--assist')
    p.add_argument('--forbid', action='append', help='额外禁用词')
    p.add_argument('--frames', help='渲染静帧目录，按主风格色板比对')
    p.add_argument('--palette-min', type=float, default=0.6)
    p.add_argument('--strict', action='store_true', help='提醒也算不通过')
    p.add_argument('--root')
    p.set_defaults(func=cmd_check)

    p = sub.add_parser('recommend', help='按内容、语气推荐 3 个拉开差别的风格方向')
    p.add_argument('--query', help='自由描述')
    p.add_argument('--content', help='内容类型，如 教程 / 记录 / 测评')
    p.add_argument('--platform')
    p.add_argument('--tone', choices=tuple(STRENGTH), help='动作语气：克制 / 中 / 强')
    p.add_argument('--n', type=int, default=3)
    p.add_argument('--avoid', action='append')
    p.add_argument('--edit', help='读决策书与频道档案：栏目描述、避开清单、最近换掉的风格')
    p.add_argument('--apply', action='store_true', help='写进决策书第 6 格')
    p.add_argument('--json', action='store_true')
    p.add_argument('--media')
    p.add_argument('--root')
    p.set_defaults(func=cmd_recommend)

    p = sub.add_parser('learn', help='参考片 → 特征、关键帧、样片（仅本机），补规范的色板与代表帧')
    p.add_argument('--ref', required=True, help='本地视频文件')
    p.add_argument('--key', required=True, help='风格 key（目录里的，或新建）')
    p.add_argument('--title', help='新风格的显示名')
    p.add_argument('--source', help='来源链接或说明')
    p.add_argument('--note')
    p.add_argument('--keyframes', type=int, default=8)
    p.add_argument('--scene', type=float, default=0.3)
    p.add_argument('--media')
    p.add_argument('--root')
    p.set_defaults(func=cmd_learn)

    p = sub.add_parser('gallery', help='代表帧：生图示意、登记真帧、索引页')
    g = p.add_subparsers(dest='gallery_cmd', required=True)
    for name in ('estimate', 'concept'):
        gp = g.add_parser(name, help='报价 / 生成示意帧')
        gp.add_argument('--keys', nargs='*', help='默认所有还没代表帧的')
        gp.add_argument('--aspect', default='16:9')
        gp.add_argument('--resolution'); gp.add_argument('--quality')
        gp.add_argument('--confirmed', action='store_true')
        gp.add_argument('--max-cost', type=float)
        gp.add_argument('--force', action='store_true')
        gp.add_argument('--jobs', type=int, help='并发数，默认用 budget.concurrency')
        gp.add_argument('--media'); gp.add_argument('--root')
    gs = g.add_parser('set', help='登记真帧 / 样片')
    gs.add_argument('key')
    gs.add_argument('--frame', required=True, help='相对媒体目录的路径')
    gs.add_argument('--sample')
    gs.add_argument('--kind', choices=('render', 'concept', 'reference'), default='render')
    gs.add_argument('--media'); gs.add_argument('--root')
    gh = g.add_parser('html', help='生成画廊索引页')
    gh.add_argument('--out')
    gh.add_argument('--media'); gh.add_argument('--root')
    gk = g.add_parser('pack', help='把媒体目录里的示意帧缩成小图打包进 assets/gallery/')
    gk.add_argument('--media'); gk.add_argument('--root')
    gm = g.add_parser('sample', help='下载开源风格包的样片到媒体目录（先报大小，--yes 才下载）')
    gm.add_argument('keys', nargs='+')
    gm.add_argument('--yes', action='store_true')
    gm.add_argument('--media'); gm.add_argument('--root')
    p.set_defaults(func=cmd_gallery)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
