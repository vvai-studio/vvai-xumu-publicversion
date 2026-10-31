#!/usr/bin/env python3
"""本地网页看板：频道档案、创作决策书、素材缩略图墙、风格画廊、镜头进度与确认点，一页看完。

只看和选，不是第二个对话框。写操作只有三种，每一种都转调 director.py，JSON 仍是唯一事实源：
  点风格方向   → director.py update（第 6 格 style_choice）+ confirm --grids 6
  确认某一格   → director.py confirm --grids N
  确认点通过   → director.py gate pass|skip <名> [--note]
改文字仍在对话框说；看板读到的文件变了，刷新页面即可。

  python board.py serve --workspace <工作区> [--edit <edit>] [--port 8765] [--media <媒体目录>]
只监听 127.0.0.1；标准库实现，没有构建步骤。
"""
import argparse
import html
import json
import mimetypes
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(HERE))
import director  # noqa: E402
import style_tools  # noqa: E402

PY = sys.executable


def run_director(*argv):
    """转调 director.py 的命令行，保证和手工操作走同一条路。"""
    res = subprocess.run([PY, str(HERE / 'director.py'), *argv], capture_output=True, text=True, encoding='utf-8', errors='replace')
    return res.returncode == 0, (res.stdout + res.stderr).strip()


def safe_child(root, rel):
    """root 下的相对路径；跳出 root 的一律拒绝。"""
    root = Path(root).resolve()
    target = (root / unquote(rel).lstrip('/')).resolve()
    if root != target and root not in target.parents:
        return None
    return target if target.is_file() else None


# ---------------------------------------------------------------- 状态

def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def channel_state(workspace):
    channel = Path(workspace) / 'channel'
    brand = read_json(channel / 'brand.json')
    if brand is None:
        return {'exists': False, 'path': str(channel)}
    series = [read_json(p) for p in sorted((channel / 'series').glob('*.json'))]
    log = (channel / 'changelog.md')
    lines = log.read_text(encoding='utf-8').splitlines()[-15:] if log.exists() else []
    return {'exists': True, 'path': str(channel), 'brand': brand, 'series': [s for s in series if s], 'changelog': lines}


def edit_state(edit, media):
    if not edit:
        return {'exists': False}
    edit = Path(edit)
    doc = read_json(edit / 'director.json')
    state = {'exists': edit.is_dir(), 'path': str(edit), 'director': doc,
             'grids': {k: {'page': v[0], 'title': v[1], 'required': list(v[2]), 'optional': list(v[3])} for k, v in director.GRIDS.items()},
             'mode_text': director.MODE_TEXT, 'gates': director.gate_table(doc) if doc else [],
             'footage_sheet': (edit / 'footage' / 'scan.html').is_file(),
             'decision_md': (edit / '创作决策书.md').is_file()}
    plan = read_json(edit / 'visual-plan.json')
    shots = []
    if plan:
        for s in plan.get('shots', []):
            frame = ''
            for cand in (edit / 'verify' / 'frames' / f'{s.get("id")}.png', edit / 'verify' / 'frames' / f'{s.get("id")}.jpg',
                         edit / 'shots' / str(s.get('id')) / 'still.png'):
                if cand.is_file():
                    frame = str(cand.relative_to(edit)).replace('\\', '/')
                    break
            shots.append({'id': s.get('id'), 'role': s.get('role'), 'route': s.get('route'), 'style': s.get('style', ''),
                          'status': s.get('status'), 'from_frame': s.get('from_frame'), 'duration_frames': s.get('duration_frames'),
                          'purpose': s.get('purpose', ''), 'frame': frame})
    state['plan'] = {'exists': plan is not None, 'fps': (plan or {}).get('timeline', {}).get('fps'), 'shots': shots}
    check = read_json(edit / 'verify' / 'style-check.json')
    state['style_check'] = check
    if doc:
        options = doc['grids'].get('6', {}).get('style_options') or []
        for o in options:
            o['frame_url'] = frame_url(o.get('frame', ''), media)
    return state


def frame_url(frame, media):
    """gallery.frame / style_options.frame → 看板能读到的 URL。"""
    if not frame:
        return ''
    p = Path(frame)
    try:
        if p.is_absolute():
            if media and (Path(media).resolve() in p.resolve().parents):
                return '/media/' + p.resolve().relative_to(Path(media).resolve()).as_posix()
            if SKILL in p.resolve().parents:
                return '/skill/' + p.resolve().relative_to(SKILL).as_posix()
            return ''
    except OSError:
        return ''
    if frame.startswith('assets/'):
        return '/skill/' + frame
    return '/media/' + frame


def gallery_state(media):
    specs = style_tools.all_specs()
    items = []
    for key, s in specs.items():
        if s.get('kind') == 'combo':
            continue
        g = s.get('gallery') or {}
        items.append({'key': key, 'name': s.get('name', key), 'family': s.get('family', ''), 'fits': s.get('fits', ''),
                      'frame_url': frame_url(g.get('frame', ''), media), 'frame_kind': g.get('frame_kind', ''),
                      'palette': s.get('spec', {}).get('palette') or [], 'template': bool(s.get('template')), 'reference': bool(s.get('reference')),
                      'sample_url': g.get('sample_url', '')})
    return items


def build_state(workspace, edit, media):
    return {'workspace': str(workspace), 'media': str(media) if media else '',
            'channel': channel_state(workspace), 'edit': edit_state(edit, media), 'gallery': gallery_state(media)}


# ---------------------------------------------------------------- 三种写操作

def choose_style(edit, key):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'grids': {'6': {'style_choice': key}}}, f, ensure_ascii=False)
        tmp = f.name
    ok, text = run_director('update', '--edit', str(edit), '--from', tmp)
    Path(tmp).unlink(missing_ok=True)
    if not ok:
        return False, text
    return run_director('confirm', '--edit', str(edit), '--grids', '6')


def confirm_grids(edit, grids):
    ids = ','.join(str(g) for g in grids)
    if not ids:
        return False, '没有要确认的格'
    return run_director('confirm', '--edit', str(edit), '--grids', ids)


def pass_gate(edit, gate, action, note=''):
    if action not in ('pass', 'skip'):
        return False, 'action 只能是 pass 或 skip'
    argv = ['gate', action, gate, '--edit', str(edit)]
    if note:
        argv += ['--note', note]
    return run_director(*argv)


# ---------------------------------------------------------------- 页面

PAGE = r'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>序幕看板</title>
<style>
/* 剪辑室看板：深色为默认（看图为主），浅色跟系统。顶栏两行（项目 + 分页），正文单栏，分区标题 + 细线列表，
   只有"要你拿主意"的东西（第 6 格风格方向、确认点）才用卡片或强调色。 */
