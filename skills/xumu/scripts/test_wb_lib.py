"""Tests of the whiteboard-world role animation helpers (no HyperFrames needed)."""
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'assets' / 'templates' / 'whiteboard-world'))
from wb_lib import ICONS, ROLE_RECIPES, Comp, recipe_beats  # noqa: E402


def draw_times(comp):
    return [float(m) for line in comp.js for m in re.findall(r'^draw\("#p\d+", ([\d.]+)', line)]


class RoleSceneTests(unittest.TestCase):
    def setUp(self):
        self.c = Comp('unused', total=20.0)
        self.c.new_world()

    def test_every_icon_makes_a_path(self):
        for name, fn in ICONS.items():
            d = fn(100, 200, 220)
            self.assertTrue(d.startswith('M '), name)
            self.assertNotIn('nan', d, name)

    def test_recipes_only_use_known_icons(self):
        for recipe, steps in ROLE_RECIPES.items():
            for icon, label in steps:
                self.assertIn(icon, ICONS, recipe)
                self.assertTrue(label, recipe)

    def test_scene_draws_one_icon_per_beat_in_order(self):
        beats = recipe_beats('research', [3.0, 4.2, 5.0])
        parts = self.c.role_scene(160, 200, '调研', 1.0, beats, sub='先把情况调查清楚')
        html = ''.join(parts)
        self.assertIn('调研', html)
        self.assertIn('市场', html)
        self.assertNotIn('上网搜索', html)   # only as many steps as times given
        # head underline + three icons, drawn in time order
        times = draw_times(self.c)
        self.assertEqual(len(times), 4)
        self.assertEqual(times, sorted(times))
        self.assertEqual(times[1:], [3.0, 4.2, 5.0])

    def test_unfinished_result_is_a_red_label(self):
        parts = self.c.role_scene(0, 0, '数据分析', 1.0, [(2.0, 'bars', '这次还没跑', 'red')])
        html = ''.join(parts)
        self.assertRegex(html, r'class="hand-t red"[^>]*>这次还没跑')
        self.assertIn('class="k red"', html)

    def test_custom_icon_callable(self):
        parts = self.c.role_scene(0, 0, 'X', 1.0, [(2.0, lambda x, y, s: f'M {x} {y} L {x+s} {y}')])
        self.assertIn('M 0 300 L 220 300', ''.join(parts))

    def test_rejects_out_of_order_and_unknown(self):
        with self.assertRaises(ValueError):
            self.c.role_scene(0, 0, 'X', 1.0, [(3.0, 'doc'), (2.0, 'doc')])
        with self.assertRaises(ValueError):
            self.c.role_scene(0, 0, 'X', 1.0, [(2.0, 'rocket')])
        with self.assertRaises(ValueError):
            recipe_beats('planner', [1, 2, 3, 4])


if __name__ == '__main__':
    unittest.main()
