"""Numerical convention and actual adapter wiring; generated audio only."""
import json
import math
import subprocess
import sys
from dataclasses import replace
from unittest.mock import patch

import numpy as np

from helpers import SyntheticTestCase, dependencies
from suara.audio.preprocessing import preprocess_audio
from suara.contracts import AudioData, ContractError, PitchFeatures
from suara.pipeline import run_pipeline
from suara.timbre import MODEL_VERSION, PROCESSING_VERSION, analyze_timbre


def audio(samples, rate=16000):
    return AudioData(waveform=[float(x) for x in samples], sample_rate=rate,
                     duration_s=len(samples) / rate, warnings=[])


def reference_mfcc(samples):
    """Independent scalar filterbank + explicit cosine transform oracle.

    Deliberately uses neither the extractor's mel filters nor scipy's DCT/window.
    """
    def to_mel(hz):
        return hz / (200 / 3) if hz < 1000 else 15 + math.log(hz / 1000) * 27 / math.log(6.4)
    def to_hz(mel):
        return mel * (200 / 3) if mel < 15 else 1000 * math.exp((mel - 15) * math.log(6.4) / 27)
    edges = [to_hz(i * to_mel(8000) / 41) for i in range(42)]
    filters = np.zeros((40, 257))
    for band in range(40):
        low, middle, high = edges[band:band + 3]
        for bin_index in range(257):
            hz = bin_index * 16000 / 512
            filters[band, bin_index] = max(0, min((hz-low)/(middle-low), (high-hz)/(high-middle))) * 2/(high-low)
    window = [0.5 - 0.5 * math.cos(2 * math.pi * i / 512) for i in range(512)]
    means = []
    for start in range(0, len(samples) - 511, 160):
        power = np.abs(np.fft.rfft(np.asarray(samples[start:start+512]) * window)) ** 2
        logs = 10 * np.log10(np.maximum(filters @ power, 1e-10))
        means.append([sum(logs[m] * math.cos(math.pi * k * (m + 0.5) / 40) for m in range(40))
                      * math.sqrt((1 if k == 0 else 2) / 40) for k in range(20)])
    return np.mean(means, axis=0)


