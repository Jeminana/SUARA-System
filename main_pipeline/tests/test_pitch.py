"""Tests for the real pitch adapter using generated waveforms and fake workers."""
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from helpers import SyntheticTestCase, tiny_audio
from suara.contracts import AudioData, ContractError, PipelineError, PitchFeatures
from suara.pitch import MODEL_VERSION, WORKER_PROTOCOL, _encode_request, analyze_pitch


def response(frames):
    return json.dumps({"protocol": WORKER_PROTOCOL, "frames": frames},
                      allow_nan=False, separators=(",", ":")).encode()


def frame(hz, confidence=0.8):
    return {"frequency_hz": hz, "confidence": confidence}


class PitchAdapterTests(SyntheticTestCase):
    def setUp(self):
        super().setUp()
        self.worker = Path(sys.executable).resolve()
        self.env = patch.dict(os.environ, {"SUARA_CREPE_PYTHON": str(self.worker)}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def fake_run(self, stdout, returncode=0):
        class Completed:
            def __init__(self):
                self.stdout = stdout
                self.stderr = b"diagnostic text must not be surfaced"
                self.returncode = returncode
        return patch("suara.pitch.subprocess.run", return_value=Completed())

    def test_generated_tone_request_and_frequency_aggregation(self):
        waveform = (0.25 * np.sin(2 * np.pi * 220 * np.arange(16000) / 16000)).tolist()
        audio = AudioData(waveform=waveform, sample_rate=16000, duration_s=1.0, warnings=[])
        original = list(audio.waveform)
        frames = [frame(220), frame(110), frame(330), frame(440, 0.49), frame(float("nan"), 0.9)]
        # Real worker serializes nonfinite detector values as JSON null.
        frames[-1] = {"frequency_hz": None, "confidence": 0.9}
        with self.fake_run(response(frames)) as run:
            result = analyze_pitch(audio)
        self.assertEqual((result.min_pitch_hz, result.max_pitch_hz, result.median_pitch_hz),
                         (110.0, 330.0, 220.0))
        self.assertEqual(result.voiced_ratio, 3 / 5)
        self.assertAlmostEqual(result.confidence, 0.8)
        self.assertEqual(result.model_version, MODEL_VERSION)
        self.assertEqual(result.mode, "real")
        self.assertEqual(audio.waveform, original)
        args, kwargs = run.call_args
        self.assertFalse(kwargs["shell"])
        payload = kwargs["input"]
        self.assertTrue(payload.startswith(b"SUARAP01"))
        self.assertGreater(len(payload), 16 + len(waveform) * 4)
        result.validate()

    def test_no_voiced_frames_returns_null_pitch_statistics(self):
        with self.fake_run(response([frame(0, 0.9), frame(220, 0.49),
                                     frame(220, 1.1), frame(None, None)])):
            result = analyze_pitch(tiny_audio())
        self.assertEqual(result.voiced_ratio, 0.0)
        self.assertIsNone(result.min_pitch_hz)
        self.assertIsNone(result.max_pitch_hz)
        self.assertIsNone(result.median_pitch_hz)
        self.assertIsNone(result.confidence)
        self.assertTrue(result.warnings)
        result.validate()

    def test_confidence_at_exact_threshold_is_accepted(self):
        with self.fake_run(response([frame(220, 0.5), frame(0, 0.9)])):
            result = analyze_pitch(tiny_audio())
        self.assertEqual(result.voiced_ratio, 0.5)
        self.assertEqual(result.min_pitch_hz, 220.0)
        self.assertEqual(result.max_pitch_hz, 220.0)
        self.assertEqual(result.median_pitch_hz, 220.0)
        self.assertEqual(result.confidence, 0.5)
        result.validate()

    def test_invalid_response_schema_and_nonnumeric_values_fail(self):
        payloads = (
            b"not json",
            json.dumps({"protocol": WORKER_PROTOCOL, "frames": []}).encode(),
            response([{"frequency_hz": 220}]),
            json.dumps({"protocol": WORKER_PROTOCOL,
                        "frames": [frame("220", 0.8)]}).encode(),
        )
        for payload in payloads:
            with self.subTest(payload=payload[:30]), self.fake_run(payload):
                with self.assertRaises(PipelineError) as caught:
                    analyze_pitch(tiny_audio())
                self.assertEqual(caught.exception.error.code, "module_failure")
                self.assertEqual(caught.exception.error.stage, "pitch")

    def test_worker_nonzero_exit_and_timeout_are_failures(self):
        with self.fake_run(b"", returncode=3):
            with self.assertRaises(PipelineError):
                analyze_pitch(tiny_audio())
        with patch("suara.pitch.subprocess.run", side_effect=__import__(
                "subprocess").TimeoutExpired(cmd="worker", timeout=1)):
            with self.assertRaises(PipelineError) as caught:
                analyze_pitch(tiny_audio())
            self.assertEqual(caught.exception.error.code, "module_failure")

    def test_missing_worker_environment_and_timeout_configuration(self):
        with patch.dict(os.environ, {"SUARA_CREPE_PYTHON": ""}):
            with self.assertRaises(PipelineError) as caught:
                analyze_pitch(tiny_audio())
            self.assertEqual(caught.exception.error.code, "invalid_configuration")
        with patch.dict(os.environ, {"SUARA_CREPE_TIMEOUT_S": "nan"}):
            with self.assertRaises(PipelineError) as caught:
                analyze_pitch(tiny_audio())
            self.assertEqual(caught.exception.error.code, "invalid_configuration")

    def test_invalid_frequency_is_unvoiced_and_contract_is_enforced(self):
        with self.fake_run(response([frame(-1, 0.8), frame(220, -0.1), frame(220, 0.9)])):
            result = analyze_pitch(tiny_audio())
        self.assertEqual(result.voiced_ratio, 1 / 3)
        self.assertEqual((result.min_pitch_hz, result.max_pitch_hz, result.median_pitch_hz),
                         (220.0, 220.0, 220.0))
        with self.assertRaises(ContractError):
            PitchFeatures(min_pitch_hz=0.0, max_pitch_hz=0.0, median_pitch_hz=0.0,
                          voiced_ratio=1.0, confidence=None, mode="real",
                          model_version=MODEL_VERSION, warnings=[])

    def test_unsupported_sample_rate_fails_without_worker(self):
        audio = AudioData(waveform=[0.1, 0.2], sample_rate=8000,
                          duration_s=2 / 8000, warnings=[])
        with patch("suara.pitch.subprocess.run") as run:
            with self.assertRaises(PipelineError) as caught:
                analyze_pitch(audio)
        self.assertEqual(caught.exception.error.code, "invalid_audio")
        run.assert_not_called()

    def test_request_serialization_does_not_change_audio(self):
        audio = tiny_audio()
        before = list(audio.waveform)
        payload = _encode_request(audio)
        metadata_size = int.from_bytes(payload[8:12], "big")
        metadata = json.loads(payload[12:12 + metadata_size])
        self.assertEqual(metadata["sample_count"], len(audio.waveform))
        self.assertEqual(metadata["sample_rate"], 16000)
        self.assertEqual(audio.waveform, before)


@unittest.skipUnless(os.environ.get("SUARA_CREPE_INTEGRATION") == "1",
                     "set SUARA_CREPE_INTEGRATION=1 to run the real CREPE worker")
class CrepeIntegrationTests(SyntheticTestCase):
    def test_generated_220_hz_tone_runs_in_isolated_worker(self):
        rate = 16000
        time = np.arange(rate, dtype=np.float64) / rate
        samples = (0.25 * np.sin(2 * math.pi * 220 * time)).tolist()
        result = analyze_pitch(AudioData(waveform=samples, sample_rate=rate,
                                         duration_s=1.0, warnings=[]))
        self.assertEqual(result.mode, "real")
        self.assertGreater(result.voiced_ratio, 0.5)
        self.assertAlmostEqual(result.median_pitch_hz, 220, delta=8)
