"""Catalog (rights) manifest, recordings manifest and correction log.

catalog.csv     one row per catalog item S01..; split, excerpt, MIDI reference and rights record
recordings.csv  one row per audio item; kind is synth_melody | isolated_vocal | mix | licensed_mix
corrections.csv optional manual correction log (minutes and corrected note files)

Splits are assigned per song, so paired stems, mixtures and alternate crops of one song can
never land in different splits.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

CATALOG_REQUIRED = ["song_id", "title", "split", "source_type", "creator", "licence_or_permission",
                    "excerpt_start_s", "excerpt_end_s", "midi_path"]
CATALOG_OPTIONAL = {"melody_id": "", "lead_track": "", "source_url": "", "item_id": "",
                    "allowed_uses": "", "access_date": "", "redistribution_restrictions": "",
                    "verified_key": "", "bpm": "", "verified_by": "", "verified_notes_path": "",
                    "excluded": "false", "exclusion_reason": "", "notes": ""}
RECORDING_REQUIRED = ["recording_id", "song_id", "kind", "file_path"]
RECORDING_OPTIONAL = {"singer_id": "", "take": "", "consent": "", "audio_offset_s": "0",
                      "reference_type": "", "reference_path": "", "reference_f0_path": "",
                      "unresolved_path": "", "paired_with": "", "device": "", "excluded": "false",
                      "exclusion_reason": "", "notes": ""}
CORRECTION_COLUMNS = ["recording_id", "method", "reviewer", "correction_minutes",
                      "corrected_notes_path", "notes"]

SONG_RE = re.compile(r"^S\d{2}$")
TAKE_RE = re.compile(r"^(P\d{2})_(M\d{2})_(T\d{2})")
KINDS = {"synth_melody", "isolated_vocal", "mix", "licensed_mix"}
ISOLATED_KINDS = {"synth_melody", "isolated_vocal"}
MIX_KINDS = {"mix", "licensed_mix"}
HUMAN_KINDS = {"isolated_vocal", "mix"}  # recordings of a participant need consent
SPLITS = {"dev", "test"}
TRUE = {"1", "true", "yes", "y"}


class ManifestError(ValueError):
    pass


def _read(path: Path, required: list[str], optional: dict) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ManifestError(f"{path.name} is missing columns: {missing}")
    for col, default in optional.items():
        if col not in df.columns:
            df[col] = default
    df = df.apply(lambda s: s.str.strip())
    df["excluded"] = df["excluded"].str.lower().isin(TRUE)
    return df


def _exclude(df: pd.DataFrame, mask, reason: str) -> None:
    mask = mask & ~df["excluded"]
    df.loc[mask, "excluded"] = True
    df.loc[mask, "exclusion_reason"] = reason


def resolve(root: Path, p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else (root / q).resolve()


def load_catalog(path: Path, data_root: Path) -> tuple[pd.DataFrame, list[str]]:
    """Returns the catalog and a list of warnings that need a person's attention."""
    df = _read(path, CATALOG_REQUIRED, CATALOG_OPTIONAL)
    errors, warnings = [], []
    dupes = df["song_id"][df["song_id"].duplicated()].tolist()
    if dupes:
        errors.append(f"duplicate song_id: {dupes}")
    for r in df.itertuples():
        if not SONG_RE.match(r.song_id):
            errors.append(f"{r.song_id}: song IDs must look like S01")
        if r.split not in SPLITS:
            errors.append(f"{r.song_id}: split must be dev or test, got '{r.split}'")
        try:
            if float(r.excerpt_end_s) <= float(r.excerpt_start_s):
                errors.append(f"{r.song_id}: excerpt_end_s must be after excerpt_start_s")
        except ValueError:
            errors.append(f"{r.song_id}: excerpt boundaries must be numbers")
    if errors:
        raise ManifestError("Catalog problems:\n  " + "\n  ".join(errors))

    _exclude(df, df["licence_or_permission"] == "", "rights: licence_or_permission not recorded")
    df["midi_abs"] = [str(resolve(data_root, p)) if p else "" for p in df["midi_path"]]
    df["verified_notes_abs"] = [str(resolve(data_root, p)) if p else "" for p in df["verified_notes_path"]]
    for r in df[~df["excluded"]].itertuples():
        if not r.midi_path and not r.verified_notes_path:
            raise ManifestError(f"{r.song_id}: needs midi_path or verified_notes_path as its reference")
        for col in ("midi_abs", "verified_notes_abs"):
            p = getattr(r, col)
            if p and not Path(p).is_file():
                raise ManifestError(f"{r.song_id}: file not found: {p}")
        length = float(r.excerpt_end_s) - float(r.excerpt_start_s)
        if not 20 <= length <= 40:
            warnings.append(f"{r.song_id}: excerpt is {length:.1f} s; the procedure asks for 20-40 s")
        if r.source_type != "team_composed":
            missing = [c for c in ("source_url", "item_id", "allowed_uses", "access_date",
                                   "redistribution_restrictions") if not getattr(r, c)]
            if missing:
                warnings.append(f"{r.song_id}: external item rights record incomplete: {missing}")
        if not r.verified_by:
            warnings.append(f"{r.song_id}: reference melody has no verified_by reviewer yet")
    counts = df.loc[~df["excluded"], "split"].value_counts().to_dict()
    if counts.get("dev", 0) != 2 or counts.get("test", 0) != 3:
        warnings.append(f"split counts are {counts}; the procedure proposes 2 dev and 3 test excerpts")
    return df, warnings


