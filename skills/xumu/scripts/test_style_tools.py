"""风格规范生成与合规检查；静帧比对需要 ffmpeg。"""
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import style_tools
from style_tools import main


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        main(list(argv))
    return out.getvalue()


CATALOG = """# 风格目录

## A. 教学解说

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `whiteboard-world` 白板一镜到底 **已验证 · 有模板**（[做法](whiteboard-world.md)） | 白底 | 推、甩、拉；画笔手跟随 | 教程 | HyperFrames；`hf:whiteboard-ink` |
| `isometric` 等距 2.5D **有参考片** | 等距网格 | 分层抬升、爆炸拆解 | 架构 | SVG；`gn:exploded-assembly`；`mg15:03-isometric` |
| `cartoon-collage` 卡通拼贴 | 米色纸纹 | 剪贴落地 | 科普 | 插画剪贴 **需素材**；`hf:hw-box-label` |

## J. 组合方式

| key | 说明 |
|---|---|
| `person-in-scene` 人物入景 | 抠像后放进任一场景风格 |
"""


def shot(sid, route, style=None, **kw):
    s = {'id': sid, 'role': 'background', 'route': route, 'from_frame': 0, 'duration_frames': 90, 'purpose': 'p',
         'audio_policy': 'silent', 'status': 'planned'}
    if style:
        s['style'] = style
    s.update(kw)
    return s


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xumu-style-')
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.catalog = self.root / 'catalog.md'
        self.catalog.write_text(CATALOG, encoding='utf-8')
        self.out = self.root / 'styles'

    def test_parse_and_sync(self):
        rows = style_tools.parse_catalog(CATALOG)
        self.assertEqual([r['key'] for r in rows], ['whiteboard-world', 'isometric', 'cartoon-collage', 'person-in-scene'])
        self.assertEqual(rows[0]['name'], '白板一镜到底')
        self.assertEqual(rows[0]['tags'], ['已验证 · 有模板'])
        self.assertEqual(rows[3]['kind'], 'combo')
        out = run('sync-catalog', '--catalog', str(self.catalog), '--out', str(self.out))
        self.assertIn('新建 4', out)
        wb = json.loads((self.out / 'whiteboard-world' / 'style.json').read_text(encoding='utf-8'))
        self.assertEqual(wb['template'], 'assets/templates/whiteboard-world')   # 真实模板目录存在
        self.assertIsNone(wb['reference'])
        iso = json.loads((self.out / 'isometric' / 'style.json').read_text(encoding='utf-8'))
        self.assertEqual(iso['reference'], 'mg15:03-isometric')
        self.assertEqual(iso['spec']['signature_moves'], ['分层抬升、爆炸拆解'])   # 只按逗号分号拆，顿号留在一个动作里
        cc = json.loads((self.out / 'cartoon-collage' / 'style.json').read_text(encoding='utf-8'))
        self.assertTrue(cc['needs_assets'])
        # 人填的 spec 在再次同步时保留，目录文字变了描述跟着更新
        run('set', 'isometric', '--root', str(self.out), '--set', 'spec.palette=["#112233"]', '--set', 'spec.strength_max=克制')
        self.catalog.write_text(CATALOG.replace('等距网格', '等距网格、柔和阴影'), encoding='utf-8')
        out = run('sync-catalog', '--catalog', str(self.catalog), '--out', str(self.out))
        self.assertIn('更新描述 1', out)
        iso = json.loads((self.out / 'isometric' / 'style.json').read_text(encoding='utf-8'))
        self.assertEqual(iso['look'], '等距网格、柔和阴影')
        self.assertEqual(iso['spec']['palette'], ['#112233'])
        self.assertIn('isometric', run('list', '--root', str(self.out)))

    def test_real_catalog_has_127_entries(self):
        rows = style_tools.parse_catalog(style_tools.CATALOG.read_text(encoding='utf-8'))
        self.assertEqual(len(rows), 127)
        self.assertEqual(len({r['key'] for r in rows}), 127)

    def test_opuscar_styles_have_reference_source_and_packed_frame(self):
        rows = [r for r in style_tools.parse_catalog(style_tools.CATALOG.read_text(encoding='utf-8')) if r['key'].startswith('opuscar-')]
        self.assertEqual(len(rows), 59)
        specs = style_tools.all_specs()
        if not any(k.startswith('opuscar-') for k in specs):
            self.skipTest('Opuscar style packs are not part of this edition')
        for r in rows:
            spec = style_tools.spec_from_row(r)
            self.assertEqual(spec['reference'], 'opus:' + r['key'][len('opuscar-'):])
            g = specs[r['key']]['gallery']
            self.assertEqual(g['frame_kind'], 'reference')
            self.assertTrue((style_tools.SKILL / g['frame']).is_file(), r['key'])
            self.assertTrue(g['sample_url'].startswith('https://github.com/lemomo-ai/lemo-opuscar/releases/'))

    @unittest.skipUnless(shutil.which('ffmpeg') and style_tools.have_numpy(), '要 ffmpeg 与 numpy')
    def test_dominant_colors_reads_a_still_image(self):
        with tempfile.TemporaryDirectory(prefix='xumu-still-') as tmp:
            img = Path(tmp) / 'still.png'
            subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-y', '-f', 'lavfi', '-i', 'color=c=0x1F3B2E:size=64x36',
                            '-frames:v', '1', str(img)], check=True, capture_output=True)
            self.assertTrue(style_tools.dominant_colors(img))


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.specs = {
            'whiteboard-world': {'template': 'assets/templates/whiteboard-world', 'reference': None,
                                 'spec': {'palette': ['#ffffff', '#2b2b2b'], 'strength_max': '中', 'max_chars_per_s': 4.0, 'min_dwell_s': 1.2}},
            'isometric': {'template': None, 'reference': 'mg15:03-isometric', 'spec': {'strength_max': '强'}},
            'neon': {'template': None, 'reference': None, 'spec': {}},
        }

    def plan(self, *shots):
        return {'timeline': {'fps': 30}, 'shots': list(shots)}

    def test_freedom_levels(self):
        plan = self.plan(shot('a', 'real'), shot('b', 'mg', 'whiteboard-world'), shot('c', 'mg', 'isometric'),
                         shot('d', 'mg', 'neon'), shot('e', 'three', 'neon'))
        errors, _, custom = style_tools.check_plan(plan, self.specs, 'L0', 'whiteboard-world', 'neon')
        self.assertEqual(custom, ['d', 'e'])
        self.assertTrue(any('c: L0' in e for e in errors))
        self.assertTrue(any('e: L0' in e for e in errors))
        self.assertTrue(any('c: 风格 isometric 不在' in e for e in errors))
        errors, _, _ = style_tools.check_plan(plan, self.specs, 'L1', 'whiteboard-world', 'isometric')
        self.assertFalse(any('c:' in e and 'L1' in e for e in errors))   # 有参考片源码的不算从零定制
        self.assertTrue(any('d: L1' in e for e in errors))
        errors, _, _ = style_tools.check_plan(plan, self.specs, 'L2', 'whiteboard-world', 'neon')
        self.assertTrue(any('L2 定制镜头 2 个超过两成' in e for e in errors))
        errors, _, _ = style_tools.check_plan(self.plan(*[shot(f's{i}', 'real') for i in range(8)], shot('x', 'three', 'neon')),
                                              self.specs, 'L2', 'whiteboard-world', 'neon')
        self.assertFalse(any('L2' in e for e in errors))
        errors, _, _ = style_tools.check_plan(plan, self.specs, 'L3', 'whiteboard-world', 'neon')
        self.assertFalse(any('L3' in e or 'L2' in e for e in errors))

    def test_readability_forbidden_strength(self):
        plan = self.plan(shot('t1', 'mg', 'whiteboard-world', screen_text='一二三四五六七八九十一二', duration_frames=60),
                         shot('t2', 'mg', 'whiteboard-world', screen_text='短', duration_frames=20),
                         shot('t3', 'mg', 'whiteboard-world', props={'strength': '强'}),
                         shot('t4', 'real', purpose='放一段竞品 logo'))
        errors, warnings, _ = style_tools.check_plan(plan, self.specs, 'L1', 'whiteboard-world', forbidden=['竞品'])
        self.assertTrue(any('t1' in w and '字/秒' in w for w in warnings))
        self.assertTrue(any('t2' in w and '最短停留' in w for w in warnings))
        self.assertTrue(any('t3' in w and '动作档位 强' in w for w in warnings))
        self.assertTrue(any('t4' in e and '禁用项' in e for e in errors))

    def test_cli_writes_report(self):
        with tempfile.TemporaryDirectory(prefix='xumu-style-') as tmp:
            root = Path(tmp)
            styles = root / 'styles'
            for key, spec in self.specs.items():
                (styles / key).mkdir(parents=True)
                (styles / key / 'style.json').write_text(json.dumps({'key': key, 'name': key, 'family': 'A. x', 'tags': [], **spec}), encoding='utf-8')
            edit = root / 'edit'
            edit.mkdir()
            (edit / 'visual-plan.json').write_text(json.dumps(self.plan(shot('a', 'real'), shot('b', 'mg', 'neon'))), encoding='utf-8')
            with self.assertRaises(SystemExit):
                run('check', '--edit', str(edit), '--root', str(styles), '--freedom', 'L1', '--style', 'whiteboard-world')
            report = json.loads((edit / 'verify' / 'style-check.json').read_text(encoding='utf-8'))
            self.assertFalse(report['ok'])
            self.assertTrue((edit / 'verify' / 'style-check.md').exists())
            out = run('check', '--edit', str(edit), '--root', str(styles), '--freedom', 'L3', '--style', 'neon')
            self.assertIn('通过', out)


