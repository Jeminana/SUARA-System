"""Compare two reviewers' note annotations of the same recording.

    python tools/compare_annotations.py reviewer_a.csv reviewer_b.csv --out ambiguity_log.csv \
        --names athirah adib

Both files use start_s, end_s, midi_note (audio time). Notes are matched one to one with the
same rule as the evaluation (onset within 50 ms, pitch within 50 cents). Each unmatched note is
paired with the other reviewer's unmatched note it overlaps most, so the ambiguity log has one
row per disagreement (pitch, timing, or a note only one reviewer marked). The reviewers resolve
or document each row; the agreed file then becomes the verified reference.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import mir_eval
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from e3.evaluation import note_metrics  # noqa: E402
from e3.references import note_name, read_notes_csv  # noqa: E402


def match(a: pd.DataFrame, b: pd.DataFrame, onset_s: float, cents: float) -> list[tuple[int, int]]:
    if not len(a) or not len(b):
        return []
    return mir_eval.transcription.match_notes(
        a[["start_s", "end_s"]].to_numpy(), mir_eval.util.midi_to_hz(a["midi_note"].to_numpy(float)),
        b[["start_s", "end_s"]].to_numpy(), mir_eval.util.midi_to_hz(b["midi_note"].to_numpy(float)),
        onset_tolerance=onset_s, pitch_tolerance=cents, offset_ratio=None)


def disagreements(a: pd.DataFrame, b: pd.DataFrame, matched: list[tuple[int, int]],
                  names: tuple[str, str] = ("A", "B")) -> pd.DataFrame:
    """One row per disagreement, pairing unmatched notes by greatest time overlap."""
    na, nb = names
    left_a = [i for i in range(len(a)) if i not in {i for i, _ in matched}]
    left_b = [j for j in range(len(b)) if j not in {j for _, j in matched}]
    overlaps = sorted(((min(a.end_s.iat[i], b.end_s.iat[j]) - max(a.start_s.iat[i], b.start_s.iat[j]), i, j)
                       for i in left_a for j in left_b), reverse=True)
    pairs = []
    for ov, i, j in overlaps:
        if ov > 0 and i in left_a and j in left_b:
            pairs.append((i, j))
            left_a.remove(i)
            left_b.remove(j)
    pairs += [(i, None) for i in left_a] + [(None, j) for j in left_b]

    def side(df, k, who):
        if k is None:
            return {f"{who}_start_s": np.nan, f"{who}_end_s": np.nan, f"{who}_note": ""}
        r = df.iloc[k]
        return {f"{who}_start_s": r.start_s, f"{who}_end_s": r.end_s, f"{who}_note": note_name(r.midi_note)}

    rows = []
    for i, j in pairs:
        if j is None:
            issue = f"only {na}"
        elif i is None:
            issue = f"only {nb}"
        elif a.midi_note.iat[i] != b.midi_note.iat[j]:
            issue = "pitch"
        else:
            issue = "timing"
        times = [df.start_s.iat[k] for df, k in ((a, i), (b, j)) if k is not None]
        rows.append({"time_s": min(times), "issue": issue, **side(a, i, na), **side(b, j, nb), "resolution": ""})
    cols = ["time_s", "issue", f"{na}_note", f"{nb}_note", f"{na}_start_s", f"{na}_end_s",
            f"{nb}_start_s", f"{nb}_end_s", "resolution"]
    return pd.DataFrame(rows, columns=cols).sort_values("time_s").reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("reviewer_a", type=Path)
    ap.add_argument("reviewer_b", type=Path)
    ap.add_argument("--out", type=Path, default=Path("ambiguity_log.csv"))
    ap.add_argument("--names", nargs=2, default=["A", "B"], metavar=("NAME_A", "NAME_B"))
    ap.add_argument("--onset-tolerance-s", type=float, default=0.05)
    ap.add_argument("--pitch-tolerance-cents", type=float, default=50.0)
    args = ap.parse_args()
    a, b = read_notes_csv(args.reviewer_a), read_notes_csv(args.reviewer_b)
    cfg = {"onset_tolerance_s": args.onset_tolerance_s, "pitch_tolerance_cents": args.pitch_tolerance_cents,
           "offset_ratio": 0.2, "offset_min_tolerance_s": 0.05}
    m = note_metrics(a, b, cfg)
    print(f"A: {len(a)} notes, B: {len(b)} notes, matched {m['matched_notes']}, "
          f"agreement F1 {m['note_f1']:.3f}, with offsets {m['note_f1_with_offset']:.3f}")

    log = disagreements(a, b, match(a, b, args.onset_tolerance_s, args.pitch_tolerance_cents), tuple(args.names))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    log.to_csv(args.out, index=False, float_format="%.3f")
    counts = ", ".join(f"{k} {v}" for k, v in log["issue"].value_counts().items())
    print(f"{len(log)} disagreements written to {args.out} ({counts or 'none'}); fill in 'resolution' for each.")
    if len(log) == 0 and np.isfinite(m["note_f1"]):
        print("Reviewers agree on every note within tolerance.")


if __name__ == "__main__":
    main()
