"""Strict verification of the generated Phase 4A synthetic dataset only."""
import csv
import json
from pathlib import Path

import numpy as np
import soundfile as sf


def validate(config_path="config/e1_synthetic_tones.json", data_root="data"):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    root = Path(data_root)
    manifest = root / "manifests/e1_official_synthetic.csv"
    with manifest.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 12, f"expected 12 manifest rows, got {len(rows)}"
    ids = [r["recording_id"] for r in rows]
    assert len(set(ids)) == 12, "recording IDs are not unique"
    assert len(list((root / "raw/synthetic/official").glob("*.wav"))) == 12
    assert len(list((root / "references/synthetic/official").glob("*_reference.csv"))) == 12
    expected_frames = round(config["duration_s"] * config["sample_rate_hz"])
    expected_rows = round(config["duration_s"] / config["time_grid_s"])
    start, end = config["tone_interval_s"]
    by_id = {f"SYN_T01_R{i:03d}": tone for i, tone in enumerate(config["tones"], 1)}
    for row in rows:
        rid = row["recording_id"]
        assert rid in by_id
        assert row["recording_type"] == "synthetic"
        assert row["participant_id"] == "" and row["consent_status"] == "not_applicable"
        assert row["split"] == "test"
        audio_path, ref_path = root / row["audio_path"], root / row["reference_path"]
        assert audio_path.is_file() and ref_path.is_file()
        info = sf.info(str(audio_path))
        audio, rate = sf.read(str(audio_path), dtype="float32", always_2d=True)
        assert rate == config["sample_rate_hz"] and info.channels == 1
        assert audio.shape == (expected_frames, 1), f"{rid}: duration/frame count mismatch"
        assert info.subtype == "FLOAT", f"{rid}: expected floating-point WAV"
        assert float(np.max(np.abs(audio))) < 0.95, f"{rid}: clipping/peak limit exceeded"
        left = round(start * rate)
        right = round(end * rate)
        assert np.count_nonzero(audio[:left]) == 0 and np.count_nonzero(audio[right:]) == 0, f"{rid}: silence regions are not silent"
        assert np.max(np.abs(audio[left + round(0.06 * rate):right - round(0.06 * rate)])) > 0.1
        with ref_path.open(newline="", encoding="utf-8") as f:
            refs = list(csv.DictReader(f))
        assert len(refs) == expected_rows, f"{rid}: reference row count mismatch"
        expected_f0 = float(by_id[rid]["target_f0_hz"])
        for frame, ref in enumerate(refs):
            time_s = frame * config["time_grid_s"]
            voiced = start <= time_s < end
            assert ref["recording_id"] == rid
            assert abs(float(ref["time_s"]) - time_s) < 1e-9, f"{rid}: time grid mismatch at {frame}"
            assert ref["voiced"] == str(voiced).lower(), f"{rid}: voicing mismatch at {time_s}"
            if voiced:
                assert abs(float(ref["reference_f0_hz"]) - expected_f0) < 1e-10, f"{rid}: F0 mismatch"
            else:
                assert ref["reference_f0_hz"] == "", f"{rid}: unvoiced reference F0 must be missing"
        assert abs(float(row["duration"]) - config["duration_s"]) < 1e-12
        assert int(row["original_sample_rate"]) == rate and int(row["working_sample_rate"]) == rate
    print("Synthetic dataset verification OK: 12 WAVs, 12 exact references, 16 kHz mono float, 3.0 s, correct silence/voicing/F0 grid, no clipping")


if __name__ == "__main__":
    validate()