class RecommendTests(unittest.TestCase):
    def specs(self):
        def s(key, name, family, fits, strength='中', template=None, reference=None, frame=''):
            return {'key': key, 'name': name, 'family': family, 'kind': 'style', 'fits': fits, 'look': '',
                    'template': template, 'reference': reference, 'spec': {'strength_max': strength},
                    'gallery': {'frame': frame, 'frame_kind': 'concept' if frame else '', 'sample': ''}}
        return {
            'whiteboard-world': s('whiteboard-world', '白板一镜到底', 'A. 教学', '教程、案例拆解', template='x', frame='styles/wb/concept.png'),
            'flat-diagram': s('flat-diagram', '扁平图解', 'A. 教学', '概念、机制、流程'),
            'terminal-code': s('terminal-code', '终端代码', 'C. 界面', '编程、AI 工具、开发教程'),
            'poster-colorblock': s('poster-colorblock', '海报色块', 'D. 平面', '观点冲击、口号', strength='强'),
            'neon': s('neon', '霓虹', 'G. 科技', '夜生活、娱乐', strength='强'),
            'person-in-scene': {'key': 'person-in-scene', 'kind': 'combo', 'family': 'J', 'name': '人物入景', 'spec': {}, 'gallery': {}},
        }

    def test_recommend_diversifies_by_family_and_respects_tone(self):
        picks, ranked = style_tools.recommend(self.specs(), 'AI 工具教程', tone='克制', n=3, media='/m')
        keys = [p['key'] for p in picks]
        self.assertEqual(keys[0], 'whiteboard-world')          # 教程命中 + 模板 + 有图
        self.assertEqual(len({p['family'] for p in picks}), 3)   # 三个不同大类
        self.assertNotIn('person-in-scene', [r['key'] for r in ranked])
        self.assertEqual(picks[0]['frame'].replace('\\', '/'), '/m/styles/wb/concept.png')
        neon = next(r for r in ranked if r['key'] == 'neon')
        self.assertTrue(any('比要的 克制 强' in w for w in neon['why']))
        picks, ranked = style_tools.recommend(self.specs(), 'AI 工具教程', n=3, avoid={'whiteboard-world'}, replaced={'terminal-code'})
        self.assertNotIn('whiteboard-world', [p['key'] for p in picks])
        tc = next(r for r in ranked if r['key'] == 'terminal-code')
        self.assertIn('最近刚换掉', tc['why'])
        self.assertNotIn('terminal-code', [p['key'] for p in picks])   # 刚换掉的被压到后面

    def test_recently_replaced_and_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'changelog.md'
            log.write_text('- 2026-10-27 栏目 a style.main：whiteboard-world → chalkboard（用户说）\n', encoding='utf-8')
            self.assertEqual(style_tools.recently_replaced(log), {'whiteboard-world'})
        prompt = style_tools.concept_prompt({'name': '黑板粉笔', 'look': '墨绿板面', 'signature': '粉笔描画', 'fits': '课堂感'}, '9:16')
        self.assertIn('竖屏 9:16', prompt)
        self.assertIn('墨绿板面', prompt)
        self.assertIn('无水印', prompt)

    def test_gallery_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'index.html'
            style_tools.write_gallery_html(self.specs(), Path(tmp), out)
            page = out.read_text(encoding='utf-8')
            self.assertIn('wb/concept.png', page)     # 相对索引页的路径
            self.assertEqual(style_tools.frame_path({'gallery': {'frame': 'assets/gallery/x.jpg'}}, '/m').replace('\\', '/'),
                             (style_tools.SKILL / 'assets/gallery/x.jpg').as_posix())
            self.assertIn('暂无代表帧', page)
            self.assertNotIn('person-in-scene', page)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'needs ffmpeg')
