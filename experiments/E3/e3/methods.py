"""Analysis tools: provisional pitch detector, contour segmentation, Basic Pitch and Demucs.

The pitch detector is a small interface (name, settings, contour) so E3 can rerun with the
detector E1 selects; pYIN is the provisional baseline. Heavy libraries are imported only
when the tool is built, so check runs do not load TensorFlow or torch.
"""
from __future__ import annotations

import time
from pathlib import Path

import librosa
import numpy as np
import pandas as pd
import soundfile as sf
from scipy.ndimage import median_filter

from .references import NOTE_COLUMNS, clean_notes, empty_notes, hz_to_midi


def load_mono(path: str | Path, sr: int | None = None) -> tuple[np.ndarray, int]:
    y, sr = librosa.load(str(path), sr=sr, mono=True, res_type="soxr_hq")
    return y.astype(np.float32), int(sr)


def audio_qc(y: np.ndarray, sr: int, qc: dict) -> dict:
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    rms = librosa.feature.rms(y=y)[0] if len(y) else np.zeros(1)
    silent = rms < (np.max(rms) * 10 ** (-qc["silence_top_db"] / 20) if np.max(rms) > 0 else 1)
    return {"duration_s": round(len(y) / sr, 3), "sample_rate": sr, "peak": round(peak, 4),
            "clip_fraction": float(np.mean(np.abs(y) >= qc["clip_threshold"])) if len(y) else 0.0,
            "silence_fraction": float(np.mean(silent))}


# --------------------------------------------------------------------------- pitch detector
class PyinDetector:
    name = "pyin"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.sr = int(cfg["sample_rate"])
        self.hop = int(cfg["hop_length"])

    def settings(self) -> dict:
        return dict(self.cfg)

    def contour(self, y: np.ndarray, sr: int) -> pd.DataFrame:
        if sr != self.sr:
            y = librosa.resample(y, orig_sr=sr, target_sr=self.sr, res_type="soxr_hq")
        f0, flag, prob = librosa.pyin(
            y, fmin=librosa.note_to_hz(self.cfg["fmin_note"]), fmax=librosa.note_to_hz(self.cfg["fmax_note"]),
            sr=self.sr, frame_length=int(self.cfg["frame_length"]), hop_length=self.hop, center=True)
        times = librosa.times_like(f0, sr=self.sr, hop_length=self.hop)
        voiced = flag & (prob >= float(self.cfg["min_voiced_prob"])) & np.isfinite(f0)
        f0 = np.where(voiced, f0, np.nan)
        return pd.DataFrame({"time_s": times, "f0_hz": f0, "midi": hz_to_midi(f0),
                             "voiced_prob": prob, "voiced": voiced})


def build_detector(cfg: dict):
    if cfg["detector"] == "pyin":
        return PyinDetector(cfg["pyin"])
    raise ValueError(f"unknown pitch detector '{cfg['detector']}' (add E1's selection in methods.py)")


def _voiced_runs(voiced: np.ndarray) -> list[tuple[int, int]]:
    edges = np.diff(np.r_[0, voiced.astype(int), 0])
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


