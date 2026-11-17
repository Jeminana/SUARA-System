"""Rule-based pitch-range recommender (T08); standard library only.

All distances are in semitones (MIDI scale), so an octave weighs the same at any pitch:

    outside    = semitones the melody goes above the singer's highest observed pitch
                 + semitones it goes below the singer's lowest observed pitch
    range_fit  = max(0, 1 - outside / 12)
    centre_fit = max(0, 1 - |melody centre - singer's median pitch| / 12)
    score      = 0.8 * range_fit + 0.2 * centre_fit, rounded to 4 decimals

The weights and the 12-semitone scale are unvalidated starting values. A score is a
range-fit rule, not a probability or a measure of suitability. Timbre is not used.
Songs that cannot be scored are left out rather than given an invented fit: a melody
range that is missing or marked unverified, and every song when the profile has no
voiced pitch. Ties sort by song_id, as the Recommendation contract requires.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from suara.contracts import Recommendation, SongFeatures, VoiceProfile
from suara.errors import validate_top_k

SCORING_VERSION = "pitch-range-fit-v1"
RANGE_WEIGHT = 0.8
CENTRE_WEIGHT = 0.2
SCALE_SEMITONES = 12.0
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def hz_to_midi(hz: float) -> float:
    return 69.0 + 12.0 * math.log2(hz / 440.0)


def note_name(midi: float) -> str:
    """Nearest note, MIDI 60 = C4."""
    nearest = round(midi)
    return f"{NOTE_NAMES[nearest % 12]}{nearest // 12 - 1}"


def scorable(song: SongFeatures) -> bool:
    return song.melody_min_pitch_hz is not None and song.provenance != "unverified"


def fit(voice_low: float, voice_high: float, voice_median: float,
        song_low: float, song_high: float) -> tuple[float, float, float, float]:
    """(score, semitones above, semitones below, centre distance); all inputs in MIDI."""
    above = max(0.0, song_high - voice_high)
    below = max(0.0, voice_low - song_low)
    centre = abs((song_low + song_high) / 2 - voice_median)
    range_fit = max(0.0, 1.0 - (above + below) / SCALE_SEMITONES)
    centre_fit = max(0.0, 1.0 - centre / SCALE_SEMITONES)
    return round(RANGE_WEIGHT * range_fit + CENTRE_WEIGHT * centre_fit, 4), above, below, centre


def _semitones(value: float) -> str:
    rounded = round(value, 1)
    return f"{rounded:g} semitone{'' if rounded == 1 else 's'}"


def _explain(song_low: float, song_high: float, voice_low: float, voice_high: float,
             above: float, below: float, centre: float, mock: bool) -> str:
    if above == 0 and below == 0:
        position = "fully inside the range you sang"
    else:
        position = " and ".join(part for part in (
            f"{_semitones(above)} above your highest note" if above else "",
            f"{_semitones(below)} below your lowest note" if below else "") if part)
    text = (f"Melody {note_name(song_low)}-{note_name(song_high)}; your recorded range "
            f"{note_name(voice_low)}-{note_name(voice_high)}. The melody is {position}, and its centre is "
            f"{_semitones(centre)} from your typical note. Range-fit rule {SCORING_VERSION}: "
            f"a short recording shows only the notes you sang, and this score does not measure how well the song suits your voice.")
    if mock:
        text += " Synthetic mock input: the voice profile or song range is a fixture, not a measurement."
    return text


def recommend_songs(voice_profile: VoiceProfile, song_catalog: Sequence[SongFeatures],
                    top_k: int = 5) -> list[Recommendation]:
    """Up to top_k scorable songs ranked by pitch-range fit; inputs are not modified."""
    validate_top_k(top_k)
    voice_profile.validate()
    for song in song_catalog:
        song.validate()
    pitch = voice_profile.pitch
    if pitch.voiced_ratio == 0:
        return []
    voice_low, voice_high = hz_to_midi(pitch.min_pitch_hz), hz_to_midi(pitch.max_pitch_hz)
    voice_median = hz_to_midi(pitch.median_pitch_hz)
    scored = []
    for song in song_catalog:
        if not scorable(song):
            continue
        song_low, song_high = hz_to_midi(song.melody_min_pitch_hz), hz_to_midi(song.melody_max_pitch_hz)
        score, above, below, centre = fit(voice_low, voice_high, voice_median, song_low, song_high)
        mock = voice_profile.analysis_mode == "mock" or song.provenance == "mock"
        scored.append(Recommendation(
            song_id=song.song_id, title=song.title, artist=song.artist, score=score,
            explanation=_explain(song_low, song_high, voice_low, voice_high, above, below, centre, mock),
            scoring_version=SCORING_VERSION, mode="mock" if mock else "real",
        ))
    scored.sort(key=lambda rec: (-rec.score, rec.song_id))
    return scored[:top_k]


recommend_songs.suara_mode = "real"
