"""Build one blind re-check package per reviewer from the ambiguity logs.

    python tools/make_resolution_package.py --data data --names athirah adib

For each song, nearby disagreements in data/annotations/P01_M0N_T01_ambiguity_log.csv are
grouped into spots to re-check. Each reviewer's sheet lists the spots with only their own notes
there, never the other reviewer's answer, so the re-check stays independent. Reviewers fix
their own note layer at those spots and export it again as M0N_<name>_v2.csv; running
compare_annotations.py on the two v2 files then shows what is still unresolved.

Writes data/reviewer_package/E3_resolution_<name>.zip with the recordings, the reviewer's own
first-round exports, their sheet, a note frequency table and RESOLUTION_GUIDE.md.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from e3.references import note_name, read_notes_csv  # noqa: E402

E3 = Path(__file__).resolve().parents[1]
PAD_S = 0.15
CHECKS = {"pitch": "pitch: measure the held frequency and pick the closer note",
          "timing": "start: where the voice begins this note",
          "only": "notes: is each note here really sung as a separate note? delete or add as needed"}
# A note both reviewers agreed on, for checking the frequency reading before the real spots.
PRACTICE = {"recording": "M01", "start_s": 2.91, "end_s": 4.07, "note": "A3"}


def spots(log: pd.DataFrame, names: tuple[str, str]) -> list[dict]:
    """Group disagreement rows whose time windows touch into one spot to re-check."""
    starts = log[[f"{n}_start_s" for n in names]].min(axis=1)
    ends = log[[f"{n}_end_s" for n in names]].max(axis=1)
    rows = sorted(zip(starts, ends, log["issue"]))
    out: list[dict] = []
    for s, e, issue in rows:
        kind = "only" if issue.startswith("only") else issue
        if out and s <= out[-1]["end_s"] + 0.05:
            out[-1]["end_s"] = max(out[-1]["end_s"], e)
            out[-1]["kinds"].add(kind)
        else:
            out.append({"start_s": s, "end_s": e, "kinds": {kind}})
    return out


def own_notes(notes: pd.DataFrame, start: float, end: float) -> str:
    overlap = np.minimum(notes.end_s, end) - np.maximum(notes.start_s, start)
    inside = notes[overlap >= 0.05]
    if inside.empty:
        return "(no note)"
    return "; ".join(f"{note_name(r.midi_note)} {r.start_s:.2f}-{r.end_s:.2f}s" for r in inside.itertuples())


def frequency_table(low: int = 40, high: int = 67) -> pd.DataFrame:
    midi = np.arange(low, high + 1)
    hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)  # noqa: E731
    return pd.DataFrame({"note": [note_name(m) for m in midi], "midi": midi,
                         "lowest_hz": hz(midi - 0.5).round(1), "centre_hz": hz(midi).round(1),
                         "highest_hz": hz(midi + 0.5).round(1)})


def sheet(data: Path, name: str, names: tuple[str, str], songs: list[str]) -> pd.DataFrame:
    blank = {"measured_hz": "", "changed (yes/no)": "", "comment": ""}
    p = PRACTICE
    rows = [{"spot": f"{p['recording']}-practice", "recording": p["recording"],
             "look_from_s": p["start_s"], "look_to_s": p["end_s"],
             "what_to_check": f"practice: should measure as {p['note']}; do not change", "your_notes_there": p["note"],
             **blank}]
    for song in songs:
        log = pd.read_csv(data / "annotations" / f"P01_{song}_T01_ambiguity_log.csv")
        mine = read_notes_csv(data / "annotations" / f"P01_{song}_T01_{name}.csv")
        for k, s in enumerate(spots(log, names), 1):
            start, end = max(0.0, s["start_s"] - PAD_S), s["end_s"] + PAD_S
            rows.append({"spot": f"{song}-{k:02d}", "recording": song, "look_from_s": round(start, 2),
                         "look_to_s": round(end, 2),
                         "what_to_check": " + ".join(CHECKS[c] for c in ("pitch", "timing", "only") if c in s["kinds"]),
                         "your_notes_there": own_notes(mine, s["start_s"], s["end_s"]), **blank})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=E3 / "data")
    ap.add_argument("--names", nargs=2, required=True, metavar=("NAME_A", "NAME_B"))
    args = ap.parse_args()
    names = tuple(args.names)
    songs = sorted(p.name.split("_")[1] for p in (args.data / "annotations").glob("P01_M*_T01_ambiguity_log.csv"))
    freq = frequency_table()
    for name in names:
        root = args.data / "reviewer_package" / f"E3_resolution_{name}"
        pkg = root / f"E3_resolution_{name}"
        if root.exists():
            shutil.rmtree(root)
        (pkg / "recordings").mkdir(parents=True)
        (pkg / "your_first_round").mkdir()
        for song in songs:
            shutil.copy2(args.data / "audio" / f"{song}.wav", pkg / "recordings" / f"{song}.wav")
            shutil.copy2(args.data / "annotations" / "returned" / name / f"{song}_{name}.csv",
                         pkg / "your_first_round" / f"{song}_{name}.csv")
        s = sheet(args.data, name, names, songs)
        s.to_csv(pkg / f"recheck_sheet_{name}.csv", index=False)
        freq.to_csv(pkg / "note_frequencies.csv", index=False)
        shutil.copy2(E3 / "RESOLUTION_GUIDE.md", pkg / "RESOLUTION_GUIDE.md")
        (pkg / "README.txt").write_text(
            "Private recordings - do not upload or share outside the SUARA team. Delete when the project ends.\n"
            "Open RESOLUTION_GUIDE.md for the steps. Work alone; do not discuss with the other reviewer.\n"
            f"Send back: M01_{name}_v2.csv to M05_{name}_v2.csv and the filled recheck_sheet_{name}.csv.\n")
        zip_path = shutil.make_archive(str(args.data / "reviewer_package" / f"E3_resolution_{name}"), "zip", root)
        per_song = s[s.spot.str.contains("-practice") == False].groupby("recording").size().to_dict()  # noqa: E712
        print(f"{name}: {len(s) - 1} spots {per_song} -> {zip_path}")


if __name__ == "__main__":
    main()
