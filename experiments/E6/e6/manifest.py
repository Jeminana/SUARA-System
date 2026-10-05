"""Manifest loading, validation and split assignment.

Original recordings are named P01_M01_T01 (participant, melody, take). Stress-test
variants (for example a second device) are extra rows with condition != original and
parent_recording_id pointing at the original; they always inherit the parent's split.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

REQUIRED = ["recording_id", "participant_id", "melody_id", "take", "key", "device",
            "duration_s", "consent", "file_path"]
OPTIONAL = {"condition": "original", "parent_recording_id": "", "excluded": "false",
            "exclusion_reason": "", "notes": ""}
ID_RE = re.compile(r"^(P\d{2})_(M\d{2})_(T\d{2})$")


class ManifestError(ValueError):
    pass


def load_manifest(path: Path, audio_root: Path, accepted_consent: list[str]) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ManifestError(f"Manifest is missing columns: {missing}")
    for col, default in OPTIONAL.items():
        if col not in df.columns:
            df[col] = default
    df = df.apply(lambda s: s.str.strip())
    df.loc[df["condition"] == "", "condition"] = "original"
    df["excluded"] = df["excluded"].str.lower().isin(["1", "true", "yes", "y"])

    errors = []
    dupes = df["recording_id"][df["recording_id"].duplicated()].tolist()
    if dupes:
        errors.append(f"duplicate recording_id: {dupes}")

    originals = df[df["condition"] == "original"].set_index("recording_id")
    for r in df.itertuples():
        if r.condition == "original":
            m = ID_RE.match(r.recording_id)
            if not m:
                errors.append(f"{r.recording_id}: original IDs must look like P01_M01_T01")
            elif m.groups() != (r.participant_id, r.melody_id, r.take):
                errors.append(f"{r.recording_id}: participant/melody/take columns do not match the ID")
        else:
            parent = r.parent_recording_id
            if parent not in originals.index:
                errors.append(f"{r.recording_id}: parent_recording_id '{parent}' is not an original row")
            else:
                p = originals.loc[parent]
                if (p["participant_id"], p["melody_id"], p["take"]) != (r.participant_id, r.melody_id, r.take):
                    errors.append(f"{r.recording_id}: participant/melody/take differ from parent {parent}")
    if errors:
        raise ManifestError("Manifest problems:\n  " + "\n  ".join(errors))

    # Leakage key: a variant and its parent share one source recording.
    df["source_id"] = df["parent_recording_id"].where(df["condition"] != "original", df["recording_id"])

    accepted = {v.lower() for v in accepted_consent}
    no_consent = ~df["consent"].str.lower().isin(accepted) & ~df["excluded"]
    df.loc[no_consent, "excluded"] = True
    df.loc[no_consent, "exclusion_reason"] = "consent not recorded as accepted"

    df["abs_path"] = [str((audio_root / p).resolve()) for p in df["file_path"]]
    missing_files = df[~df["excluded"] & ~df["abs_path"].map(lambda p: Path(p).is_file())]
    if len(missing_files):
        raise ManifestError(f"Audio files not found: {missing_files['file_path'].tolist()}")

    # A variant cannot be used when its parent is excluded.
    excluded_sources = set(df.loc[df["excluded"] & (df["condition"] == "original"), "recording_id"])
    orphan = (df["condition"] != "original") & df["source_id"].isin(excluded_sources) & ~df["excluded"]
    df.loc[orphan, "excluded"] = True
    df.loc[orphan, "exclusion_reason"] = "parent recording excluded"
    return df


def assign_splits(df: pd.DataFrame, splits_cfg: dict) -> pd.DataFrame:
    def split_of(melody: str, take: str) -> str:
        for name in ("dev", "enroll", "same_melody", "query"):
            s = splits_cfg[name]
            if melody == s["melody"] and take in s["takes"]:
                return name
        return "unused"

    df = df.copy()
    df["split"] = [split_of(m, t) for m, t in zip(df["melody_id"], df["take"])]
    return df


def check_no_leakage(enroll: pd.DataFrame, queries: pd.DataFrame) -> None:
    """No query recording (or any crop/variant of it) may contribute to an enrollment profile."""
    shared = set(enroll["source_id"]) & set(queries["source_id"])
    if shared:
        raise ManifestError(f"Leakage: recordings used for both enrollment and queries: {sorted(shared)}")
