"""Song catalog loading from an exported JSON file; standard library only.

The E3 export (experiments/E3/handoff/song_features.json) is a JSON list of complete
SongFeatures objects. Loading never imports experiment code. Hz units are the
exporter's responsibility; this loader checks structure and contract invariants.
"""
from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

from suara.contracts import ContractError, SongFeatures
from suara.errors import failure

SONG_FIELDS = tuple(field.name for field in fields(SongFeatures))


def _reject_constant(name: str) -> None:
    raise ContractError(f"Catalog JSON must not contain {name}")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ContractError("Catalog record repeats a field")
    return dict(pairs)


def _song(record: object) -> SongFeatures:
    if not isinstance(record, dict) or set(record) != set(SONG_FIELDS):
        # schema_version is required on the wire even though the constructor defaults it.
        raise ContractError(f"Each catalog record must have exactly these fields: {', '.join(SONG_FIELDS)}")
    return SongFeatures(**record)


def load_song_catalog(path: str | Path) -> list[SongFeatures]:
    """Validated SongFeatures from a JSON list; an empty list is a valid empty catalog."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise failure("invalid_catalog", "recommendation", "Song catalog file could not be read.") from exc
    try:
        records = json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_unique_keys)
        if not isinstance(records, list):
            raise ContractError("Catalog JSON must be a list of SongFeatures objects")
        songs = [_song(record) for record in records]
        ids = [song.song_id for song in songs]
        if len(ids) != len(set(ids)):
            raise ContractError("Duplicate catalog song_id")
        return songs
    except (TypeError, ValueError) as exc:  # includes JSONDecodeError and ContractError
        raise failure("invalid_catalog", "recommendation", "Song catalog is not a valid SongFeatures list.") from exc
