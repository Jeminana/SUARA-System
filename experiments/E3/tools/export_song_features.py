"""Export a finished catalog run as SongFeatures records for the main SUARA app (task T06).

    python tools/export_song_features.py outputs/pilot_catalog --data data

Reads <run>/catalog/song_profile_details.csv and data/catalog.csv and writes
handoff/song_features.json: one record per song in the integration contract's SongFeatures
shape (docs/INTEGRATION_CONTRACT.md, schema 1.0.0). The app runs on Python 3.12 and does not
import E3, so this file is the boundary between them.

- The range is the song's reliable lowest and highest melody note (the catalog run's low_midi
  and high_midi), converted from MIDI to Hz once: Hz = 440 * 2 ** ((midi - 69) / 12).
- provenance is verified_melody only when the catalog names who verified the melody and both
  endpoints exist; otherwise unverified.
- source_description states the source type, excerpt boundaries and verification without
  names or file paths, because the repository is public.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

SCHEMA_VERSION = "1.0.0"
FEATURE_VERSION = "e3-melody-range-v1"
FIELDS = ["song_id", "title", "artist", "melody_min_pitch_hz", "melody_max_pitch_hz",
          "feature_version", "provenance", "source_description", "schema_version"]
PROVENANCE = {"mock", "unverified", "verified_melody"}
# Team-made songs get a public artist label; other sources use the catalog's creator.
TEAM_SOURCES = {"ai_drafted_team_approved": ("SUARA team (AI-drafted pilot song)",
                                             "AI-drafted, team-owned pilot melody made for the SUARA capstone"),
                "team_composed": ("SUARA team", "team-composed melody made for the SUARA capstone")}
METHODS = {"midi_reference": "the written lead-vocal melody (MIDI score)",
           "verified_notes": "a reviewer-corrected note transcription of the lead vocal"}


def midi_to_hz(midi: float) -> float:
    return round(440.0 * 2 ** ((float(midi) - 69) / 12), 4)


def _present(value) -> bool:
    return value is not None and value != "" and not (isinstance(value, float) and math.isnan(value))


def song_record(profile: dict, song: dict, feature_version: str) -> dict:
    """One SongFeatures record from a song_profile_details row and its data/catalog.csv row."""
    sid = profile["song_id"]
    reviewers = [] if profile["verified_by"] in ("", "unverified") else \
        [r for r in str(profile["verified_by"]).split(";") if r.strip()]
    has_range = _present(profile["low_midi"]) and _present(profile["high_midi"])
    lo, hi = (float(profile["low_midi"]), float(profile["high_midi"])) if has_range else (None, None)
    verified = bool(reviewers) and has_range and profile["method"] in METHODS
    source_type = song["source_type"]
    if source_type in TEAM_SOURCES:
        artist, origin = TEAM_SOURCES[source_type]
        title = f"Pilot song {int(sid[1:])}: {song['title']}"
    else:
        artist, origin, title = song["creator"], f"{source_type} source", song["title"]
    start, end = float(profile["excerpt_start_s"]), float(profile["excerpt_end_s"])
    parts = [origin[:1].upper() + origin[1:],
             f"range from {METHODS.get(profile['method'], profile['method'])} over the excerpt "
             f"{start:.2f}-{end:.2f} s, not from a full-mix spectrum or a singer recording",
             f"MIDI {lo:.0f}-{hi:.0f} converted to Hz with A4 = 440 Hz"
             if has_range else "no melody range available",
             f"melody approved by {len(reviewers)} team member{'s' if len(reviewers) != 1 else ''}"
             if reviewers else "melody not verified",
             "describes this excerpt only, not the full song"]
    flags = [f for f in str(profile["quality_flag"]).split(";") if f and f != "excerpt"]
    if flags:
        parts.append(f"profile flags: {', '.join(flags)}")
    return {"song_id": f"E3-{sid}", "title": title, "artist": artist,
            "melody_min_pitch_hz": midi_to_hz(lo) if has_range else None,
            "melody_max_pitch_hz": midi_to_hz(hi) if has_range else None,
            "feature_version": f"{feature_version}/{profile['profile_version']}",
            "provenance": "verified_melody" if verified else "unverified",
            "source_description": "; ".join(parts) + ".", "schema_version": SCHEMA_VERSION}


def check_records(records: list[dict]) -> None:
    """The SongFeatures rules from the contract, checked here so E3 never imports the app."""
    ids = [r.get("song_id") for r in records]
    if len(set(ids)) != len(ids):
        raise SystemExit("Duplicate song_id in export.")
    for r in records:
        if list(r) != FIELDS:
            raise SystemExit(f"{r.get('song_id')}: fields must be exactly {FIELDS}")
        for k in ("song_id", "title", "artist", "feature_version", "source_description"):
            if not isinstance(r[k], str) or not r[k].strip():
                raise SystemExit(f"{r['song_id']}: {k} must be nonempty text")
        lo, hi = r["melody_min_pitch_hz"], r["melody_max_pitch_hz"]
        if (lo is None) != (hi is None):
            raise SystemExit(f"{r['song_id']}: melody endpoints must both be null or both present")
        if lo is not None and not (isinstance(lo, float) and isinstance(hi, float)
                                   and math.isfinite(lo) and math.isfinite(hi) and 0 < lo <= hi):
            raise SystemExit(f"{r['song_id']}: melody endpoints must be finite with 0 < min <= max")
        if r["provenance"] not in PROVENANCE or (r["provenance"] == "verified_melody" and lo is None):
            raise SystemExit(f"{r['song_id']}: invalid provenance for its range")
        if r["schema_version"] != SCHEMA_VERSION:
            raise SystemExit(f"{r['song_id']}: schema_version must be {SCHEMA_VERSION}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path, help="finished catalog run folder, e.g. outputs/pilot_catalog")
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=Path("handoff/song_features.json"))
    args = ap.parse_args()
    profiles = pd.read_csv(args.run / "catalog" / "song_profile_details.csv", keep_default_na=False)
    songs = pd.read_csv(args.data / "catalog.csv", dtype=str, keep_default_na=False).set_index("song_id", drop=False)
    missing = sorted(set(profiles["song_id"]) - set(songs.index))
    if missing:
        raise SystemExit(f"Songs in the catalog run but not in {args.data / 'catalog.csv'}: {missing}")
    records = [song_record(p, songs.loc[p["song_id"]].to_dict(), FEATURE_VERSION)
               for p in profiles.sort_values("song_id").to_dict("records")]
    check_records(records)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = pd.Series([r["provenance"] for r in records]).value_counts().to_dict()
    print(f"{len(records)} SongFeatures records written to {args.out} ({counts})")


if __name__ == "__main__":
    main()
