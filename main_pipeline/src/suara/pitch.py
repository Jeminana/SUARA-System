"""CREPE tiny pitch adapter backed by an isolated E1-compatible worker."""
from __future__ import annotations

import array
import json
import math
import os
import subprocess
from pathlib import Path
from statistics import median

from suara.contracts import AudioData, DEFAULT_SAMPLE_RATE, PitchFeatures
from suara.errors import failure

WORKER_PROTOCOL = "suara-crepe-worker-v1"
MODEL_VERSION = "crepe-0.0.12-tiny-16khz-10ms-v1"
DEFAULT_TIMEOUT_S = 120.0
MAX_REQUEST_METADATA = 4096
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_AUDIO_SAMPLES = DEFAULT_SAMPLE_RATE * 60
VOICING_THRESHOLD = 0.5
_REQUEST_MAGIC = b"SUARAP01"


def _module_failure(message: str):
    return failure("module_failure", "pitch", message)


def _worker_timeout() -> float:
    raw = os.environ.get("SUARA_CREPE_TIMEOUT_S", str(DEFAULT_TIMEOUT_S))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise failure("invalid_configuration", "configuration",
                      "SUARA_CREPE_TIMEOUT_S must be a positive finite number.") from None
    if not math.isfinite(value) or value <= 0:
        raise failure("invalid_configuration", "configuration",
                      "SUARA_CREPE_TIMEOUT_S must be a positive finite number.")
    return value


def _worker_command() -> list[str]:
    configured = os.environ.get("SUARA_CREPE_PYTHON", "").strip()
    if not configured:
        raise failure("invalid_configuration", "configuration",
                      "Real pitch analysis requires SUARA_CREPE_PYTHON to point to the CREPE worker interpreter.")
    executable = Path(configured).expanduser()
    if not executable.is_absolute() or not executable.is_file() or not os.access(executable, os.X_OK):
        raise failure("invalid_configuration", "configuration",
                      "SUARA_CREPE_PYTHON must be an executable absolute path.")
    worker = (Path(__file__).resolve().parents[2] / "tools" / "crepe_pitch_worker.py").resolve()
    if not worker.is_file():
        raise _module_failure("CREPE worker program is unavailable.")
    return [str(executable), str(worker)]


def _encode_request(audio_data: AudioData) -> bytes:
    audio_data.validate()
    if audio_data.sample_rate != DEFAULT_SAMPLE_RATE:
        raise failure("invalid_audio", "pitch", "Pitch analysis requires mono audio at 16000 Hz.")
    count = len(audio_data.waveform)
    if count > MAX_AUDIO_SAMPLES:
        raise failure("invalid_audio", "pitch", "Audio sample count exceeds the supported duration.")
    metadata = json.dumps({
        "protocol": WORKER_PROTOCOL,
        "sample_rate": audio_data.sample_rate,
        "sample_count": count,
    }, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if not metadata or len(metadata) > MAX_REQUEST_METADATA:
        raise _module_failure("Pitch worker request metadata is invalid.")
    samples = array.array("f", audio_data.waveform)
    if samples.itemsize != 4:
        raise _module_failure("This platform cannot encode float32 pitch input.")
    if os.sys.byteorder != "little":
        samples.byteswap()
    return _REQUEST_MAGIC + len(metadata).to_bytes(4, "big") + metadata + samples.tobytes()


def _parse_response(stdout: bytes) -> list[tuple[float, float]]:
    if not isinstance(stdout, bytes) or len(stdout) > MAX_RESPONSE_BYTES:
        raise _module_failure("Pitch worker returned an invalid response size.")
    try:
        response = json.loads(stdout.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise _module_failure("Pitch worker returned malformed JSON.") from None
    if not isinstance(response, dict) or set(response) != {"protocol", "frames"}:
        raise _module_failure("Pitch worker returned an invalid response schema.")
    if response["protocol"] != WORKER_PROTOCOL or not isinstance(response["frames"], list):
        raise _module_failure("Pitch worker returned an unsupported response.")
    frames = response["frames"]
    if not frames or len(frames) > MAX_AUDIO_SAMPLES // 160 + 2:
        raise _module_failure("Pitch worker returned an invalid frame count.")
    parsed: list[tuple[float, float]] = []
    for frame in frames:
        if not isinstance(frame, dict) or set(frame) != {"frequency_hz", "confidence"}:
            raise _module_failure("Pitch worker returned an invalid frame schema.")
        frequency, confidence = frame["frequency_hz"], frame["confidence"]
        # JSON booleans are integers in Python, but are never numeric detector output.
        if (frequency is not None and type(frequency) not in (int, float)) or (
                confidence is not None and type(confidence) not in (int, float)):
            raise _module_failure("Pitch worker returned nonnumeric frame data.")
        parsed.append((float("nan") if frequency is None else float(frequency),
                       float("nan") if confidence is None else float(confidence)))
    return parsed


def _reject_json_constant(value: str):
    raise ValueError(f"non-standard JSON constant: {value}")


def analyze_pitch(audio_data: AudioData) -> PitchFeatures:
    """Measure CREPE tiny F0 through the configured isolated Python worker.

    The input is validated and serialized without modification. Worker failures
    raise a safe pitch-stage error; an empty accepted-voicing set is valid output.
    """
    audio_data.validate()
    if audio_data.sample_rate != DEFAULT_SAMPLE_RATE:
        raise failure("invalid_audio", "pitch", "Pitch analysis requires mono audio at 16000 Hz.")
    command = _worker_command()
    timeout = _worker_timeout()
    request = _encode_request(audio_data)
    worker_env = os.environ.copy()
    worker_env["CUDA_VISIBLE_DEVICES"] = "-1"
    worker_env.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    try:
        completed = subprocess.run(
            command, input=request, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, check=False, shell=False, env=worker_env,
        )
    except subprocess.TimeoutExpired:
        raise _module_failure("CREPE pitch analysis exceeded its configured timeout.") from None
    except OSError:
        raise _module_failure("CREPE worker could not be started.") from None
    if completed.returncode != 0:
        raise _module_failure("CREPE worker failed; no pitch result was produced.")
    frames = _parse_response(completed.stdout)
    accepted = [frequency for frequency, confidence in frames
                if math.isfinite(frequency) and frequency > 0
                and math.isfinite(confidence) and 0 <= confidence <= 1
                and confidence >= VOICING_THRESHOLD]
    ratio = len(accepted) / len(frames)
    warnings: list[str] = []
    if not accepted:
        warnings.append("No voiced pitch frames passed the CREPE confidence and value checks.")
        result = PitchFeatures(
            min_pitch_hz=None, max_pitch_hz=None, median_pitch_hz=None,
            voiced_ratio=0.0, confidence=None, mode="real", model_version=MODEL_VERSION,
            warnings=warnings,
        )
    else:
        accepted_confidence = [confidence for frequency, confidence in frames
                               if math.isfinite(frequency) and frequency > 0
                               and math.isfinite(confidence) and 0 <= confidence <= 1
                               and confidence >= VOICING_THRESHOLD]
        result = PitchFeatures(
            min_pitch_hz=float(min(accepted)), max_pitch_hz=float(max(accepted)),
            median_pitch_hz=float(median(accepted)), voiced_ratio=float(ratio),
            confidence=float(sum(accepted_confidence) / len(accepted_confidence)),
            mode="real", model_version=MODEL_VERSION, warnings=warnings,
        )
    result.validate()
    return result


analyze_pitch.suara_mode = "real"
