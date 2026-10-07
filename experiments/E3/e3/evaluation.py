"""Metrics: frame pitch accuracy, note precision/recall/F1, range and concentration band errors.

Note matching uses mir_eval's one-to-one transcription matching (onset within 50 ms, pitch
within 50 cents); offsets are reported separately.
"""
from __future__ import annotations

import warnings

import mir_eval
import numpy as np
import pandas as pd

from .profiles import profile_stats
from .references import contour_to_frames, frame_grid, notes_to_frames


def _note_arrays(notes: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    if notes.empty:
        return np.zeros((0, 2)), np.zeros(0)
    return (notes[["start_s", "end_s"]].to_numpy(float),
            mir_eval.util.midi_to_hz(notes["midi_note"].to_numpy(float)))


def frame_metrics(ref: np.ndarray, est: np.ndarray, cents: float) -> dict:
    """ref/est are MIDI pitch per frame with NaN for unvoiced. Missing predictions on reference
    voiced frames count as failures."""
    rv, ev = np.isfinite(ref), np.isfinite(est)
    both = rv & ev
    diff = np.full(ref.shape, np.nan)
    diff[both] = np.abs(est[both] - ref[both])
    correct = both & (diff * 100 <= cents)
    octave = both & ~correct & ((np.abs(diff - 12) * 100 <= cents) | (np.abs(diff - 24) * 100 <= cents))
    n_ref = int(rv.sum())
    return {
        "ref_voiced_frames": n_ref,
        "frame_accuracy": float(correct.sum() / n_ref) if n_ref else np.nan,
        "voicing_recall": float(both.sum() / n_ref) if n_ref else np.nan,
        "voicing_false_alarm": float((ev & ~rv).sum() / max((~rv).sum(), 1)),
        "octave_error_rate": float(octave.sum() / n_ref) if n_ref else np.nan,
        "median_abs_cents_voiced": float(np.nanmedian(diff[both]) * 100) if both.any() else np.nan,
    }


def note_metrics(ref: pd.DataFrame, est: pd.DataFrame, cfg: dict) -> dict:
    ri, rp = _note_arrays(ref)
    ei, ep = _note_arrays(est)
    onset, cents = float(cfg["onset_tolerance_s"]), float(cfg["pitch_tolerance_cents"])
    out = {"ref_notes": len(ref), "est_notes": len(est)}
    if len(ri) == 0 or len(ei) == 0:
        return {**out, "note_precision": 0.0, "note_recall": 0.0, "note_f1": 0.0,
                "note_f1_with_offset": 0.0, "offset_f1": 0.0, "matched_notes": 0,
                "mean_abs_onset_error_s": np.nan, "mean_abs_offset_error_s": np.nan}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p, r, f, _ = mir_eval.transcription.precision_recall_f1_overlap(
            ri, rp, ei, ep, onset_tolerance=onset, pitch_tolerance=cents, offset_ratio=None)
        _, _, f_off, _ = mir_eval.transcription.precision_recall_f1_overlap(
            ri, rp, ei, ep, onset_tolerance=onset, pitch_tolerance=cents,
            offset_ratio=float(cfg["offset_ratio"]), offset_min_tolerance=float(cfg["offset_min_tolerance_s"]))
        _, _, f_offonly = mir_eval.transcription.offset_precision_recall_f1(
            ri, ei, offset_ratio=float(cfg["offset_ratio"]),
            offset_min_tolerance=float(cfg["offset_min_tolerance_s"]))
        match = mir_eval.transcription.match_notes(ri, rp, ei, ep, onset_tolerance=onset,
                                                   pitch_tolerance=cents, offset_ratio=None)
    m = np.array(match, dtype=int).reshape(-1, 2)
    return {**out, "note_precision": float(p), "note_recall": float(r), "note_f1": float(f),
            "note_f1_with_offset": float(f_off), "offset_f1": float(f_offonly), "matched_notes": len(m),
            "mean_abs_onset_error_s": float(np.mean(np.abs(ri[m[:, 0], 0] - ei[m[:, 1], 0]))) if len(m) else np.nan,
            "mean_abs_offset_error_s": float(np.mean(np.abs(ri[m[:, 0], 1] - ei[m[:, 1], 1]))) if len(m) else np.nan}


def range_metrics(ref: pd.DataFrame, est: pd.DataFrame, reliable_min_note_s: float) -> dict:
    r, e = profile_stats(ref, reliable_min_note_s), profile_stats(est, reliable_min_note_s)

    def err(k):
        return abs(e[k] - r[k]) if r[k] is not None and e[k] is not None else np.nan
    return {"low_error_st": err("low_midi"), "high_error_st": err("high_midi"),
            "p10_error_st": err("p10_midi"), "p90_error_st": err("p90_midi")}


def evaluate(ref_notes: pd.DataFrame, est_notes: pd.DataFrame, duration_s: float, cfg: dict,
             ref_f0: tuple | None = None, est_contour: pd.DataFrame | None = None) -> dict:
    """All metrics for one prediction. Frame accuracy uses the continuous contour when the
    method has one, and the verified F0 annotation as reference when available."""
    times = frame_grid(duration_s, float(cfg["frame_hop_s"]))
    ref_frames = contour_to_frames(*ref_f0, times) if ref_f0 is not None else notes_to_frames(ref_notes, times)
    if est_contour is not None:
        est_frames = contour_to_frames(est_contour["time_s"].to_numpy(float),
                                       est_contour["midi"].to_numpy(float), times)
    else:
        est_frames = notes_to_frames(est_notes, times)
    return {"frame_source": "contour" if est_contour is not None else "notes",
            "reference_frames": "f0_annotation" if ref_f0 is not None else "notes",
            **frame_metrics(ref_frames, est_frames, float(cfg["pitch_tolerance_cents"])),
            **note_metrics(ref_notes, est_notes, cfg),
            **range_metrics(ref_notes, est_notes, float(cfg["reliable_min_note_s"]))}


def quality_flags(m: dict, flag_cfg: dict) -> list[str]:
    flags = []
    if np.isfinite(m.get("octave_error_rate", np.nan)) and m["octave_error_rate"] > flag_cfg["octave_error_rate"]:
        flags.append("octave_errors")
    if np.isfinite(m.get("frame_accuracy", np.nan)) and m["frame_accuracy"] < flag_cfg["outlier_frame_accuracy"]:
        flags.append("outlier")
    if m.get("est_notes", 0) == 0:
        flags.append("no_notes")
    for k in ("low_error_st", "high_error_st"):
        if np.isfinite(m.get(k, np.nan)) and m[k] > flag_cfg["range_endpoint_semitones"]:
            flags.append("range_endpoint_off")
            break
    return flags


def target_check(rows: pd.DataFrame, target: dict) -> dict:
    """Pilot targets on clean test excerpts: mean frame accuracy, mean note F1 and every reliable
    range endpoint within the tolerance. These justify further testing only."""
    if rows.empty:
        return {"n_excerpts": 0}
    frame = float(rows["frame_accuracy"].mean())
    f1 = float(rows["note_f1"].mean())
    worst = float(np.nanmax(rows[["low_error_st", "high_error_st"]].to_numpy(float)))
    return {"n_excerpts": len(rows), "mean_frame_accuracy": frame, "mean_note_f1": f1,
            "worst_endpoint_error_st": worst,
            "frame_accuracy_met": frame >= target["min_frame_accuracy"],
            "note_f1_met": f1 >= target["min_note_f1"],
            "range_endpoints_met": worst <= target["max_endpoint_error_semitones"],
            "all_met": bool(frame >= target["min_frame_accuracy"] and f1 >= target["min_note_f1"]
                            and worst <= target["max_endpoint_error_semitones"])}
