"""看板：状态组装、三种写操作、静态文件边界；起一个本机端口走一遍 HTTP。"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import board
import director


def run_director(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        director.main(list(argv))
    return out.getvalue()


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xumu-board-')
        self.ws = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.edit = self.ws / 'outputs' / 'demo' / 'edit'
        self.edit.mkdir(parents=True)
        self.media = self.ws / 'media'
        (self.media / 'styles' / 'x').mkdir(parents=True)
        (self.media / 'styles' / 'x' / 'concept.png').write_bytes(b'\x89PNG fake')
        director.ffprobe_facts = lambda path: None
        run_director('init', '--workspace', str(self.ws), '--name', '看板频道', '--platform', '抖音')
        run_director('series', 'add', '--channel', str(self.ws / 'channel'), '--key', 'ai-tutorial', '--title', 'AI 工具教程',
                     '--spine', 'narration', '--style', 'whiteboard-world')
        run_director('propose', '--edit', str(self.edit), '--channel', str(self.ws / 'channel'), '--first-time')
        (self.edit / 'visual-plan.json').write_text(json.dumps({'timeline': {'fps': 30}, 'shots': [
            {'id': 's1', 'role': 'background', 'route': 'real', 'status': 'planned', 'from_frame': 0, 'duration_frames': 90, 'purpose': '人物'}]}), encoding='utf-8')

    def doc(self):
        return json.loads((self.edit / 'director.json').read_text(encoding='utf-8'))

    def test_state(self):
        state = board.build_state(self.ws, self.edit, self.media)
        self.assertTrue(state['channel']['exists'])
        self.assertEqual(state['channel']['series'][0]['key'], 'ai-tutorial')
        self.assertEqual(state['edit']['director']['mode'], 'full-auto')
        self.assertEqual([g['gate'] for g in state['edit']['gates'] if g['required']], ['reference-clip'])
        self.assertEqual(state['edit']['plan']['shots'][0]['id'], 's1')
        self.assertTrue(any(g['key'] == 'whiteboard-world' for g in state['gallery']))
        self.assertTrue(all(g['frame_url'].startswith(('/skill/', '/media/', '')) for g in state['gallery']))
        self.assertEqual(board.frame_url('assets/gallery/x.jpg', self.media), '/skill/assets/gallery/x.jpg')
        self.assertEqual(board.frame_url('styles/x/concept.png', self.media), '/media/styles/x/concept.png')
        self.assertEqual(board.frame_url(str(self.media / 'styles' / 'x' / 'concept.png'), self.media), '/media/styles/x/concept.png')
        empty = board.build_state(self.ws / 'nowhere', None, None)
        self.assertFalse(empty['channel']['exists'])
        self.assertFalse(empty['edit']['exists'])

    def test_writes_go_through_director(self):
        ok, text = board.choose_style(self.edit, 'chalkboard')
        self.assertTrue(ok, text)
        d = self.doc()
        self.assertEqual(d['grids']['6']['style_choice'], 'chalkboard')
        self.assertEqual(d['grids']['6']['status'], 'confirmed')
        ok, _ = board.confirm_grids(self.edit, ['0', '4'])
        self.assertTrue(ok)
        self.assertEqual(self.doc()['grids']['4']['status'], 'confirmed')
        ok, text = board.pass_gate(self.edit, 'reference-clip', 'skip', '')
        self.assertFalse(ok)  # 跳过要理由，由 director 拦
        ok, _ = board.pass_gate(self.edit, 'reference-clip', 'pass', '用户看了前 60 秒')
        self.assertTrue(ok)
        self.assertEqual(self.doc()['gates']['reference-clip']['status'], 'passed')
        ok, _ = board.pass_gate(self.edit, 'reference-clip', 'nuke', '')
        self.assertFalse(ok)

    def test_safe_child(self):
        self.assertIsNotNone(board.safe_child(self.media, 'styles/x/concept.png'))
        self.assertIsNone(board.safe_child(self.media, '../channel/brand.json'))
        self.assertIsNone(board.safe_child(self.media, 'styles/x'))   # 目录不算

    def test_http_roundtrip(self):
        server = board.make_server(self.ws, self.edit, self.media, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        base = f'http://127.0.0.1:{server.server_address[1]}'
        page = urlopen(base + '/').read().decode('utf-8')
        self.assertIn('序幕看板', page)
        state = json.loads(urlopen(base + '/api/state').read().decode('utf-8'))
        self.assertEqual(state['edit']['director']['series'], 'ai-tutorial')
        self.assertEqual(urlopen(base + '/media/styles/x/concept.png').read(), b'\x89PNG fake')
        with self.assertRaises(HTTPError):
            urlopen(base + '/media/../channel/brand.json')
        req = Request(base + '/api/choose-style', data=json.dumps({'key': 'neon'}).encode(), headers={'Content-Type': 'application/json'})
        res = json.loads(urlopen(req).read().decode('utf-8'))
        self.assertTrue(res['ok'], res)
        self.assertEqual(self.doc()['grids']['6']['style_choice'], 'neon')
        req = Request(base + '/api/gate', data=json.dumps({'gate': 'listen', 'action': 'skip', 'note': ''}).encode(), headers={'Content-Type': 'application/json'})
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req)
        self.assertEqual(ctx.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
