"""Build a manifest skeleton from audio files named P01_M01_T01*.wav.

    python tools/make_manifest.py data/raw data/manifest.csv

Durations are filled in; key, device and consent are left for the team to complete.
An existing manifest is never overwritten.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import soundfile as sf

NAME_RE = re.compile(r"^(P\d{2})_(M\d{2})_(T\d{2})$")
AUDIO_EXT = {".wav", ".flac", ".ogg", ".aiff", ".aif"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio_root", type=Path)
    ap.add_argument("manifest", type=Path)
    args = ap.parse_args()
    if args.manifest.exists():
        raise SystemExit(f"{args.manifest} already exists; edit it instead.")

    rows, skipped = [], []
    for f in sorted(p for p in args.audio_root.rglob("*") if p.suffix.lower() in AUDIO_EXT):
        m = NAME_RE.match(f.stem)
        if not m:
            skipped.append(f.name)
            continue
        info = sf.info(f)
        rows.append({"recording_id": f.stem, "participant_id": m[1], "melody_id": m[2], "take": m[3],
                     "key": "", "device": "", "duration_s": round(info.frames / info.samplerate, 3),
                     "consent": "", "file_path": f.relative_to(args.audio_root).as_posix(),
                     "condition": "original", "parent_recording_id": "", "excluded": "false",
                     "exclusion_reason": "", "notes": ""})
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.manifest, index=False)
    print(f"Wrote {len(rows)} rows to {args.manifest}. Fill in key, device and consent.")
    if skipped:
        print("Not named like P01_M01_T01 (add variant rows by hand):", ", ".join(skipped))


if __name__ == "__main__":
    main()
