"""组合配方与表达指导：数据完整、检索、写进决策书第 4 格。"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import craft
import director
import style_tools


def run(module, *argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        module.main(list(argv))
    return out.getvalue()


class DataTests(unittest.TestCase):
    def test_counts_and_cross_references(self):
        recipes = craft.load('recipes')['recipes']
        expressions = craft.load('expressions')['expressions']
        self.assertEqual((len(recipes), len(expressions)), (18, 64))
        ids = {e['id'] for e in expressions}
        styles = style_tools.all_specs()
        has_opuscar = any(k.startswith('opuscar-') for k in styles)   # the free edition ships without the Opuscar packs
        for r in recipes:
            self.assertTrue(r['steps'], r['id'])
            self.assertFalse(set(r['expressions']) - ids, r['id'])
            missing = {s for s in set(r['styles']) - set(styles) if has_opuscar or not s.startswith('opuscar-')}
            self.assertFalse(missing, r['id'])
        self.assertEqual(len({e['layer'] for e in expressions}), 11)
        # 原库每条都带的两句通用免责不进序幕
        self.assertFalse(any('使用该模式不代表执行器已实现' in c for e in expressions for c in e['constraints']))


class SearchTests(unittest.TestCase):
    def test_recipe_and_expression_search(self):
        self.assertIn('data-comparison', run(craft, 'recipes', '数据', '对比').splitlines()[0])
        out = run(craft, 'search', '转场', '--limit', '3')
        self.assertEqual(len(out.splitlines()), 3)
        self.assertTrue(all('转场' in line for line in out.splitlines()))
        self.assertIn('sound.attention-mix', run(craft, 'search', '--layer', '声音'))
        shown = json.loads(run(craft, 'show', 'evidence-board-brief'))
        self.assertEqual((shown['type'], len(shown['steps'])), ('recipe', 6))


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xumu-craft-')
        self.addCleanup(self.temp.cleanup)
        ws = Path(self.temp.name)
        self.edit = ws / 'outputs' / 'demo' / 'edit'
        self.edit.mkdir(parents=True)
        director.ffprobe_facts = lambda path: None
        run(director, 'init', '--workspace', str(ws), '--name', '测试频道')
        run(director, 'propose', '--edit', str(self.edit), '--channel', str(ws / 'channel'), '--no-default-series')

    def doc(self):
        return json.loads((self.edit / 'director.json').read_text(encoding='utf-8'))

    def test_suggest_reads_promise(self):
        doc = self.doc()
        doc['grids']['3']['promise'] = '把一个抽象概念分层讲清'
        (self.edit / 'director.json').write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
        self.assertEqual(craft.suggest(self.doc())[0][1]['id'], 'layered-concept-reveal')

    def test_apply_drafts_storyline_once(self):
        out = run(craft, 'apply', 'evidence-board-brief', '--edit', str(self.edit))
        self.assertIn('起了故事线草稿', out)
        g4 = self.doc()['grids']['4']
        self.assertEqual(g4['recipe']['id'], 'evidence-board-brief')
        self.assertEqual([s['beat'] for s in g4['storyline']], ['铺垫', '证据', '证据', '证据', '高点', '落点'])
        self.assertIn('证据板讲清资讯', (self.edit / '创作决策书.md').read_text(encoding='utf-8'))
        self.assertEqual(director.validate(self.doc(), False), [])
        g4['storyline'] = [{'id': 'a', 'goal': '用户自己排的'}]
        doc = self.doc()
        doc['grids']['4'] = g4
        (self.edit / 'director.json').write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
        self.assertIn('未改', run(craft, 'apply', 'data-comparison', '--edit', str(self.edit)))
        self.assertEqual(self.doc()['grids']['4']['storyline'], [{'id': 'a', 'goal': '用户自己排的'}])
        with self.assertRaises(SystemExit):
            run(craft, 'apply', 'no-such-recipe', '--edit', str(self.edit))


if __name__ == '__main__':
    unittest.main()
