#!/usr/bin/env python3
"""Local key page: a one-time web page on this computer where the user pastes an API key, for people who don't use a
terminal. First setup and key changes both go through it.

  python key_setup.py [--var VVAI_API_KEY] [--status] [--replace] [--no-open] [--no-verify] [--timeout 900]

The page listens on 127.0.0.1 only, behind a random one-time path; requests from another origin or host are refused.
The key is checked (造物社: a free balance call) before it is saved, and the server exits by itself once it is saved
or after --timeout seconds. Exit code 0 = saved, 2 = timed out, 3 = refused, 4 = this process may not save.

A key is asked for once. --status answers whether one is saved (exit 0 usable, 1 not; offline, never the value), and
without --replace the page does not open when one is usable: the script says so and exits 0. Agent hosts can start
scripts without the user's variables, so check through this script, not through the shell's environment.

An agent host's sandbox can read the saved key but refuse to store one, so the page checks first and exits 4 instead
of taking a key it cannot keep. The command in the message has to run outside the sandbox.

Where the key goes:
  Windows      the user environment variable (HKCU\\Environment, same as setx), then Windows is told it changed;
  macOS/Linux  one `export VAR='…'` line in the shell start file (~/.zshrc for zsh, ~/.bashrc or ~/.bash_profile for
               bash, else ~/.profile), replacing an earlier line for the same variable.
Nothing here prints, logs or stores the key anywhere else, and the agent never needs to see it.

An agent host or terminal started before the change still holds the old environment. load_user_env() copies the saved
values into os.environ, so the cloud scripts (audio, image, avatar, transcribe) pick up a new key without a restart.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

VVAI_BASE = 'https://vvai.token6688.com'
KEYS = {   # variable -> what the page says; verify names a free online check
    'VVAI_API_KEY': {'label': '造物社', 'where': '登录造物社，在「管理密钥」页新建一把密钥（只显示一次，先复制）',
                     'use': '生图、配音、配乐、数字人', 'verify': 'vvai'},
    'ELEVENLABS_API_KEY': {'label': 'ElevenLabs', 'where': 'ElevenLabs 网站的 API Keys 页', 'use': '云端转录（区分说话人）'},
    'DASHSCOPE_API_KEY': {'label': '阿里云百炼', 'where': '阿里云百炼控制台的 API-KEY 页', 'use': 'Fun-ASR 中文转录'},
    'AZURE_SPEECH_KEY': {'label': 'Azure 语音', 'where': 'Azure 门户里语音资源的「密钥和终结点」页', 'use': 'Azure 快速转录'},
}
SHELL_FILES = ('.zshrc', '.zprofile', '.zshenv', '.bashrc', '.bash_profile', '.profile')
MARK = '# xumu key_setup'
BAD_CHARS = set('\'"\\$`')


def valid_key(value):
    """A pasted key: 8–512 visible ASCII characters, none that would break a shell line. Catches pasted placeholders
    such as 'sk-你的密钥' and stray spaces."""
    return (8 <= len(value) <= 512 and all(0x21 <= ord(c) <= 0x7e for c in value)
            and not (set(value) & BAD_CHARS))


def rc_file(home=None, shell=None, platform=sys.platform):
    home = Path(home or Path.home())
    name = Path(shell if shell is not None else os.environ.get('SHELL', '')).name
    if name == 'zsh' or (not name and platform == 'darwin'):
        return home / '.zshrc'
    if name == 'bash':
        return home / ('.bash_profile' if platform == 'darwin' else '.bashrc')
    return home / '.profile'


def _export_re(var):
    return re.compile(rf'^\s*export\s+{re.escape(var)}=')


def write_rc(path, var, value):
    path = Path(path)
    lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    lines = [ln for ln in lines if not _export_re(var).match(ln)]
    lines.append(f"export {var}='{value}'  {MARK}")
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def read_rc(path, var):
    path = Path(path)
    if not path.exists():
        return None
    found = None
    for ln in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if _export_re(var).match(ln):
            m = re.match(r"""^\s*export\s+\w+=(?:'([^']*)'|"([^"]*)"|(\S+))""", ln)
            if m:
                found = next(g for g in m.groups() if g is not None)
    return found


def _winreg():
    import winreg
    return winreg


