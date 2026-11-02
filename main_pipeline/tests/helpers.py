"""Synthetic fixtures and test-only adapters; no participant assets or AI models."""
from pathlib import Path
import tempfile
import unittest
import wave

import numpy as np

from suara.contracts import AudioData, PipelineDependencies, PipelineError
from suara.audio.preprocessing import preprocess_audio
from suara.mocks.pitch import analyze_pitch
from suara.mocks.timbre import analyze_timbre
from suara.mocks.recommender import recommend_songs

ROOT = Path(__file__).resolve().parents[1]


def write_wav(path, *, rate=16000, width=2, channels=1, duration=0.5,
              amplitude=0.25, frequency=220, samples=None):
    """Vectorized integer PCM writer, including packed signed 24-bit samples."""
    if samples is None:
        tone = amplitude * np.sin(2 * np.pi * frequency * np.arange(round(rate * duration)) / rate)
        samples = np.repeat(tone[:, None], channels, axis=1)
    values = np.asarray(samples).reshape(-1)
    scale = 2 ** (8 * width - 1)
    integers = np.clip(np.rint(values * scale), -scale, scale - 1).astype(np.int64)
    if width == 1:
        raw = (integers + 128).astype('u1').tobytes()
    elif width == 3:
        raw = np.column_stack([(integers >> shift) & 255 for shift in (0, 8, 16)]).astype('u1').tobytes()
    else:
        raw = integers.astype(f'<i{width}').tobytes()
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((channels, width, rate, 0, 'NONE', 'not compressed'))
        stream.writeframes(raw)
    return Path(path)


def tiny_audio():
    return AudioData(waveform=[0.25, -0.25], sample_rate=16000,
                     duration_s=2 / 16000, warnings=[])


def dependencies(**overrides):
    values = dict(preprocess_audio=lambda path, *, target_sample_rate: tiny_audio(),
                  analyze_pitch=analyze_pitch, analyze_timbre=analyze_timbre,
                  recommend_songs=recommend_songs)
    values.update(overrides)
    return PipelineDependencies(**values)


class SyntheticTestCase(unittest.TestCase):
    def setUp(self):
        (ROOT / '.smoke').mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=ROOT / '.smoke')
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def wav(self, **kwargs):
        return write_wav(self.folder / 'synthetic.wav', **kwargs)

    def assert_error(self, code, action, stage=None):
        with self.assertRaises(PipelineError) as caught:
            action()
        self.assertEqual(caught.exception.error.code, code)
        if stage:
            self.assertEqual(caught.exception.error.stage, stage)
        return caught.exception
