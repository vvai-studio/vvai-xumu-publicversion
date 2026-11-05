#!/usr/bin/env python3
"""Image backend: stills for B-roll and MG through the provider the user configured, behind audio_cloud's paid-call layer.

  python image_cloud.py estimate --prompt TEXT [--aspect 16:9] [--count N] [--ref IMG ...] [--transparent]
  python image_cloud.py generate --edit EDIT --name NAME --prompt TEXT|--prompt-file FILE [--aspect 16:9] [--count N] [--ref IMG ...]
                                 [--transparent] [--model M] [--resolution R] [--quality Q] --confirmed [--max-cost N]

Defaults: gt-image-2.5-flare at 4K and quality high for every image; another model or setting only when the user asks
(--model / --resolution / --quality, or "image" in backends.local.json). Providers and budget are the ones in the
"audio" section; "image" says which provider and model to use (audio_cloud.py setup writes both for 造物社).

Same rules as every paid call: quote all channels, pin the cheapest one whose 24 h success rate passes the bar,
run without asking only under the no-confirm limit, never switch channel after a failure, log each submission to
<edit>/image_log.json before polling (an interrupted run resumes the task), and reuse an identical earlier request
instead of paying again. Another take of the same prompt needs a new --name. A refunded upstream failure (seen live:
the model answered with text instead of an image) is retried up to twice on the same channel with a new request id;
if it keeps failing, rewrite the prompt as a plain description of the picture, not a request or a conversation.

Tasks go through the asynchronous entry (/api/v1/model-runtime/invoke + /v1/tasks): the synchronous image endpoint
answers 200 even on failure once its keep-alive starts. Local reference images are uploaded to the gateway first
(free; inline base64 adds a transfer fee). Downloads take original_url when the platform kept a lossless file and get
the extension from the file's own bytes (result URLs may have none).
"""
import argparse
from pathlib import Path
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

LOG = 'image_log.json'
# refunded failures worth one more try on the same channel; content_blocked needs a new prompt instead
RETRYABLE = ('image_task_failed', 'upstream_error', 'upstream_outage', 'vendor_model_unavailable')
MAGIC = ((b'\x89PNG\r\n\x1a\n', '.png'), (b'\xff\xd8\xff', '.jpg'), (b'RIFF', '.webp'))


def extension(data):
    return next((ext for sig, ext in MAGIC if data.startswith(sig)), '.png')


def image_params(icfg, prompt, aspect='16:9', count=1, refs=(), overrides=None, transparent=False):
    p = {'prompt': prompt, 'aspect_ratio': aspect, **ac.IMAGE_DEFAULTS['defaults'], **(icfg.get('defaults') or {}),
         **{k: v for k, v in (overrides or {}).items() if v}}
    if count > 1:
        p['count'] = count
    if transparent:
        p.update(background='transparent', output_format='png')
    if refs:
        p['images'] = list(refs)
        p.setdefault('mode', 'image-edit' if len(refs) == 1 else 'multi-reference')
    return p


def provider(cfg, icfg, http=None):
    pname = icfg.get('provider')
    if not pname:
        raise ac.Refused('没有配置生图服务商：运行 audio_cloud.py setup 写入造物社的默认设置')
    prov = ac.provider_of(cfg, pname, http)
    if not hasattr(prov, 'submit_image'):
        raise ac.Refused(f'服务商 "{pname}"（{prov.kind}）不支持生图')
    return prov, icfg.get('model', ac.IMAGE_DEFAULTS['model'])


def quote(prov, model, params, b, limit, count=1):
    q = prov.quote(model, params)
    best, ordered, notes = ac.choose_channel(q['channels'], b['min_success_rate'], b['avoid_vendors'])
    return {'provider': prov.name, 'note': q['note'], 'count': count, 'channels': ordered or q['channels'],
            'chosen': best, 'total': None if best is None else best['price'], 'currency': prov.currency,
            'notes': notes, 'limit': limit}


def size_of(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                        '-of', 'csv=p=0:s=x', str(path)], capture_output=True, text=True)
    return r.stdout.strip() or '?'


def submit(prov, model, params, lane, key, attempt, log, edit, out, extra):
    # the gateway de-duplicates by client_request_id: a retry after a failure needs a new one, or it gets the old task
    task = prov.submit_image(model, params, lane, request_id=f'xumu-{key}-{attempt}')
    entry = {'key': key, 'kind': 'image', 'provider': prov.name, 'model': model, 'lane': lane, 'task_id': task,
             'state': 'submitted', 'params': params, 'at': time.strftime('%Y-%m-%d %H:%M:%S'), **extra}
    log.append(entry)
    ac.write_log(edit, log, LOG)
    out(f'已提交 {task}')
    return entry


def wait(prov, task, sleep, poll_every, timeout):
    waited = 0.0
    while True:
        st = prov.poll(task)
        if st.get('final'):
            return st
        if waited >= timeout:
            raise RuntimeError(f'超时：{task} 仍未完成；稍后重跑同一命令会继续查询')
        sleep(poll_every)
        waited += poll_every


