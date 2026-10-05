"""Generate synthetic 'singers' to smoke-test the pipeline end to end.

    python tools/make_synthetic_data.py --out data/synthetic

Each synthetic singer has a register offset, formant scaling, vibrato and breathiness;
three shared melodies are sung in two takes, plus a simulated second-device variant of
each M03 take. This checks the code path only - it says nothing about real singing
voices, and results on it must never be reported as experimental evidence.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf
from scipy.signal import butter, sosfilt

SR = 16000
MELODIES = {  # MIDI notes relative to the singer's register, (note, beats)
    "M01": [(0, 1), (2, 1), (4, 1), (5, 1), (7, 2), (5, 1), (4, 1), (2, 1), (0, 2), (4, 1), (7, 1), (9, 2), (7, 2)],
    "M02": [(7, 2), (5, 1), (4, 1), (2, 2), (0, 1), (2, 1), (4, 2), (5, 1), (7, 1), (4, 2), (2, 1), (0, 3)],
    "M03": [(0, 1), (0, 1), (7, 1), (7, 1), (9, 1), (9, 1), (7, 2), (5, 1), (5, 1), (4, 1), (4, 1), (2, 1), (2, 1), (0, 2)],
}
VOWELS = [(800, 1200, 2500), (400, 2000, 2600), (300, 870, 2250), (500, 1700, 2500), (350, 600, 2400)]


def singer_params(rng, i):
    return {"base_midi": rng.choice([48, 52, 55, 57, 60, 64]) + rng.integers(-2, 3),
            "formant_scale": rng.uniform(0.85, 1.2), "tilt_db": rng.uniform(-14, -8),
            "vib_rate": rng.uniform(4.5, 6.5), "vib_depth": rng.uniform(0.2, 0.6),
            "breath": rng.uniform(0.005, 0.03), "bandwidth": rng.uniform(80, 160)}


def sing(p, melody, rng, beat_s=0.75):
    notes = MELODIES[melody]
    beat_s *= rng.uniform(0.95, 1.05)
    f0, amp, vowel_idx = [], [], []
    for n, (step, beats) in enumerate(notes):
        dur = int(beat_s * beats * SR)
        t = np.arange(dur) / SR
        midi = p["base_midi"] + step + p["vib_depth"] * np.sin(2 * np.pi * p["vib_rate"] * t) * np.minimum(t / 0.3, 1)
        f0.append(440 * 2 ** ((midi - 69) / 12))
        env = np.minimum(1, t / 0.04) * np.minimum(1, (t[::-1]) / 0.08)
        amp.append(env * rng.uniform(0.8, 1.0))
        vowel_idx.append(np.full(dur, n % len(VOWELS)))
    f0, amp, vowel_idx = map(np.concatenate, (f0, amp, vowel_idx))
    phase = 2 * np.pi * np.cumsum(f0) / SR
    y = np.zeros_like(f0)
    formants = np.array(VOWELS)[vowel_idx] * p["formant_scale"]
    for h in range(1, 60):
        fh = h * f0
        ok = fh < 7000
        if not ok.any():
            break
        env = sum(np.exp(-0.5 * ((fh - formants[:, k]) / p["bandwidth"]) ** 2) for k in range(3))
        gain = 10 ** (p["tilt_db"] * np.log2(h) / 20) * (0.15 + env)
        y += ok * gain * np.sin(h * phase)
    y = y * amp + p["breath"] * rng.standard_normal(len(y)) * amp
    y /= np.max(np.abs(y)) + 1e-9
    pad = np.zeros(int(0.5 * SR))
    return (0.7 * np.concatenate([pad, y, pad])).astype(np.float32)


def second_device(y, rng):
    sos = butter(4, [250, 5000], btype="band", fs=SR, output="sos")
    z = sosfilt(sos, y) + 0.01 * rng.standard_normal(len(y))
    return (0.7 * z / np.max(np.abs(z))).astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/synthetic"))
    ap.add_argument("--singers", type=int, default=6)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    raw = args.out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(1, args.singers + 1):
        p = singer_params(rng, i)
        for melody in MELODIES:
            for take in ("T01", "T02"):
                rid = f"P{i:02d}_{melody}_{take}"
                y = sing(p, melody, rng)
                sf.write(raw / f"{rid}.wav", y, SR)
                base = {"participant_id": f"P{i:02d}", "melody_id": melody, "take": take,
                        "key": f"midi{p['base_midi']}", "duration_s": round(len(y) / SR, 3),
                        "consent": "synthetic", "excluded": "false", "exclusion_reason": "",
                        "notes": "synthetic test signal"}
                rows.append({"recording_id": rid, **base, "device": "synthetic_mic1",
                             "file_path": f"{rid}.wav", "condition": "original", "parent_recording_id": ""})
                if melody == "M03":
                    vid = f"{rid}_D2"
                    sf.write(raw / f"{vid}.wav", second_device(y, rng), SR)
                    rows.append({"recording_id": vid, **base, "device": "synthetic_mic2",
                                 "file_path": f"{vid}.wav", "condition": "device2", "parent_recording_id": rid})
    pd.DataFrame(rows).to_csv(args.out / "manifest.csv", index=False)
    print(f"Wrote {len(rows)} synthetic clips and manifest to {args.out}")


if __name__ == "__main__":
    main()
