"""Behavioral tests of motion_index: mg-styles-15 prompt parsing, index build and Chinese search."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

import motion_index
from motion_index import build, frames, search, split_title

PROMPT = '''# 测试贴纸风 2.5D Test Sticker / 2.5D

**原片**：示例片「一张贴纸」 · 1080×1920 · 30 fps · 10 秒 · AI 评审终评 7.50 / 10

## 提示词

```text
You are the director.

# Style
测试贴纸风 2.5D Test Sticker / 2.5D

# Output (fixed)
- 1080×1920, 30 fps, exactly 10.000 s, H.264 MP4 with stereo AAC audio (48 kHz), mastered to −14 LUFS integrated,
  true peak ≤ −1 dBTP. Final file: video.mp4.

# Suggested technical route
HTML: SVG stickers with a white outline on a large canvas
(You may choose a better route if it clearly raises quality; say why.)

# Creative seed
A sticker lands.

# Signature features and key techniques (the result is judged against these)
知识区常见的贴纸包装。
视觉特征 照片贴纸化, 冷静底色, 大画布运镜
关键技法 抠图后加 10px 白描边
镜头沿长缓动曲线平移

# How to work
1. Treatment.
```
'''


class SplitTitleTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(split_title('液态流动 Liquid Motion'), ('液态流动', 'Liquid Motion'))

    def test_bracket_and_latin_inside_chinese_name(self):
        self.assertEqual(split_title('复古系（80s Synthwave / Y2K 千禧） Retro: 80s Synthwave'),
                         ('复古系（80s Synthwave / Y2K 千禧）', 'Retro: 80s Synthwave'))

    def test_acronyms_repeated_in_english_stay_with_chinese(self):
        self.assertEqual(split_title('等轴 2.5D Isometric / 2.5D'), ('等轴 2.5D', 'Isometric / 2.5D'))
        self.assertEqual(split_title('赛博朋克 HUD / FUI Cyberpunk HUD / FUI (Fictional UI)'),
                         ('赛博朋克 HUD / FUI', 'Cyberpunk HUD / FUI (Fictional UI)'))

    def test_english_words_are_not_moved(self):
        self.assertEqual(split_title('线条动画 Line Art / Line Animation'), ('线条动画', 'Line Art / Line Animation'))


class Mg15IndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xumu-mg15-test-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / 'prompts').mkdir()
        (root / 'prompts' / '99-sticker.md').write_text(PROMPT, encoding='utf-8')
        self.index = build(None, None, root)

    def test_entry_carries_signature_features_route_and_links(self):
        self.assertEqual(self.index['counts']['mg-styles-15'], 1)
        e = self.index['entries'][0]
        self.assertEqual(e['id'], 'mg15:99-sticker')
        self.assertEqual((e['name_local'], e['name']), ('测试贴纸风 2.5D', 'Test Sticker / 2.5D'))
        self.assertEqual(e['tags'], ['照片贴纸化', '冷静底色', '大画布运镜'])
        self.assertEqual(e['techniques'], ['抠图后加 10px 白描边', '镜头沿长缓动曲线平移'])
        self.assertEqual(e['summary'], '知识区常见的贴纸包装。')
        self.assertTrue(e['route'].startswith('HTML: SVG stickers'))
        self.assertNotIn('You may choose', e['route'])
        self.assertTrue(e['output'].startswith('1080×1920'))
        self.assertIn('1080×1920', e['film'])
        self.assertTrue(e['preview_url'].endswith('#99-sticker'))
        self.assertTrue(e['source_dir'].endswith('99-sticker'))

    def test_two_character_chinese_terms_match_inside_text(self):
        hits = search(self.index, ['贴纸'])
        self.assertEqual(hits[0]['id'], 'mg15:99-sticker')
        self.assertEqual(search(self.index, ['白描边'])[0]['id'], 'mg15:99-sticker')
        self.assertEqual(search(self.index, ['水墨']), [])


OPUS_STYLE = '''# Test Ink — Style Prompt

> Ink on rice paper, animated: one brushstroke is a mountain.

## 1. Essence, and what it is not

Brush first.

## 8. Native moves (and how they are built)

- **One stroke is everything.** *Fits content like:* a product born from one line.
| **Ink bloom** | `ink.js`: bloom |

## 9. Material

- **Not a move.** paper grain
'''


class OpusIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xumu-opus-test-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for slug in ('test-ink', '_template'):
            folder = root / 'styles' / slug
            folder.mkdir(parents=True)
            (folder / 'STYLE.md').write_text(OPUS_STYLE, encoding='utf-8')
            (folder / 'style.json').write_text(json.dumps({'slug': slug, 'en': 'Test Ink', 'cn': '测试水墨',
                                                           'category_cn': '手绘与绘画', 'uses': ['Poetry']}), encoding='utf-8')
        self.index = build(None, None, None, root)

    def test_entry_maps_to_style_key_and_lists_native_moves(self):
        self.assertEqual(self.index['counts']['lemo-opuscar'], 1)      # _template is skipped
        e = self.index['entries'][0]
        self.assertEqual((e['id'], e['style_key'], e['name_local']), ('opus:test-ink', 'opuscar-test-ink', '测试水墨'))
        self.assertEqual(e['tags'], ['One stroke is everything', 'Ink bloom'])
        self.assertEqual(e['techniques'][:2], ['Essence, and what it is not', 'Native moves (and how they are built)'])
        self.assertTrue(e['summary'].startswith('Ink on rice paper'))
        self.assertTrue(e['preview_url'].endswith('/test-ink.mp4'))

    def test_search_by_style_key_and_chinese_name(self):
        self.assertEqual(search(self.index, ['水墨'])[0]['id'], 'opus:test-ink')
        self.assertEqual(search(self.index, ['opuscar-test-ink'])[0]['id'], 'opus:test-ink')


class SampleFetchTests(unittest.TestCase):
    """A shortlisted Shotcraft preview comes out of the bulk zip alone; a name the zip lacks uses its single upload."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xumu-samples-test-')
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.zip = self.root / 'gallery-media.zip'
        with zipfile.ZipFile(self.zip, 'w') as z:
            z.writestr('media/a.mp4', b'zipped a')
            z.writestr('media/b.mp4', b'zipped b')
        (self.root / 'c-single.mp4').write_bytes(b'single c')

    def test_members_and_fallback(self):
        rows = [{'source': 'shotcraft', 'name': n, 'url': 'zip', 'member': n, 'bytes': 1, 'dest': str(self.root / 'out' / n),
                 'single': (self.root / 'c-single.mp4').as_uri() if n == 'c.mp4' else None}
                for n in ('a.mp4', 'c.mp4', 'd.mp4')]
        with mock.patch.object(motion_index, 'remote_zip', lambda url: zipfile.ZipFile(self.zip)):
            done, failed = motion_index.fetch_samples(rows)
        self.assertEqual(done, ['a.mp4', 'c.mp4'])
        self.assertTrue(failed[0].startswith('d.mp4: not in'))
        self.assertEqual((self.root / 'out' / 'a.mp4').read_bytes(), b'zipped a')
        self.assertEqual((self.root / 'out' / 'c.mp4').read_bytes(), b'single c')
        self.assertFalse((self.root / 'out' / 'b.mp4').exists())


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'needs ffmpeg')
class FramesTests(unittest.TestCase):
    """Contact sheets: one row of evenly spaced frames per sample, missing samples say how to get them."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xumu-frames-test-')
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.clip = self.root / 'clip.mp4'
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=size=320x180:rate=30',
                        '-t', '3', '-pix_fmt', 'yuv420p', str(self.clip)], check=True)
        self.index = {'entries': [{'id': 'gn:test', 'clip': str(self.clip)}, {'id': 'gn:noclip', 'clip': None}]}

    def width(self, path):
        out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                              '-of', 'csv=p=0', str(path)], capture_output=True, text=True, check=True).stdout
        return [int(v) for v in out.strip().split(',')]

    def test_sheet_has_all_frames_and_missing_ids_are_reported(self):
        result = frames(self.index, ['gn:test', str(self.clip), 'gn:noclip', 'gn:unknown'], self.root / 'refs', n=6, height=90)
        self.assertEqual([s['id'] for s in result['sheets']], ['gn:test', str(self.clip)])
        self.assertEqual(self.width(result['sheets'][0]['sheet']), [160 * 6, 90])
        self.assertEqual(len(result['sheets'][0]['times_s']), 6)
        self.assertEqual(result['combined'][0]['rows'], ['gn:test', str(self.clip)])
        self.assertEqual(self.width(result['combined'][0]['file']), [960, 2 * 98])
        self.assertEqual({m['id'] for m in result['missing']}, {'gn:noclip', 'gn:unknown'})


if __name__ == '__main__':
    unittest.main()
