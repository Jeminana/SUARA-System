"""Song and melody profiles for the E4/E5 handoff.

Duration weighting: each note contributes according to its sounding duration. The 10th-90th
percentile band is a melody concentration proxy for the excerpt; it is not a singer comfort
range. Every profile here describes an excerpt, never a complete song.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .references import note_name

PROFILE_FIELDS = ["song_id", "excerpt_start_s", "excerpt_end_s", "low_midi", "high_midi", "p10_midi",
                  "p90_midi", "verified_key", "bpm", "source_type", "method", "verified_by", "quality_flag"]


def weighted_percentile(pitches: np.ndarray, weights: np.ndarray, q: float) -> float | None:
    if len(pitches) == 0 or weights.sum() <= 0:
        return None
    order = np.argsort(pitches)
    p, w = pitches[order], weights[order]
    cum = np.cumsum(w) / w.sum()
    return float(p[min(np.searchsorted(cum, q / 100.0), len(p) - 1)])


def profile_stats(notes: pd.DataFrame, reliable_min_note_s: float) -> dict:
    """Reliable endpoints ignore notes shorter than reliable_min_note_s (grace notes, glitches)."""
    if notes.empty:
        return {"low_midi": None, "high_midi": None, "p10_midi": None, "p90_midi": None,
                "sounding_s": 0.0, "n_notes": 0, "mean_abs_interval_st": None, "max_interval_st": None}
    dur = (notes["end_s"] - notes["start_s"]).to_numpy(float)
    pitch = notes["midi_note"].to_numpy(float)
    reliable = pitch[dur >= reliable_min_note_s]
    steps = np.abs(np.diff(notes.sort_values("start_s")["midi_note"].to_numpy(float)))
    return {"low_midi": float(reliable.min()) if len(reliable) else None,
            "high_midi": float(reliable.max()) if len(reliable) else None,
            "p10_midi": weighted_percentile(pitch, dur, 10),
            "p90_midi": weighted_percentile(pitch, dur, 90),
            "sounding_s": float(dur.sum()), "n_notes": len(notes),
            "mean_abs_interval_st": float(steps.mean()) if len(steps) else None,
            "max_interval_st": float(steps.max()) if len(steps) else None}


def histogram(notes: pd.DataFrame) -> pd.DataFrame:
    """Duration-weighted pitch histogram with one bin per semitone."""
    if notes.empty:
        return pd.DataFrame(columns=["midi_note", "note_name", "seconds", "fraction"])
    dur = notes["end_s"] - notes["start_s"]
    h = dur.groupby(notes["midi_note"].round().astype(int)).sum().rename("seconds").reset_index()
    h["note_name"] = h["midi_note"].map(note_name)
    h["fraction"] = h["seconds"] / h["seconds"].sum()
    return h[["midi_note", "note_name", "seconds", "fraction"]]


def profile_row(song: dict, notes: pd.DataFrame, reliable_min_note_s: float, source_type: str,
                method: str, verified_by: str, flags: list[str], version: str) -> dict:
    s = profile_stats(notes, reliable_min_note_s)
    unknown = "unknown"  # key and tempo are never guessed
    return {"song_id": song["song_id"], "excerpt_start_s": float(song["excerpt_start_s"]),
            "excerpt_end_s": float(song["excerpt_end_s"]),
            "low_midi": s["low_midi"], "high_midi": s["high_midi"],
            "p10_midi": s["p10_midi"], "p90_midi": s["p90_midi"],
            "verified_key": song.get("verified_key") or unknown, "bpm": song.get("bpm") or unknown,
            "source_type": source_type, "method": method, "verified_by": verified_by or "unverified",
            "quality_flag": ";".join(["excerpt", *flags]), "profile_version": version,
            "low_note": note_name(s["low_midi"]), "high_note": note_name(s["high_midi"]),
            "n_notes": s["n_notes"], "sounding_s": s["sounding_s"],
            "mean_abs_interval_st": s["mean_abs_interval_st"], "max_interval_st": s["max_interval_st"]}
