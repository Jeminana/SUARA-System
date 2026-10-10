"""Convert a Sonic Visualiser note-layer export into an E3 note CSV.

    python tools/import_annotation.py exported.csv data/annotations/P01_M01_T01_reviewerA.csv

Sonic Visualiser exports note layers as rows of time, value, duration[, level, label], with or
without a header. Values are read as MIDI pitch when they look like MIDI numbers (<= 127) and
as Hz otherwise; either way the output pitch is rounded to the nearest semitone.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from e3.references import hz_to_midi  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("exported", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    raw = pd.read_csv(args.exported, header=None)
    if not pd.api.types.is_numeric_dtype(raw[0]):  # first row was a header
        raw = pd.read_csv(args.exported)
        raw.columns = range(raw.shape[1])
    if raw.shape[1] < 3:
        raise SystemExit("Expected at least time, value and duration columns (export a Notes layer).")
    value = raw[1].astype(float).to_numpy()
    midi = value if np.nanmedian(value) <= 127 else hz_to_midi(value)
    notes = pd.DataFrame({"start_s": raw[0].astype(float), "end_s": raw[0].astype(float) + raw[2].astype(float),
                          "midi_note": np.round(midi)})
    notes = notes[(notes["end_s"] > notes["start_s"]) & notes["midi_note"].notna()].sort_values("start_s")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    notes.round(4).to_csv(args.out, index=False)
    print(f"{len(notes)} notes written to {args.out} "
          f"({'MIDI' if np.nanmedian(value) <= 127 else 'Hz'} values detected)")


if __name__ == "__main__":
    main()
