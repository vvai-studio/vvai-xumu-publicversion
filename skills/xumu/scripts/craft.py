#!/usr/bin/env python3
"""组合配方与表达指导：编剧排故事线、导演设计镜头时查的参考（来自 chaojifeng-video-design，MIT）。

  recipes [词…]        18 类组合配方：按内容找结构（输入、分步镜头目的、画面动作、声音、检查）
  suggest --edit <e>   按决策书的一句话、素材、栏目描述推荐配方
  apply --edit <e> <id>   把配方记进决策书第 4 格；故事线还空时按配方步骤起一版草稿
  search <词…> [--layer 文字]   64 项表达：局部手法的目的、输入、参数、退路与检查问题
  show <id…>           配方或表达的全文

配方和表达都是"怎么讲清楚"的指导，不是执行器：能不能做、做出来效果如何，仍按本片实测。
"""
import argparse
import json
from pathlib import Path
import sys

SKILL = Path(__file__).resolve().parent.parent
CRAFT = SKILL / 'library' / 'craft'


def load(name):
    return json.loads((CRAFT / f'{name}.json').read_text(encoding='utf-8'))


def tokens(text):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import director
    return director.tokens(text)


def recipe_text(r):
    steps = ' '.join(s['purpose'] + ' ' + s['visual'] for s in r['steps'])
    return ' '.join([r['name'], r['intent'], ' '.join(r['scenarios']), ' '.join(r['inputs']), steps])


def expression_text(e):
    return ' '.join([e['id'], e['name'], e['layer'], e['intent'], e['transform'], ' '.join(e['inputs']), ' '.join(e['scenarios'])])


STOP = set('的了是和与在把就也')


def rank(items, query, text_of, name_of):
    words = {w for w in tokens(query) if not STOP & set(w)}
    rows = []
    for it in items:
        hits = words & tokens(text_of(it))
        if not hits:
            continue
        score = len(hits) + 2 * len(words & tokens(name_of(it)))
        rows.append((score, it, sorted(hits)))
    rows.sort(key=lambda r: (-r[0], r[1]['id']))
    return rows


def find(id_):
    for r in load('recipes')['recipes']:
        if r['id'] == id_:
            return 'recipe', r
    for e in load('expressions')['expressions']:
        if e['id'] == id_:
            return 'expression', e
    return None, None


def beat_for(i, n, purpose):
    """配方步骤 → 故事线 beat 的粗分：首段铺垫、末段落点、倒数第二段高点，其余看字面。"""
    if i == 0:
        return '铺垫'
    if i == n - 1:
        return '落点'
    if '转' in purpose or '反' in purpose:
        return '转折'
    if i == n - 2 and n >= 4:
        return '高点'
    return '证据'


def cmd_recipes(args):
    data = load('recipes')['recipes']
    if args.terms:
        rows = rank(data, ' '.join(args.terms), recipe_text, lambda r: r['name'])
    else:
        rows = [(0, r, []) for r in data]
    for score, r, hits in rows[:args.limit]:
        print(f'{r["id"]:<26} {r["name"]}（{"、".join(r["scenarios"])}，{len(r["steps"])} 步）：{r["intent"]}')
    if not rows:
        print('没有匹配的配方；不带词列出全部')


def suggest(doc, n=3):
    g = doc.get('grids', {})
    parts = [g.get('3', {}).get('promise', ''), g.get('2', {}).get('spine', {}).get('reason', '')]
    parts += [i.get('summary', '') for i in g.get('1', {}).get('inputs', []) if isinstance(i, dict)]
    parts += [seg.get('goal', '') for seg in g.get('4', {}).get('storyline', [])]
    return rank(load('recipes')['recipes'], ' '.join(filter(None, parts)), recipe_text, lambda r: r['name'])[:n]


