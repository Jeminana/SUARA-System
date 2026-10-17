"""Prepare the pilot recordings: synthesized melodies, mixes, annotation drafts and manifests.

    python tools/prepare_pilot_data.py --data data --singer P01

Expects data/midi/S0N.mid (from make_pilot_songs.py) and one isolated vocal per song at
data/audio/M0N.wav. Original recordings are never modified. For each song it:

1. aligns the MIDI melody to the recording with dynamic time warping on chroma features
   (standard score-to-audio alignment; none of the methods under test is used, so drafts do
   not lean towards any of them)
2. renders the synthesized melody (MIDI time) as the controlled transcription check
3. renders the accompaniment on the singer's timing and mixes it under the vocal
4. writes an annotation draft: the MIDI notes moved to the singer's timing, MIDI pitches
   unchanged, as an E3 note CSV and a Sonic Visualiser import CSV, for two reviewers to correct
5. writes catalog.csv and recordings.csv (never overwrites existing ones)

Human rows stay excluded ("awaiting verified annotation") until tools/build_verified.py builds
data/annotations/<id>_verified.csv from the two reviewers' annotations and includes them.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import librosa
import matplotlib
import numpy as np
import pandas as pd
import pretty_midi
import soundfile as sf

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_pilot_songs import SONGS, render  # noqa: E402

SR = 22050
HOP = 512                 # ~23 ms alignment frames
MIX_SR = 44100
ACCOMP_DB = -3.0          # accompaniment level relative to the vocal (RMS)
DEV_SONGS = {"S01", "S02"}


def features(chroma: np.ndarray, active: np.ndarray) -> np.ndarray:
    """Chroma plus a silence dimension so rests align with rests."""
    c = chroma * active[None, :]
    return np.vstack([c, (~active).astype(float)[None, :]]) + 1e-6


def align(pm: pretty_midi.PrettyMIDI, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Monotone map from MIDI time to audio time (two arrays to interpolate between)."""
    fs = SR / HOP
    lead = next(i for i in pm.instruments if i.name == "Lead Vocal")
    roll = lead.get_chroma(fs=fs)
    midi_active = roll.sum(0) > 0
    chroma_a = librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=HOP, fmin=librosa.note_to_hz("C2"))
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    n = min(chroma_a.shape[1], len(rms))
    audio_active = rms[:n] > np.max(rms) * 10 ** (-30 / 20)
    X = features(roll / np.maximum(roll.max(0, keepdims=True), 1e-9), midi_active)
    Y = features(chroma_a[:, :n], audio_active)
    _, wp = librosa.sequence.dtw(X=X, Y=Y, metric="cosine")
    wp = wp[::-1]
    t_midi, t_audio = wp[:, 0] / fs, wp[:, 1] / fs
    # one audio time per MIDI frame, kept strictly increasing for interpolation
    uniq, idx = np.unique(t_midi, return_index=True)
    ta = np.maximum.accumulate(np.array([np.median(t_audio[t_midi == u]) for u in uniq]))
    return uniq, ta + np.arange(len(ta)) * 1e-6