def segment_contour(contour: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """Voiced contour -> note events.

    Within each voiced run the contour is median smoothed; a new note starts once the pitch
    stays more than pitch_change_semitones from the current note's median for change_frames
    frames (so vibrato and short blips do not split notes). Notes shorter than min_note_s are
    dropped and same-pitch neighbours closer than merge_gap_s are merged. Each note's pitch is
    its median rounded to the nearest semitone; confidence is its mean voiced probability.
    """
    times = contour["time_s"].to_numpy(float)
    midi = contour["midi"].to_numpy(float)
    prob = contour["voiced_prob"].to_numpy(float)
    voiced = np.isfinite(midi)
    if len(times) < 2 or not voiced.any():
        return empty_notes()
    hop = float(np.median(np.diff(times)))
    thr, k = float(rules["pitch_change_semitones"]), int(rules["change_frames"])
    size = int(rules["smoothing_frames"])
    spans = []
    for a, b in _voiced_runs(voiced):
        m = midi[a:b]
        if size > 1 and len(m) >= size:
            m = median_filter(m, size=size, mode="nearest")
        start, cur, pending = 0, [m[0]], []
        for i in range(1, len(m)):
            if abs(m[i] - np.median(cur)) > thr:
                pending.append(m[i])
                if len(pending) >= k:
                    split = i - len(pending) + 1
                    spans.append((a + start, a + split, np.median(cur)))
                    start, cur, pending = split, list(pending), []
            else:
                cur += pending + [m[i]]
                pending = []
        spans.append((a + start, b, np.median(cur + pending)))

    rows = [(times[i0], times[i1 - 1] + hop, float(np.round(p)), float(np.mean(prob[i0:i1])))
            for i0, i1, p in spans]
    notes = pd.DataFrame(rows, columns=NOTE_COLUMNS)
    notes = merge_same_pitch(notes, float(rules["merge_gap_s"]))
    return clean_notes(notes[(notes["end_s"] - notes["start_s"]) >= float(rules["min_note_s"])])


def merge_same_pitch(notes: pd.DataFrame, gap_s: float) -> pd.DataFrame:
    """Join consecutive notes of the same pitch separated by at most gap_s (fragmented sustains)."""
    if notes.empty:
        return notes
    notes = notes.sort_values("start_s").reset_index(drop=True)
    out = [notes.iloc[0].to_dict()]
    for r in notes.iloc[1:].to_dict("records"):
        last = out[-1]
        if r["midi_note"] == last["midi_note"] and r["start_s"] - last["end_s"] <= gap_s:
            w1, w2 = last["end_s"] - last["start_s"], r["end_s"] - r["start_s"]
            last["confidence"] = (last["confidence"] * w1 + r["confidence"] * w2) / max(w1 + w2, 1e-9)
            last["end_s"] = max(last["end_s"], r["end_s"])
        else:
            out.append(r)
    return pd.DataFrame(out, columns=NOTE_COLUMNS)


# ------------------------------------------------------------------------------ Basic Pitch
class BasicPitchTranscriber:
    name = "basic_pitch"

    def __init__(self, cfg: dict):
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import Model

        self.cfg = cfg
        t0 = time.perf_counter()
        self.model_path = Path(ICASSP_2022_MODEL_PATH)
        self.model = Model(self.model_path)
        # A silent file through the real inference path pays the first-call costs (graph tracing,
        # lazy audio loading), so they count as model loading instead of being charged to
        # whichever excerpt happens to run first.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            silent = Path(tmp) / "warmup.wav"
            sf.write(silent, np.zeros(22050 * 3, dtype=np.float32), 22050)
            self.infer(silent)
        self.load_time_s = time.perf_counter() - t0

    def record(self) -> dict:
        return {"model": "basic-pitch ICASSP 2022", "model_path": str(self.model_path),
                "model_format": self.model_path.suffix or self.model_path.name,
                "load_time_s": self.load_time_s}

    def infer(self, audio_path: str | Path) -> dict:
        from basic_pitch.inference import run_inference
        return run_inference(str(audio_path), self.model)

    def notes(self, output: dict, params: dict):
        """Model output -> (PrettyMIDI, raw note events with amplitude)."""
        from basic_pitch.constants import AUDIO_SAMPLE_RATE, FFT_HOP
        from basic_pitch.note_creation import model_output_to_notes

        min_len = int(np.round(float(params["minimum_note_length_ms"]) / 1000 * (AUDIO_SAMPLE_RATE / FFT_HOP)))
        midi, events = model_output_to_notes(
            output, onset_thresh=float(params["onset_threshold"]), frame_thresh=float(params["frame_threshold"]),
            min_note_len=min_len,
            min_freq=librosa.note_to_hz(params["min_note"]) if params.get("min_note") else None,
            max_freq=librosa.note_to_hz(params["max_note"]) if params.get("max_note") else None,
            multiple_pitch_bends=False, melodia_trick=bool(params["melodia_trick"]))
        raw = pd.DataFrame([(e[0], e[1], e[2], e[3]) for e in events], columns=NOTE_COLUMNS)
        return midi, clean_notes(raw)


def select_lead_line(events: pd.DataFrame, rules: dict) -> tuple[pd.DataFrame, dict]:
    """Reduce general note transcription to one lead line with documented, fixed rules.

    1. drop notes shorter than min_note_s
    2. visit notes by priority (amplitude: loudest first, highest: skyline) and reject any note
       overlapping an accepted note by more than overlap_tolerance_s; a rejected note of the
       same pitch is a duplicate, of another pitch a false chord note
    3. trim remaining small overlaps so the line is monophonic
    4. merge same-pitch neighbours closer than merge_gap_s (fragmented sustained notes)
    """
    counts = {"raw_notes": len(events), "short_removed": 0, "duplicates_removed": 0,
              "chord_notes_removed": 0, "fragments_merged": 0, "lead_notes": 0}
    if events.empty:
        return empty_notes(), counts
    dur = events["end_s"] - events["start_s"]
    keep = events[dur >= float(rules["min_note_s"])]
    counts["short_removed"] = len(events) - len(keep)
    order = ["confidence", "midi_note"] if rules["priority"] == "amplitude" else ["midi_note", "confidence"]
    tol = float(rules["overlap_tolerance_s"])
    accepted: list[dict] = []
    for r in keep.sort_values(order, ascending=False).to_dict("records"):
        clash = [a for a in accepted
                 if min(a["end_s"], r["end_s"]) - max(a["start_s"], r["start_s"]) > tol]
        if not clash:
            accepted.append(r)
        elif any(a["midi_note"] == r["midi_note"] for a in clash):
            counts["duplicates_removed"] += 1
        else:
            counts["chord_notes_removed"] += 1
    line = pd.DataFrame(accepted, columns=NOTE_COLUMNS).sort_values("start_s").reset_index(drop=True)
    if len(line) > 1:
        nxt = line["start_s"].shift(-1)
        line["end_s"] = np.where(nxt.notna() & (line["end_s"] > nxt), nxt, line["end_s"])
    before = len(line)
    line = merge_same_pitch(line, float(rules["merge_gap_s"]))
    counts["fragments_merged"] = before - len(line)
    line = clean_notes(line)
    counts["lead_notes"] = len(line)
    return line, counts


# ----------------------------------------------------------------------------------- Demucs
class DemucsSeparator:
    name = "demucs"

    def __init__(self, cfg: dict, cache_dir: Path):
        import torch
        from demucs.api import Separator

        self.cfg = cfg
        self.cache_dir = cache_dir
        device = cfg["device"]
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        t0 = time.perf_counter()
        self.sep = Separator(model=cfg["model"], device=device, shifts=int(cfg["shifts"]),
                             overlap=float(cfg["overlap"]), split=True, jobs=0, progress=False)
        self.load_time_s = time.perf_counter() - t0
        self.samplerate = int(self.sep.samplerate)
        if cfg["stem"] not in self.sep.model.sources:
            raise ValueError(f"{cfg['model']} has no '{cfg['stem']}' stem: {self.sep.model.sources}")

    def vocals(self, audio_path: str | Path, seed: int) -> tuple[np.ndarray, int]:
        """Feed the model its own format (its sample rate and channel count) and return the
        selected stem as mono float32 at the model sample rate."""
        import torch
        from demucs.audio import convert_audio

        data, sr = sf.read(str(audio_path), dtype="float32", always_2d=True)
        wav = convert_audio(torch.from_numpy(data.T.copy()), sr, self.samplerate, self.sep.audio_channels)
        torch.manual_seed(seed)  # shifts use random offsets
        with torch.no_grad():
            _, stems = self.sep.separate_tensor(wav)
        return stems[self.cfg["stem"]].mean(0).cpu().numpy().astype(np.float32), self.samplerate

    def record(self) -> dict:
        """Model name plus the exact HuggingFace snapshot and checkpoint blobs used."""
        rec = {"model": self.cfg["model"], "sources": list(self.sep.model.sources),
               "samplerate": self.samplerate, "audio_channels": self.sep.audio_channels,
               "device": self.device, "shifts": self.cfg["shifts"], "overlap": self.cfg["overlap"],
               "load_time_s": self.load_time_s, "checkpoints": []}
        try:
            from huggingface_hub import scan_cache_dir
            from demucs.hf import hf_repo_name

            want = hf_repo_name(self.cfg["model"])
            for repo in scan_cache_dir(self.cache_dir / "hub").repos:
                if repo.repo_id.split("/")[-1] != want:
                    continue
                for rev in repo.revisions:
                    rec["checkpoints"].append({
                        "repo_id": repo.repo_id, "commit": rev.commit_hash,
                        "files": {f.file_name: f.blob_path.name for f in rev.files}})
        except Exception as e:  # the record must never block a run, but the gap is visible
            rec["checkpoint_record_error"] = f"{type(e).__name__}: {e}"
        return rec
