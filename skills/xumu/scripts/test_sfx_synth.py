"""Tests of sfx_synth: deterministic, bounded, placed at the right sample."""
from pathlib import Path
import tempfile
import unittest
import wave

import numpy as np

import sfx_synth as sx


class SynthTests(unittest.TestCase):
    def test_every_preset_is_deterministic_and_at_gain(self):
        for name in sx.PRESETS:
            a = sx.make(name, seed=2, gain=-6)
            b = sx.make(name, seed=2, gain=-6)
            self.assertTrue(np.array_equal(a, b), name)
            self.assertAlmostEqual(float(np.abs(a).max()), 10 ** (-6 / 20), places=4)
            self.assertLess(len(a), sx.SR, name)            # short effects, under a second

    def test_seed_and_pitch_change_the_sound(self):
        self.assertFalse(np.array_equal(sx.make('sparkle', seed=1), sx.make('sparkle', seed=2)))
        self.assertFalse(np.array_equal(sx.make('pop', pitch=1.0), sx.make('pop', pitch=1.3)))

    def test_track_places_events_and_never_clips(self):
        events = [{'t': 0.5, 'preset': 'pop', 'gain': -1}, {'t': 0.5, 'preset': 'ding', 'gain': -1},
                  {'t': 9.0, 'preset': 'click'}]                 # last one beyond the end: skipped
        out = sx.track(events, 2.0)
        self.assertEqual(len(out), 2 * sx.SR)
        self.assertLessEqual(float(np.abs(out).max()), 0.98 + 1e-9)
        self.assertEqual(float(np.abs(out[:int(0.5 * sx.SR) - 1]).max()), 0.0)
        self.assertGreater(float(np.abs(out[int(0.5 * sx.SR):int(0.6 * sx.SR)]).max()), 0.1)

    def test_file_event_puts_the_peak_on_t(self):
        # a downloaded sound: 0.2 s of near-silence then an impulse; peak=0.2 must land exactly on t
        src = np.zeros(int(0.5 * sx.SR))
        src[int(0.2 * sx.SR)] = 1.0
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'fs-1.wav'
            sx.write_wav(p, src)
            out = sx.track([{'t': 1.0, 'file': str(p), 'gain': -6, 'peak': 0.2}], 2.0)
            self.assertEqual(int(np.argmax(np.abs(out))), int(1.0 * sx.SR))
            self.assertAlmostEqual(float(np.abs(out).max()), 10 ** (-6 / 20), places=3)
            # without peak the file simply starts at t; start/length trim the file
            out = sx.track([{'t': 1.0, 'file': str(p), 'gain': -6}], 2.0)
            self.assertEqual(int(np.argmax(np.abs(out))), int(1.2 * sx.SR))
            out = sx.track([{'t': 0.1, 'file': str(p), 'gain': -6, 'start': 0.15, 'length': 0.1}], 1.0)
            self.assertEqual(int(np.argmax(np.abs(out))), int(0.15 * sx.SR))
            # peak alignment that would start before 0 drops the head instead of failing
            out = sx.track([{'t': 0.1, 'file': str(p), 'gain': -6, 'peak': 0.2}], 1.0)
            self.assertEqual(int(np.argmax(np.abs(out))), int(0.1 * sx.SR))

    def test_write_wav_format(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'x.wav'
            sx.write_wav(p, sx.make('click'))
            with wave.open(str(p)) as w:
                self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, 48000))


if __name__ == '__main__':
    unittest.main()