def save(var, value, platform=sys.platform, home=None, shell=None):
    """Persist for the user; returns where it went (no value)."""
    if platform == 'win32':
        import ctypes
        wr = _winreg()
        with wr.OpenKey(wr.HKEY_CURRENT_USER, 'Environment', 0, wr.KEY_SET_VALUE) as h:
            wr.SetValueEx(h, var, 0, wr.REG_SZ, value)
        # HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG: programs started from now on see the new value
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, 'Environment', 0x0002, 5000, None)
        return 'Windows 用户环境变量'
    path = rc_file(home, shell, platform)
    write_rc(path, var, value)
    return str(path)


def saved_value(var, platform=sys.platform, home=None, shell=None):
    if platform == 'win32':
        wr = _winreg()
        try:
            with wr.OpenKey(wr.HKEY_CURRENT_USER, 'Environment') as h:
                return wr.QueryValueEx(h, var)[0] or None
        except OSError:
            return None
    return read_rc(rc_file(home, shell, platform), var)


def find_saved(var, platform=sys.platform, home=None, shell=None):
    """The saved value wherever it lives: a host may run scripts with another SHELL, or none, than the one that saved it."""
    value = saved_value(var, platform, home, shell)
    if value or platform == 'win32':
        return value
    home = Path(home or Path.home())
    return next(filter(None, (read_rc(home / name, var) for name in SHELL_FILES)), None)


def key_state(var, environ=os.environ, **kw):
    """'saved', 'session' (only this process has it, so a new window will not) or None. Offline; never the value."""
    try:
        saved = find_saved(var, **kw)
    except Exception:  # noqa: BLE001 - a missing registry or unreadable file just means nothing was found
        saved = None
    return 'saved' if saved else 'session' if environ.get(var) else None


def can_save(platform=sys.platform, home=None, shell=None):
    """False when this process may not store a key, as in an agent host's sandbox: better said before the user pastes."""
    if platform == 'win32':
        wr = _winreg()
        try:
            wr.OpenKey(wr.HKEY_CURRENT_USER, 'Environment', 0, wr.KEY_SET_VALUE).Close()
            return True
        except OSError:
            return False
    path = rc_file(home, shell, platform)
    return os.access(path if path.exists() else path.parent, os.W_OK)


def no_save_help(var, platform=sys.platform):
    run = '& ' if platform == 'win32' else ''
    return (f'这个 AI 工具的沙箱不允许保存 {var}，贴了也存不住，所以没有继续。二选一：\n'
            '1. 让 Agent 申请在沙箱外运行 key_setup.py；\n'
            '2. 在系统终端（不是 AI 工具里）运行下面这行，网页会打开：\n'
            f'{run}"{sys.executable}" "{Path(__file__).resolve()}" --var {var} --replace\n'
            '保存后所有新窗口都能读到。不要把密钥发到聊天里，也不要只设在当前会话。')


STATE_TEXT = {
    'saved': '{var}：已保存，不用再填',
    'session': '{var}：只有当前会话能读到，没有存进这台电脑，新窗口可能读不到。要长期可用，运行 key_setup.py --replace',
    None: '{var}：未配置，运行 key_setup.py 打开网页让用户填',
}


def load_user_env(names=tuple(KEYS), environ=os.environ, **kw):
    """Copy the user's saved keys into this process, so a key set or changed after the host started is used without a
    restart. The saved value wins over a stale inherited one. Returns the names loaded (never values)."""
    loaded = []
    for var in names:
        try:
            value = saved_value(var, **kw) or (None if environ.get(var) else find_saved(var, **kw))
        except Exception:  # noqa: BLE001 - a missing registry or unreadable file just means nothing to load
            value = None
        if value and environ.get(var) != value:
            environ[var] = value
            loaded.append(var)
    return loaded


def verify_vvai(key, opener=urllib.request.urlopen):
    req = urllib.request.Request(VVAI_BASE + '/v1/skills/balance', headers={'Authorization': f'Bearer {key}'})
    try:
        with opener(req, timeout=20) as r:
            d = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return False, {401: '密钥不对或已作废（401）', 403: '密钥没有开通这个接口（403）'}.get(e.code, f'HTTP {e.code}')
    except Exception as e:  # noqa: BLE001
        return False, f'连不上造物社（{type(e).__name__}）'
    d = d.get('data', d) if isinstance(d, dict) else {}
    bal = (d.get('credits') or {}).get('available')
    return True, f'余额 {bal} ⚡' if bal is not None else '连通'


VERIFIERS = {'vvai': verify_vvai}

