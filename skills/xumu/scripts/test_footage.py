"""剪素材链：纯逻辑部分不需要 ffmpeg；带 ffmpeg 的用合成视频跑整条链。"""
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import footage
from footage import main
import cue


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        main(list(argv))
    return out.getvalue()


def shot(sid, file, start, end, score, **kw):
    base = {'id': sid, 'file': file, 'start': start, 'end': end, 'duration': end - start, 'score': score,
            'flags': [], 'luma': 120, 'bright': 0, 'sharp': 5, 'motion': 2, 'motion_var': 1, 'voiced': None, 'faces': None, 'thumb': ''}
    base.update(kw)
    return base


class LogicTests(unittest.TestCase):
    def test_split_shots_merges_fragments(self):
        self.assertEqual(footage.split_shots(10.0, [3.0, 3.4, 7.0], 1.0), [(0.0, 3.0), (3.0, 7.0), (7.0, 10.0)])
        self.assertEqual(footage.split_shots(5.0, [], 1.0), [(0.0, 5.0)])
        self.assertEqual(footage.split_shots(5.0, [12.0], 1.0), [(0.0, 5.0)])  # 越界的切点忽略

    def test_score_flags(self):
        good = {'luma': 120, 'bright': 0.0, 'sharp': 6.0, 'motion': 2.0, 'motion_var': 3.0, 'duration': 4.0, 'voiced': 0.8}
        score, flags = footage.score_shot(good, 6.0)
        self.assertEqual(score, 100)
        self.assertEqual(flags, ['有声'])
        bad = dict(good, luma=20, sharp=1.0, motion_var=90, duration=1.0, voiced=None)
        score, flags = footage.score_shot(bad, 6.0)
        self.assertEqual(score, 100 - 30 - 20 - 15 - 10)
        self.assertEqual(flags, ['过暗', '偏糊', '抖/乱', '太短'])

    def test_voiced_ratio(self):
        spans = [(1.0, 2.0), (3.5, float('inf'))]
        self.assertEqual(footage.voiced_ratio(spans, 0.0, 4.0), 0.62)
        self.assertEqual(footage.voiced_ratio([], 0.0, 4.0), 1.0)

    def test_pick_fills_segments_in_score_then_time_order(self):
        shots = [shot('c0101', 'a.mp4', 0, 8, 90), shot('c0102', 'a.mp4', 8, 12, 40), shot('c0103', 'a.mp4', 12, 20, 80),
                 shot('c0201', 'b.mp4', 0, 5, 95)]
        segs = [{'id': 'S1', 'goal': '开场', 'refs': ['b.mp4'], 'seconds': 4},
                {'id': 'S2', 'goal': '主体', 'refs': [], 'seconds': 10}]
        picks = footage.pick(shots, segs, max_shot=6, min_score=50)
        self.assertEqual([c['id'] for c in picks[0]['clips']], ['c0201'])          # 点名文件
        self.assertEqual([c['id'] for c in picks[1]['clips']], ['c0101', 'c0103'])  # 40 分的被排除，按时间顺序
        self.assertEqual(picks[1]['total_s'], 12.0)
        self.assertEqual(picks[1]['short_by_s'], 0)
        # 点名镜头 id
        picks = footage.pick(shots, [{'id': 'X', 'refs': ['c0102'], 'seconds': 2}], 6, 0)
        self.assertEqual([c['id'] for c in picks[0]['clips']], ['c0102'])

    def test_pick_snaps_to_beats(self):
        shots = [shot('c0101', 'a.mp4', 0, 10, 90)]
        picks = footage.pick(shots, [{'id': 'S1', 'refs': [], 'seconds': 5}], max_shot=5.3, min_score=0, period=0.5)
        self.assertEqual(picks[0]['clips'][0]['dur'], 5.5)

    def test_estimate_beats_on_synthetic_clicks(self):
        import numpy as np
        rate, period = 22050, 0.5          # 120 BPM
        t = np.arange(0, 8, 1 / rate)
        samples = np.zeros_like(t, dtype=np.float32)
        for k in np.arange(0, 8, period):
            i = int(k * rate)
            samples[i:i + 400] = np.sin(2 * np.pi * 1000 * t[:400]) * 0.8
        bpm, times = footage.estimate_beats(samples, rate)
        self.assertAlmostEqual(bpm, 120, delta=2)      # 周期跨在两个整数帧之间，靠抛物线插值逼近
        self.assertGreaterEqual(len(times), 15)
        self.assertLess(abs(times[1] - times[0] - period), 0.02)


class CueAnchorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xumu-cue-')
        self.edit = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        (self.edit / 'edl_footage.json').write_text(json.dumps({'fps': 30, 'clips': [
            {'id': 'c0101', 'segment': 'S1', 'file': 'a.mp4', 'in': 0.2, 'out': 4.2, 'start': 0.0, 'end': 4.0},
            {'id': 'c0201', 'segment': 'S2', 'file': 'b.mp4', 'in': 1.0, 'out': 4.0, 'start': 4.0, 'end': 7.0}]}), encoding='utf-8')
        (self.edit / 'beats.json').write_text(json.dumps({'bpm': 120, 'period': 0.5, 'times': [0.1, 0.6, 1.1, 1.6, 2.1]}), encoding='utf-8')

    def test_clip_and_beat_anchors_without_narration(self):
        timing = cue.Timing(self.edit)
        self.assertEqual(timing.seconds({'clip': 'c0201'}), 4.0)
        self.assertEqual(timing.seconds({'clip': 'c0101', 'edge': 'end', 'offset': -0.5}), 3.5)
        self.assertEqual(timing.frame({'beat': 2}), 33)
        self.assertEqual(timing.seconds({'beat_near': 1.5}), 1.6)
        self.assertEqual(timing.total(), 7.0)
        with self.assertRaises(ValueError):
            timing.seconds({'clip': 'nope'})
        with self.assertRaises(ValueError):
            timing.seconds({'beat': 99})

    def test_nothing_to_anchor(self):
        empty = Path(self.temp.name) / 'empty'
        empty.mkdir()
        with self.assertRaises(ValueError):
            cue.Timing(empty)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'needs ffmpeg')
class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xumu-footage-')
        self.ws = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.edit = self.ws / 'edit'
        self.edit.mkdir()
        self.clip = self.ws / 'clip.mp4'
        # 3 秒动态测试图 + 3 秒静止彩条，中间一个硬切；带 440Hz 音
        subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-y',
                        '-f', 'lavfi', '-i', 'testsrc=duration=3:size=320x240:rate=10',
                        '-f', 'lavfi', '-i', 'smptebars=duration=3:size=320x240:rate=10',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=6',
                        '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]', '-map', '2:a',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(self.clip)],
                       check=True, capture_output=True)

    def test_scan_select_render_and_cue(self):
        out = run('scan', '--edit', str(self.edit), '--inputs', str(self.clip))
        self.assertIn('1 个文件', out)
        scan = json.loads((self.edit / 'footage' / 'scan.json').read_text(encoding='utf-8'))
        shots = scan['files'][0]['shots']
        self.assertEqual(len(shots), 2)
        self.assertAlmostEqual(shots[1]['start'], 3.0, delta=0.3)
        self.assertIn('几乎静止', shots[1]['flags'])       # 彩条不动
        self.assertNotIn('抖/乱', shots[1]['flags'])       # 切点那一帧的跳变不算抖
        self.assertTrue((self.edit / 'footage' / 'scan.html').exists())
        self.assertTrue((self.edit / 'footage' / 'thumbs' / f'{shots[0]["id"]}.jpg').exists())
        self.assertIsNotNone(shots[0]['voiced'])
        out = run('select', '--edit', str(self.edit), '--total', '4', '--max-shot', '2', '--min-score', '0')
        picks = json.loads((self.edit / 'footage' / 'picks.json').read_text(encoding='utf-8'))
        self.assertEqual(len(picks[0]['clips']), 2)
        run('render', '--edit', str(self.edit), '--size', '240x240', '--fps', '10')
        video = self.edit / 'build' / '粗剪_预览.mp4'
        self.assertTrue(video.exists())
        edl = json.loads((self.edit / 'edl_footage.json').read_text(encoding='utf-8'))
        self.assertEqual(edl['clips'][1]['start'], edl['clips'][0]['end'])
        timing = cue.Timing(self.edit)
        self.assertEqual(timing.seconds({'clip': edl['clips'][1]['id']}), edl['clips'][1]['start'])
        # 节拍：440Hz 连续音没有起音，不应崩；用 beep 流测 bpm
        beep = self.ws / 'beep.wav'
        subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-y', '-f', 'lavfi', '-i', 'sine=frequency=800:beep_factor=4:duration=8', str(beep)],
                       check=True, capture_output=True)
        out = run('beats', '--edit', str(self.edit), '--music', str(beep))
        beats = json.loads((self.edit / 'beats.json').read_text(encoding='utf-8'))
        self.assertIn(round(beats['bpm']), (60, 120, 180))
        run('select', '--edit', str(self.edit), '--total', '4', '--max-shot', '2', '--min-score', '0', '--music')
        picks = json.loads((self.edit / 'footage' / 'picks.json').read_text(encoding='utf-8'))
        for c in picks[0]['clips']:
            self.assertAlmostEqual(c['dur'] / beats['period'], round(c['dur'] / beats['period']), places=2)


if __name__ == '__main__':
    unittest.main()
