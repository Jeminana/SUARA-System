"""Day 2 smoke coverage only; all recordings are generated in temporary folders."""
from __future__ import annotations

import json
import math
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from dataclasses import replace
from pathlib import Path

from suara.audio.preprocessing import preprocess_audio
from suara.contracts import PipelineDependencies, PipelineError, PitchFeatures
from suara.mocks.pitch import analyze_pitch
from suara.mocks.recommender import recommend_songs
from suara.mocks.timbre import analyze_timbre
from suara.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]


class PipelineSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        (ROOT / ".smoke").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / ".smoke")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def wav(self, *, rate: int = 16000, channels: int = 1, width: int = 2,
            duration: float = 0.5, silent: bool = False) -> Path:
        path = self.folder / "tone.wav"
        scale = 2 ** (width * 8 - 1)
        raw = bytearray()
        for index in range(round(rate * duration)):
            value = 0 if silent else round(scale * 0.25 * math.sin(2 * math.pi * 220 * index / rate))
            sample = bytes([value + 128]) if width == 1 else value.to_bytes(width, "little", signed=True)
            raw.extend(sample)
            if channels == 2:
                half = value // 2
                raw.extend(bytes([half + 128]) if width == 1 else half.to_bytes(width, "little", signed=True))
        with wave.open(str(path), "wb") as stream:
            stream.setparams((channels, width, rate, 0, "NONE", "not compressed"))
            stream.writeframes(raw)
        return path

    def assert_code(self, code: str, action) -> None:
        with self.assertRaises(PipelineError) as caught:
            action()
        self.assertEqual(caught.exception.error.code, code)

    def test_mono_pcm_widths(self) -> None:
        for width in (1, 2, 3, 4):
            with self.subTest(width=width):
                audio = preprocess_audio(self.wav(width=width))
                self.assertEqual((audio.sample_rate, len(audio.waveform)), (16000, 8000))
                self.assertAlmostEqual(max(audio.waveform), 0.25, delta=0.01)
                self.assertEqual(audio.warnings, [])

    def test_stereo_and_resampling(self) -> None:
        audio = preprocess_audio(self.wav(rate=44100, channels=2))
        self.assertEqual(len(audio.waveform), 8000)
        self.assertEqual(audio.duration_s, 0.5)
        self.assertAlmostEqual(max(audio.waveform), 0.1875, delta=0.005)
        self.assertTrue(any("Stereo" in text for text in audio.warnings))
        self.assertTrue(any("resample_poly" in text for text in audio.warnings))

    def test_missing_and_corrupt_files(self) -> None:
        self.assert_code("audio_not_found", lambda: preprocess_audio(self.folder / "missing.wav"))
        path = self.folder / "broken.wav"
        path.write_bytes(b"not a WAV")
        self.assert_code("invalid_audio", lambda: preprocess_audio(path))

    def test_rejected_audio_basics(self) -> None:
        for kwargs, code in (({"silent": True}, "silent_audio"),
                             ({"duration": 0.1}, "audio_too_short"),
                             ({"duration": 0}, "invalid_audio")):
            with self.subTest(code=code):
                self.assert_code(code, lambda: preprocess_audio(self.wav(**kwargs)))

    def test_truncated_data_rejected(self) -> None:
        path = self.wav()
        path.write_bytes(path.read_bytes()[:-2])
        self.assert_code("invalid_audio", lambda: preprocess_audio(path))

    def test_wav_format_headers(self) -> None:
        path = self.wav()
        original = path.read_bytes()
        # Convert the generated PCM16 header to full-width extensible PCM.
        extension = struct.pack("<HHI", 22, 16, 0) + bytes.fromhex("0100000000001000800000aa00389b71")
        fmt = bytearray(original[20:36] + extension)
        struct.pack_into("<H", fmt, 0, 0xFFFE)
        body = b"WAVEfmt " + struct.pack("<I", len(fmt)) + fmt + original[36:]
        path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)
        self.assertEqual(len(preprocess_audio(path).waveform), 8000)
        for tag in (3, 6):  # float / compressed formats are outside the contract
            with self.subTest(tag=tag):
                changed = bytearray(original)
                struct.pack_into("<H", changed, 20, tag)
                path.write_bytes(changed)
                self.assert_code("unsupported_audio", lambda: preprocess_audio(path))
        changed = bytearray(original)
        struct.pack_into("<H", changed, 32, 1)  # wrong block alignment for PCM16
        path.write_bytes(changed)
        self.assert_code("invalid_audio", lambda: preprocess_audio(path))

    def test_mock_end_to_end_determinism(self) -> None:
        path = self.wav()
        first, second = run_pipeline(path), run_pipeline(path)
        self.assertEqual(first.voice_profile, second.voice_profile)
        self.assertEqual(first.recommendations, second.recommendations)
        self.assertEqual(first.analysis_mode, "mock")
        self.assertEqual(first.voice_profile.pitch.mode, "mock")
        self.assertEqual(first.voice_profile.timbre.mode, "mock")
        self.assertEqual(len(first.recommendations), 5)
        self.assertEqual([r.score for r in first.recommendations], [0.9, 0.8, 0.7, 0.6, 0.5])
        self.assertTrue(all(r.mode == "mock" for r in first.recommendations))
        self.assertEqual(json.loads(first.to_json())["schema_version"], "1.0.0")
        self.assertGreaterEqual(first.processing_time_s, 0)

    def test_empty_catalog_and_top_k(self) -> None:
        path = self.wav()
        self.assertEqual(run_pipeline(path, song_catalog=[]).recommendations, [])
        self.assertEqual(len(run_pipeline(path, top_k=2).recommendations), 2)
        self.assert_code("invalid_configuration", lambda: run_pipeline(path, top_k=True))

    def test_real_mode_does_not_fallback(self) -> None:
        path = self.wav()
        self.assert_code("invalid_configuration", lambda: run_pipeline(path, mode="real"))
        mocks = PipelineDependencies(preprocess_audio=preprocess_audio, analyze_pitch=analyze_pitch,
            analyze_timbre=analyze_timbre, recommend_songs=recommend_songs)
        self.assert_code("invalid_configuration", lambda: run_pipeline(
            path, mode="real", dependencies=mocks, song_catalog=[]))

    def test_custom_injection_and_unvoiced_profile(self) -> None:
        calls = []
        # Test-only stubs exercise the real-mode API, not real feature extraction.
        def pitch(audio_data):
            calls.append("pitch")
            return PitchFeatures(min_pitch_hz=None, max_pitch_hz=None, median_pitch_hz=None,
                voiced_ratio=0.0, confidence=None, mode="real", model_version="test-stub-v1",
                warnings=["Test-only stub: no accepted voiced frames."])
        def timbre(audio_data):
            calls.append("timbre")
            return replace(analyze_timbre(audio_data), mode="real", model_version="test-stub-v1",
                processing_version="test-stub-v1", warnings=["Test-only timbre stub."])
        def rank(voice_profile, song_catalog, top_k=5):
            calls.append("recommendation")
            self.assertEqual(top_k, 3)
            self.assertEqual(song_catalog, [])
            return []
        dependencies = PipelineDependencies(preprocess_audio=preprocess_audio, analyze_pitch=pitch,
            analyze_timbre=timbre, recommend_songs=rank)
        result = run_pipeline(self.wav(), mode="real", dependencies=dependencies, song_catalog=[], top_k=3)
        self.assertEqual(calls, ["pitch", "timbre", "recommendation"])
        self.assertEqual(result.voice_profile.status, "no_voiced_pitch")
        self.assertIsNone(result.voice_profile.pitch.min_pitch_hz)

    def test_bad_module_and_ranking_results(self) -> None:
        path = self.wav()
        dependencies = PipelineDependencies(preprocess_audio=preprocess_audio,
            analyze_pitch=lambda audio_data: {}, analyze_timbre=analyze_timbre,
            recommend_songs=recommend_songs)
        self.assert_code("invalid_features", lambda: run_pipeline(path, dependencies=dependencies))
        dependencies = replace(dependencies, analyze_pitch=analyze_pitch,
            recommend_songs=lambda voice_profile, song_catalog, top_k=5: [object()])
        self.assert_code("invalid_catalog", lambda: run_pipeline(path, dependencies=dependencies))
        def broken(audio_data):
            raise RuntimeError("private/local/path must not reach public JSON")
        dependencies = replace(dependencies, analyze_pitch=broken)
        with self.assertRaises(PipelineError) as caught:
            run_pipeline(path, dependencies=dependencies)
        self.assertEqual(caught.exception.error.code, "module_failure")
        self.assertEqual(caught.exception.error.stage, "pitch")
        self.assertNotIn("private", caught.exception.error.to_json())

    def test_cli_json_and_error_channels(self) -> None:
        valid = subprocess.run([sys.executable, "-m", "suara.cli", "--audio", str(self.wav()),
            "--mode", "mock", "--top-k", "2"], capture_output=True, text=True)
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertEqual(valid.stderr, "")
        self.assertEqual(len(json.loads(valid.stdout)["recommendations"]), 2)
        invalid = subprocess.run([sys.executable, "-m", "suara.cli", "--audio", "missing.wav"],
            capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(invalid.stdout, "")
        self.assertEqual(json.loads(invalid.stderr)["code"], "audio_not_found")

    def test_mock_imports_do_not_load_models(self) -> None:
        process = subprocess.run([sys.executable, "-c",
            "import sys; from suara.pipeline import run_pipeline; "
            "run_pipeline(sys.argv[1]); "
            "assert not ({'torch','tensorflow','librosa','speechbrain','crepe'} & sys.modules.keys())",
            str(self.wav())], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == "__main__":
    unittest.main()