PAGE = '''<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>设置 __LABEL__ 密钥</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--fg:#1d1d1f;--mute:#6e6e73;--line:#d9d6cf;--accent:#2f5bea;--ok:#1f8a4c;--bad:#c4332b}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--card:#202020;--fg:#f2f2f2;--mute:#a0a0a0;--line:#3a3a3a;
--accent:#6d8cff;--ok:#4cc27e;--bad:#ff6b61}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,"PingFang SC",
"Microsoft YaHei",sans-serif;display:grid;place-items:center;min-height:100vh;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:28px;width:100%;max-width:460px}
h1{font-size:20px;margin:0 0 6px}p{color:var(--mute);margin:0 0 14px}ol{margin:0 0 18px;padding-left:20px;color:var(--mute)}
label{display:block;font-weight:600;margin-bottom:6px}code{font-size:13px}
.row{display:flex;gap:8px}input{flex:1;min-width:0;padding:10px 12px;border:1px solid var(--line);border-radius:8px;
background:transparent;color:var(--fg);font:14px ui-monospace,Consolas,monospace}
button{padding:10px 14px;border:0;border-radius:8px;background:var(--accent);color:#fff;font:inherit;cursor:pointer}
button.ghost{background:transparent;color:var(--mute);border:1px solid var(--line)}
button:disabled{opacity:.5;cursor:default}#msg{margin-top:16px;min-height:1.6em;white-space:pre-line}
.ok{color:var(--ok)}.bad{color:var(--bad)}small{display:block;color:var(--mute);margin-top:14px}
</style></head><body><form class="card" id="f" autocomplete="off">
<h1>设置 __LABEL__ 密钥</h1><p>用于__USE__。保存到这台电脑的 <code>__VAR__</code>，不上传、不发到聊天里。</p>
<ol><li>__WHERE__</li><li>粘贴到下面，点「__ACTION__」</li><li>看到 ✓ 后回到对话，告诉 Agent「好了」</li></ol>
<label for="k">密钥</label>
<div class="row"><input id="k" type="password" placeholder="粘贴密钥" spellcheck="false" autofocus>
<button type="button" class="ghost" id="eye">显示</button></div>
<div style="margin-top:14px"><button id="go" type="submit">__ACTION__</button></div>
<div id="msg" role="status"></div>
<small>这个页面只在本机运行，保存后自动关闭；__MINUTES__ 分钟内没保存也会自动关闭。</small>
</form><script>
const k=document.getElementById('k'),msg=document.getElementById('msg'),go=document.getElementById('go');
document.getElementById('eye').onclick=e=>{const s=k.type==='password';k.type=s?'text':'password';
 e.target.textContent=s?'隐藏':'显示'};
document.getElementById('f').onsubmit=async e=>{e.preventDefault();const v=k.value.trim();
 const say=(cls,t)=>{msg.className=cls;msg.textContent=t};
 if(!v)return say('bad','先粘贴密钥');
 if(/[^\\x21-\\x7e]/.test(v))return say('bad','里面有中文或空格，不像真密钥。请回到网站重新复制');
 go.disabled=true;say('','正在检查…');
 try{const r=await fetch(location.pathname,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
  body:'key='+encodeURIComponent(v)});const d=await r.json();say(d.ok?'ok':'bad',d.msg);
  if(d.ok){k.value='';k.disabled=true}else go.disabled=false}
 catch(err){say('bad','页面已关闭或连不上，请让 Agent 重新打开');go.disabled=false}};
</script></body></html>'''


def render_page(var, verify, timeout):
    info = KEYS.get(var, {'label': var, 'where': '在服务商网站上新建一把密钥并复制', 'use': '序幕的外部服务'})
    esc = lambda s: str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return (PAGE.replace('__LABEL__', esc(info['label'])).replace('__USE__', esc(info['use']))
            .replace('__WHERE__', esc(info['where'])).replace('__VAR__', esc(var))
            .replace('__ACTION__', '验证并保存' if verify else '保存')
            .replace('__MINUTES__', str(max(1, round(timeout / 60)))))


