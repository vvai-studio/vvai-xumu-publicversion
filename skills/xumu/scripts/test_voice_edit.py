"""voice_edit: the checking rounds must not need a full picture export or a full re-transcription.

Text-only parts run everywhere; the cut/listen round trip runs only where ffmpeg is on PATH (synthetic tone, not QA).
"""
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import voice_edit as ve


def transcript(words, start=0.2, step=0.5):
    out = []
    for k, w in enumerate(words):
        out.append({'text': w, 'start': round(start + k * step, 3), 'end': round(start + k * step + 0.4, 3), 'type': 'word'})
    return {'language_code': 'zh', 'words': out}


class CompareTests(unittest.TestCase):
    def test_matching_text_passes(self):
        v = ve.compare_window('今天讲剪辑先看口播', '今天讲剪辑，先看口播。')
        self.assertTrue(v['ok'], v)
        self.assertEqual(v['missing'], [])

    def test_missing_run_is_flagged(self):
        v = ve.compare_window('今天讲剪辑先看口播', '今天讲先看口播')
        self.assertFalse(v['ok'])
        self.assertEqual(v['missing'], ['剪辑'])

    def test_single_homophone_is_tolerated(self):
        v = ve.compare_window('今天讲剪辑先看口播', '今天讲剪集先看口播')
        self.assertTrue(v['ok'], v)

    def test_empty_expectation_is_fine(self):
        self.assertTrue(ve.compare_window('', '呃')['ok'])

    def test_expected_text_takes_kept_chars_in_window(self):
        chars = [{'c': c, 't': t} for c, t in (('今', 0.1), ('天', 0.3), ('，', 0.5), ('好', 2.0))]
        self.assertEqual(ve.expected_text(chars, 0.0, 1.0), '今天')
        self.assertEqual(ve.expected_text(chars, 1.5, 3.0), '好')


class CheckWindowsTests(unittest.TestCase):
    def test_report_lists_each_window_with_verdict(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'transcripts').mkdir()
            (root / 'transcripts' / 'a.json').write_text(json.dumps(transcript(list('今天讲剪辑先看口播'))), encoding='utf-8')
            edl = {'fps': 30, 'sources': {'a': 'a.wav'},
                   'segments': [{'source': 'a', 'start': 0.0, 'end': 2.0, 'section': 'B01'},
                                {'source': 'a', 'start': 2.5, 'end': 4.7, 'section': 'B01', 'join': 'keep'}]}
            windows = ve.listen_windows(edl, pad=0.5)
            self.assertEqual(len(windows), 1)
            heard = {0: '今天讲剪辑先看'}
            report, rows, flagged = ve.check_windows(edl, root / 'transcripts', windows, lambda w: heard[0])
            self.assertEqual(len(rows), 1)
            self.assertIn('剪点核对', report)
            self.assertIn(rows[0]['expected'][:2], '今天讲剪辑先看口播')
            # A transcriber that drops two kept characters is a flagged window, not a pass.
            report, rows, flagged = ve.check_windows(edl, root / 'transcripts', windows, lambda w: '今天讲看口播')
            self.assertEqual(flagged, 1)
            self.assertIn('**疑点**', report)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg not on PATH')
class AudioOnlyRoundTrip(unittest.TestCase):
    def test_audio_only_cut_feeds_listen_without_a_picture_export(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / 'talk.wav'
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=6',
                            '-ac', '2', '-ar', '48000', str(src)], check=True)
            edl = {'fps': 30, 'sources': {'a': str(src)}, 'total_seconds': 3.5,
                   'segments': [{'source': 'a', 'start': 0.5, 'end': 2.0, 'section': 'B01'},
                                {'source': 'a', 'start': 3.0, 'end': 5.0, 'section': 'B01', 'join': 'keep'}],
                   'suspects': []}
            edl_file = root / 'edl_voice.json'
            edl_file.write_text(json.dumps(edl), encoding='utf-8')
            cut = root / 'build' / 'voice_cut.wav'
            cut.parent.mkdir()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = ve.main(['render', str(edl_file), '--out', str(cut), '--audio-only'])
            result = json.loads(out.getvalue())
            self.assertEqual(code, 0, result)
            self.assertTrue(result['audio_only'])
            self.assertEqual(result['frames'], 45 + 60)
            probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,duration',
                                    '-of', 'json', str(cut)], capture_output=True, text=True, check=True)
            streams = json.loads(probe.stdout)['streams']
            self.assertEqual([s['codec_type'] for s in streams], ['audio'])
            self.assertAlmostEqual(float(streams[0]['duration']), 3.5, places=2)
            # No .mkv picture segments were cut for the audio-only round.
            self.assertFalse(list((cut.parent / 'voice_segs').glob('*.mkv')))
            # --audio-only refuses a video container name.
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ve.main(['render', str(edl_file), '--out', str(root / 'x.mp4'), '--audio-only']), 1)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = ve.main(['listen', str(edl_file), '--video', str(cut), '--out-dir', str(root / 'listen')])
            result = json.loads(out.getvalue())
            self.assertEqual(code, 0, result)
            self.assertEqual(result['clips'], 1)
            self.assertTrue((root / 'listen' / '试听合集.m4a').is_file())
            self.assertIn('试听合集.m4a', (root / 'listen' / '试听清单.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
