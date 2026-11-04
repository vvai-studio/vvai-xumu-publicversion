"""三层档案与创作决策书的结构行为；不涉及真实媒体。"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import director
from director import main


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        main(list(argv))
    return out.getvalue()


class DirectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xumu-director-')
        self.ws = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.channel = self.ws / 'channel'
        self.edit = self.ws / 'outputs' / 'demo' / 'edit'
        self.edit.mkdir(parents=True)
        (self.ws / 'talk.mp4').write_bytes(b'not real media')
        (self.ws / 'script.md').write_text('# 文案', encoding='utf-8')
        # 没有 ffprobe 也要能清点
        director.ffprobe_facts = lambda path: None
        run('init', '--workspace', str(self.ws), '--name', '测试频道', '--platform', '抖音')
        run('series', 'add', '--channel', str(self.channel), '--key', 'ai-tutorial', '--title', 'AI 工具教程',
            '--spine', 'narration', '--style', 'whiteboard-world')

    def doc(self):
        return json.loads((self.edit / 'director.json').read_text(encoding='utf-8'))

    def test_init_and_series(self):
        brand = json.loads((self.channel / 'brand.json').read_text(encoding='utf-8'))
        self.assertEqual(brand['name'], '测试频道')
        self.assertEqual(brand['platforms'], ['抖音'])
        series = json.loads((self.channel / 'series' / 'ai-tutorial.json').read_text(encoding='utf-8'))
        self.assertEqual(series['style']['main'], 'whiteboard-world')
        self.assertIn('新建栏目 ai-tutorial', (self.channel / 'changelog.md').read_text(encoding='utf-8'))
        self.assertIn('ai-tutorial', run('series', 'list', '--channel', str(self.channel)))
        with self.assertRaises(SystemExit):
            run('init', '--workspace', str(self.ws))

    def test_series_copy(self):
        run('series', 'add', '--channel', str(self.channel), '--key', 'vlog', '--title', '周末记录',
            '--copy-from', 'ai-tutorial', '--spine', 'storyline')
        copied = json.loads((self.channel / 'series' / 'vlog.json').read_text(encoding='utf-8'))
        self.assertEqual(copied['spine']['kind'], 'storyline')
        self.assertEqual(copied['style']['main'], 'whiteboard-world')

    def test_propose_inherits_and_inventories(self):
        out = run('propose', '--edit', str(self.edit), '--channel', str(self.channel),
                  '--inputs', str(self.ws / 'talk.mp4'), str(self.ws / 'script.md'), '--first-time')
        self.assertIn('决策书草稿已写', out)
        doc = self.doc()
        self.assertEqual(doc['series'], 'ai-tutorial')
        self.assertEqual(doc['mode'], 'full-auto')
        self.assertEqual(doc['grids']['0']['series_action'], 'reuse')
        self.assertEqual(doc['grids']['6']['style_choice'], 'whiteboard-world')
        self.assertEqual(doc['grids']['2']['spine']['kind'], 'narration')
        kinds = sorted(i['kind'] for i in doc['grids']['1']['inputs'])
        self.assertEqual(kinds, ['media', 'text'])
        md = (self.edit / '创作决策书.md').read_text(encoding='utf-8')
        self.assertIn('当前模式', md)
        self.assertIn('全托', md)
        self.assertIn('## 编剧页', md)
        self.assertIn('## 导演页', md)

    def test_no_series_means_new(self):
        run('propose', '--edit', str(self.edit), '--channel', str(self.channel), '--no-default-series')
        doc = self.doc()
        self.assertIsNone(doc['series'])
        self.assertEqual(doc['grids']['0']['series_action'], 'new')
        self.assertEqual(doc['mode'], 'semi')

    def filled_draft(self):
        return {
            'grids': {
                '2': {'spine': {'kind': 'narration', 'source': 'talk.mp4', 'reason': '口播已经把结构说清'}},
                '3': {'promise': '三步学会用 X 剪视频'},
                '4': {'storyline': [
                    {'id': 'S1', 'goal': '引出问题', 'source_refs': ['talk.mp4#0:00-0:20'], 'beat': '铺垫', 'est_duration': 20},
                    {'id': 'S2', 'goal': '演示三步', 'source_refs': ['talk.mp4#0:20-2:00'], 'beat': '证据', 'est_duration': 100},
                ]},
                '5': {'must_keep': ['三步演示'], 'cut_candidates': ['开头寒暄'], 'opener': 'S1', 'target_duration': 150},
                '7': {'visual_tier': 'full', 'visual_ratio': {'person': 0.3, 'real': 0.5, 'animation': 0.2},
                      'evidence_segments': ['S2']},
                '9': {'freedom': 'L1'},
            },
            'reasons': ['栏目已定白板，沿用'],
        }

    def test_visual_tier_required_before_merge(self):
        run('propose', '--edit', str(self.edit), '--channel', str(self.channel), '--inputs', str(self.ws / 'talk.mp4'))
        self.assertIn('还没定', (self.edit / '创作决策书.md').read_text(encoding='utf-8'))
        draft = self.filled_draft()
        draft['grids']['7']['visual_tier'] = ''
        path = self.ws / 'draft.json'
        path.write_text(json.dumps(draft, ensure_ascii=False), encoding='utf-8')
        run('update', '--edit', str(self.edit), '--from', str(path))
        run('confirm', '--edit', str(self.edit), '--all')
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            main(['check', '--edit', str(self.edit), '--ready'])
        self.assertIn('visual_tier', out.getvalue())
        doc = self.doc()
        doc['grids']['7']['visual_tier'] = '精做'
        (self.edit / 'director.json').write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            main(['check', '--edit', str(self.edit)])
        self.assertIn('plain', out.getvalue())

    def test_propose_tier_flag(self):
        run('propose', '--edit', str(self.edit), '--channel', str(self.channel), '--tier', 'plain')
        self.assertEqual(self.doc()['grids']['7']['visual_tier'], 'plain')
        self.assertIn('素剪', (self.edit / '创作决策书.md').read_text(encoding='utf-8'))

    def test_update_check_confirm_merge(self):
        run('propose', '--edit', str(self.edit), '--channel', str(self.channel), '--inputs', str(self.ws / 'talk.mp4'))
        draft = self.ws / 'draft.json'
        draft.write_text(json.dumps(self.filled_draft(), ensure_ascii=False), encoding='utf-8')
        run('update', '--edit', str(self.edit), '--from', str(draft))
        self.assertEqual(self.doc()['version'], 2)
        run('check', '--edit', str(self.edit))
        with self.assertRaises(SystemExit):
            run('check', '--edit', str(self.edit), '--ready')  # 还没确认
        with self.assertRaises(SystemExit):
            run('merge', '--edit', str(self.edit))
        run('merge', '--edit', str(self.edit), '--draft')  # 草稿可以先写
        run('confirm', '--edit', str(self.edit), '--grids', '0,4,6')
        self.assertIsNone(self.doc()['confirmed_at'])
        run('confirm', '--edit', str(self.edit), '--all', '--mode', 'full-auto')
        doc = self.doc()
        self.assertIsNotNone(doc['confirmed_at'])
        self.assertEqual(doc['grids']['9']['mode'], 'full-auto')
        self.assertIn('可以合并', run('check', '--edit', str(self.edit), '--ready'))
        run('merge', '--edit', str(self.edit))
        project = (self.edit / 'project.md').read_text(encoding='utf-8')
        self.assertIn('## 制作定位', project)
        self.assertIn('| 一句话 | 三步学会用 X 剪视频 | 本片 | 已确认 |', project)
        # 和栏目一样的值标为栏目继承，但带本片的确认状态；本片改过的才标本片
        self.assertIn('| 主风格 | whiteboard-world | 栏目 | 已确认 |', project)
        self.assertIn('| 画面比例 | person 0.3；real 0.5；animation 0.2；strong_motion opener | 本片 | 已确认 |', project)
        self.assertIn('| 画面档位 | full | 本片 | 已确认 |', project)
        self.assertIn('| 旁白 | original | 品牌 | 已确认 |', project)
        self.assertIn('| 品牌色 | 待定 | 待定 |  |', project)
        self.assertIn('| 受众与目的 | 待定 | 待定 |  |', project)
        self.assertIn('S2 证据：演示三步', project)
        self.assertEqual(project.count(director.BEGIN), 1)
        # 再合并一次只替换标记之间的内容
        run('merge', '--edit', str(self.edit))
        self.assertEqual((self.edit / 'project.md').read_text(encoding='utf-8').count(director.BEGIN), 1)

    def test_merge_keeps_other_sections(self):
        run('propose', '--edit', str(self.edit), '--channel', str(self.channel))
        (self.edit / 'project.md').write_text('# demo\n\n## 进度\n\n- 还没开始\n', encoding='utf-8')
        run('merge', '--edit', str(self.edit), '--draft')
        project = (self.edit / 'project.md').read_text(encoding='utf-8')
        self.assertIn('## 进度', project)
        self.assertIn('## 制作定位', project)
        self.assertIn('未全部确认', project)

    def test_inventory_and_spine_suggestion(self):
        run('propose', '--edit', str(self.edit), '--channel', str(self.channel), '--no-default-series')
        (self.ws / 'a.jpg').write_bytes(b'x')
        (self.ws / 'b.png').write_bytes(b'x')
        out = run('inventory', '--edit', str(self.edit), '--inputs', str(self.ws / 'a.jpg'), str(self.ws / 'b.png'))
        self.assertIn('照片 2', out)
        self.assertEqual(self.doc()['grids']['2']['spine']['kind'], 'storyline')
        out = run('inventory', '--edit', str(self.edit), '--inputs', str(self.ws / 'script.md'))
        self.assertIn('脊梁建议：script', out)
        # 没有 ffprobe 时视频算 media，按无声画面处理；有 ffprobe 的机器上会识别出讲话
        profile = director.input_profile([{'kind': 'video'}, {'kind': 'image'}])
        self.assertEqual(director.suggest_spine(profile)[0], 'narration')
        profile = director.input_profile([{'kind': 'video', 'speech_ratio': 0.1}, {'kind': 'image'}])
        self.assertEqual(director.suggest_spine(profile)[0], 'storyline')

    def test_still_stays_an_image(self):
        # ffprobe 把静态图读成一帧视频：必须仍归为 image，保留尺寸，不带时长
        png = self.ws / 'shot.png'
        png.write_bytes(b'x')
        facts = {'has_video': True, 'has_audio': False, 'duration_s': 0.04, 'width': 320, 'height': 240}
        with mock.patch.object(director, 'ffprobe_facts', lambda path: facts):
            item = director.inventory([png])[0]
        self.assertEqual(item['kind'], 'image')
        self.assertEqual((item['width'], item['height']), (320, 240))
        self.assertNotIn('duration_s', item)
        self.assertNotIn('has_video', item)
        self.assertEqual(director.input_profile([item])['images'], 1)

    def test_classify(self):
        run('series', 'add', '--channel', str(self.channel), '--key', 'weekend', '--title', '周末记录',
            '--spine', 'storyline', '--from', str(self.write_json({'description': '周末出门拍的生活片段'})))
        run('propose', '--edit', str(self.edit), '--channel', str(self.channel), '--no-default-series')
        out = run('classify', '--edit', str(self.edit), '--describe', '这期是 AI 工具的教程')
        self.assertIn('ai-tutorial', out.splitlines()[0])
        run('classify', '--edit', str(self.edit), '--describe', '周末出门拍的片段', '--apply')
        doc = self.doc()
        self.assertEqual(doc['series'], 'weekend')
        self.assertEqual(doc['grids']['0']['series_action'], 'reuse')
        # 没有任何依据时建议新建
        run('classify', '--edit', str(self.edit), '--apply')
        self.assertEqual(self.doc()['grids']['0']['series_action'], 'new')

    def write_json(self, data):
        path = self.ws / f'tmp-{len(data)}.json'
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return path

    def test_change_scopes(self):
        run('propose', '--edit', str(self.edit), '--channel', str(self.channel))
        # 只这一期
        run('change', '--edit', str(self.edit), '--scope', 'one-off', '--set', 'style.main=chalkboard', '--set', 'edit_policy.cut=tight')
        doc = self.doc()
        self.assertEqual(doc['grids']['6']['style_choice'], 'chalkboard')
        self.assertEqual(doc['grids']['6']['status'], 'edited')
        self.assertEqual(doc['overrides']['series']['edit_policy.cut'], 'tight')
        series = json.loads((self.channel / 'series' / 'ai-tutorial.json').read_text(encoding='utf-8'))
        self.assertEqual(series['style']['main'], 'whiteboard-world')
        run('merge', '--edit', str(self.edit), '--draft')
        project = (self.edit / 'project.md').read_text(encoding='utf-8')
        self.assertIn('| 剪辑尺度 | tight | 本片 | 已改 |', project)  # 一次性改动算本片
        self.assertIn('| 主风格 | chalkboard | 本片 | 已改 |', project)
        self.assertIn('| 风格强度 | 中 | 栏目 | 继承 |', project)  # 没改的仍是栏目
        # 以后都这样
        run('change', '--edit', str(self.edit), '--scope', 'series', '--set', 'style.main=chalkboard', '--reason', '用户说以后都用黑板')
        series = json.loads((self.channel / 'series' / 'ai-tutorial.json').read_text(encoding='utf-8'))
        self.assertEqual(series['style']['main'], 'chalkboard')
        log = (self.channel / 'changelog.md').read_text(encoding='utf-8')
        self.assertIn('栏目 ai-tutorial style.main：whiteboard-world → chalkboard（用户说以后都用黑板）', log)
        # 新开栏目
        run('change', '--edit', str(self.edit), '--scope', 'new-series', '--new-key', 'ai-news', '--title', 'AI 快讯',
            '--set', 'duration.target_s=[40,60]')
        doc = self.doc()
        self.assertEqual(doc['series'], 'ai-news')
        self.assertEqual(doc['grids']['0']['series_action'], 'new')
        new = json.loads((self.channel / 'series' / 'ai-news.json').read_text(encoding='utf-8'))
        self.assertEqual(new['duration']['target_s'], [40, 60])
        self.assertEqual(new['style']['main'], 'chalkboard')  # 复制自改过的旧栏目
        # 品牌层
        run('change', '--edit', str(self.edit), '--scope', 'brand', '--set', 'palette.primary=#112233')
        brand = json.loads((self.channel / 'brand.json').read_text(encoding='utf-8'))
        self.assertEqual(brand['palette']['primary'], '#112233')
        self.assertIn('品牌层 palette.primary', (self.channel / 'changelog.md').read_text(encoding='utf-8'))
        with self.assertRaises(SystemExit):
            run('change', '--edit', str(self.edit), '--scope', 'series', '--layer', 'brand', '--set', 'name=x')

    def test_reference_entry(self):
        run('propose', '--edit', str(self.edit), '--channel', str(self.channel))
        run('reference', '--edit', str(self.edit), '--ref', 'https://example.com/v/1', '--style-key', 'chalkboard', '--notes', '比目录更粗的粉笔')
        doc = self.doc()
        self.assertEqual(doc['grids']['6']['style_choice'], 'chalkboard')
        self.assertEqual(len(doc['grids']['6']['style_options']), 1)
        self.assertEqual(doc['grids']['6']['style_notes'], '比目录更粗的粉笔')
        assets = json.loads((self.edit / 'assets.json').read_text(encoding='utf-8'))
        self.assertEqual(assets['sources'][0]['kind'], 'style-reference')
        with self.assertRaises(SystemExit):
            run('reference', '--edit', str(self.edit), '--ref', str(self.ws / 'missing.mp4'))

    def test_gates_follow_mode(self):
        run('propose', '--edit', str(self.edit), '--channel', str(self.channel), '--first-time')
        out = run('gates', '--edit', str(self.edit))
        self.assertIn('还要过：reference-clip', out)
        self.assertNotIn('还要过：edit-strategy', out)
        run('confirm', '--edit', str(self.edit), '--all', '--mode', 'pro')
        out = run('gates', '--edit', str(self.edit))
        self.assertIn('还要过：edit-strategy、listen、visual-plan、reference-clip、delivery', out)
        run('gate', 'pass', 'edit-strategy', '--edit', str(self.edit))
        with self.assertRaises(SystemExit):
            run('gate', 'skip', 'listen', '--edit', str(self.edit))  # 跳过要理由
        run('gate', 'skip', 'listen', '--edit', str(self.edit), '--note', '总控自己能听')
        doc = self.doc()
        self.assertEqual(doc['gates']['edit-strategy']['status'], 'passed')
        self.assertEqual(doc['gates']['listen']['note'], '总控自己能听')
        self.assertIn('还要过：visual-plan、reference-clip、delivery', run('gates', '--edit', str(self.edit)))
        md = (self.edit / '创作决策书.md').read_text(encoding='utf-8')
        self.assertIn('✓ 剪辑与旁白策略', md)
        run('merge', '--edit', str(self.edit), '--draft')
        self.assertIn('确认点：✓ 剪辑与旁白策略；– 剪点试听合集；○ 画面方案', (self.edit / 'project.md').read_text(encoding='utf-8'))

    def test_migrate_old_project(self):
        (self.edit / 'project.md').write_text(
            '# 旧片\n\n## 制作定位\n\n- 平台：B站 横屏\n- 风格：whiteboard-world，克制\n\n| 项 | 值 |\n|---|---|\n| 时长 | 3 分钟 |\n\n## 进度\n\n- 做完了\n',
            encoding='utf-8')
        out = run('migrate', '--edit', str(self.edit), '--channel', str(self.channel), '--series', 'ai-tutorial')
        self.assertIn('标 migrated', out)
        doc = self.doc()
        self.assertEqual(doc['migrated']['hints']['平台'], 'B站 横屏')
        self.assertEqual(doc['migrated']['hints']['时长'], '3 分钟')
        self.assertEqual(doc['series'], 'ai-tutorial')
        self.assertEqual(doc['mode'], 'semi')
        self.assertIn('## 迁移自旧项目', (self.edit / '创作决策书.md').read_text(encoding='utf-8'))
        with self.assertRaises(SystemExit):
            run('migrate', '--edit', str(self.edit), '--channel', str(self.channel))  # 已有决策书
        # 用户说不建档
        other = self.ws / 'outputs' / 'old2' / 'edit'
        other.mkdir(parents=True)
        (other / 'project.md').write_text('# 旧片2\n\n## 制作定位\n\n随便写的\n', encoding='utf-8')
        run('migrate', '--edit', str(other), '--skip')
        self.assertTrue((other / 'project.md').read_text(encoding='utf-8').startswith(director.SKIP_MARK))
        with self.assertRaises(SystemExit):
            run('migrate', '--edit', str(other), '--channel', str(self.channel))
        self.assertFalse((other / 'director.json').exists())

    def test_validate_rejects_bad_values(self):
        run('propose', '--edit', str(self.edit), '--channel', str(self.channel))
        doc = self.doc()
        doc['grids']['9']['freedom'] = 'L9'
        doc['grids']['0']['series_action'] = 'maybe'
        errors = director.validate(doc)
        self.assertTrue(any('freedom' in e for e in errors))
        self.assertTrue(any('series_action' in e for e in errors))


if __name__ == '__main__':
    unittest.main()
