"""Reference melodies: MIDI lead track import and verification, annotation files, frame grids.

Note tables everywhere in E3 use excerpt time (0 = excerpt start) and the columns
start_s, end_s, midi_note, confidence. MIDI 60 is C4.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pretty_midi

NOTE_COLUMNS = ["start_s", "end_s", "midi_note", "confidence"]
LEAD_HINTS = ("lead", "vocal", "melody", "voice")


def hz_to_midi(f0: np.ndarray) -> np.ndarray:
    """69 + 12 * log2(F0 / 440); non-positive or missing F0 becomes NaN."""
    f0 = np.asarray(f0, dtype=float)
    out = np.full(f0.shape, np.nan)
    ok = np.isfinite(f0) & (f0 > 0)
    out[ok] = 69 + 12 * np.log2(f0[ok] / 440.0)
    return out


def note_name(midi: float | None) -> str:
    if midi is None or not np.isfinite(midi):
        return ""
    return pretty_midi.note_number_to_name(int(round(midi)))


def empty_notes() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=float) for c in NOTE_COLUMNS})


def clean_notes(notes: pd.DataFrame) -> pd.DataFrame:
    if notes.empty:
        return empty_notes()
    notes = notes.copy()
    if "confidence" not in notes:
        notes["confidence"] = 1.0
    notes = notes[NOTE_COLUMNS].astype(float)
    notes = notes[notes["end_s"] > notes["start_s"]]
    return notes.sort_values(["start_s", "midi_note"]).reset_index(drop=True)


def crop_notes(notes: pd.DataFrame, start: float, end: float) -> pd.DataFrame:
    """Keep the part of each note inside [start, end] and shift to excerpt time."""
    if notes.empty:
        return empty_notes()
    n = notes[(notes["end_s"] > start) & (notes["start_s"] < end)].copy()
    n["start_s"] = n["start_s"].clip(lower=start) - start
    n["end_s"] = n["end_s"].clip(upper=end) - start
    return clean_notes(n)


def shift_notes(notes: pd.DataFrame, offset_s: float, duration_s: float) -> pd.DataFrame:
    """Audio time -> excerpt time for a recording whose excerpt starts offset_s into the file."""
    return crop_notes(notes, offset_s, offset_s + duration_s)


def read_notes_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in ("start_s", "end_s", "midi_note") if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: note file is missing columns {missing}")
    return clean_notes(df)


def read_f0_csv(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Verified sung F0 as time_s, f0_hz (0 or blank = unvoiced). Returns times and MIDI pitch."""
    df = pd.read_csv(path)
    if not {"time_s", "f0_hz"} <= set(df.columns):
        raise ValueError(f"{path}: F0 file needs time_s and f0_hz columns")
    return df["time_s"].to_numpy(float), hz_to_midi(df["f0_hz"].to_numpy(float))


def _pick_lead(pm: pretty_midi.PrettyMIDI, lead_track: str) -> tuple[int, pretty_midi.Instrument]:
    pitched = [(i, inst) for i, inst in enumerate(pm.instruments) if not inst.is_drum]
    if not pitched:
        raise ValueError("MIDI file has no pitched tracks")
    if lead_track:
        if lead_track.isdigit():
            idx = int(lead_track)
            if idx >= len(pm.instruments):
                raise ValueError(f"lead_track index {idx} out of range ({len(pm.instruments)} tracks)")
            return idx, pm.instruments[idx]
        named = [(i, inst) for i, inst in pitched if inst.name.strip().lower() == lead_track.lower()]
        if not named:
            raise ValueError(f"no track named '{lead_track}'; tracks: {[inst.name for _, inst in pitched]}")
        return named[0]
    if len(pitched) == 1:
        return pitched[0]
    hinted = [(i, inst) for i, inst in pitched if any(h in inst.name.lower() for h in LEAD_HINTS)]
    if len(hinted) == 1:
        return hinted[0]
    raise ValueError(f"several tracks and no lead_track set: {[inst.name for _, inst in pitched]}")


def overlap_count(notes: pd.DataFrame, tolerance_s: float = 0.01) -> int:
    """Number of notes that start before the previous note ends (a lead line should have none)."""
    if len(notes) < 2:
        return 0
    n = notes.sort_values("start_s")
    prev_end = n["end_s"].cummax().shift(1)
    return int((n["start_s"] < prev_end - tolerance_s).sum())


def load_midi_reference(path: str | Path, lead_track: str, start_s: float,
                        end_s: float) -> tuple[pd.DataFrame, dict]:
    """Import the known MIDI melody, crop it to the excerpt and report what a person must verify."""
    pm = pretty_midi.PrettyMIDI(str(path))
    idx, inst = _pick_lead(pm, lead_track)
    song = clean_notes(pd.DataFrame(
        [(n.start, n.end, n.pitch, n.velocity / 127.0) for n in inst.notes], columns=NOTE_COLUMNS))
    notes = crop_notes(song, start_s, end_s)
    tempo_times, tempi = pm.get_tempo_changes()
    info = {
        "lead_track_index": idx,
        "lead_track_name": inst.name,
        "lead_program": inst.program,
        "tracks": "; ".join(f"{i}:{t.name or '(unnamed)'}{' [drum]' if t.is_drum else ''}"
                            for i, t in enumerate(pm.instruments)),
        "song_notes": len(song),
        "excerpt_notes": len(notes),
        "excerpt_overlapping_notes": overlap_count(notes),
        "excerpt_low": note_name(notes["midi_note"].min()) if len(notes) else "",
        "excerpt_high": note_name(notes["midi_note"].max()) if len(notes) else "",
        "midi_end_s": round(pm.get_end_time(), 3),
        "excerpt_inside_midi": bool(end_s <= pm.get_end_time() + 1e-6),
        "excerpt_sounding_s": round(float((notes["end_s"] - notes["start_s"]).sum()), 3),
        "tempo_changes": len(tempi),
        "midi_tempo_bpm": round(float(tempi[0]), 3) if len(tempi) == 1 else "",
        "tempo_map": "; ".join(f"{t:.2f}s={b:.2f}" for t, b in zip(tempo_times, tempi)),
        "midi_key_signatures": "; ".join(pretty_midi.key_number_to_key_name(k.key_number)
                                         for k in pm.key_signature_changes),
        "time_signatures": "; ".join(f"{t.numerator}/{t.denominator}" for t in pm.time_signature_changes),
        "pitch_bends": len(inst.pitch_bends),
    }
    return notes, info


def frame_grid(duration_s: float, hop_s: float) -> np.ndarray:
    return np.arange(0.0, duration_s, hop_s)


def notes_to_frames(notes: pd.DataFrame, times: np.ndarray) -> np.ndarray:
    """MIDI pitch per frame, NaN where no note sounds; the higher pitch wins where notes overlap."""
    out = np.full(times.shape, np.nan)
    for r in notes.sort_values("midi_note").itertuples():
        out[(times >= r.start_s) & (times < r.end_s)] = r.midi_note
    return out


def contour_to_frames(c_times: np.ndarray, c_midi: np.ndarray, times: np.ndarray) -> np.ndarray:
    """Nearest contour frame for each grid time; NaN outside the contour or where unvoiced."""
    out = np.full(times.shape, np.nan)
    if len(c_times) < 2:
        return out
    hop = float(np.median(np.diff(c_times)))
    k = np.clip(np.searchsorted(c_times, times), 1, len(c_times) - 1)
    k -= (times - c_times[k - 1]) < (c_times[k] - times)
    near = np.abs(c_times[k] - times) <= hop
    out[near] = c_midi[k[near]]
    return out
