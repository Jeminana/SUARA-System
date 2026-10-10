"""Write the five E3 pilot songs as MIDI files, plus guide audio for the singer to learn from.

    python tools/make_pilot_songs.py --out data

Draft melodies for a singer with a G2-E4 range, one melodic case per song (narrow range,
wide range, sustained high notes, large jumps, fast notes). Each file has a "Lead Vocal"
track (one note at a time) and an "Accompaniment" track (bass + chords), opening with one bar
of accompaniment as a count-in. The team reviews and approves these before recording; if
they are edited in MuseScore, the edited MIDI becomes the reference instead of this script.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pretty_midi
import soundfile as sf

SINGER_LOW, SINGER_HIGH = "G2", "E4"
BEATS_PER_BAR = 4
CHORDS = {  # bass root, chord tones (played above the voice so the melody stays audible)
    "C": ("C2", ["C4", "E4", "G4"]), "D": ("D2", ["D4", "F#4", "A4"]), "Dm": ("D2", ["D4", "F4", "A4"]),
    "E": ("E2", ["E4", "G#4", "B4"]), "Em": ("E2", ["E4", "G4", "B4"]), "F": ("F2", ["F4", "A4", "C5"]),
    "F#m": ("F#2", ["F#4", "A4", "C#5"]), "G": ("G2", ["G4", "B4", "D5"]), "A": ("A2", ["A4", "C#5", "E5"]),
    "A7": ("A2", ["G4", "C#5", "E5"]), "Am": ("A2", ["A4", "C5", "E5"]), "Bm": ("B2", ["B4", "D5", "F#4"]),
}

# Each bar: melody as (note or "r" for rest, beats) and chords as (chord, beats); both sum to 4.
SONGS = {
    "S01": {
        "title": "Narrow range", "case": "narrow range (a perfect fifth, D3-A3)", "bpm": 96, "key": "D Major",
        "bars": [
            ([("D3", 1), ("E3", 1), ("F#3", 1), ("G3", 1)], [("D", 4)]),
            ([("A3", 2), ("G3", 1), ("F#3", 1)], [("D", 4)]),
            ([("E3", 1), ("F#3", 1), ("G3", 1), ("E3", 1)], [("A7", 4)]),
            ([("D3", 3), ("r", 1)], [("D", 4)]),
            ([("F#3", 1), ("G3", 1), ("A3", 1), ("A3", 1)], [("D", 4)]),
            ([("G3", 1), ("F#3", 1), ("E3", 2)], [("Em", 4)]),
            ([("F#3", 1), ("E3", 1), ("D3", 1), ("E3", 1)], [("D", 4)]),
            ([("F#3", 3), ("r", 1)], [("D", 4)]),
            ([("A3", 1.5), ("G3", 0.5), ("F#3", 1), ("G3", 1)], [("D", 4)]),
            ([("A3", 1), ("G3", 1), ("F#3", 2)], [("D", 4)]),
            ([("E3", 1), ("G3", 1), ("F#3", 1), ("E3", 1)], [("A7", 4)]),
            ([("D3", 4)], [("D", 4)]),
        ],
    },
    "S02": {
        "title": "Wide range", "case": "wide range (17 semitones, A2-D4)", "bpm": 92, "key": "D Major",
        "bars": [
            ([("D3", 1), ("F#3", 1), ("A3", 1), ("D4", 1)], [("D", 4)]),
            ([("C#4", 2), ("A3", 2)], [("A", 4)]),
            ([("B3", 1), ("A3", 1), ("F#3", 1), ("D3", 1)], [("Bm", 4)]),
            ([("A2", 3), ("r", 1)], [("A", 4)]),
            ([("A2", 1), ("C#3", 1), ("E3", 1), ("A3", 1)], [("A", 4)]),
            ([("B3", 1), ("C#4", 1), ("D4", 2)], [("Bm", 4)]),
            ([("A3", 1), ("F#3", 1), ("E3", 1), ("C#3", 1)], [("A", 4)]),
            ([("D3", 3), ("r", 1)], [("D", 4)]),
            ([("D4", 1), ("A3", 1), ("F#3", 1), ("D3", 1)], [("D", 4)]),
            ([("B2", 1), ("D3", 1), ("G3", 1), ("B3", 1)], [("G", 4)]),
            ([("A3", 1), ("F#3", 1), ("E3", 1), ("C#3", 1)], [("A", 4)]),
            ([("D3", 4)], [("D", 4)]),
        ],
    },
    "S03": {
        "title": "Sustained high notes", "case": "sustained high notes (D4 and C#4 held, E4 touched once)",
        "bpm": 72, "key": "A Major",
        "bars": [
            ([("E3", 1), ("A3", 1), ("B3", 1), ("C#4", 1)], [("A", 4)]),
            ([("D4", 4)], [("D", 4)]),
            ([("C#4", 1), ("B3", 1), ("A3", 1), ("B3", 1)], [("A", 4)]),
            ([("C#4", 3), ("r", 1)], [("F#m", 4)]),
            ([("A3", 1), ("B3", 1), ("C#4", 1), ("D4", 1)], [("D", 4)]),
            ([("E4", 1), ("D4", 1), ("C#4", 2)], [("A", 4)]),
            ([("B3", 1), ("A3", 1), ("G#3", 1), ("B3", 1)], [("E", 4)]),
            ([("A3", 3), ("r", 1)], [("A", 4)]),
        ],
    },
    "S04": {
        "title": "Large jumps", "case": "large jumps (octaves and sixths, A2-D4)", "bpm": 88, "key": "C Major",
        "bars": [
            ([("C3", 1), ("C4", 1), ("B3", 1), ("G3", 1)], [("C", 4)]),
            ([("A3", 1), ("C3", 1), ("F3", 2)], [("F", 4)]),
            ([("E3", 1), ("C4", 1), ("A3", 1), ("D3", 1)], [("Am", 4)]),
            ([("G3", 3), ("r", 1)], [("G", 4)]),
            ([("A2", 1), ("A3", 1), ("G3", 1), ("E3", 1)], [("Am", 4)]),
            ([("F3", 1), ("D4", 1), ("C4", 2)], [("F", 4)]),
            ([("G3", 1), ("B2", 1), ("D3", 1), ("G3", 1)], [("G", 4)]),
            ([("C3", 3), ("r", 1)], [("C", 4)]),
            ([("C4", 1), ("E3", 1), ("G3", 1), ("C4", 1)], [("C", 4)]),
            ([("D4", 1), ("D3", 1), ("F3", 1), ("A3", 1)], [("Dm", 4)]),
            ([("B3", 1), ("B2", 1), ("D3", 1), ("G3", 1)], [("G", 4)]),
            ([("C3", 4)], [("C", 4)]),
        ],
    },
    "S05": {
        "title": "Fast notes", "case": "fast notes (eighths and sixteenths, A2-A3)", "bpm": 100, "key": "G Major",
        "bars": [
            ([("D3", .5), ("E3", .5), ("F#3", .5), ("G3", .5), ("A3", .5), ("G3", .5), ("F#3", .5), ("E3", .5)],
             [("G", 4)]),
            ([("F#3", .25), ("G3", .25), ("A3", .5), ("F#3", .5), ("D3", .5), ("E3", 1), ("r", 1)], [("D", 4)]),
            ([("B2", .5), ("C3", .5), ("D3", .5), ("E3", .5), ("F#3", .25), ("G3", .25), ("F#3", .25), ("E3", .25),
              ("D3", .5), ("B2", .5)], [("Em", 4)]),
            ([("C3", .5), ("E3", .5), ("D3", .5), ("C3", .5), ("B2", 1), ("r", 1)], [("C", 2), ("G", 2)]),
            ([("G3", .5), ("F#3", .5), ("E3", .5), ("F#3", .5), ("G3", .5), ("A3", .5), ("G3", .5), ("F#3", .5)],
             [("G", 4)]),
            ([("E3", .25), ("F#3", .25), ("G3", .5), ("E3", .5), ("C3", .5), ("D3", 1), ("r", 1)],
             [("C", 2), ("D", 2)]),
            ([("D3", .5), ("E3", .25), ("F#3", .25), ("G3", .5), ("A3", .5), ("G3", .25), ("F#3", .25), ("E3", .25),
              ("D3", .25), ("C3", .5), ("B2", .5)], [("D", 2), ("G", 2)]),
            ([("C3", .5), ("A2", .5), ("D3", .5), ("F#3", .5), ("G3", 2)], [("Am", 1), ("D", 1), ("G", 2)]),
            ([("D3", .5), ("E3", .5), ("F#3", .5), ("G3", .5), ("A3", .5), ("G3", .5), ("F#3", .5), ("E3", .5)],
             [("G", 4)]),
            ([("F#3", .25), ("G3", .25), ("A3", .5), ("F#3", .5), ("D3", .5), ("E3", 1), ("r", 1)], [("D", 4)]),
            ([("D3", .5), ("E3", .25), ("F#3", .25), ("G3", .5), ("A3", .5), ("G3", .25), ("F#3", .25), ("E3", .25),
              ("D3", .25), ("C3", .5), ("B2", .5)], [("D", 2), ("G", 2)]),
            ([("C3", .5), ("A2", .5), ("D3", .5), ("F#3", .5), ("G3", 2)], [("Am", 1), ("D", 1), ("G", 2)]),
        ],
    },
}

ARTICULATION = 0.95  # sung notes end slightly before the next one starts
N = pretty_midi.note_name_to_number


def build(song: dict) -> tuple[pretty_midi.PrettyMIDI, list, list]:
    beat = 60.0 / song["bpm"]
    pm = pretty_midi.PrettyMIDI(initial_tempo=song["bpm"])
    pm.key_signature_changes.append(pretty_midi.KeySignature(pretty_midi.key_name_to_key_number(song["key"]), 0))
    pm.time_signature_changes.append(pretty_midi.TimeSignature(4, 4, 0))
    lead = pretty_midi.Instrument(program=53, name="Lead Vocal")    # GM Voice Oohs
    acc = pretty_midi.Instrument(program=0, name="Accompaniment")   # GM Acoustic Grand Piano
    first_chord = song["bars"][0][1][0][0]
    bars = [([("r", 4)], [(first_chord, 4)])] + song["bars"]       # one bar count-in
    t = 0.0
    for i, (melody, chords) in enumerate(bars):
        for part in (melody, chords):
            if abs(sum(b for _, b in part) - BEATS_PER_BAR) > 1e-9:
                raise ValueError(f"bar {i} does not add up to {BEATS_PER_BAR} beats: {part}")
        m_t = t
        for name, beats in melody:
            if name != "r":
                lead.notes.append(pretty_midi.Note(100, N(name), m_t, m_t + beats * beat * ARTICULATION))
            m_t += beats * beat
        c_t = t
        for chord, beats in chords:
            root, tones = CHORDS[chord]
            end = c_t + beats * beat
            acc.notes.append(pretty_midi.Note(72, N(root), c_t, end - 0.02))
            k = c_t
            while k < end - 1e-9:  # chords on every beat
                for tone in tones:
                    acc.notes.append(pretty_midi.Note(55, N(tone), k, min(k + beat, end) - 0.03))
                k += beat
            c_t = end
        t += BEATS_PER_BAR * beat
    pm.instruments += [lead, acc]
    return pm, lead.notes, acc.notes


def render(notes: list, length_s: float, sr: int, harmonics: int, tilt: float, gain: float) -> np.ndarray:
    """Simple additive synthesis for a practice guide (not a recording)."""
    y = np.zeros(int(length_s * sr) + sr, dtype=np.float32)
    for n in notes:
        a, b = int(n.start * sr), min(int(n.end * sr), len(y))
        if b - a < 2:  # warped or out-of-range notes can collapse
            continue
        t = np.arange(b - a) / sr
        f = pretty_midi.note_number_to_hz(n.pitch)
        tone = sum(tilt ** (h - 1) * np.sin(2 * np.pi * f * h * t) for h in range(1, harmonics + 1) if f * h < sr / 2.2)
        env = np.minimum(1, t / 0.02) * np.minimum(1, (t[-1] - t) / 0.04 + 1e-3)
        y[a:b] += gain * (n.velocity / 127) * env * tone
    return y


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data"))
    args = ap.parse_args()
    (args.out / "midi").mkdir(parents=True, exist_ok=True)
    (args.out / "guide").mkdir(parents=True, exist_ok=True)
    low, high, sr = N(SINGER_LOW), N(SINGER_HIGH), 44100
    print(f"{'song':5} {'case':58} {'bpm':>3} {'length':>7} {'range':>9} {'longest':>8} {'shortest':>8} {'max leap':>8}")
    for sid, song in SONGS.items():
        pm, lead, acc = build(song)
        pitches = [n.pitch for n in lead]
        if min(pitches) < low or max(pitches) > high:
            raise ValueError(f"{sid} leaves the singer's range {SINGER_LOW}-{SINGER_HIGH}")
        if any(b.start < a.end for a, b in zip(lead, lead[1:])):
            raise ValueError(f"{sid} lead track is not one note at a time")
        length = pm.get_end_time()
        pm.write(str(args.out / "midi" / f"{sid}.mid"))
        melody = render(lead, length, sr, 8, 0.6, 0.5)
        accomp = render(acc, length, sr, 4, 0.4, 0.25)
        full = melody + accomp
        peak = max(np.abs(full).max(), 1e-9)
        sf.write(args.out / "guide" / f"{sid}_guide_with_accompaniment.wav", 0.8 * full / peak, sr)
        sf.write(args.out / "guide" / f"{sid}_melody_only.wav", 0.8 * melody / max(np.abs(melody).max(), 1e-9), sr)
        durs = [n.end - n.start for n in lead]
        leap = max(abs(b - a) for a, b in zip(pitches, pitches[1:]))
        rng = f"{pretty_midi.note_number_to_name(min(pitches))}-{pretty_midi.note_number_to_name(max(pitches))}"
        print(f"{sid:5} {song['case']:58} {song['bpm']:>3} {length:6.1f}s {rng:>9} {max(durs):7.2f}s "
              f"{min(durs):7.2f}s {leap:>5} st")
    print(f"\nWrote MIDI to {args.out / 'midi'} and practice audio to {args.out / 'guide'}")


if __name__ == "__main__":
    main()
