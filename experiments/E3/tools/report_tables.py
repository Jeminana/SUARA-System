"""Supporting tables for the report, computed from a finished test run (no tool is rerun).

    python tools/report_tables.py outputs/pilot_test --names athirah adib

Writes into the run folder:

- reviewer_sensitivity.csv  the run's methods scored three ways: against the agreed notes with
  unresolved spots left out (the main result), and against each reviewer's full annotation with
  nothing left out. If the conclusions agree, the unresolved spots do not change them.
- intended_vs_sung_aligned.csv  how often the sung pitch equals the intended MIDI pitch, note by
  note on the singer's timing (the DTW-aligned draft), per reviewer and for the agreed notes.
  The pipeline's intended_vs_sung.csv compares on MIDI time, so it mixes timing with pitch.
- frame_error_breakdown.csv  where the reference-voiced frames went for each contour method:
  correct, missed (no pitch), near miss (50 to 100 cents) or wrong (over 100 cents).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from e3 import evaluation as ev  # noqa: E402
from e3 import references as rf  # noqa: E402

TAGS = {"pyin": "pyin", "basic_pitch": "basic_pitch", "demucs+pyin": "demucs_pyin", "pyin_mix": "pyin_mix",
        "demucs+basic_pitch": "demucs_basic_pitch"}


def human_recordings(data: Path) -> tuple[pd.DataFrame, pd.Series]:
    recs = pd.read_csv(data / "recordings.csv", dtype=str, keep_default_na=False)
    cat = pd.read_csv(data / "catalog.csv").set_index("song_id")
    dur = cat["excerpt_end_s"] - cat["excerpt_start_s"]
    recs = recs[recs["kind"].isin(["isolated_vocal", "mix"]) & (recs["excluded"].str.lower() != "true")].copy()
    recs["take"] = np.where(recs["kind"] == "mix", recs["paired_with"], recs["recording_id"])
    recs["audio_offset_s"] = recs["audio_offset_s"].astype(float)
    return recs, dur


def outputs_for(run: Path, rid: str):
    """(method label, excerpt-time notes, excerpt-time contour or None) for each saved output."""
    d = run / "raw" / rid
    for label, tag in TAGS.items():
        f = d / f"{tag}_notes.csv"
        if f.is_file():
            c = d / f"{tag}_contour_audio_time.csv"
            yield label, rf.read_notes_csv(f), (pd.read_csv(c) if c.is_file() else None)


def excerpt_contour(c: pd.DataFrame | None, offset: float, dur: float) -> pd.DataFrame | None:
    if c is None:
        return None
    c = c.assign(time_s=c["time_s"] - offset)
    return c[(c["time_s"] >= 0) & (c["time_s"] < dur)].reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--names", nargs=2, required=True)
    ap.add_argument("--data", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = ap.parse_args()
    cfg = yaml.safe_load((args.run / "config_used.yaml").read_text())["evaluation"]
    ann = args.data / "annotations"
    recs, dur = human_recordings(args.data)
    tested = {p.name for p in (args.run / "raw").iterdir()}

    sens, breakdown = [], []
    for r in recs[recs["recording_id"].isin(tested)].itertuples():
        d, off = float(dur[r.song_id]), r.audio_offset_s
        refs = {"agreed notes, unresolved spots left out":
                (rf.shift_notes(rf.read_notes_csv(ann / f"{r.take}_verified.csv"), off, d),
                 rf.read_regions_csv(ann / f"{r.take}_unresolved.csv", off, d))}
        for who in args.names:
            refs[f"{who} full annotation"] = (rf.shift_notes(rf.read_notes_csv(ann / f"{r.take}_{who}.csv"), off, d),
                                             None)
        for label, notes, contour in outputs_for(args.run, r.recording_id):
            c = excerpt_contour(contour, off, d)
            for ref_name, (ref, ignore) in refs.items():
                m = ev.evaluate(ref, notes, d, cfg, None, c, ignore)
                sens.append({"recording_id": r.recording_id, "kind": r.kind, "method": label, "reference": ref_name,
                             "frame_accuracy": m["frame_accuracy"], "note_f1": m["note_f1"],
                             "low_error_st": m["low_error_st"], "high_error_st": m["high_error_st"]})
            if c is not None:
                ref, ignore = refs["agreed notes, unresolved spots left out"]
                times = rf.frame_grid(d, float(cfg["frame_hop_s"]))
                keep = ~rf.in_regions(times, ignore)
                rv = rf.notes_to_frames(ref, times)[keep]
                est = rf.contour_to_frames(c["time_s"].to_numpy(float), c["midi"].to_numpy(float), times)[keep]
                voiced = np.isfinite(rv)
                cents = np.abs(est[voiced] - rv[voiced]) * 100
                n = voiced.sum()
                breakdown.append({"recording_id": r.recording_id, "method": label, "ref_voiced_frames": int(n),
                                  "correct": float(np.sum(cents <= 50) / n),
                                  "missed_no_pitch": float(np.sum(~np.isfinite(cents)) / n),
                                  "near_miss_50_100_cents": float(np.sum((cents > 50) & (cents <= 100)) / n),
                                  "wrong_over_100_cents": float(np.sum(cents > 100) / n)})

    s = pd.DataFrame(sens)
    s.to_csv(args.run / "reviewer_sensitivity_per_recording.csv", index=False)
    agg = (s.groupby(["method", "kind", "reference"], sort=False)
           .agg(n=("recording_id", "size"), frame_accuracy=("frame_accuracy", "mean"), note_f1=("note_f1", "mean"),
                worst_endpoint_error_st=("low_error_st", "max"), worst_high_error_st=("high_error_st", "max"))
           .reset_index())
    agg["worst_endpoint_error_st"] = agg[["worst_endpoint_error_st", "worst_high_error_st"]].max(axis=1)
    agg.drop(columns="worst_high_error_st").to_csv(args.run / "reviewer_sensitivity.csv", index=False)
    pd.DataFrame(breakdown).to_csv(args.run / "frame_error_breakdown.csv", index=False)

    rows = []
    for take in sorted(recs.loc[recs["kind"] == "isolated_vocal", "recording_id"]):
        draft = rf.read_notes_csv(ann / "drafts" / f"{take}_draft.csv")
        for who in [*args.names, "verified"]:
            sung = rf.read_notes_csv(ann / f"{take}_{who}.csv")
            same = paired = 0
            for n in sung.itertuples():
                overlap = np.minimum(draft.end_s, n.end_s) - np.maximum(draft.start_s, n.start_s)
                if overlap.max() > 0:
                    paired += 1
                    same += int(draft.midi_note.iat[int(overlap.argmax())] == n.midi_note)
            rows.append({"recording_id": take, "annotation": who, "sung_notes": len(sung),
                         "paired_with_intended": paired, "same_pitch_as_intended": same,
                         "same_pitch_fraction": same / paired if paired else np.nan})
    pd.DataFrame(rows).to_csv(args.run / "intended_vs_sung_aligned.csv", index=False)
    print(f"Wrote reviewer_sensitivity.csv, frame_error_breakdown.csv and intended_vs_sung_aligned.csv to {args.run}")


if __name__ == "__main__":
    main()