class TimbreTests(SyntheticTestCase):
    def test_numerical_parity_with_independent_reference(self):
        rng = np.random.default_rng(42)
        for samples in (rng.uniform(-0.5, 0.5, 1200), np.zeros(1024),
                        0.25 * np.sin(2 * np.pi * 440 * np.arange(1600) / 16000)):
            with self.subTest(signal_energy=float(np.sum(samples ** 2))):
                actual = analyze_timbre(audio(samples))
                np.testing.assert_allclose(actual.mfcc_mean, reference_mfcc(samples), atol=1e-10, rtol=1e-10)
                self.assertEqual(actual.processing_version, PROCESSING_VERSION)
                self.assertEqual(actual.model_version, MODEL_VERSION)
                self.assertEqual(actual.mode, 'real')
                self.assertEqual(len(actual.mfcc_mean), 20)
                actual.validate()
                json.loads(actual.to_json())

    def test_silence_and_complete_frame_tail_policy(self):
        silent = analyze_timbre(audio(np.zeros(512)))
        self.assertAlmostEqual(silent.mfcc_mean[0], -100 * math.sqrt(40), places=10)
        np.testing.assert_allclose(silent.mfcc_mean[1:], 0, atol=1e-10)
        self.assertIsNone(silent.spectral_centroid_mean_hz)
        self.assertTrue(silent.warnings)
        # A 159-sample tail cannot form another frame; its energy is ignored.
        tail = analyze_timbre(audio(np.r_[np.zeros(512), np.ones(159)]))
        self.assertEqual(tail, silent)

    def test_centroid_and_gain_preservation(self):
        samples = 0.25 * np.sin(2 * np.pi * 1000 * np.arange(832) / 16000)
        first = analyze_timbre(audio(samples))
        self.assertAlmostEqual(first.spectral_centroid_mean_hz, 1000, places=8)
        quieter = analyze_timbre(audio(samples / 2))
        self.assertLess(quieter.mfcc_mean[0], first.mfcc_mean[0])
        # Silent frames contribute to MFCC pooling, but not centroid pooling.
        separated = analyze_timbre(audio(np.r_[samples, np.zeros(1600)]))
        self.assertNotEqual(first.mfcc_mean, separated.mfcc_mean)
        self.assertTrue(0 <= separated.spectral_centroid_mean_hz <= 8000)

    def test_read_only_deterministic_and_audio_sensitive(self):
        value = audio(np.random.default_rng(7).uniform(-0.2, 0.2, 1000))
        before = value.to_dict()
        first = analyze_timbre(audio_data=value)
        self.assertEqual(value.to_dict(), before)
        self.assertEqual(first, analyze_timbre(value))
        other = analyze_timbre(audio(np.sin(np.arange(1000)) * 0.2))
        self.assertNotEqual(first.mfcc_mean, other.mfcc_mean)

    def test_reject_invalid_short_and_wrong_rate(self):
        self.assert_error('audio_too_short', lambda: analyze_timbre(audio([0.1] * 511)), 'timbre')
        self.assert_error('invalid_audio', lambda: analyze_timbre(audio([0.1] * 512, 8000)), 'timbre')
        value = audio([0.1] * 512)
        value.waveform[0] = float('nan')
        with self.assertRaises(ContractError):
            analyze_timbre(value)

    def test_preprocessing_and_mixed_mode_profile(self):
        path = self.wav(rate=44100, channels=2)
        deps = dependencies(preprocess_audio=preprocess_audio, analyze_timbre=analyze_timbre)
        result = run_pipeline(path, dependencies=deps)
        expected = analyze_timbre(preprocess_audio(path))
        self.assertEqual(result.voice_profile.timbre, expected)
        self.assertEqual(result.voice_profile.pitch.mode, 'mock')
        self.assertEqual(result.analysis_mode, 'mock')
        self.assertTrue(all(r.mode == 'mock' for r in result.recommendations))
        self.assertTrue(any('resample_poly' in w for w in result.voice_profile.warnings))
        self.assertEqual(json.loads(result.to_json())['voice_profile']['timbre']['processing_version'], 'mfcc-20-v1')
        self.assert_error('invalid_configuration', lambda: run_pipeline(path, mode='real', dependencies=deps, song_catalog=[]))

    def test_unvoiced_profile_with_measured_timbre(self):
        def unvoiced(audio_data):
            return PitchFeatures(min_pitch_hz=None, max_pitch_hz=None, median_pitch_hz=None,
                                 voiced_ratio=0.0, confidence=None, mode='real',
                                 model_version='test-only-unvoiced-stub', warnings=[])
        result = run_pipeline(self.wav(), song_catalog=[], dependencies=dependencies(
            preprocess_audio=preprocess_audio, analyze_pitch=unvoiced, analyze_timbre=analyze_timbre))
        self.assertEqual(result.voice_profile.status, 'no_voiced_pitch')
        self.assertEqual(result.voice_profile.timbre.mode, 'real')
        # This tests assembly only; the pitch stub is not an actual E1 adapter.

    def test_failures_are_safe_and_never_fallback(self):
        path = self.wav()
        deps = dependencies(preprocess_audio=preprocess_audio, analyze_timbre=analyze_timbre)
        with patch('suara.timbre._mel_filters', side_effect=RuntimeError('private recording path')):
            exc = self.assert_error('module_failure', lambda: run_pipeline(path, dependencies=deps), 'timbre')
        self.assertNotIn('private', exc.error.to_json())
        invalid = analyze_timbre(preprocess_audio(path))
        invalid.mfcc_mean[0] = float('inf')
        self.assert_error('invalid_features', lambda: run_pipeline(path, dependencies=replace(
            deps, analyze_timbre=lambda _: invalid)), 'timbre')

    def test_cli_measured_timbre_selection_and_mock_import_isolation(self):
        result = subprocess.run([sys.executable, '-m', 'suara.cli', '--audio', str(self.wav()),
                                 '--timbre', 'real'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload['voice_profile']['timbre']['mode'], 'real')
        self.assertEqual(payload['voice_profile']['pitch']['mode'], 'mock')
        self.assertEqual(payload['analysis_mode'], 'mock')
        check = subprocess.run([sys.executable, '-c',
            "import sys; from suara.pipeline import run_pipeline; run_pipeline(sys.argv[1]); "
            "assert 'suara.timbre' not in sys.modules", str(self.wav())], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
