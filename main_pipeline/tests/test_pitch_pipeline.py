"""Pipeline and CLI integration tests across the CREPE worker boundary."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
import sys
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import ROOT, SyntheticTestCase
from suara.audio.preprocessing import preprocess_audio
from suara.cli import main
from suara.contracts import (
    AudioData, PipelineDependencies, TimbreFeatures,
)
from suara.pitch import MODEL_VERSION, WORKER_PROTOCOL, analyze_pitch
from suara.pipeline import run_pipeline
from suara.recommender import SCORING_VERSION


E3_CATALOG = ROOT.parent / "experiments" / "E3" / "handoff" / "song_features.json"


def run_real_cli(audio_path):
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(["--audio", str(audio_path), "--mode", "real",
                     "--catalog", str(E3_CATALOG), "--top-k", "2"])
    return code, stdout.getvalue(), stderr.getvalue()


def assert_real_ranking(test, result):
    profile = result["voice_profile"]
    test.assertEqual(result["analysis_mode"], "real")
    test.assertEqual(profile["pitch"]["mode"], "real")
    test.assertEqual(profile["timbre"]["mode"], "real")
    test.assertEqual(len(profile["timbre"]["mfcc_mean"]), 20)
    recommendations = result["recommendations"]
    test.assertEqual(len(recommendations), 2)
    keys = [(-rec["score"], rec["song_id"]) for rec in recommendations]
    test.assertEqual(keys, sorted(keys))
    for rec in recommendations:
        test.assertTrue(rec["song_id"].startswith("E3-"))
        test.assertEqual(rec["mode"], "real")
        test.assertEqual(rec["scoring_version"], SCORING_VERSION)
        test.assertTrue(rec["explanation"])


def response(frames):
    return json.dumps({"protocol": WORKER_PROTOCOL, "frames": frames},
                      allow_nan=False, separators=(",", ":"))


def frame(frequency_hz, confidence):
    return {"frequency_hz": frequency_hz, "confidence": confidence}


class PitchPipelineIntegrationTests(SyntheticTestCase):
    """Use actual preprocessing/adapter/pipeline and a protocol fake worker."""

    def setUp(self):
        super().setUp()
        worker = self.folder / "fake_crepe_worker.py"
        worker.write_text(textwrap.dedent(f"""\
            import json, os, struct, sys, time
            payload = sys.stdin.buffer.read()
            if len(payload) < 12 or payload[:8] != b"SUARAP01":
                print("invalid fake worker request", file=sys.stderr)
                raise SystemExit(20)
            metadata_size = struct.unpack(">I", payload[8:12])[0]
            metadata_end = 12 + metadata_size
            try:
                metadata = json.loads(payload[12:metadata_end].decode("utf-8"))
            except Exception:
                print("invalid fake worker metadata", file=sys.stderr)
                raise SystemExit(21)
            if (metadata.get("protocol") != {WORKER_PROTOCOL!r}
                    or metadata.get("sample_rate") != 16000
                    or metadata.get("sample_count", -1) * 4 != len(payload) - metadata_end):
                print("invalid fake worker payload", file=sys.stderr)
                raise SystemExit(22)
            time.sleep(float(os.environ.get("SUARA_TEST_CREPE_DELAY", "0")))
            status = int(os.environ.get("SUARA_TEST_CREPE_EXIT", "0"))
            if status:
                print("private test worker diagnostic", file=sys.stderr)
                raise SystemExit(status)
            output = os.environ.get("SUARA_TEST_CREPE_RESPONSE")
            if output is None:
                output = json.dumps({{"protocol": {WORKER_PROTOCOL!r}, "frames": []}})
            sys.stdout.write(output + "\\n")
        """))
        command = patch("suara.pitch._worker_command", return_value=[sys.executable, str(worker)])
        command.start()
        self.addCleanup(command.stop)
        self.env = patch.dict(os.environ, {
            "SUARA_CREPE_TIMEOUT_S": "2",
            "SUARA_TEST_CREPE_DELAY": "0",
            "SUARA_TEST_CREPE_EXIT": "0",
        }, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    @staticmethod
    def _real_timbre_test_double(audio_data: AudioData) -> TimbreFeatures:
        audio_data.validate()
        return TimbreFeatures(
            mfcc_mean=[0.0] * 20, spectral_centroid_mean_hz=1000.0,
            mode="real", model_version="test-only-timbre-double",
            processing_version="test-only-timbre-double",
            warnings=["Test-only timbre double; not production validated."],
        )

    @staticmethod
    def _real_rank_test_double(voice_profile, song_catalog, top_k=5):
        # Empty test catalog keeps this test focused on pitch/profile wiring.
        assert song_catalog == []
        assert isinstance(top_k, int)
        return []

    def _dependencies(self, pitch_response: str, *, capture: dict):
        os.environ["SUARA_TEST_CREPE_RESPONSE"] = pitch_response

        def preprocess_and_capture(path, *, target_sample_rate):
            audio = preprocess_audio(path, target_sample_rate=target_sample_rate)
            capture["audio"] = audio
            capture["before"] = audio.to_dict()
            return audio

        return PipelineDependencies(
            preprocess_audio=preprocess_and_capture,
            analyze_pitch=analyze_pitch,
            analyze_timbre=self._real_timbre_test_double,
            recommend_songs=self._real_rank_test_double,
        )

    def _run(self, path, deps):
        return run_pipeline(path, mode="real", song_catalog=[], dependencies=deps)

    def test_voiced_wav_uses_actual_preprocessor_adapter_and_profile(self):
        capture = {}
        fake_response = response([frame(110.0, 0.7), frame(220.0, 0.8),
                                  frame(330.0, 0.9), frame(440.0, 0.49),
                                  frame(None, None)])
        result = self._run(self.wav(duration=1.0, frequency=220),
                           self._dependencies(fake_response, capture=capture))

        audio = capture["audio"]
        self.assertEqual(audio.sample_rate, 16000)
        self.assertTrue(all(type(value) is float for value in audio.waveform))
        self.assertEqual(audio.to_dict(), capture["before"])
        pitch = result.voice_profile.pitch
        self.assertEqual((pitch.min_pitch_hz, pitch.max_pitch_hz, pitch.median_pitch_hz),
                         (110.0, 330.0, 220.0))
        self.assertEqual(pitch.voiced_ratio, 3 / 5)
        self.assertEqual(pitch.mode, "real")
        self.assertEqual(pitch.model_version, MODEL_VERSION)
        self.assertEqual(result.voice_profile.analysis_mode, "real")
        self.assertEqual(result.voice_profile.status, "warning")
        self.assertIn("Test-only timbre double; not production validated.",
                      result.voice_profile.warnings)
        self.assertEqual(result.analysis_mode, "real")
        self.assertEqual(result.recommendations, [])
        result.validate()
        result.to_json()

    def test_unvoiced_non_silent_wav_assembles_null_pitch_profile(self):
        capture = {}
        fake_response = response([frame(0.0, 0.9), frame(220.0, 0.49),
                                  frame(220.0, 1.01), frame(None, None)])
        # The generated 220 Hz WAV passes preprocessing. The fake worker returns
        # no accepted F0 frames, exercising unvoiced assembly without silence QC.
        result = self._run(self.wav(duration=1.0, frequency=220),
                           self._dependencies(fake_response, capture=capture))
        pitch = result.voice_profile.pitch
        self.assertGreater(sum(x * x for x in capture["audio"].waveform) / len(
            capture["audio"].waveform), 1e-8)
        self.assertEqual(capture["audio"].sample_rate, 16000)
        self.assertEqual(pitch.voiced_ratio, 0.0)
        self.assertIsNone(pitch.min_pitch_hz)
        self.assertIsNone(pitch.max_pitch_hz)
        self.assertIsNone(pitch.median_pitch_hz)
        self.assertIsNone(pitch.confidence)
        self.assertEqual(result.voice_profile.status, "no_voiced_pitch")
        self.assertEqual(result.voice_profile.analysis_mode, "real")
        self.assertEqual(result.analysis_mode, "real")
        self.assertTrue(pitch.warnings)
        result.validate()

    def test_invalid_detector_response_is_safe_pitch_stage_error(self):
        capture = {}
        invalid_response = json.dumps({
            "protocol": WORKER_PROTOCOL,
            "frames": [{"frequency_hz": "220", "confidence": 0.8}],
        })
        deps = self._dependencies(invalid_response, capture=capture)
        error = self.assert_error(
            "module_failure", lambda: self._run(self.wav(), deps), "pitch")
        self.assertNotIn("private", error.error.to_json())

    def test_worker_exit_and_timeout_propagate_safely(self):
        with patch.dict(os.environ, {"SUARA_TEST_CREPE_EXIT": "7"}):
            error = self.assert_error("module_failure", lambda: self._run(
                self.wav(), self._dependencies(response([]), capture={})), "pitch")
            self.assertNotIn("private", error.error.to_json())
        with patch.dict(os.environ, {
                "SUARA_TEST_CREPE_EXIT": "0",
                "SUARA_TEST_CREPE_DELAY": "0.5",
                "SUARA_CREPE_TIMEOUT_S": "0.05",
        }):
            self.assert_error("module_failure", lambda: self._run(
                self.wav(), self._dependencies(response([]), capture={})), "pitch")

    def test_real_cli_ranks_e3_catalog_or_reports_safe_failure(self):
        audio = self.wav(duration=1.0)
        with patch.dict(os.environ, {"SUARA_TEST_CREPE_RESPONSE": response([frame(220, 0.9)])}):
            code, stdout, stderr = run_real_cli(audio)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stderr, "")
        assert_real_ranking(self, json.loads(stdout))

        with patch.dict(os.environ, {"SUARA_TEST_CREPE_RESPONSE": response([frame(220, 0.1)])}):
            code, stdout, stderr = run_real_cli(audio)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stderr, "")
        result = json.loads(stdout)
        self.assertEqual(result["voice_profile"]["status"], "no_voiced_pitch")
        self.assertEqual(result["recommendations"], [])

        with patch.dict(os.environ, {"SUARA_TEST_CREPE_EXIT": "7"}):
            code, stdout, stderr = run_real_cli(audio)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        error = json.loads(stderr)
        self.assertEqual((error["code"], error["stage"]), ("module_failure", "pitch"))
        self.assertNotIn("private", stderr)


@unittest.skipUnless(os.environ.get("SUARA_CREPE_INTEGRATION") == "1",
                     "set SUARA_CREPE_INTEGRATION=1 to run actual CREPE end to end")
class RealCrepePipelineIntegrationTests(SyntheticTestCase):
    """Opt-in preprocess -> actual CREPE adapter -> pipeline -> profile check."""

    def test_generated_220_hz_wav_runs_through_real_cli(self):
        code, stdout, stderr = run_real_cli(self.wav(duration=1.0, frequency=220))
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stderr, "")
        result = json.loads(stdout)
        assert_real_ranking(self, result)
        pitch = result["voice_profile"]["pitch"]
        self.assertEqual(pitch["model_version"], MODEL_VERSION)
        self.assertAlmostEqual(pitch["median_pitch_hz"], 220.0, delta=8.0)

    def test_generated_220_hz_wav_runs_through_real_pipeline(self):
        def test_timbre(audio_data):
            return PitchPipelineIntegrationTests._real_timbre_test_double(audio_data)

        def test_rank(profile, catalog, top_k=5):
            return []

        dependencies = PipelineDependencies(
            preprocess_audio=preprocess_audio,
            analyze_pitch=analyze_pitch,
            analyze_timbre=test_timbre,
            recommend_songs=test_rank,
        )
        result = run_pipeline(self.wav(duration=1.0, frequency=220), mode="real",
                              song_catalog=[], dependencies=dependencies)
        result.validate()
        result.to_json()
        self.assertEqual(result.voice_profile.pitch.mode, "real")
        self.assertEqual(result.voice_profile.pitch.model_version, MODEL_VERSION)
        self.assertGreater(result.voice_profile.pitch.voiced_ratio, 0.5)
        self.assertAlmostEqual(result.voice_profile.pitch.median_pitch_hz, 220.0, delta=8.0)
        self.assertEqual(result.voice_profile.analysis_mode, "real")
        self.assertEqual(result.analysis_mode, "real")
        self.assertEqual(result.voice_profile.status, "warning")
