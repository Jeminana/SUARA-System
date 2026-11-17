#!/usr/bin/env python3
"""Isolated CREPE 0.0.12 worker; protocol data only on stdin/stdout."""
from __future__ import annotations

import array
import json
import math
import os
import struct
import sys

PROTOCOL = "suara-crepe-worker-v1"
MAGIC = b"SUARAP01"
SAMPLE_RATE = 16000
MAX_SAMPLES = SAMPLE_RATE * 60
MAX_METADATA = 4096


class RequestError(ValueError):
    pass


def read_exact(stream, count: int) -> bytes:
    pieces = bytearray()
    while len(pieces) < count:
        part = stream.read(count - len(pieces))
        if not part:
            raise RequestError("truncated request")
        pieces.extend(part)
    return bytes(pieces)


def load_request() -> tuple[list[float], int]:
    stream = sys.stdin.buffer
    if read_exact(stream, len(MAGIC)) != MAGIC:
        raise RequestError("invalid request magic")
    metadata_size = struct.unpack(">I", read_exact(stream, 4))[0]
    if not 1 <= metadata_size <= MAX_METADATA:
        raise RequestError("invalid metadata size")
    try:
        metadata = json.loads(read_exact(stream, metadata_size).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestError("invalid request metadata") from exc
    if (not isinstance(metadata, dict)
            or set(metadata) != {"protocol", "sample_rate", "sample_count"}
            or metadata["protocol"] != PROTOCOL):
        raise RequestError("unsupported request schema")
    rate, count = metadata["sample_rate"], metadata["sample_count"]
    if type(rate) is not int or rate != SAMPLE_RATE:
        raise RequestError("sample rate must be 16000 Hz")
    if type(count) is not int or not 1 <= count <= MAX_SAMPLES:
        raise RequestError("sample count is outside supported bounds")
    payload_size = count * 4
    payload = read_exact(stream, payload_size)
    if stream.read(1):
        raise RequestError("trailing request data")
    waveform = array.array("f")
    waveform.frombytes(payload)
    if sys.byteorder != "little":
        waveform.byteswap()
    if not all(math.isfinite(value) and abs(value) <= 1 for value in waveform):
        raise RequestError("waveform samples must be finite and normalized")
    return waveform, rate


def main() -> int:
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    try:
        waveform, sample_rate = load_request()
    except (RequestError, struct.error) as exc:
        print(f"Invalid CREPE worker request: {exc}.", file=sys.stderr)
        return 2
    try:
        import crepe
        import numpy as np

        # CREPE's public predict() does not expose batch_size; it delegates to
        # keras.Model.predict(), so pin the E1 setting at that boundary.
        model = crepe.core.build_and_load_model("tiny")
        predict = model.predict

        def predict_batch_32(inputs, **kwargs):
            kwargs.setdefault("batch_size", 32)
            return predict(inputs, **kwargs)

        model.predict = predict_batch_32
        times, frequency, confidence, _ = crepe.predict(
            np.asarray(waveform, dtype=np.float32), sample_rate,
            model_capacity="tiny", viterbi=False, center=True,
            step_size=10, verbose=0,
        )
        del times
        frequency = np.asarray(frequency, dtype=np.float64)
        confidence = np.asarray(confidence, dtype=np.float64)
        if frequency.ndim != 1 or confidence.ndim != 1 or frequency.shape != confidence.shape:
            raise RuntimeError("unexpected detector output dimensions")
        response = {
            "protocol": PROTOCOL,
            "frames": [
                {"frequency_hz": float(hz) if np.isfinite(hz) else None,
                 "confidence": float(score) if np.isfinite(score) else None}
                for hz, score in zip(frequency, confidence, strict=True)
            ],
        }
        sys.stdout.write(json.dumps(response, allow_nan=False, separators=(",", ":")))
        sys.stdout.write("\n")
        sys.stdout.flush()
        return 0
    except Exception:
        # Keep exception messages and any paths/audio details out of public logs.
        print("CREPE inference failed.", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
