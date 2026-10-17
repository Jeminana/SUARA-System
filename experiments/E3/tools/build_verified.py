"""Build verified references from two reviewers' annotations, leaving disputed spots unscored.

    python tools/build_verified.py --data data --names athirah adib
    python tools/build_verified.py --data data --names athirah adib --suffix _v2   # after the re-check

Reads data/annotations/returned/<name>/M0N_<name><suffix>.csv for both reviewers. For each
recording it writes, under data/annotations/:

- P01_M0N_T01_<name><suffix>.csv     each reviewer's notes in E3 format
- P01_M0N_T01_ambiguity_log<suffix>.csv  one row per disagreement
- P01_M0N_T01_verified.csv           the notes both reviewers agree on (onset within 50 ms,
                                     same pitch), with their start and end times averaged
- P01_M0N_T01_unresolved.csv         the disputed spots, which scoring leaves out

and annotation_summary.csv with how much sung time each recording loses to unresolved spots.
It then updates data/recordings.csv for P01_M0N_T01 and its mix: includes them, points the
reference and unresolved paths at the new files, and moves audio_offset_s to just before the
first annotated note if the reviewers placed it earlier than the draft. Rerun with the re-check
files to shrink the unresolved spots; verified and unresolved files are replaced each time.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compare_annotations import disagreements, match  # noqa: E402
from import_annotation import read_export  # noqa: E402
from make_resolution_package import spots  # noqa: E402

from e3.references import in_regions, note_name  # noqa: E402

ONSET_S, CENTS = 0.05, 50.0
LEAD_IN_S = 0.05  # region starts are moved this much earlier so early onsets still fall inside


def verified_notes(a: pd.DataFrame, b: pd.DataFrame, matched: list[tuple[int, int]]) -> pd.DataFrame:
    rows = [{"start_s": (a.start_s.iat[i] + b.start_s.iat[j]) / 2, "end_s": (a.end_s.iat[i] + b.end_s.iat[j]) / 2,
             "midi_note": a.midi_note.iat[i]} for i, j in matched]
    return pd.DataFrame(rows, columns=["start_s", "end_s", "midi_note"]).sort_values("start_s").round(4)


def unresolved_spots(log: pd.DataFrame, a: pd.DataFrame, b: pd.DataFrame, names: tuple[str, str],
                     reason: str) -> pd.DataFrame:
    def listed(notes, s, e):
        inside = notes[(np.minimum(notes.end_s, e) - np.maximum(notes.start_s, s)) >= 0.05]
        return "; ".join(note_name(m) for m in inside.midi_note) or "(no note)"

    rows = [{"start_s": round(max(0.0, sp["start_s"] - LEAD_IN_S), 4), "end_s": round(sp["end_s"], 4),
             "issues": "+".join(sorted(sp["kinds"])), f"{names[0]}_notes": listed(a, sp["start_s"], sp["end_s"]),
             f"{names[1]}_notes": listed(b, sp["start_s"], sp["end_s"]), "reason": reason}
            for sp in spots(log, names)] if len(log) else []
    return pd.DataFrame(rows, columns=["start_s", "end_s", "issues", f"{names[0]}_notes", f"{names[1]}_notes",
                                       "reason"])


def sung_time(notes: list[pd.DataFrame], regions: np.ndarray, start: float, end: float,
              hop: float = 0.01) -> tuple[float, float]:
    """Seconds inside [start, end] where either reviewer marked a note, and how many of them
    fall in the unresolved regions."""
    t = np.arange(start, end, hop)
    voiced = np.zeros(t.shape, dtype=bool)
    for n in notes:
        voiced |= in_regions(t, n[["start_s", "end_s"]].to_numpy(float))
    return float(voiced.sum() * hop), float((voiced & in_regions(t, regions)).sum() * hop)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    ap.add_argument("--names", nargs=2, required=True, metavar=("NAME_A", "NAME_B"))
    ap.add_argument("--suffix", default="", help="reviewer file suffix, e.g. _v2 for the re-check files")
    ap.add_argument("--singer", default="P01")
    ap.add_argument("--reason", default="reviewers disagree; awaiting re-check")
    args = ap.parse_args()
    names, ann = tuple(args.names), args.data / "annotations"
    ret = ann / "returned"
    songs = sorted(p.name.split("_")[0] for p in (ret / names[0]).glob(f"M*_{names[0]}{args.suffix}.csv"))
    if not songs:
        raise SystemExit(f"No files like {ret / names[0]}/M01_{names[0]}{args.suffix}.csv")

    rec_path = args.data / "recordings.csv"
    recs = pd.read_csv(rec_path, dtype=str, keep_default_na=False)
    if "unresolved_path" not in recs.columns:
        recs["unresolved_path"] = ""
    cat = pd.read_csv(args.data / "catalog.csv", dtype=str, keep_default_na=False).set_index("song_id")

    summary = []
    for song in songs:
        rid = f"{args.singer}_{song}_T01"
        a, _ = read_export(ret / names[0] / f"{song}_{names[0]}{args.suffix}.csv")
        b, _ = read_export(ret / names[1] / f"{song}_{names[1]}{args.suffix}.csv")
        for who, notes in zip(names, (a, b)):
            notes.to_csv(ann / f"{rid}_{who}{args.suffix}.csv", index=False)
        pairs = match(a, b, ONSET_S, CENTS)
        log = disagreements(a, b, pairs, names)
        log.to_csv(ann / f"{rid}_ambiguity_log{args.suffix}.csv", index=False, float_format="%.3f")
        verified = verified_notes(a, b, pairs)
        unresolved = unresolved_spots(log, a, b, names, args.reason)
        verified.to_csv(ann / f"{rid}_verified.csv", index=False)
        unresolved.to_csv(ann / f"{rid}_unresolved.csv", index=False)

        iso = recs["recording_id"] == rid
        if not iso.any():
            raise SystemExit(f"{rid} is not in {rec_path}")
        row = recs[iso].iloc[0]
        song_id = row["song_id"]
        dur = float(cat.at[song_id, "excerpt_end_s"]) - float(cat.at[song_id, "excerpt_start_s"])
        first = min(a.start_s.min(), b.start_s.min())
        offset = round(max(0.0, min(float(row["audio_offset_s"] or 0), first - LEAD_IN_S)), 3)
        both = iso | (recs["paired_with"] == rid)
        recs.loc[both, ["excluded", "exclusion_reason", "audio_offset_s"]] = ["false", "", str(offset)]
        recs.loc[iso, ["reference_type", "reference_path", "unresolved_path"]] = [
            "notes_csv", f"annotations/{rid}_verified.csv", f"annotations/{rid}_unresolved.csv"]

        sung, lost = sung_time([a, b], unresolved[["start_s", "end_s"]].to_numpy(float), offset, offset + dur)
        summary.append({"recording_id": rid, f"{names[0]}_notes": len(a), f"{names[1]}_notes": len(b),
                        "agreed_notes": len(verified), "disagreements": len(log),
                        "unresolved_spots": len(unresolved), "sung_s": round(sung, 2),
                        "unresolved_sung_s": round(lost, 2),
                        "unresolved_fraction": round(lost / sung, 3) if sung else np.nan,
                        "source_files": f"M0N_<name>{args.suffix}.csv", "built": date.today().isoformat()})
        print(f"{rid}: {len(verified)} agreed notes, {len(unresolved)} unresolved spots "
              f"({summary[-1]['unresolved_fraction']:.0%} of sung time left out), offset {offset}s")

    backup = rec_path.with_name("recordings.before_build_verified.csv")
    if not backup.exists():
        shutil.copy2(rec_path, backup)
    recs.to_csv(rec_path, index=False)
    pd.DataFrame(summary).to_csv(ann / "annotation_summary.csv", index=False)
    print(f"Updated {rec_path} (first version kept as {backup.name}); summary in {ann / 'annotation_summary.csv'}")


if __name__ == "__main__":
    main()