def make_server(var, verify=None, saver=save, timeout=900, port=0):
    """The page server; srv.url is the one-time address, srv.result is filled once a key is saved."""
    token = secrets.token_urlsafe(18)
    page = render_page(var, verify, timeout)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):   # never echo requests: the body holds the key
            pass

        def _send(self, code, body, ctype='application/json; charset=utf-8'):
            b = body.encode('utf-8')
            self.send_response(code)
            for k, v in (('Content-Type', ctype), ('Cache-Control', 'no-store'), ('X-Frame-Options', 'DENY'),
                         ('Referrer-Policy', 'no-referrer'), ('Content-Length', str(len(b)))):
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(b)

        def _ours(self):
            host = f'127.0.0.1:{self.server.server_address[1]}'
            origin = self.headers.get('Origin')
            return (self.path == '/' + token and self.headers.get('Host') == host
                    and origin in (None, 'http://' + host))

        def do_GET(self):
            if not self._ours():
                return self._send(404, 'not found', 'text/plain; charset=utf-8')
            self._send(200, page, 'text/html; charset=utf-8')

        def do_POST(self):
            if not self._ours():
                return self._send(403, '{}')
            reply = lambda ok, text: self._send(200, json.dumps({'ok': ok, 'msg': text}, ensure_ascii=False))
            if self.server.result:
                return reply(True, '已经保存过了，可以关掉这个页面。')
            n = min(int(self.headers.get('Content-Length') or 0), 4096)
            key = (parse_qs(self.rfile.read(n).decode('utf-8', 'replace')).get('key') or [''])[0].strip()
            if not valid_key(key):
                return reply(False, '格式不对：密钥应是一串英文字母、数字和符号，没有空格和中文。请重新复制')
            note = '已保存（没有在线验证）'
            if verify:
                ok, note = verify(key)
                if not ok:
                    return reply(False, f'验证没通过：{note}。没有保存，检查后再试')
            try:
                where = saver(var, key)
            except PermissionError:
                return reply(False, no_save_help(var))
            except Exception as e:  # noqa: BLE001
                return reply(False, f'保存失败（{type(e).__name__}），请把这句话告诉 Agent')
            self.server.result = {'var': var, 'where': where, 'note': note}
            reply(True, f'✓ 已保存（{note}）。\n可以关掉这个页面，回到对话告诉 Agent「好了」。')
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    srv.result = None
    srv.url = f'http://127.0.0.1:{srv.server_address[1]}/{token}'
    return srv


def run(var, verify=True, open_browser=True, timeout=900, out=print):
    checker = VERIFIERS.get(KEYS.get(var, {}).get('verify')) if verify else None
    srv = make_server(var, checker, timeout=timeout)
    timer = threading.Timer(timeout, srv.shutdown)
    timer.daemon = True
    timer.start()
    out(f'密钥设置页已打开（只在本机）：{srv.url}')
    out('浏览器没有弹出时，把这个地址复制到浏览器里打开。保存后页面自动关闭。')
    if open_browser:
        webbrowser.open(srv.url)
    try:
        srv.serve_forever()
    finally:
        timer.cancel()
        srv.server_close()
    if not srv.result:
        out(f'{timeout // 60} 分钟内没有保存，页面已关闭。需要时再运行一次。')
        return 2
    r = srv.result
    out(f'已保存 {r["var"]} 到 {r["where"]}：{r["note"]}。之后运行的序幕脚本会直接读到，不用重启。')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--var', default='VVAI_API_KEY', help='environment variable to set (default VVAI_API_KEY)')
    ap.add_argument('--status', action='store_true', help='say whether a key is configured, and open nothing')
    ap.add_argument('--replace', action='store_true', help='open the page even though a key is configured (key change)')
    ap.add_argument('--no-open', action='store_true', help="print the address instead of opening the browser")
    ap.add_argument('--no-verify', action='store_true', help='save without the free online check')
    ap.add_argument('--timeout', type=int, default=900, help='seconds before the page closes unsaved')
    a = ap.parse_args(argv)
    if not re.fullmatch(r'[A-Z][A-Z0-9_]*', a.var):
        print(f'变量名 {a.var} 不合法：只能是大写字母、数字和下划线')
        return 3
    state = key_state(a.var)
    if a.status:
        print(STATE_TEXT[state].format(var=a.var))
        return 0 if state else 1
    if state and not a.replace:
        print(STATE_TEXT[state].format(var=a.var) + '。没有打开网页；要换密钥时加 --replace。')
        return 0
    if not can_save():
        print(no_save_help(a.var))
        return 4
    return run(a.var, not a.no_verify, not a.no_open, a.timeout)


if __name__ == '__main__':
    try:   # a GBK console must not crash on ✓ or ⚡; the address must show at once when run in the background
        sys.stdout.reconfigure(errors='replace', line_buffering=True)
    except AttributeError:
        pass
    sys.exit(main())