def warp(notes, tm, ta) -> list[pretty_midi.Note]:
    return [pretty_midi.Note(n.velocity, n.pitch, float(np.interp(n.start, tm, ta)),
                             float(np.interp(n.end, tm, ta))) for n in notes]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--singer", default="P01")
    args = ap.parse_args()
    d = args.data
    drafts, review = d / "annotations" / "drafts", d / "annotations" / "alignment_review"
    for p in (drafts, review):
        p.mkdir(parents=True, exist_ok=True)
    catalog, recordings = [], []
    for i, (sid, song) in enumerate(SONGS.items(), start=1):
        mid, vocal_file = f"M{i:02d}", d / "audio" / f"M{i:02d}.wav"
        if not vocal_file.is_file():
            print(f"{sid}: {vocal_file} not found, skipped")
            continue
        rid = f"{args.singer}_{mid}_T01"
        pm = pretty_midi.PrettyMIDI(str(d / "midi" / f"{sid}.mid"))
        lead = next(x for x in pm.instruments if x.name == "Lead Vocal").notes
        acc = next(x for x in pm.instruments if x.name == "Accompaniment").notes
        first, end = lead[0].start, pm.get_end_time()
        y, _ = librosa.load(str(vocal_file), sr=SR, mono=True)
        tm, ta = align(pm, y)
        offset = float(np.interp(first, tm, ta))

        # 2. synthesized melody in MIDI time
        syn = render(lead, end, MIX_SR, 8, 0.6, 0.5)
        sf.write(d / "audio" / f"SYN_{sid}.wav", 0.8 * syn / np.abs(syn).max(), MIX_SR)

        # 3. accompaniment on the singer's timing, mixed under the vocal
        v, _ = librosa.load(str(vocal_file), sr=MIX_SR, mono=True)
        a = render(warp(acc, tm, ta), len(v) / MIX_SR, MIX_SR, 4, 0.4, 0.25)[: len(v)]
        a = np.pad(a, (0, len(v) - len(a)))
        rms = lambda s: np.sqrt(np.mean(s ** 2)) + 1e-12  # noqa: E731
        mix = v + a * (rms(v) / rms(a)) * 10 ** (ACCOMP_DB / 20)
        sf.write(d / "audio" / f"{rid}_MIX.wav", (0.9 * mix / np.abs(mix).max()).astype(np.float32), MIX_SR)

        # 4. annotation draft (audio time; MIDI pitches)
        draft = warp(lead, tm, ta)
        rows = pd.DataFrame([(n.start, n.end, n.pitch) for n in draft], columns=["start_s", "end_s", "midi_note"])
        rows.round(4).to_csv(drafts / f"{rid}_draft.csv", index=False)
        sv = pd.DataFrame({"time": rows["start_s"], "value": rows["midi_note"],
                           "duration": rows["end_s"] - rows["start_s"],
                           "level": 0.8, "label": [pretty_midi.note_number_to_name(int(p)) for p in rows["midi_note"]]})
        sv.round(4).to_csv(drafts / f"{rid}_draft_sonic_visualiser.csv", index=False, header=False)

        # alignment picture so a person can check the draft starts in sensible places
        fig, ax = plt.subplots(figsize=(14, 3))
        ax.plot(np.arange(len(y)) / SR, y / np.abs(y).max() * 3 + rows["midi_note"].min() - 4, color="0.6", lw=0.3)
        for r in rows.itertuples():
            ax.add_patch(plt.Rectangle((r.start_s, r.midi_note - 0.4), r.end_s - r.start_s, 0.8, color="tab:blue"))
        ax.set_xlim(0, len(y) / SR)
        ax.set_ylim(rows["midi_note"].min() - 8, rows["midi_note"].max() + 3)
        ax.set_title(f"{rid}: draft notes (blue) over the waveform (grey)", fontsize=9, loc="left")
        fig.tight_layout()
        fig.savefig(review / f"{rid}.png", dpi=90)
        plt.close(fig)

        catalog.append({
            "song_id": sid, "melody_id": mid, "title": song["title"],
            "split": "dev" if sid in DEV_SONGS else "test", "source_type": "ai_drafted_team_approved",
            "creator": "Drafted with Claude (AI assistant) via tools/make_pilot_songs.py; approved by the SUARA team",
            "source_url": "tools/make_pilot_songs.py", "item_id": sid,
            "licence_or_permission": "Created for the SUARA capstone; team-owned",
            "allowed_uses": "SUARA capstone research", "access_date": date.today().isoformat(),
            "redistribution_restrictions": "team only",
            "excerpt_start_s": round(first, 4), "excerpt_end_s": round(end, 4),
            "midi_path": f"midi/{sid}.mid", "lead_track": "Lead Vocal",
            "verified_key": song["key"].replace("Major", "major"), "bpm": song["bpm"],
            "verified_by": "SUARA team", "notes": f"case: {song['case']}"})
        human = {"song_id": sid, "singer_id": args.singer, "take": "T01", "consent": "yes",
                 "audio_offset_s": round(offset, 3), "reference_type": "notes_csv",
                 "reference_path": f"annotations/{rid}_verified.csv", "device": "",
                 "excluded": "true", "exclusion_reason": "awaiting verified annotation"}
        recordings += [
            {"recording_id": f"SYN_{sid}", "song_id": sid, "kind": "synth_melody",
             "file_path": f"audio/SYN_{sid}.wav", "audio_offset_s": round(first, 4), "reference_type": "midi",
             "excluded": "false", "notes": "MIDI melody rendered by tools/prepare_pilot_data.py"},
            {**human, "recording_id": rid, "kind": "isolated_vocal", "file_path": f"audio/{vocal_file.name}",
             "notes": 'sung on "na"; original file name kept'},
            {**human, "recording_id": f"{rid}_MIX", "kind": "mix", "file_path": f"audio/{rid}_MIX.wav",
             "paired_with": rid, "reference_type": "", "reference_path": "", "consent": "",
             "notes": f"vocal + accompaniment aligned to the singer, accompaniment {ACCOMP_DB:+.0f} dB"},
        ]
        print(f"{sid}: song starts {offset:5.2f}s into {vocal_file.name}; wrote SYN_{sid}.wav, {rid}_MIX.wav, draft")

    for name, rows in (("catalog.csv", catalog), ("recordings.csv", recordings)):
        path = d / name
        if path.exists():
            print(f"{path} already exists; not overwritten")
        else:
            pd.DataFrame(rows).to_csv(path, index=False)
            print(f"wrote {path}")
    corrections = d / "corrections.csv"
    if not corrections.exists():
        corrections.write_text("recording_id,method,reviewer,correction_minutes,corrected_notes_path,notes\n")


if __name__ == "__main__":
    main()
