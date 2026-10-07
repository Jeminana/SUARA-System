"""Compare two reviewers' note annotations of the same recording.

    python tools/compare_annotations.py reviewer_a.csv reviewer_b.csv --out ambiguity_log.csv

Both files use start_s, end_s, midi_note (audio time). Notes are matched one to one with the
same rule as the evaluation (onset within 50 ms, pitch within 50 cents). Unmatched notes from
either reviewer are written to the ambiguity log for the reviewers to resolve or document;
the agreed file then becomes the verified reference.
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("reviewer_a", type=Path)
    ap.add_argument("reviewer_b", type=Path)
    ap.add_argument("--out", type=Path, default=Path("ambiguity_log.csv"))
    ap.add_argument("--onset-tolerance-s", type=float, default=0.05)
    ap.add_argument("--pitch-tolerance-cents", type=float, default=50.0)
    args = ap.parse_args()
    a, b = read_notes_csv(args.reviewer_a), read_notes_csv(args.reviewer_b)
    cfg = {"onset_tolerance_s": args.onset_tolerance_s, "pitch_tolerance_cents": args.pitch_tolerance_cents,
           "offset_ratio": 0.2, "offset_min_tolerance_s": 0.05}
    m = note_metrics(a, b, cfg)
    print(f"A: {len(a)} notes, B: {len(b)} notes, matched {m['matched_notes']}, "
          f"agreement F1 {m['note_f1']:.3f}, with offsets {m['note_f1_with_offset']:.3f}")

    matched = mir_eval.transcription.match_notes(
        a[["start_s", "end_s"]].to_numpy(), mir_eval.util.midi_to_hz(a["midi_note"].to_numpy(float)),
        b[["start_s", "end_s"]].to_numpy(), mir_eval.util.midi_to_hz(b["midi_note"].to_numpy(float)),
        onset_tolerance=args.onset_tolerance_s, pitch_tolerance=args.pitch_tolerance_cents,
        offset_ratio=None) if len(a) and len(b) else []
    ma = {i for i, _ in matched}
    mb = {j for _, j in matched}
    rows = [{"reviewer": who, "start_s": r.start_s, "end_s": r.end_s, "midi_note": r.midi_note,
             "note": note_name(r.midi_note), "resolution": ""}
            for who, df, used in (("A", a, ma), ("B", b, mb))
            for i, r in enumerate(df.itertuples()) if i not in used]
    log = pd.DataFrame(rows, columns=["reviewer", "start_s", "end_s", "midi_note", "note", "resolution"])
    log.sort_values("start_s").to_csv(args.out, index=False, float_format="%.4f")
    print(f"{len(log)} unmatched notes written to {args.out}; fill in 'resolution' for each.")
    if len(log) == 0 and np.isfinite(m["note_f1"]):
        print("Reviewers agree on every note within tolerance.")


if __name__ == "__main__":
    main()
