"""Generate a synthetic five-song catalog to smoke-test the E3 pipeline end to end.

    python tools/make_synthetic_data.py --out data/synthetic

Each song gets a MIDI file (lead + accompaniment), a synthesized melody, a voice-like
"isolated vocal" that deviates from the MIDI (detuning, timing jitter, vibrato, a lead-in),
its exact annotation, and a mix of that vocal with the accompaniment. This checks the code
path only - it says nothing about real singing or real songs, and results on it must never
be reported as experimental evidence.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pretty_midi
import soundfile as sf

SR = 44100
EXCERPT_S = 24.0
LEAD_IN_S = 0.5
CHORDS = [(48, 52, 55), (43, 47, 50), (45, 48, 52), (41, 45, 48)]  # C G Am F
# (bpm, phrase of (midi, beats)) chosen to cover the procedure's melodic cases
SONGS = {
    "S01": ("narrow range", 100, [(64, 1), (65, 1), (67, 2), (65, 1), (64, 1), (62, 2), (64, 1), (67, 1),
                                  (69, 1), (67, 1), (65, 2), (64, 2)]),
    "S02": ("wide range", 96, [(57, 1), (60, 1), (64, 1), (69, 1), (72, 2), (76, 2), (74, 1), (71, 1),
                               (67, 1), (62, 1), (59, 2), (55, 2)]),
    "S03": ("sustained high notes", 80, [(67, 1), (69, 1), (71, 1), (72, 1), (76, 4), (74, 1), (72, 1),
                                         (71, 2), (77, 4)]),
    "S04": ("large jumps", 90, [(60, 1), (72, 1), (64, 1), (76, 1), (67, 2), (55, 1), (67, 1), (57, 1),
                                (69, 1), (65, 2)]),
    "S05": ("fast notes", 120, [(72, 0.5), (71, 0.5), (69, 0.5), (67, 0.5), (65, 0.25), (67, 0.25), (69, 0.25),
                                (71, 0.25), (72, 1), (67, 0.5), (64, 0.5), (65, 0.5), (67, 0.5), (69, 2)]),
}
SPLITS = {"S01": "dev", "S02": "dev", "S03": "test", "S04": "test", "S05": "test"}


def melody_notes(bpm: float, phrase: list) -> list[tuple[float, float, int]]:
    """Repeat the phrase with a short rest until the excerpt is full."""
    beat, t, out = 60.0 / bpm, 0.0, []
    while t < EXCERPT_S:
        for midi, beats in phrase:
            dur = beats * beat
            if t + dur * 0.9 > EXCERPT_S:
                return out
            out.append((t, t + dur * 0.9, midi))  # 10% articulation gap
            t += dur
        t += beat  # rest between phrases
    return out


def harmonic_tone(f0: np.ndarray, n_harm: int, tilt: float) -> np.ndarray:
    phase = 2 * np.pi * np.cumsum(f0) / SR
    y = np.zeros_like(f0)
    for h in range(1, n_harm + 1):
        y += (f0 * h < SR / 2.2) * tilt ** (h - 1) * np.sin(h * phase)
    return y


def render(notes, total_s, voice: bool, rng) -> tuple[np.ndarray, list, np.ndarray]:
    """Additive synthesis. voice=True adds detune, timing jitter, vibrato and breath noise and
    returns what was actually 'sung' as notes and a 10 ms F0 track."""
    n = int(total_s * SR)
    f0 = np.zeros(n)
    amp = np.zeros(n)
    sung = []
    for start, end, midi in notes:
        if voice:
            start += LEAD_IN_S + rng.normal(0, 0.015)
            end += LEAD_IN_S + rng.normal(0, 0.015)
            cents = rng.normal(0, 12)
        else:
            cents = 0.0
        a, b = int(start * SR), min(int(end * SR), n)
        if b - a < 10:
            continue
        t = np.arange(b - a) / SR
        m = midi + cents / 100
        if voice:
            m = m + 0.3 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(t / 0.25, 1)
        f0[a:b] = 440 * 2 ** ((m - 69) / 12)
        env = np.minimum(1, t / 0.03) * np.minimum(1, (t[-1] - t) / 0.05 + 1e-3)
        amp[a:b] = env
        sung.append((start, end, midi))
    y = harmonic_tone(np.where(f0 > 0, f0, 1.0), 12 if voice else 6, 0.6 if voice else 0.45) * amp
    if voice:
        y += 0.01 * rng.standard_normal(n) * amp
    times = np.arange(0, total_s, 0.01)
    track = np.array([f0[min(int(t * SR), n - 1)] if amp[min(int(t * SR), n - 1)] > 0.3 else 0.0 for t in times])
    return y.astype(np.float32), sung, np.c_[times, track]


def accompaniment(bpm: float, total_s: float, offset_s: float) -> tuple[np.ndarray, list]:
    bar = 4 * 60.0 / bpm
    n = int(total_s * SR)
    y = np.zeros(n, dtype=np.float32)
    events = []
    t, i = 0.0, 0
    while t < EXCERPT_S:
        chord = CHORDS[i % len(CHORDS)]
        end = min(t + bar, EXCERPT_S)
        a, b = int((t + offset_s) * SR), min(int((end + offset_s) * SR), n)
        tt = np.arange(b - a) / SR
        env = np.minimum(1, tt / 0.02) * np.exp(-tt / 1.5)
        for k, midi in enumerate((chord[0] - 12, *chord)):
            f = 440 * 2 ** ((midi - 69) / 12)
            y[a:b] += (0.5 if k == 0 else 0.25) * env * harmonic_tone(np.full(b - a, f), 5, 0.5)
            events.append((t, end, midi - 0))
        t, i = end, i + 1
    return y, events


def write_midi(path: Path, bpm: float, lead: list, acc: list) -> None:
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    pm.key_signature_changes.append(pretty_midi.KeySignature(0, 0))  # C major
    pm.time_signature_changes.append(pretty_midi.TimeSignature(4, 4, 0))
    for name, program, notes, vel in (("Lead Vocal", 53, lead, 100), ("Accompaniment", 0, acc, 70)):
        inst = pretty_midi.Instrument(program=program, name=name)
        inst.notes = [pretty_midi.Note(vel, int(m), float(s), float(e)) for s, e, m in notes]
        pm.instruments.append(inst)
    pm.write(str(path))


def norm(y: np.ndarray, peak: float = 0.7) -> np.ndarray:
    return (peak * y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/synthetic"))
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    for sub in ("midi", "audio", "annotations"):
        (args.out / sub).mkdir(parents=True, exist_ok=True)
    catalog, recordings, corrections = [], [], []
    for i, (sid, (desc, bpm, phrase)) in enumerate(SONGS.items(), start=1):
        mid = f"M{i:02d}"
        lead = melody_notes(bpm, phrase)
        acc_dry, acc_events = accompaniment(bpm, EXCERPT_S + 0.5, 0.0)
        write_midi(args.out / "midi" / f"{sid}.mid", bpm, lead, acc_events)

        synth, _, _ = render(lead, EXCERPT_S + 0.5, voice=False, rng=rng)
        sf.write(args.out / "audio" / f"SYN_{sid}.wav", norm(synth), SR)

        total = EXCERPT_S + LEAD_IN_S + 0.5
        vocal, sung, f0 = render(lead, total, voice=True, rng=rng)
        vid = f"P01_{mid}_T01"
        sf.write(args.out / "audio" / f"{vid}.wav", norm(vocal), SR)
        pd.DataFrame(sung, columns=["start_s", "end_s", "midi_note"]).round(4).to_csv(
            args.out / "annotations" / f"{vid}_notes.csv", index=False)
        pd.DataFrame(f0, columns=["time_s", "f0_hz"]).round(3).to_csv(
            args.out / "annotations" / f"{vid}_f0.csv", index=False)
        acc, _ = accompaniment(bpm, total, LEAD_IN_S)
        mix = norm(vocal) + 0.6 * norm(acc)
        sf.write(args.out / "audio" / f"{vid}_MIX.wav", norm(np.c_[mix, mix]), SR)

        catalog.append({"song_id": sid, "melody_id": mid, "title": f"Synthetic {desc}", "split": SPLITS[sid],
                        "source_type": "team_composed", "creator": "tools/make_synthetic_data.py",
                        "licence_or_permission": "synthetic test material", "excerpt_start_s": 0.0,
                        "excerpt_end_s": EXCERPT_S, "midi_path": f"midi/{sid}.mid", "lead_track": "Lead Vocal",
                        "verified_key": "C major", "bpm": bpm, "verified_by": "synthetic",
                        "notes": f"synthetic: {desc}"})
        base = {"song_id": sid, "consent": "synthetic", "device": "synthetic", "notes": "synthetic test signal"}
        recordings += [
            {**base, "recording_id": f"SYN_{sid}", "kind": "synth_melody", "file_path": f"audio/SYN_{sid}.wav",
             "reference_type": "midi", "audio_offset_s": 0.0, "consent": ""},
            {**base, "recording_id": vid, "kind": "isolated_vocal", "singer_id": "P01", "take": "T01",
             "file_path": f"audio/{vid}.wav", "audio_offset_s": LEAD_IN_S, "reference_type": "notes_csv",
             "reference_path": f"annotations/{vid}_notes.csv", "reference_f0_path": f"annotations/{vid}_f0.csv"},
            {**base, "recording_id": f"{vid}_MIX", "kind": "mix", "singer_id": "P01", "take": "T01",
             "file_path": f"audio/{vid}_MIX.wav", "audio_offset_s": LEAD_IN_S, "paired_with": vid},
        ]
        if SPLITS[sid] == "test":
            # Exercises the corrected-version path: a "perfect" correction back to the annotation.
            corrections.append({"recording_id": vid, "method": "pyin", "reviewer": "synthetic",
                                "correction_minutes": 2.0, "corrected_notes_path": f"annotations/{vid}_notes.csv",
                                "notes": "synthetic code-path test, not a real correction"})
    pd.DataFrame(catalog).to_csv(args.out / "catalog.csv", index=False)
    pd.DataFrame(recordings).to_csv(args.out / "recordings.csv", index=False)
    pd.DataFrame(corrections).to_csv(args.out / "corrections.csv", index=False)
    print(f"Wrote {len(catalog)} songs and {len(recordings)} recordings to {args.out}")


if __name__ == "__main__":
    main()