def generate(cfg, icfg, edit, name, prompt, aspect='16:9', count=1, refs=(), overrides=None, transparent=False,
             confirmed=False, max_cost=None, http=None, sleep=time.sleep, poll_every=4.0, timeout=900, retries=2,
             out=print):
    prov, model = provider(cfg, icfg, http)
    b = ac.budget(cfg)
    limit = b['confirm_over'] if max_cost is None else float(max_cost)
    # the request key uses the reference files' content, so a re-upload (new URL) still finds the earlier result
    keyed = image_params(icfg, prompt, aspect, count, [], overrides, transparent)
    key = ac.request_key(prov.name, model, name, {**keyed, 'refs': [ac.file_hash(r) for r in refs]}, prompt)
    log = ac.read_log(edit, LOG)
    prev = next((e for e in reversed(log) if e.get('key') == key), None)   # newest attempt
    idir = Path(edit) / 'images'
    if prev and prev.get('state') == 'success' and all((idir / f).exists() for f in prev.get('files', [])):
        out(f'同样的需求已经生成过：{", ".join(prev["files"])}（复用，不再付费）')
        return prev
    attempt = sum(1 for e in log if e.get('key') == key)
    if prev and prev.get('state') == 'submitted':
        out(f'上次已提交（{prev["task_id"]}），继续查询，不重复付费')
    else:
        urls = [prov.upload_file(r) for r in refs]
        params = image_params(icfg, prompt, aspect, count, urls, overrides, transparent)
        q = quote(prov, model, params, b, limit, count)
        out(ac.quote_text(q))
        ac.gate(q, limit, confirmed)
        prev = submit(prov, model, params, q['chosen'].get('lane'), key, attempt, log, edit, out,
                      {'name': name, 'prompt': prompt, 'alternatives': [c for c in q['channels'] if c is not q['chosen']][:3]})
        attempt += 1
    while True:
        st = wait(prov, prev['task_id'], sleep, poll_every, timeout)
        prev['cost'] = st.get('cost')
        if st.get('ok'):
            break
        prev['state'], prev['error'] = 'failed', st.get('error')
        ac.write_log(edit, log, LOG)
        if not (st.get('refunded') and st.get('error_class') in RETRYABLE and retries > 0):
            break
        # refunded upstream hiccup (e.g. the model answered with text instead of an image): same channel, new request
        retries -= 1
        out(f'这次没出图（未扣费）：{st.get("error")}；同一渠道重试一次')
        prev = submit(prov, model, prev['params'], prev['lane'], key, attempt, log, edit, out,
                      {k: prev.get(k) for k in ('name', 'prompt', 'alternatives')})
        attempt += 1
    if not st.get('ok'):
        alts = prev.get('alternatives') or []
        raise ac.Refused('\n'.join([f'生图失败：{st.get("error") or "未知错误"}', '失败的任务不扣费。没有自动换渠道；可选：']
                                   + [f'  {c.get("vendor")}（lane {c.get("lane")}）{round(c["price"], 4)} {prov.currency}'
                                      for c in alts] + ([] if alts else ['  稍后再试，或换另一个服务商'])
                                   + ['同一渠道反复失败时，可以把它的 vendor 写进 budget.avoid_vendors 再重跑']))
    idir.mkdir(parents=True, exist_ok=True)
    urls = st.get('urls') or [st['url']]
    files = []
    for k, url in enumerate(urls):
        data = ac.fetch(prov.http, url, sleep)
        f = (name if len(urls) == 1 else f'{name}_{"ABCDEFGHIJKLMNOPQRSTUVWXYZ"[k]}') + extension(data)
        (idir / f).write_bytes(data)
        files.append(f)
    prev.update(state='success', files=files)
    ac.write_log(edit, log, LOG)
    out(f'完成：{", ".join(f"{f}（{size_of(idir / f)}）" for f in files)}，花费 {st.get("cost")}')
    return prev


def main(argv=None, cfg=None, icfg=None, http=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    for nm in ('estimate', 'generate'):
        p = sub.add_parser(nm)
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument('--prompt'); g.add_argument('--prompt-file', help='UTF-8 text file with the prompt (long prompts)')
        p.add_argument('--aspect', default='16:9')
        p.add_argument('--count', type=int, default=1); p.add_argument('--ref', action='append', default=[])
        p.add_argument('--transparent', action='store_true'); p.add_argument('--model')
        p.add_argument('--resolution'); p.add_argument('--quality')
        if nm == 'generate':
            p.add_argument('--edit', required=True); p.add_argument('--name', required=True)
            p.add_argument('--confirmed', action='store_true'); p.add_argument('--max-cost', type=float)
    a = ap.parse_args(argv)
    if a.prompt_file:
        a.prompt = Path(a.prompt_file).read_text(encoding='utf-8-sig').strip()
    cfg = ac.load_config() if cfg is None else cfg
    icfg = dict(ac.load_config(section='image') if icfg is None else icfg)
    if a.model:
        icfg['model'] = a.model
    over = {'resolution': a.resolution, 'quality': a.quality}
    try:
        if a.cmd == 'estimate':
            prov, model = provider(cfg, icfg, http)
            b = ac.budget(cfg)
            refs = [f'https://example.com/ref{k}.png' for k in range(len(a.ref))]   # the estimate only counts them
            params = image_params(icfg, a.prompt, a.aspect, a.count, refs, over, a.transparent)
            print(ac.quote_text(quote(prov, model, params, b, b['confirm_over'], a.count)), end='')
        else:
            generate(cfg, icfg, a.edit, a.name, a.prompt, a.aspect, a.count, a.ref, over, a.transparent, a.confirmed,
                     a.max_cost, http)
    except ac.Refused as e:
        print(str(e))
        return 3
    return 0


if __name__ == '__main__':
    import key_setup
    key_setup.load_user_env()   # a key saved after this terminal or agent host started
    sys.exit(main())