class LearnTests(unittest.TestCase):
    def test_learn_writes_refs_and_fills_spec(self):
        with tempfile.TemporaryDirectory(prefix='xumu-learn-') as tmp:
            root = Path(tmp)
            styles, media = root / 'styles', root / 'media'
            (styles / 'chalkboard').mkdir(parents=True)
            (styles / 'chalkboard' / 'style.json').write_text(json.dumps({
                'key': 'chalkboard', 'name': '黑板', 'family': 'A', 'kind': 'style', 'spec': {'palette': []}, 'gallery': {'frame': ''}}), encoding='utf-8')
            clip = root / 'ref.mp4'
            subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=4:size=320x240:rate=10',
                            '-f', 'lavfi', '-i', 'color=c=0x1F3B2E:duration=4:size=320x240:rate=10',
                            '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(clip)],
                           check=True, capture_output=True)
            out = run('learn', '--ref', str(clip), '--key', 'chalkboard', '--root', str(styles), '--media', str(media), '--keyframes', '4')
            self.assertIn('第 1 份参考', out)
            spec = json.loads((styles / 'chalkboard' / 'style.json').read_text(encoding='utf-8'))
            self.assertTrue(spec['spec']['palette'])
            self.assertEqual(spec['spec']['palette_status'], 'draft')
            self.assertEqual(spec['gallery']['frame_kind'], 'reference')
            self.assertTrue((media / spec['gallery']['frame']).exists())
            index = json.loads((media / 'styles' / 'chalkboard' / 'refs.json').read_text(encoding='utf-8'))
            self.assertEqual(len(index['refs']), 1)
            self.assertEqual(len(index['refs'][0]['keyframes']), 4)
            self.assertTrue((media / index['refs'][0]['sample']).exists())
            with self.assertRaises(SystemExit):
                run('learn', '--ref', str(clip), '--key', 'brand-new', '--root', str(styles), '--media', str(media))  # 新风格要 --title


@unittest.skipUnless(shutil.which('ffmpeg'), 'needs ffmpeg')
class FrameTests(unittest.TestCase):
    def test_palette_share(self):
        with tempfile.TemporaryDirectory(prefix='xumu-style-') as tmp:
            img = Path(tmp) / 'red.png'
            subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-y', '-f', 'lavfi', '-i', 'color=c=0xC93B3B:size=64x36:duration=0.1',
                            '-frames:v', '1', str(img)], check=True, capture_output=True)
            self.assertGreaterEqual(style_tools.frame_palette_share(img, ['#c93b3b', '#ffffff']), 0.95)
            self.assertLessEqual(style_tools.frame_palette_share(img, ['#1133aa']), 0.05)


if __name__ == '__main__':
    unittest.main()