def cmd_suggest(args):
    if args.edit:
        doc = json.loads((Path(args.edit) / 'director.json').read_text(encoding='utf-8'))
        if args.query:
            doc.setdefault('grids', {}).setdefault('3', {})['promise'] = doc['grids']['3'].get('promise', '') + ' ' + args.query
        rows = suggest(doc, args.n)
    else:
        rows = rank(load('recipes')['recipes'], args.query or '', recipe_text, lambda r: r['name'])[:args.n]
    if not rows:
        print('对不上任何配方：先填决策书第 3 格（一句话）与第 1 格的素材摘要，或给 --query')
        return
    for score, r, hits in rows:
        print(f'{score:>2}  {r["id"]:<26} {r["name"]}：{r["intent"]}\n    匹配 {"、".join(hits[:6])}')


def cmd_apply(args):
    edit = Path(args.edit)
    file = edit / 'director.json'
    doc = json.loads(file.read_text(encoding='utf-8'))
    kind, r = find(args.id)
    if kind != 'recipe':
        raise SystemExit(f'没有这个配方：{args.id}（craft.py recipes 看全部）')
    g4 = doc['grids'].setdefault('4', {})
    g4['recipe'] = {'id': r['id'], 'name': r['name']}
    drafted = False
    if not g4.get('storyline') or args.force:
        n = len(r['steps'])
        g4['storyline'] = [{'id': f's{i + 1}', 'goal': s['purpose'], 'beat': beat_for(i, n, s['purpose']), 'source_refs': [],
                            'est_duration': '', 'recipe_step': i + 1} for i, s in enumerate(r['steps'])]
        drafted = True
    g4['status'] = 'proposed'
    doc.setdefault('reasons', []).append(f'故事线结构：按配方 {r["name"]}（{r["id"]}）' + ('起草' if drafted else '对照'))
    file.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import director
    try:
        brand, series_item = director.channel_for(doc)
    except (SystemExit, OSError, KeyError):
        brand, series_item = None, None
    director.write_md(doc, edit, brand, series_item)
    print(f'第 4 格配方 → {r["name"]}' + (f'；按 {len(r["steps"])} 步起了故事线草稿，source_refs 与时长待填' if drafted else '；故事线已有，未改（--force 重起）'))


def cmd_search(args):
    data = load('expressions')['expressions']
    if args.layer:
        data = [e for e in data if e['layer'] == args.layer]
    rows = rank(data, ' '.join(args.terms), expression_text, lambda e: e['name']) if args.terms else [(0, e, []) for e in data]
    for score, e, hits in rows[:args.limit]:
        print(f'{e["id"]:<34} {e["layer"]} · {e["name"]}：{e["intent"]}')
    if not rows:
        print('没有匹配的表达；可按层看：--layer ' + ' / '.join(load('expressions')['layers']))


def cmd_show(args):
    out = []
    for id_ in args.ids:
        kind, item = find(id_)
        if not kind:
            raise SystemExit(f'没有这一条：{id_}')
        out.append({'type': kind, **item})
    print(json.dumps(out if len(out) > 1 else out[0], ensure_ascii=False, indent=2))


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('recipes', help='列出 / 搜索组合配方')
    p.add_argument('terms', nargs='*')
    p.add_argument('--limit', type=int, default=18)
    p.set_defaults(func=cmd_recipes)
    p = sub.add_parser('suggest', help='按决策书推荐配方')
    p.add_argument('--edit')
    p.add_argument('--query', help='补一句内容描述')
    p.add_argument('--n', type=int, default=3)
    p.set_defaults(func=cmd_suggest)
    p = sub.add_parser('apply', help='配方记进决策书第 4 格')
    p.add_argument('id')
    p.add_argument('--edit', required=True)
    p.add_argument('--force', action='store_true', help='故事线已有也按配方重起')
    p.set_defaults(func=cmd_apply)
    p = sub.add_parser('search', help='搜索表达指导')
    p.add_argument('terms', nargs='*')
    p.add_argument('--layer')
    p.add_argument('--limit', type=int, default=12)
    p.set_defaults(func=cmd_search)
    p = sub.add_parser('show', help='配方或表达全文')
    p.add_argument('ids', nargs='+')
    p.set_defaults(func=cmd_show)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