:root{
 --bg:#131418;--surface:#1b1d22;--raised:#24272e;--line:#2b2e35;--line-2:#3a3e48;
 --fg:#e8e9ec;--fg-2:#b6b9c1;--mute:#8d919b;--ph:#1f2228;
 --acc:#8fa2ff;--acc-ink:#0e1330;--ok:#4cc38a;--warn:#e5b454;--bad:#f2706a;
 --sans:"PingFang SC","Microsoft YaHei UI","Microsoft YaHei","Noto Sans CJK SC","Source Han Sans SC",system-ui,-apple-system,"Segoe UI",sans-serif;
 --mono:ui-monospace,"Cascadia Mono","SF Mono",Consolas,"Liberation Mono",monospace;
 --t-xs:12px;--t-sm:13px;--t-md:14px;--t-lg:16px;--t-xl:20px;
 --r:8px;color-scheme:dark}
@media (prefers-color-scheme:light){:root:not([data-theme="dark"]){
 --bg:#f4f5f7;--surface:#ffffff;--raised:#eceef2;--line:#e0e3e9;--line-2:#c9ced8;
 --fg:#1a1c21;--fg-2:#434853;--mute:#5f6571;--ph:#e6e9ee;
 --acc:#3b52d4;--acc-ink:#ffffff;--ok:#1a8452;--warn:#9a6300;--bad:#c4352e;color-scheme:light}}
:root[data-theme="light"]{
 --bg:#f4f5f7;--surface:#ffffff;--raised:#eceef2;--line:#e0e3e9;--line-2:#c9ced8;
 --fg:#1a1c21;--fg-2:#434853;--mute:#5f6571;--ph:#e6e9ee;
 --acc:#3b52d4;--acc-ink:#ffffff;--ok:#1a8452;--warn:#9a6300;--bad:#c4352e;color-scheme:light}
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;font:var(--t-md)/1.6 var(--sans);background:var(--bg);color:var(--fg);-webkit-font-smoothing:antialiased}
a{color:var(--acc);text-underline-offset:2px}
h1,h2,h3{margin:0;font-weight:600;text-wrap:balance}
p{margin:0}
.mono{font-family:var(--mono);font-size:.92em}.dim{color:var(--mute)}
:focus-visible{outline:2px solid var(--acc);outline-offset:2px;border-radius:4px}

/* 顶栏 */
.top{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
.top>div,.top>nav{max-width:1200px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.topbar{display:flex;align-items:center;gap:12px;padding-block:10px 4px}
.topbar h1{font-size:var(--t-lg);letter-spacing:.02em}
.proj{color:var(--mute);font-size:var(--t-sm);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sp{flex:1}
.tabs{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none}
.tabs button{appearance:none;background:none;border:0;color:var(--fg-2);font:inherit;font-size:var(--t-md);padding:8px 10px 10px;min-height:40px;cursor:pointer;white-space:nowrap;box-shadow:inset 0 -2px 0 transparent;display:inline-flex;align-items:center;gap:6px;border-radius:0}
.tabs button:hover{color:var(--fg)}
.tabs button[aria-selected="true"]{color:var(--fg);font-weight:600;box-shadow:inset 0 -2px 0 var(--acc)}
.badge{font-size:11px;line-height:18px;min-width:18px;padding:0 5px;border-radius:9px;background:var(--acc);color:var(--acc-ink);font-weight:600;text-align:center}

main{max-width:1200px;margin:0 auto;padding-block:20px 72px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:flex;flex-direction:column;gap:32px}

/* 按钮与标记 */
.btn{appearance:none;min-height:32px;padding:0 12px;border-radius:7px;border:1px solid var(--line-2);background:var(--raised);color:var(--fg);font:inherit;font-size:var(--t-sm);cursor:pointer;white-space:nowrap;transition:background .12s,border-color .12s,opacity .12s}
.btn:hover{border-color:var(--mute)}
.btn.primary{background:var(--acc);border-color:var(--acc);color:var(--acc-ink);font-weight:600}
.btn.primary:hover{filter:brightness(1.08)}
.btn.ghost{background:none;border-color:transparent;color:var(--fg-2)}
.btn.ghost:hover{color:var(--fg);border-color:var(--line-2)}
.btn:disabled{opacity:.5;cursor:progress}
.tag{display:inline-block;font-size:var(--t-xs);line-height:20px;padding:0 8px;border-radius:999px;background:var(--raised);color:var(--fg-2);white-space:nowrap;font-weight:500}
.tag.acc{background:color-mix(in srgb,var(--acc) 16%,transparent);color:var(--acc)}
.tag.ok{background:color-mix(in srgb,var(--ok) 15%,transparent);color:var(--ok)}
.tag.warn{background:color-mix(in srgb,var(--warn) 16%,transparent);color:var(--warn)}
.tag.bad{background:color-mix(in srgb,var(--bad) 15%,transparent);color:var(--bad)}
.req{font-size:11px;line-height:16px;padding:0 5px;border-radius:4px;background:var(--bad);color:var(--bg);font-weight:600;vertical-align:1px}
.todo{color:var(--warn)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{font-size:var(--t-sm);line-height:22px;padding:0 8px;border-radius:5px;background:var(--raised);color:var(--fg)}
.choice{font-family:var(--mono);font-weight:600;color:var(--acc)}
.chosen{display:inline-flex;align-items:center;min-height:32px;font-size:var(--t-sm);font-weight:600;color:var(--acc)}

/* 分区 */
.sec{display:flex;flex-direction:column;gap:12px;min-width:0}
.sec-h{display:flex;align-items:baseline;gap:10px;font-size:var(--t-lg)}
.count{font-size:var(--t-sm);font-weight:400;color:var(--mute)}
.sec-h .tag{align-self:center}
.lead{color:var(--fg-2);font-size:var(--t-sm)}

/* 当前模式横幅 */
.mode{display:flex;flex-direction:column;gap:6px;padding:12px 16px;border-radius:var(--r);background:var(--surface);border:1px solid var(--line)}
.mode-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px}
.mode-name{font-weight:600;font-size:var(--t-md)}
.mode-name::before{content:"当前模式 ";font-weight:400;color:var(--mute);font-size:var(--t-sm)}
.meta{color:var(--mute);font-size:var(--t-xs);font-variant-numeric:tabular-nums}
.mode p{color:var(--fg-2);font-size:var(--t-sm);max-width:72ch}
.mode .pend{color:var(--fg)}
.mode .pend a{font-weight:600}

/* 决策书格子：左列格名，右列定义表 */
.grids{border-top:1px solid var(--line)}
.g{display:grid;grid-template-columns:200px minmax(0,1fr);gap:10px 28px;padding:16px 0;border-bottom:1px solid var(--line);scroll-margin-top:120px}
.g-h{display:flex;flex-direction:column;align-items:flex-start;gap:10px}
.g-t{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.g-t h3{font-size:var(--t-md)}
.gid{font-family:var(--mono);font-size:var(--t-xs);color:var(--mute);min-width:1.4em}
.g.feature{background:var(--surface);border:1px solid var(--line-2);border-radius:10px;padding:18px;margin:10px 0}
.g.feature h3{font-size:var(--t-lg)}
.kv{display:grid;grid-template-columns:6.5em minmax(0,1fr);gap:6px 16px;margin:0;align-items:baseline}
.kv>dt{color:var(--mute);font-size:var(--t-sm);white-space:nowrap}
.kv>dd{margin:0;min-width:0;overflow-wrap:anywhere}
.kv.wide{grid-template-columns:7em minmax(0,1fr);max-width:860px}
.sub{display:grid;grid-template-columns:auto minmax(0,1fr);gap:2px 12px;margin:0}
.sub>dt{color:var(--mute);font-size:var(--t-sm)}.sub>dd{margin:0;min-width:0;overflow-wrap:anywhere}
.rows{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}
.pair{margin-right:12px;white-space:nowrap}.pair .k{color:var(--mute);font-size:var(--t-sm)}
.note{color:var(--fg-2);font-size:var(--t-sm)}
.files{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}
.files li{display:flex;flex-wrap:wrap;gap:2px 12px;align-items:baseline}
.fname{font-weight:500;overflow-wrap:anywhere}.files .meta{font-size:var(--t-sm)}
.ratio{display:flex;gap:2px;height:8px;border-radius:4px;overflow:hidden;max-width:520px}
.ratio i{display:block;min-width:2px;background:color-mix(in srgb,var(--acc) var(--t),var(--raised))}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;margin-top:6px;font-size:var(--t-sm);color:var(--fg-2)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i{width:8px;height:8px;border-radius:2px;background:color-mix(in srgb,var(--acc) var(--t),var(--raised))}
.legend b{color:var(--fg);font-weight:500;font-variant-numeric:tabular-nums}
.beats{list-style:none;margin:8px 0 0;padding:0;display:flex;flex-direction:column;gap:4px;max-width:520px}
.beats li{display:flex;align-items:baseline;gap:10px}
.beats .grow{flex:1;min-width:0}.num{color:var(--mute);font-size:var(--t-sm);font-variant-numeric:tabular-nums}
.reasons{margin:0;padding:0 0 0 1.2em;color:var(--fg-2);font-size:var(--t-sm);display:flex;flex-direction:column;gap:4px;max-width:80ch}

/* 图块：画廊、风格候选、镜头 */
.tiles,.opts{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:20px 16px}
.opts{margin-top:14px}
.tile{margin:0;display:flex;flex-direction:column;gap:8px;min-width:0}
.shot{position:relative;aspect-ratio:16/9;max-width:100%;border-radius:var(--r);overflow:hidden;background:var(--ph);display:flex;align-items:center;justify-content:center}
.shot img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;transition:filter .15s}
.shot .ph{color:var(--mute);font-size:var(--t-sm);padding:0 12px;text-align:center}
.kind{position:absolute;left:6px;top:6px;font-size:11px;line-height:18px;padding:0 6px;border-radius:4px;background:rgba(0,0,0,.55);color:#fff}
.tile.on .shot{outline:2px solid var(--acc);outline-offset:2px}
.tile .pick{position:absolute;right:8px;bottom:8px;opacity:0;transition:opacity .12s}
.tile:hover .pick,.tile:focus-within .pick{opacity:1}
.tile:hover .shot img{filter:brightness(.85)}
@media (hover:none){.tile .pick{opacity:1}}
.over{position:absolute;right:8px;bottom:8px;min-height:26px;padding:0 8px;border-radius:6px;background:var(--acc);color:var(--acc-ink)}
.pal{display:flex;height:4px;border-radius:2px;overflow:hidden;margin-top:-2px}
.pal i{flex:1}
.tile figcaption{display:flex;flex-direction:column;gap:2px;font-size:var(--t-sm)}
.t-name{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:var(--t-md);font-weight:500}
.t-name .dim{font-weight:400;font-size:var(--t-xs)}
.t-fits{color:var(--fg-2)}
.t-flags{display:flex;gap:10px;color:var(--mute);font-size:var(--t-xs)}
.t-act{margin-top:6px;display:flex;align-items:center;gap:10px}
.t-tc{color:var(--mute);font-size:var(--t-xs);font-variant-numeric:tabular-nums}

/* 频道 */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px;display:flex;flex-direction:column;gap:10px;min-width:0}
.card h3{font-size:var(--t-md)}
.sw{display:inline-flex;align-items:center;gap:6px;margin-right:14px}.sw i{width:14px;height:14px;border-radius:3px;border:1px solid var(--line-2)}
.log{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;border-top:1px solid var(--line);max-width:860px}
.log li{display:grid;grid-template-columns:7.5em minmax(0,1fr);gap:12px;padding:8px 0;border-bottom:1px solid var(--line);font-size:var(--t-sm)}
.log time{color:var(--mute);font-family:var(--mono);font-size:var(--t-xs);padding-top:2px}

/* 确认点 */
.gates{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}
.gate{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:4px 12px;align-items:start;padding:14px 0;border-bottom:1px solid var(--line)}
.sym{font-size:var(--t-lg);line-height:1.4;text-align:center;color:var(--mute)}
.gate.ok .sym{color:var(--ok)}.gate.warn .sym{color:var(--warn)}
.gate.must:not(.ok):not(.warn) .sym{color:var(--acc);font-weight:700}
.g-title{display:flex;flex-wrap:wrap;align-items:center;gap:8px;color:var(--fg-2)}
.gate.must .g-title{color:var(--fg);font-weight:600}
.opt-l{font-size:var(--t-xs);color:var(--mute)}
.g-sub{display:flex;flex-wrap:wrap;gap:2px 12px;color:var(--mute);font-size:var(--t-xs)}
.gate.ok .st{color:var(--ok)}.gate.warn .st{color:var(--warn)}
.g-note{color:var(--fg-2);font-size:var(--t-sm);margin-top:2px}
.g-act{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.g-panel{grid-column:2/-1;display:flex;flex-direction:column;gap:6px;margin-top:6px;padding:12px;border-radius:var(--r);background:var(--surface);border:1px solid var(--line-2)}
.g-panel label{font-size:var(--t-sm);color:var(--fg-2)}
.g-panel-row{display:flex;gap:8px;flex-wrap:wrap}
input.note{flex:1;min-width:0;min-height:32px;background:var(--bg);color:var(--fg);border:1px solid var(--line-2);border-radius:7px;padding:0 10px;font:inherit;font-size:var(--t-sm)}
input.note:focus-visible{outline-offset:0}
.issues{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px;max-width:90ch}
.issues li{display:grid;grid-template-columns:16px minmax(0,1fr);gap:8px;font-size:var(--t-sm)}
.issues li::before{content:"";width:8px;height:8px;border-radius:50%;margin-top:7px;background:var(--warn)}
.issues li.bad::before{background:var(--bad)}

/* 时间线 */
.tl{display:flex;flex-direction:column;gap:6px;padding:14px 16px;border-radius:var(--r);background:var(--surface);border:1px solid var(--line)}
.lane{display:grid;grid-template-columns:3.5em minmax(0,1fr);gap:10px;align-items:center}
.lane-l{color:var(--mute);font-size:var(--t-xs)}
.track{position:relative;height:28px;border-radius:4px;background:var(--raised)}
.blk{position:absolute;top:3px;bottom:3px;min-width:3px;border-radius:3px;padding:0 5px;font:11px/22px var(--mono);overflow:hidden;white-space:nowrap;background:color-mix(in srgb,var(--fg-2) 30%,var(--raised));color:var(--fg)}
.blk.r-mg{background:color-mix(in srgb,var(--acc) 45%,var(--raised))}
.ruler{display:flex;justify-content:space-between;color:var(--mute);font:11px var(--mono)}

/* 空状态与素材 */
.empty{display:flex;flex-direction:column;gap:8px;padding:40px 24px;border:1px dashed var(--line-2);border-radius:10px;max-width:640px}
.empty h2{font-size:var(--t-lg)}
.empty p{color:var(--fg-2);font-size:var(--t-sm)}
.empty .say{color:var(--fg)}
.empty q{quotes:"「" "」";font-weight:600;color:var(--acc);margin-left:4px}
.empty .path{font-size:var(--t-xs);overflow-wrap:anywhere}
.empty.inline{padding:20px;max-width:none}
iframe{width:100%;height:calc(100vh - 150px);min-height:420px;border:1px solid var(--line);border-radius:10px;background:var(--surface);display:block}
#msg{position:fixed;right:max(16px,env(safe-area-inset-right,0px));bottom:max(16px,env(safe-area-inset-bottom,0px));z-index:9;max-width:min(480px,calc(100vw - 32px));padding:10px 14px;border-radius:var(--r);background:var(--surface);border:1px solid var(--line-2);box-shadow:0 8px 24px rgba(0,0,0,.25);white-space:pre-wrap;font-size:var(--t-sm)}
#msg.ok{border-color:var(--ok)}#msg.err{border-color:var(--bad)}

@media (max-width:720px){
 .g{grid-template-columns:minmax(0,1fr)}.g-h{flex-direction:row;flex-wrap:wrap;align-items:center;justify-content:space-between}
 .gate{grid-template-columns:24px minmax(0,1fr)}.g-act{grid-column:2;justify-content:flex-start}.g-panel{grid-column:1/-1}
 .kv,.kv.wide{grid-template-columns:5.5em minmax(0,1fr)}.cards{grid-template-columns:minmax(0,1fr)}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
</style>
<header class="top"><div class="topbar"><h1>序幕看板</h1><span class="proj" id="paths"></span><span class="sp"></span><button class="btn" type="button" data-act="refresh">刷新</button></div>
<nav id="nav" class="tabs" role="tablist" aria-label="看板分页"></nav></header>
<main id="main"><p class="dim">加载中…</p></main><div id="msg" role="status" aria-live="polite" hidden></div>
<script>
const TABS=[['decision','创作决策书'],['channel','频道档案'],['footage','素材'],['gallery','风格画廊'],['progress','镜头与确认点']];
const LABEL={series_action:'归属动作',series:'栏目',series_confidence:'把握',inputs:'素材',gaps:'缺口',spine:'脊梁',promise:'一句话',storyline:'故事线',target_duration:'目标时长',must_keep:'必须留',cut_candidates:'可删',opener:'开场',closer:'收尾',visual_ratio:'画面配比',strong_motion_slots:'强动效位',evidence_segments:'证据段',rhythm:'节奏',narration:'旁白',music_direction:'配乐方向',sfx_level:'音效',live_sound:'现场声',freedom:'自由度',mode:'托管模式',paid_items:'付费项',render_estimate_min:'渲染预估',avatar:'数字人'};
const SUB={use:'使用',model:'模型',kind:'类型',source:'来源',reason:'理由',narration:'旁白',on_camera:'出镜',portrait:'人像',allow_zoom:'允许放大',primary:'主色',secondary:'辅色',background:'底色',title:'标题',body:'正文',handwriting:'手写',license:'授权',name:'名称',intro:'片头',outro:'片尾',music:'配乐',sfx:'音效',live_sound:'现场声'};
const ST={proposed:['建议','acc'],confirmed:['已确认','ok'],edited:['已改','warn']};
const GS={pending:['○','未过',''],passed:['✓','通过','ok'],skipped:['–','跳过','warn']};
const SH={planned:['计划中',''],rendered:['已渲染','warn'],verified:['已验收','ok']};
const ROLE={background:'底层',overlay:'叠加'},ROUTE={real:'实拍',mg:'MG 动效',screen:'录屏',still:'静图',ai:'AI 生成'};
const RATIO={person:'人物',real:'实拍',animation:'动画'},TINT=[100,62,36,20];
let S=null,tab='decision',openGate=null;
try{tab=localStorage.getItem('xumu-tab')||tab}catch(_){}
if(!TABS.some(t=>t[0]===tab))tab='decision';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const isEmpty=v=>v==null||v===''||(Array.isArray(v)?!v.length:(typeof v==='object'&&Object.values(v).every(isEmpty)));
const TODO='<span class="todo">待填</span>',DASH='<span class="dim">—</span>';
const val=x=>typeof x==='boolean'?(x?'是':'否'):esc(x);
const at=s=>String(s||'').slice(5,16).replace('T',' ');
const base=p=>String(p||'').split(/[\\/]/).pop();
function tc(f,fps){f=Math.max(0,Math.round(+f||0));const s=Math.floor(f/fps),p=n=>String(n).padStart(2,'0');return p(Math.floor(s/60))+':'+p(s%60)+':'+p(f%fps)}
function secs(s){const n=Number(s);if(!isFinite(n))return esc(s);return n+' 秒'+(n>=60?'<span class="dim">（'+Math.floor(n/60)+' 分 '+Math.round(n%60)+' 秒）</span>':'')}

// 通用值：对象 → 小定义表，基本类型数组 → 标签，对象数组 → 一行一条
function fmt(v){
 if(isEmpty(v))return TODO;
 if(typeof v!=='object')return val(v);
 if(Array.isArray(v)){
  if(v.every(x=>x==null||typeof x!=='object'))return '<span class="chips">'+v.map(x=>'<span class="chip">'+val(x)+'</span>').join('')+'</span>';
  return '<ul class="rows">'+v.map(x=>'<li>'+(x&&typeof x==='object'?inline(x):val(x))+'</li>').join('')+'</ul>'}
 return '<dl class="sub">'+Object.entries(v).filter(([,x])=>!isEmpty(x)).map(([k,x])=>'<dt title="'+esc(k)+'">'+esc(SUB[k]||k)+'</dt><dd>'+(x&&typeof x==='object'?fmt(x):val(x))+'</dd>').join('')+'</dl>'}
function inline(o){return Object.entries(o).filter(([k,x])=>!isEmpty(x)&&k!=='frame_url').map(([k,x])=>'<span class="pair"><span class="k">'+esc(SUB[k]||k)+'</span> '+(typeof x==='object'?esc(JSON.stringify(x)):val(x))+'</span>').join('')}
function bar(parts,legend=true){const tot=parts.reduce((a,p)=>a+(+p.v||0),0)||1;
 return '<div class="ratio" role="img" aria-label="'+esc(parts.map(p=>p.label+' '+p.text).join('，'))+'">'+parts.map((p,i)=>'<i style="flex:'+((+p.v||0)/tot)+';--t:'+TINT[i%4]+'%" title="'+esc(p.label+' '+p.text)+'"></i>').join('')+'</div>'
  +(legend?'<div class="legend">'+parts.map((p,i)=>'<span><i style="--t:'+TINT[i%4]+'%"></i>'+esc(p.label)+' <b>'+esc(p.text)+'</b></span>').join('')+'</div>':'')}
function ratio(r){if(isEmpty(r))return TODO;const parts=Object.keys(RATIO).filter(k=>r[k]!=null).map(k=>({label:RATIO[k],v:r[k],text:Math.round(r[k]*100)+'%'}));
 return (parts.length?bar(parts):'')+(r.strong_motion?'<div class="note">强动效：'+esc(r.strong_motion)+'</div>':'')}
function storyline(list){return bar(list.map(s=>({label:s.id,v:s.est_duration||1,text:(s.est_duration||'?')+' 秒'})),false)
 +'<ol class="beats">'+list.map(s=>'<li><span class="mono">'+esc(s.id)+'</span>'+(s.beat?'<span class="chip">'+esc(s.beat)+'</span>':'')+'<span class="grow">'+esc(s.goal||'')+'</span>'+(s.est_duration?'<span class="num">'+esc(s.est_duration)+' 秒</span>':'')+'</li>').join('')+'</ol>'}
function inputs(list){return '<ul class="files">'+list.map(x=>{const meta=[x.kind,x.duration_s!=null?x.duration_s+' 秒':'',x.width&&x.height?x.width+'×'+x.height:'',x.has_audio?'有声':(x.has_audio===false?'无声':''),x.speech_ratio!=null?'人声 '+Math.round(x.speech_ratio*100)+'%':''].filter(Boolean);
 return '<li title="'+esc(x.path)+'"><span class="fname">'+esc(base(x.path)||x.path)+'</span><span class="meta">'+meta.map(esc).join(' · ')+'</span>'+(x.summary?'<div class="note">'+esc(x.summary)+'</div>':'')+'</li>'}).join('')+'</ul>'}
function dur(d){const t=d.target_s;return (Array.isArray(t)?esc(t.join('–'))+' 秒':t!=null?esc(t)+' 秒':'')+(d.form?' · '+esc({short:'短篇',long:'长片'}[d.form]||d.form):'')+(d.hard_max_s?' · 最长 '+esc(d.hard_max_s)+' 秒':'')}
function swatches(p){return Object.entries(p).filter(([,c])=>c).map(([k,c])=>'<span class="sw"><i style="background:'+esc(c)+'"></i>'+esc(SUB[k]||k)+' <span class="mono dim">'+esc(c)+'</span></span>').join('')}
const FIELD={inputs,storyline,visual_ratio:ratio,target_duration:secs,render_estimate_min:v=>esc(v)+' 分钟',
 paid_items:l=>'<span class="chips">'+l.map(p=>'<span class="chip">'+esc(p.item||'')+' <b>'+esc(p.quote||'')+'</b></span>').join('')+'</span>',
 mode:v=>esc(((S.edit.mode_text||{})[v]||v).split('：')[0])+' <span class="mono dim">'+esc(v)+'</span>'};
const tag=s=>ST[s]?'<span class="tag '+ST[s][1]+'">'+ST[s][0]+'</span>':'';
function thumb(url,ph,alt,badge,extra){return '<div class="shot">'+(url?'<img src="'+esc(url)+'" alt="'+esc(alt||'')+'" loading="lazy" onerror="this.remove()">':'')+'<span class="ph">'+esc(ph)+'</span>'+(badge?'<span class="kind">'+esc(badge)+'</span>':'')+(extra||'')+'</div>'}
function empty(t,b,say,extra,cls){return '<div class="empty'+(cls?' '+cls:'')+'"><h2>'+esc(t)+'</h2><p>'+esc(b)+'</p>'+(say?'<p class="say">下一步：在对话框里说<q>'+esc(say)+'</q></p>':'')+(extra?'<p class="mono dim path">'+esc(extra)+'</p>':'')+'</div>'}
const noProject=()=>empty('没有打开的项目','看板启动时没带 --edit，现在只能看频道档案和风格画廊。','打开看板看这条片子');
const noDecision=()=>empty('这个项目还没有创作决策书','序幕会从频道档案继承默认值、清点素材，起草编剧页和导演页；起草好后在这里看、点风格、确认格。','出创作决策书');

// ---------------------------------------------------------------- 创作决策书
function decision(){const e=S.edit;if(!e.exists)return noProject();if(!e.director)return noDecision();
 const d=e.director,ids=Object.keys(e.grids),st=id=>(d.grids[id]||{}).status,pend=ids.filter(id=>st(id)==='proposed');
 const mt=(e.mode_text||{})[d.mode]||'',cut=mt.indexOf('：'),mname=cut>0?mt.slice(0,cut):(d.mode||'未定'),mrest=cut>0?mt.slice(cut+1):mt;
 let out='<section class="mode" aria-label="当前模式"><div class="mode-h"><span class="mode-name">'+esc(mname)+'</span><span class="meta">决策书 v'+esc(d.version)+' · '+(d.series?'栏目 '+esc(d.series):'未归属栏目')+' · '+ids.filter(id=>st(id)&&st(id)!=='proposed').length+'/'+ids.length+' 格已定'+(d.confirmed_at?' · 确认于 '+esc(at(d.confirmed_at)):'')+'</span></div>'+(mrest?'<p>'+esc(mrest)+'</p>':'')
  +(pend.length?'<p class="pend">待你确认：'+pend.map(id=>'<a href="#g'+id+'">'+id+' '+esc(e.grids[id].title)+'</a>').join('、')+'</p>':'')+'</section>';
 const pages=[];for(const id of ids){const p=e.grids[id].page,last=pages[pages.length-1];if(last&&last.name===p)last.ids.push(id);else pages.push({name:p,ids:[id]})}
 for(const p of pages)out+='<section class="sec"><h2 class="sec-h">'+esc(p.name)+'<span class="count">'+p.ids.filter(id=>st(id)&&st(id)!=='proposed').length+'/'+p.ids.length+' 已定</span></h2><div class="grids">'+p.ids.map(id=>gridRow(id,e.grids[id],d.grids[id]||{})).join('')+'</div></section>';
 if(d.reasons&&d.reasons.length)out+='<section class="sec"><h2 class="sec-h">理由记录<span class="count">'+d.reasons.length+' 条</span></h2><ul class="reasons">'+d.reasons.map(r=>'<li>'+esc(r)+'</li>').join('')+'</ul></section>';
 return out}
function gridRow(id,meta,g){
 const head='<div class="g-h"><div class="g-t"><span class="gid">'+esc(id)+'</span><h3>'+esc(meta.title)+'</h3>'+tag(g.status)+'</div>'+(g.status==='proposed'?'<button class="btn primary" type="button" data-act="confirm" data-grid="'+esc(id)+'">确认这一格</button>':'')+'</div>';
 const body=id==='6'?styleGrid(g):'<dl class="kv">'+meta.required.concat(meta.optional).map(f=>field(f,g[f],meta.required.includes(f))).join('')+'</dl>';
 return '<article class="g'+(id==='6'?' feature':'')+'" id="g'+esc(id)+'">'+head+'<div>'+body+'</div></article>'}
function field(f,v,req){const miss=isEmpty(v);
 return '<dt title="'+esc(f)+'">'+esc(LABEL[f]||f)+(req&&miss?' <span class="req">必填</span>':'')+'</dt><dd>'+(miss?(req?TODO:DASH):(FIELD[f]?FIELD[f](v):fmt(v)))+'</dd>'}
function styleGrid(g){const opts=g.style_options||[],ch=g.style_choice||'';
 let o='<dl class="kv"><dt title="style_choice">主风格'+(ch?'':' <span class="req">必填</span>')+'</dt><dd>'+(ch?'<span class="choice">'+esc(ch)+'</span>':'<span class="todo">还没选，从下面挑一个</span>')+'</dd>'+(g.style_notes?'<dt title="style_notes">风格备注</dt><dd>'+esc(g.style_notes)+'</dd>':'')+'</dl>';
 if(!opts.length)return o+'<p class="dim" style="margin-top:10px">没有候选方向，可以去风格画廊里挑。</p>';
 return o+'<div class="opts">'+opts.map(x=>{const on=ch===x.key;
  return '<figure class="tile'+(on?' on':'')+'">'+thumb(x.frame_url,'无代表帧，开工时现场渲染草稿',x.key)+'<figcaption><div class="t-name"><span class="mono">'+esc(x.key)+'</span></div>'+(x.diff?'<p class="t-fits">'+esc(x.diff)+'</p>':'')
   +'<div class="t-act">'+(on?'<span class="chosen">✓ 已选</span>':'<button class="btn primary" type="button" data-act="style" data-key="'+esc(x.key)+'">选这个</button>')+(x.ref?'<a href="'+esc(x.ref)+'" target="_blank" rel="noopener">参考片</a>':'')+'</div></figcaption></figure>'}).join('')+'</div>'}

// ---------------------------------------------------------------- 频道档案
function kvRows(rows,emptyHtml){return rows.map(([l,v,fn])=>'<dt>'+esc(l)+'</dt><dd>'+(isEmpty(v)?emptyHtml:(fn?fn(v):fmt(v)))+'</dd>').join('')}
function channel(){const c=S.channel;
 if(!c.exists)return empty('还没有频道档案','频道档案记下人像、平台、品牌色、声音和栏目；以后每条片子都从这里继承默认值。','建档',c.path);
 const b=c.brand||{},sty=s=>s.style||{};
 let out='<section class="sec"><h2 class="sec-h">品牌层<span class="count">'+esc(b.name||'未命名')+'</span></h2><dl class="kv wide">'+kvRows([['人像',b.creator],['平台',b.platforms],['语言',b.language],['品牌色',b.palette,swatches],['字体',b.typography],['声音',b.voice],['片头片尾',b.intro_outro],['禁区',b.forbidden],['参考',b.references]],TODO)+'</dl></section>';
 out+='<section class="sec"><h2 class="sec-h">栏目<span class="count">'+c.series.length+' 个</span></h2>'+(c.series.length?'<div class="cards">'+c.series.map(s=>'<article class="card"><h3>'+esc(s.title||s.key)+' <span class="mono dim">'+esc(s.key)+'</span></h3>'+(s.description?'<p class="note">'+esc(s.description)+'</p>':'')
  +'<dl class="kv">'+kvRows([['脊梁',s.spine],['主风格',sty(s).main,v=>'<span class="choice">'+esc(v)+'</span>'],['辅助风格',sty(s).assist],['强度',sty(s).strength],['避开',sty(s).avoid],['时长',s.duration,dur],['画面配比',s.visual_ratio,ratio],['声音',s.sound],['自由度',s.freedom]],DASH)+'</dl></article>').join('')+'</div>'
  :empty('还没有栏目','栏目是一类反复做的片子，记着主风格、时长和画面配比。','新建一个栏目',null,'inline'))+'</section>';
 const log=c.changelog.map(l=>/^-\s+(\d{4}-\d{2}-\d{2})\s+(.*)$/.exec(l)).filter(Boolean);
 if(log.length)out+='<section class="sec"><h2 class="sec-h">最近改动<span class="count">'+log.length+' 条</span></h2><ul class="log">'+log.reverse().map(m=>'<li><time>'+esc(m[1])+'</time><span>'+esc(m[2])+'</span></li>').join('')+'</ul></section>';
 return out}

// ---------------------------------------------------------------- 素材
function footage(){const e=S.edit;if(!e.exists)return noProject();
 if(!e.footage_sheet)return empty('这个项目还没扫描素材','扫描会切镜头、给每个镜头打可用度分、出缩略图墙；脊梁是故事线或音乐时必须先扫。','扫一下素材');
 return '<iframe src="/edit/footage/scan.html" title="素材扫描缩略图墙"></iframe>'}

// ---------------------------------------------------------------- 风格画廊
function gallery(){const fams={},KIND={render:'真帧',concept:'示意图',reference:'参考片截帧'};for(const g of S.gallery)(fams[g.family]=fams[g.family]||[]).push(g);
 const d=S.edit.exists&&S.edit.director,ch=d?((d.grids['6']||{}).style_choice||''):'';
 if(!S.gallery.length)return empty('风格库是空的','styles/ 下没有读到风格规范。','检查风格库');
 let out='<p class="lead">'+S.gallery.length+' 种风格 · '+(d?(ch?'当前主风格 <span class="choice">'+esc(ch)+'</span>。把鼠标放到一张上（或用 Tab 键）可以改选。':'还没选主风格，把鼠标放到一张上点「选为主风格」。'):'没有打开的项目，只能浏览；打开项目后可以在这里选主风格。')+'</p>';
 return out+Object.keys(fams).sort().map(f=>'<section class="sec"><h2 class="sec-h">'+esc(f)+'<span class="count">'+fams[f].length+'</span></h2><div class="tiles">'+fams[f].map(g=>{const on=g.key===ch;
  const over=d?(on?'<span class="chosen over">✓ 主风格</span>':'<button class="btn primary pick" type="button" data-act="style" data-key="'+esc(g.key)+'" aria-label="选 '+esc(g.name)+' 为主风格">选为主风格</button>'):'';
  return '<figure class="tile'+(on?' on':'')+'">'+thumb(g.frame_url,'暂无代表帧',g.name,'',over)+(g.palette.length?'<div class="pal" aria-hidden="true">'+g.palette.map(c=>'<i style="background:'+esc(c)+'"></i>').join('')+'</div>':'')
   +'<figcaption><div class="t-name">'+esc(g.name)+'<span class="mono dim">'+esc(g.key)+'</span></div>'+(g.fits?'<p class="t-fits">'+esc(g.fits)+'</p>':'')+(g.frame_kind||g.template||g.reference?'<p class="t-flags">'+(g.frame_kind?'<span>'+esc(KIND[g.frame_kind]||g.frame_kind)+'</span>':'')+(g.template?'<span>有模板</span>':'')+(g.reference?'<span>有参考片</span>':'')+(g.sample_url?'<a href="'+esc(g.sample_url)+'" target="_blank" rel="noopener">看样片</a>':'')+'</p>':'')+'</figcaption></figure>'}).join('')+'</div></section>').join('')}

// ---------------------------------------------------------------- 镜头与确认点
function progress(){const e=S.edit;if(!e.exists)return noProject();let out='';
 if(!e.director)out+=noDecision();
 else{const gs=e.gates,done=gs.filter(g=>g.status!=='pending').length,req=gs.filter(g=>g.required),left=req.filter(g=>g.status==='pending').length;
  out+='<section class="sec"><h2 class="sec-h">确认点<span class="count">'+done+'/'+gs.length+' 已过'+(req.length?' · 本模式必过 '+req.length+' 处'+(left?'，还差 '+left+' 处':'，都过了'):'')+'</span></h2><ol class="gates">'+gs.map(gateRow).join('')+'</ol></section>'}
 const c=e.style_check;
 if(c)out+='<section class="sec"><h2 class="sec-h">风格合规<span class="tag '+(c.ok?'ok':'bad')+'">'+(c.ok?'通过':'不通过')+'</span></h2><p class="lead">主风格 <span class="mono">'+esc(c.main_style||'—')+'</span>'+(c.assist_style?' · 辅助 <span class="mono">'+esc(c.assist_style)+'</span>':'')+' · 自由度 '+esc(c.freedom||'—')+' · 查了 '+esc(c.shots)+' 个镜头</p>'
  +((c.errors||[]).length||(c.warnings||[]).length?'<ul class="issues">'+(c.errors||[]).map(x=>'<li class="bad"><span>'+esc(x)+'</span></li>').join('')+(c.warnings||[]).map(x=>'<li><span>'+esc(x)+'</span></li>').join('')+'</ul>':'')+'</section>';
 const p=e.plan;
 if(!p.exists)return out+'<section class="sec"><h2 class="sec-h">镜头</h2>'+empty('还没有画面方案','visual-plan.json 在流程 3 出画面方案之后才有，那时这里会列出每个镜头和时间线。','出画面方案',null,'inline')+'</section>';
 return out+'<section class="sec"><h2 class="sec-h">镜头<span class="count">'+p.shots.length+' 个 · '+esc(p.fps||'?')+' fps</span></h2>'+shots(p)+'</section>'}
function gateRow(g){const [sym,txt,cls]=GS[g.status]||['?',g.status,''],pending=g.status==='pending',op=openGate&&openGate.gate===g.gate?openGate.mode:'',k=esc(g.gate);
 const act=pending&&!op?'<div class="g-act"><button class="btn primary" type="button" data-act="gate" data-gate="'+k+'" data-mode="pass">通过</button><button class="btn" type="button" data-act="gate-open" data-gate="'+k+'" data-mode="skip">跳过…</button><button class="btn ghost" type="button" data-act="gate-open" data-gate="'+k+'" data-mode="pass">加备注</button></div>':'';
 const panel=pending&&op?'<div class="g-panel"><label for="note-'+k+'">'+(op==='skip'?'跳过理由（必填）':'通过备注（可不写）')+'</label><div class="g-panel-row"><input id="note-'+k+'" class="note" autocomplete="off" data-gate="'+k+'" data-mode="'+op+'" placeholder="'+(op==='skip'?'比如：这条不需要试听':'比如：前 60 秒偏克制')+'"><button class="btn primary" type="button" data-act="gate" data-gate="'+k+'" data-mode="'+op+'">'+(op==='skip'?'确认跳过':'通过')+'</button><button class="btn ghost" type="button" data-act="gate-cancel">取消</button></div></div>':'';
 return '<li class="gate'+(g.required?' must':'')+(cls?' '+cls:'')+'"><span class="sym" aria-label="'+esc(txt)+'">'+sym+'</span><div><div class="g-title">'+esc(g.title)+(g.required?'<span class="tag acc">必过</span>':'<span class="opt-l">不必过</span>')+'</div>'
  +'<div class="g-sub"><span>'+esc(g.stage)+'</span><span class="mono">'+k+'</span>'+(pending?'':'<span class="st">'+esc(txt)+(g.at?' · '+esc(at(g.at)):'')+'</span>')+'</div>'+(g.note?'<div class="g-note">'+esc(g.note)+'</div>':'')+'</div>'+act+panel+'</li>'}
function shots(p){const fps=+p.fps||30,end=Math.max(1,...p.shots.map(s=>(+s.from_frame||0)+(+s.duration_frames||0))),roles=[...new Set(p.shots.map(s=>s.role||'—'))];
 if(!p.shots.length)return empty('画面方案里还没有镜头','visual-plan.json 存在，但 shots 是空的。','补画面方案',null,'inline');
 const tl='<div class="tl" aria-label="镜头时间线">'+roles.map(r=>'<div class="lane"><span class="lane-l">'+esc(ROLE[r]||r)+'</span><div class="track">'+p.shots.filter(s=>(s.role||'—')===r).map(s=>{const a=+s.from_frame||0,b=a+(+s.duration_frames||0);
  return '<span class="blk r-'+esc(s.route)+'" style="left:'+(100*a/end)+'%;width:'+(100*(b-a)/end)+'%" title="'+esc(s.id+' · '+(s.purpose||'')+' · '+tc(a,fps)+'–'+tc(b,fps))+'">'+esc(s.id)+'</span>'}).join('')+'</div></div>').join('')
  +'<div class="lane"><span></span><div class="ruler"><span>00:00:00</span><span>'+tc(end,fps)+'</span></div></div></div>';
 return tl+'<div class="tiles">'+p.shots.map(s=>{const sh=SH[s.status]||[s.status||'',''];
  return '<figure class="tile">'+thumb(s.frame?'/edit/'+s.frame:'',ROUTE[s.route]||s.route||'无画面',s.id)+'<figcaption><div class="t-name"><span class="mono">'+esc(s.id)+'</span>'+(sh[0]?'<span class="tag '+sh[1]+'">'+esc(sh[0])+'</span>':'')+'</div>'
   +'<p class="t-tc mono">'+tc(s.from_frame,fps)+' 起 · '+((+s.duration_frames||0)/fps).toFixed(1)+' 秒</p><p class="t-fits">'+esc([ROLE[s.role]||s.role,ROUTE[s.route]||s.route,s.style].filter(Boolean).join(' · '))+'</p>'+(s.purpose?'<p>'+esc(s.purpose)+'</p>':'')+'</figcaption></figure>'}).join('')+'</div>'}

// ---------------------------------------------------------------- 外壳
function badge(k){const e=S&&S.edit;if(!e||!e.director)return 0;
 if(k==='decision')return Object.keys(e.grids).filter(id=>(e.director.grids[id]||{}).status==='proposed').length;
 if(k==='progress')return e.gates.filter(g=>g.required&&g.status==='pending').length+(e.style_check&&!e.style_check.ok?1:0);return 0}
function render(){$('nav').innerHTML=TABS.map(([k,t])=>{const n=badge(k);return '<button type="button" role="tab" aria-selected="'+(k===tab)+'" data-act="tab" data-tab="'+k+'">'+t+(n?'<span class="badge" aria-label="'+n+' 项待处理">'+n+'</span>':'')+'</button>'}).join('');
 $('main').innerHTML=({decision,channel,footage,gallery,progress})[tab]()}
function msg(t,kind,ms=4500){const m=$('msg');m.textContent=t;m.className=kind||'';m.hidden=false;clearTimeout(m._t);m._t=setTimeout(()=>{m.hidden=true},ms)}
async function load(){try{S=await (await fetch('/api/state')).json()}catch(err){$('main').innerHTML=empty('看板服务没响应','board.py 可能已经停了。','重新打开看板');return}
 const e=S.edit,p=$('paths');if(e.exists){const parts=e.path.split(/[\\/]/).filter(Boolean);let n=parts.pop()||'';if(n==='edit'&&parts.length)n=parts.pop();p.textContent='项目 '+n;p.title=e.path}else{p.textContent='没有打开的项目';p.title=''}
 render()}
async function post(url,body){let j;try{const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});j=await r.json()}catch(err){j={ok:false,message:'看板服务没响应：'+err.message}}
 msg(j.message||(j.ok?'已记录':'没成功'),j.ok?'ok':'err');return j}
document.addEventListener('click',async ev=>{const b=ev.target.closest('[data-act]');if(!b)return;const a=b.dataset.act;
 if(a==='tab'){tab=b.dataset.tab;try{localStorage.setItem('xumu-tab',tab)}catch(_){}openGate=null;render();return}
 if(a==='refresh'){load();return}
 if(a==='gate-open'){openGate={gate:b.dataset.gate,mode:b.dataset.mode};render();const i=$('note-'+openGate.gate);if(i)i.focus();return}
 if(a==='gate-cancel'){openGate=null;render();return}
 let url,body;
 if(a==='style'){url='/api/choose-style';body={key:b.dataset.key}}
 else if(a==='confirm'){url='/api/confirm';body={grids:[b.dataset.grid]}}
 else if(a==='gate'){const g=b.dataset.gate,mode=b.dataset.mode,i=$('note-'+g),note=i?i.value.trim():'';
  if(mode==='skip'&&!note){msg('跳过要写理由','err');if(i)i.focus();return}
  url='/api/gate';body={gate:g,action:mode,note}}
 else return;
 b.disabled=true;const j=await post(url,body);
 if(j.ok){openGate=null;await load()}else if(b.isConnected)b.disabled=false});
document.addEventListener('keydown',ev=>{const t=ev.target;
 if(t.matches&&t.matches('input.note')){if(ev.key==='Enter'){ev.preventDefault();const b=t.parentNode.querySelector('[data-act="gate"]');if(b)b.click()}else if(ev.key==='Escape'){openGate=null;render()}return}
 if(t.getAttribute&&t.getAttribute('role')==='tab'&&(ev.key==='ArrowRight'||ev.key==='ArrowLeft')){const i=TABS.findIndex(x=>x[0]===tab),n=TABS[(i+(ev.key==='ArrowRight'?1:TABS.length-1))%TABS.length][0];
  tab=n;try{localStorage.setItem('xumu-tab',tab)}catch(_){}render();const nb=document.querySelector('[data-tab="'+n+'"]');if(nb)nb.focus()}});
load();
</script></html>'''


class Handler(BaseHTTPRequestHandler):
    workspace = None
    edit = None
    media = None

    def log_message(self, fmt, *args):  # 安静
        pass

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path):
        if path is None:
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
        data = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', ctype + ('; charset=utf-8' if ctype.startswith('text/') else ''))
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/favicon.ico':
            self.send_error(404)
        elif url.path in ('/', '/index.html') or not url.path.startswith(('/api/', '/media/', '/skill/', '/edit/')):
            # 根、/index.html、以及 /decision 这类页名都回主页，页名由前端按 hash / 路径切换
            body = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif url.path == '/api/state':
            self.send_json(build_state(self.workspace, self.edit, self.media))
        elif url.path.startswith('/media/') and self.media:
            self.send_file(safe_child(self.media, url.path[len('/media/'):]))
        elif url.path.startswith('/skill/'):
            self.send_file(safe_child(SKILL, url.path[len('/skill/'):]))
        elif url.path.startswith('/edit/') and self.edit:
            self.send_file(safe_child(self.edit, url.path[len('/edit/'):]))
        else:
            self.send_error(404)

    def do_POST(self):
        url = urlparse(self.path)
        length = int(self.headers.get('Content-Length') or 0)
        try:
            body = json.loads(self.rfile.read(length) or b'{}')
        except ValueError:
            self.send_json({'ok': False, 'message': '不是 JSON'}, 400)
            return
        if not self.edit:
            self.send_json({'ok': False, 'message': '没有打开的项目'}, 400)
            return
        if url.path == '/api/choose-style':
            ok, text = choose_style(self.edit, str(body.get('key', '')).strip())
        elif url.path == '/api/confirm':
            ok, text = confirm_grids(self.edit, body.get('grids') or [])
        elif url.path == '/api/gate':
            ok, text = pass_gate(self.edit, str(body.get('gate', '')), str(body.get('action', 'pass')), str(body.get('note', '') or ''))
        else:
            self.send_json({'ok': False, 'message': '未知操作'}, 404)
            return
        self.send_json({'ok': ok, 'message': text}, 200 if ok else 400)


def make_server(workspace, edit, media, port=8765, host='127.0.0.1'):
    handler = type('BoardHandler', (Handler,), {'workspace': Path(workspace), 'edit': Path(edit) if edit else None,
                                               'media': Path(media) if media else None})
    return ThreadingHTTPServer((host, port), handler)


def cmd_serve(args):
    media = None
    try:
        media = style_tools.media_root(args.media)
    except SystemExit:
        pass
    server = make_server(args.workspace, args.edit, media, args.port)
    url = f'http://127.0.0.1:{server.server_address[1]}/'
    print(f'序幕看板：{url}' + (f'  项目 {args.edit}' if args.edit else '  （没有打开项目，只看频道与画廊）'), flush=True)
    print('只监听本机；Ctrl+C 停止。', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('serve')
    p.add_argument('--workspace', required=True, help='含 channel/ 的工作区')
    p.add_argument('--edit', help='本片的 edit 目录')
    p.add_argument('--port', type=int, default=8765)
    p.add_argument('--media', help='媒体目录，默认按 learning.media_root')
    p.set_defaults(func=cmd_serve)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