def load_recordings(path: Path, data_root: Path, catalog: pd.DataFrame,
                    accepted_consent: list[str]) -> tuple[pd.DataFrame, list[str]]:
    df = _read(path, RECORDING_REQUIRED, RECORDING_OPTIONAL)
    errors, warnings = [], []
    dupes = df["recording_id"][df["recording_id"].duplicated()].tolist()
    if dupes:
        errors.append(f"duplicate recording_id: {dupes}")
    songs = catalog.set_index("song_id")
    for r in df.itertuples():
        if r.kind not in KINDS:
            errors.append(f"{r.recording_id}: kind must be one of {sorted(KINDS)}")
        if r.song_id not in songs.index:
            errors.append(f"{r.recording_id}: song_id {r.song_id} is not in the catalog")
        if r.kind == "mix" and r.paired_with not in set(df["recording_id"]):
            errors.append(f"{r.recording_id}: a mix needs paired_with = its isolated vocal recording_id")
        if r.kind == "isolated_vocal":
            m = TAKE_RE.match(r.recording_id)
            if not m:
                warnings.append(f"{r.recording_id}: human takes are expected to be named P01_M01_T01")
            elif r.singer_id and m[1] != r.singer_id:
                errors.append(f"{r.recording_id}: singer_id {r.singer_id} does not match the ID")
    if errors:
        raise ManifestError("Recordings problems:\n  " + "\n  ".join(errors))

    df["split"] = df["song_id"].map(songs["split"])
    df["audio_offset_s"] = df["audio_offset_s"].replace("", "0").astype(float)
    _exclude(df, df["song_id"].map(songs["excluded"]).astype(bool), "catalog item excluded")

    # A mix inherits blank reference, singer and consent fields from its paired isolated vocal.
    by_id = df.set_index("recording_id")
    for i, r in df[df["kind"] == "mix"].iterrows():
        p = by_id.loc[r["paired_with"]]
        inherit = ["singer_id", "consent"]
        if not r["reference_type"]:
            inherit += ["reference_type", "reference_path", "reference_f0_path", "unresolved_path"]
        for col in inherit:
            if not r[col]:
                df.at[i, col] = p[col]
    df.loc[(df["kind"] == "synth_melody") & (df["reference_type"] == ""), "reference_type"] = "midi"
    for r in df.itertuples():
        if r.reference_type not in ("midi", "notes_csv"):
            raise ManifestError(f"{r.recording_id}: reference_type must be midi or notes_csv")
        if r.reference_type == "notes_csv" and not r.reference_path:
            raise ManifestError(f"{r.recording_id}: notes_csv reference needs reference_path")
        if r.kind in HUMAN_KINDS and r.reference_type == "midi":
            warnings.append(f"{r.recording_id}: human performance scored against intended MIDI notes; "
                            "use verified sung annotations for extraction accuracy")
        if r.kind == "licensed_mix" and r.reference_type != "notes_csv":
            warnings.append(f"{r.recording_id}: licensed excerpt without a verified annotation")

    accepted = {v.lower() for v in accepted_consent}
    _exclude(df, df["kind"].isin(HUMAN_KINDS) & ~df["consent"].str.lower().isin(accepted),
             "consent not recorded as accepted")

    for col, src in (("abs_path", "file_path"), ("reference_abs", "reference_path"),
                     ("reference_f0_abs", "reference_f0_path"), ("unresolved_abs", "unresolved_path")):
        df[col] = [str(resolve(data_root, p)) if p else "" for p in df[src]]
    live = df[~df["excluded"]]
    missing = [p for col in ("abs_path", "reference_abs", "reference_f0_abs", "unresolved_abs")
               for p in live[col] if p and not Path(p).is_file()]
    if missing:
        raise ManifestError(f"Files not found: {missing}")

    # A mix cannot be compared before/after separation once its isolated pair is excluded.
    gone = set(df.loc[df["excluded"], "recording_id"])
    _exclude(df, (df["kind"] == "mix") & df["paired_with"].isin(gone), "paired isolated vocal excluded")
    return df, warnings


def load_corrections(path: Path, data_root: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=CORRECTION_COLUMNS + ["corrected_abs"])
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [c for c in CORRECTION_COLUMNS if c not in df.columns]
    if missing:
        raise ManifestError(f"{path.name} is missing columns: {missing}")
    df = df.apply(lambda s: s.str.strip())
    df["correction_minutes"] = pd.to_numeric(df["correction_minutes"], errors="coerce")
    df["corrected_abs"] = [str(resolve(data_root, p)) if p else "" for p in df["corrected_notes_path"]]
    return df
