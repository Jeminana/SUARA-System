"""Audio loading, preprocessing, quality checks, windowing and stress perturbations."""
from __future__ import annotations

import zlib

import librosa
import numpy as np
import soundfile as sf


def load_mono(path: str) -> tuple[np.ndarray, int]:
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    return data.mean(axis=1), sr


def resample(y: np.ndarray, sr: int, target_sr: int, res_type: str) -> np.ndarray:
    if sr == target_sr:
        return y
    return librosa.resample(y, orig_sr=sr, target_sr=target_sr, res_type=res_type).astype(np.float32)


def trim_edges(y: np.ndarray, top_db: float) -> tuple[np.ndarray, int, int]:
    """Remove only leading/trailing audio below peak - top_db; breaths and vowels inside are kept."""
    _, (start, end) = librosa.effects.trim(y, top_db=top_db, frame_length=1024, hop_length=256)
    return y[start:end], int(start), int(end)


def apply_gain(y: np.ndarray, mode: str, target_dbfs: float) -> tuple[np.ndarray, float]:
    if mode == "none":
        return y, 1.0
    if mode == "peak":
        level = float(np.max(np.abs(y)))
    elif mode == "rms":
        level = float(np.sqrt(np.mean(y ** 2)))
    else:
        raise ValueError(f"Unknown gain mode: {mode}")
    if level <= 1e-9:
        return y, 1.0
    gain = 10 ** (target_dbfs / 20) / level
    return (y * gain).astype(np.float32), gain


def quality_metrics(y: np.ndarray, sr: int, qc: dict) -> dict:
    """Metrics on the resampled, untrimmed, un-normalised audio."""
    active = librosa.effects.split(y, top_db=qc["silence_top_db"])
    active_samples = int(sum(e - s for s, e in active))
    return {
        "duration_s": len(y) / sr,
        "peak": float(np.max(np.abs(y))) if len(y) else 0.0,
        "clip_fraction": float(np.mean(np.abs(y) >= qc["clip_threshold"])) if len(y) else 0.0,
        "silence_fraction": 1.0 - active_samples / max(len(y), 1),
    }


def qc_flags(metrics: dict, qc: dict) -> list[str]:
    flags = []
    if metrics["clip_fraction"] > qc["max_clip_fraction"]:
        flags.append("clipping")
    if metrics["silence_fraction"] > qc["max_silence_fraction"]:
        flags.append("excessive_silence")
    if not qc["min_duration_s"] <= metrics["duration_s"] <= qc["max_duration_s"]:
        flags.append("duration_out_of_range")
    return flags


def activity_ratio_fn(y: np.ndarray, sr: int, cfg: dict):
    """Return f(start, end) -> fraction of frames in [start, end) samples that are active/voiced."""
    hop = 256
    if cfg["method"] == "pyin":
        _, voiced, _ = librosa.pyin(y, sr=sr, fmin=librosa.note_to_hz(cfg["pyin_fmin_note"]),
                                    fmax=librosa.note_to_hz(cfg["pyin_fmax_note"]),
                                    frame_length=1024, hop_length=hop)
        frames = voiced.astype(bool)
    elif cfg["method"] == "energy":
        frames = np.zeros(1 + len(y) // hop, dtype=bool)
        for s, e in librosa.effects.split(y, top_db=cfg["energy_top_db"], frame_length=1024, hop_length=hop):
            frames[s // hop:e // hop + 1] = True
    else:
        raise ValueError(f"Unknown activity method: {cfg['method']}")

    def ratio(start: int, end: int) -> float:
        seg = frames[start // hop:max(end // hop, start // hop + 1)]
        return float(seg.mean()) if len(seg) else 0.0

    return ratio


def fixed_windows(y: np.ndarray, sr: int, window_s: float, min_active_ratio: float,
                  activity_cfg: dict) -> list[dict]:
    """Non-overlapping fixed windows; the remainder shorter than a window is dropped.

    A clip shorter than one window becomes a single whole-clip window (flagged)."""
    win = int(round(window_s * sr))
    ratio = activity_ratio_fn(y, sr, activity_cfg)
    bounds = [(s, s + win) for s in range(0, len(y) - win + 1, win)]
    short = not bounds
    if short:
        bounds = [(0, len(y))]
    windows = []
    for s, e in bounds:
        r = ratio(s, e)
        windows.append({"start_s": s / sr, "end_s": e / sr, "start": s, "end": e,
                        "active_ratio": r, "accepted": r >= min_active_ratio,
                        "rule": "short_clip_single_window" if short else "fixed_window"})
    return windows


def stable_rng(seed: int, key: str) -> np.random.Generator:
    return np.random.default_rng([seed, zlib.crc32(key.encode())])


def add_white_noise(y: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    signal_power = float(np.mean(y ** 2))
    noise = rng.standard_normal(len(y)).astype(np.float32)
    noise *= np.sqrt(signal_power / (10 ** (snr_db / 10)))
    return y + noise


def centre_crop(y: np.ndarray, sr: int, seconds: float) -> np.ndarray:
    n = int(round(seconds * sr))
    if n >= len(y):
        return y
    start = (len(y) - n) // 2
    return y[start:start + n]
