#!/usr/bin/env python3
"""Generate and analyze a known sine WAV as a software smoke test only."""

from __future__ import annotations

import argparse
import csv
import os
import warnings
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


ROOT = Path(__file__).resolve().parents[1]
TARGET_SR = 16_000
FREQUENCY_HZ = 220.0
DURATION_S = 3.0
GRID_S = 0.010


def generate_fixture(path: Path) -> None:
    source_sr = 22_050
    samples = np.arange(round(source_sr * DURATION_S), dtype=np.float64) / source_sr
    waveform = 0.5 * np.sin(2.0 * np.pi * FREQUENCY_HZ * samples)
    fade_length = round(0.02 * source_sr)
    fade = np.ones_like(waveform)
    fade[:fade_length] = np.linspace(0.0, 1.0, fade_length, endpoint=False)
    fade[-fade_length:] = np.linspace(1.0, 0.0, fade_length, endpoint=False)
    waveform *= fade
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, waveform.astype(np.float32), source_sr, subtype="FLOAT")


def load_standardized(path: Path) -> np.ndarray:
    audio, source_sr = sf.read(path, dtype="float32", always_2d=True)
    mono = audio.mean(axis=1, dtype=np.float32)
    if source_sr != TARGET_SR:
        from math import gcd

        divisor = gcd(source_sr, TARGET_SR)
        mono = resample_poly(mono, TARGET_SR // divisor, source_sr // divisor).astype(np.float32)
    if mono.ndim != 1 or not np.isfinite(mono).all():
        raise ValueError("Standardized waveform must be finite, mono floating-point data")
    return mono


def write_csv(path: Path, times: np.ndarray, f0: np.ndarray, voiced: np.ndarray, confidence: np.ndarray, detector: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if detector == "pyin":
            writer.writerow(("time_s", "f0_hz", "voiced_flag", "voiced_probability", "artifact_type"))
        else:
            writer.writerow(("time_s", "frequency_hz", "confidence", "voiced_flag", "artifact_type"))
        for t, hz, is_voiced, conf in zip(times, f0, voiced, confidence, strict=True):
            writer.writerow((f"{t:.6f}", "" if not np.isfinite(hz) else f"{hz:.6f}", int(is_voiced), f"{conf:.6f}", "smoke_test_fixture"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detector", choices=("pyin", "crepe"), required=True)
    args = parser.parse_args()
    detector = args.detector
    cache_root = ROOT / "outputs" / ".cache"
    (cache_root / "matplotlib").mkdir(parents=True, exist_ok=True)
    (cache_root / "fontconfig").mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib"))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_root))
    fixture = ROOT / "data" / "smoke" / "sine_220hz_source.wav"
    output = ROOT / "outputs" / "smoke" / f"{detector}_raw.csv"
    standardized_path = ROOT / "data" / "smoke" / "sine_220hz_mono_16khz_float.wav"

    generate_fixture(fixture)
    waveform = load_standardized(fixture)
    sf.write(standardized_path, waveform, TARGET_SR, subtype="FLOAT")
    if len(waveform) != round(TARGET_SR * DURATION_S):
        raise RuntimeError(f"Unexpected standardized sample count: {len(waveform)}")

    if detector == "pyin":
        import librosa

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            f0, voiced, probability = librosa.pyin(
                waveform,
                fmin=float(librosa.note_to_hz("C2")),
                fmax=float(librosa.note_to_hz("C6")),
                sr=TARGET_SR,
                frame_length=2048,
                hop_length=160,
                fill_na=np.nan,
            )
        for warning in captured:
            print(f"WARNING: {warning.message}")
        times = librosa.times_like(f0, sr=TARGET_SR, hop_length=160)
        confidence = probability
    else:
        import crepe

        times, f0, confidence, _ = crepe.predict(
            waveform,
            TARGET_SR,
            step_size=10,
            model_capacity="tiny",
            viterbi=False,
            verbose=1,
        )
        f0 = np.asarray(f0, dtype=float)
        voiced = np.isfinite(f0) & (f0 > 0)
        f0[~voiced] = np.nan

    times = np.asarray(times, dtype=float)
    f0 = np.asarray(f0, dtype=float)
    voiced = np.asarray(voiced, dtype=bool)
    confidence = np.asarray(confidence, dtype=float)
    write_csv(output, times, f0, voiced, confidence, detector)

    time_steps = np.diff(times)
    grid_ok = bool(len(time_steps) and np.allclose(time_steps, GRID_S, atol=1e-6, rtol=0.0))
    central = (times >= 0.5) & (times <= 2.5) & voiced & np.isfinite(f0) & (f0 > 0)
    estimate = float(np.median(f0[central])) if central.any() else float("nan")
    error_cents = float(1200.0 * np.log2(estimate / FREQUENCY_HZ)) if np.isfinite(estimate) else float("nan")
    plausible = bool(np.isfinite(error_cents) and abs(error_cents) <= 100.0)
    print(f"detector={detector}")
    print(f"fixture={fixture.relative_to(ROOT)} (software fixture, not experiment evidence)")
    print(f"standardized={standardized_path.relative_to(ROOT)} samples={len(waveform)} sr={TARGET_SR} dtype={waveform.dtype} channels=1")
    print(f"output={output.relative_to(ROOT)} frames={len(times)}")
    print(f"expected_f0_hz={FREQUENCY_HZ:.3f} median_f0_hz={estimate:.3f} error_cents={error_cents:.2f} plausible_within_100_cents={plausible}")
    print(f"grid_10ms={grid_ok} median_step_s={float(np.median(time_steps)) if len(time_steps) else float('nan'):.6f}")
    if not plausible or not grid_ok:
        raise SystemExit("Smoke test validation failed; outputs are retained for inspection.")


if __name__ == "__main__":
    main()
