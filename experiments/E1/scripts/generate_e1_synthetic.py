"""Generate the official deterministic Phase 4A E1 synthetic tone set."""
import argparse
import csv
import json
import struct
from pathlib import Path

import numpy as np


def tone_id(index):
    return f"SYN_T01_R{index:03d}"


def generate(config_path, data_root):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    rate = int(config["sample_rate_hz"])
    count = round(float(config["duration_s"]) * rate)
    start, end = (round(float(t) * rate) for t in config["tone_interval_s"])
    fade_in = round(float(config["fade_in_s"]) * rate)
    fade_out = round(float(config["fade_out_s"]) * rate)
    t = np.arange(count, dtype=np.float64) / rate
    envelope = np.zeros(count, dtype=np.float64)
    envelope[start:end] = 1.0
    # Raised-cosine ramps whose boundaries exactly match the tone interval.
    envelope[start:start + fade_in] = 0.5 - 0.5 * np.cos(np.pi * np.arange(fade_in) / fade_in)
    envelope[end - fade_out:end] = 0.5 + 0.5 * np.cos(np.pi * np.arange(fade_out) / fade_out)
    raw_root = Path(data_root) / "raw/synthetic/official"
    ref_root = Path(data_root) / "references/synthetic/official"
    manifest_path = Path(data_root) / "manifests/e1_official_synthetic.csv"
    raw_root.mkdir(parents=True, exist_ok=True)
    ref_root.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["recording_id", "participant_id", "task", "duration", "original_sample_rate", "working_sample_rate", "channel_count", "split", "reference_path", "audio_path", "consent_status", "condition", "noise_snr_db", "exclusion_status", "exclusion_reason", "parent_recording_id", "recording_type"]
    manifest_rows = []
    tones = config["tones"]
    if len(tones) != 12:
        raise ValueError(f"Configuration must contain exactly 12 tones, got {len(tones)}")
    for i, tone in enumerate(tones, 1):
        rid = tone_id(i)
        f0 = float(tone["target_f0_hz"])
        signal = np.zeros(count, dtype=np.float64)
        for harmonic in config["harmonics"]:
            multiple = int(harmonic["multiple"])
            amp = float(harmonic["relative_amplitude"])
            signal += amp * np.sin(2.0 * np.pi * f0 * multiple * t)
        signal *= envelope
        peak = float(np.max(np.abs(signal)))
        if peak > 0.95:
            raise ValueError(f"Generated signal would clip: {rid}, peak={peak}")
        audio_rel = f"raw/synthetic/official/{rid}.wav"
        ref_rel = f"references/synthetic/official/{rid}_reference.csv"
        # Write a minimal IEEE-float WAV directly. Some libsndfile builds add
        # a timestamped PEAK metadata chunk, breaking byte-for-byte reruns.
        samples = signal.astype("<f4").tobytes()
        data_size = len(samples)
        wav_header = struct.pack(
            "<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + data_size, b"WAVE",
            b"fmt ", 16, 3, 1, rate, rate * 4, 4, 32, b"data", data_size
        )
        (Path(data_root) / audio_rel).write_bytes(wav_header + samples)
        with (Path(data_root) / ref_rel).open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["recording_id", "time_s", "reference_f0_hz", "voiced"])
            for frame in range(round(float(config["duration_s"]) / float(config["time_grid_s"]))):
                time_s = frame * float(config["time_grid_s"])
                voiced = float(config["tone_interval_s"][0]) <= time_s < float(config["tone_interval_s"][1])
                writer.writerow([rid, f"{time_s:.2f}", f"{f0:.12f}" if voiced else "", str(voiced).lower()])
        manifest_rows.append({
            "recording_id": rid, "participant_id": "", "task": "synthetic_tone",
            "duration": f"{config['duration_s']:.3f}", "original_sample_rate": rate,
            "working_sample_rate": rate, "channel_count": 1, "split": "test",
            "reference_path": ref_rel, "audio_path": audio_rel,
            "consent_status": "not_applicable", "condition": "clean_synthetic_harmonic",
            "noise_snr_db": "", "exclusion_status": "included", "exclusion_reason": "",
            "parent_recording_id": "", "recording_type": "synthetic"
        })
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(f"Generated {len(manifest_rows)} synthetic recordings in {raw_root}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/e1_synthetic_tones.json")
    parser.add_argument("--data-root", default="data")
    args = parser.parse_args()
    generate(args.config, args.data_root)
