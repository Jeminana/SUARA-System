"""E3 stages.

check   : validate the catalog/rights and recordings manifests, import and verify MIDI
          references, export reference notes, audio QC; --tools runs every tool on a short crop.
dev     : dev songs only. Sweep contour segmentation rules and Basic Pitch thresholds to choose
          settings before locking.
test    : locked run on held-out songs. Raw outputs, metrics, corrections, profiles, timing.
catalog : build the E4/E5 handoff catalog from verified reference melodies.
"""
from __future__ import annotations

import itertools
import shutil
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

from . import catalog as cat, evaluation as ev, io_utils, plots, profiles as pf, references as rf
from .methods import (BasicPitchTranscriber, DemucsSeparator, audio_qc, build_detector, load_mono,
                      segment_contour, select_lead_line)

# tool: which analysis runs; separate: Demucs vocal stem first; diagnostic: never selected as a route
METHODS = {
    "basic_pitch":        {"kinds": cat.ISOLATED_KINDS, "tool": "basic_pitch", "separate": False,
                           "source_type": "isolated", "diagnostic": False},
    "detector_isolated":  {"kinds": cat.ISOLATED_KINDS, "tool": "detector", "separate": False,
                           "source_type": "isolated", "diagnostic": False},
    "demucs_detector":    {"kinds": cat.MIX_KINDS, "tool": "detector", "separate": True,
                           "source_type": "separated_mix", "diagnostic": False},
    "demucs_basic_pitch": {"kinds": cat.MIX_KINDS, "tool": "basic_pitch", "separate": True,
                           "source_type": "separated_mix", "diagnostic": False},
    "detector_mix":       {"kinds": cat.MIX_KINDS, "tool": "detector", "separate": False,
                           "source_type": "full_mix", "diagnostic": True},
}


def md_table(df: pd.DataFrame) -> str:
    def fmt(v):
        if isinstance(v, float):
            return "Not measured" if np.isnan(v) else f"{v:.3f}"
        return str(v)
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    rule = "|" + "---|" * len(df.columns)
    body = ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([head, rule, *body])


class Run:
    def __init__(self, config_path: Path, stage: str, run_name: str | None, synthetic: bool,
                 data_root: str | None = None, tools: bool = False):
        self.config_path = config_path.resolve()
        self.cfg = io_utils.load_config(config_path)
        self.base = self.config_path.parent
        self.stage = stage
        self.synthetic = synthetic
        self.tools = tools
        self.data_root = self.path(data_root or self.cfg["paths"]["data_root"])
        name = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.out = self.path(self.cfg["paths"]["output_root"]) / f"{name}_{stage}"
        self.out.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.config_path, self.out / "config_used.yaml")
        self.log = io_utils.setup_logging(self.out)
        self.seed = int(self.cfg["seed"])
        np.random.seed(self.seed)
        self._detector = self._bp = self._demucs = None
        self.cache: dict = {}
        self.log.info("Data root: %s", self.data_root)
        if synthetic:
            self.log.warning("SYNTHETIC DATA MODE: outputs test the code only and are not experimental evidence.")

    def path(self, p: str) -> Path:
        p = Path(p)
        return p if p.is_absolute() else self.base / p

    # ------------------------------------------------------------------ data
    def load(self, need_recordings: bool = True) -> None:
        paths = self.cfg["paths"]
        self.catalog, warnings = cat.load_catalog(cat.resolve(self.data_root, paths["catalog"]), self.data_root)
        self.songs = self.catalog.set_index("song_id", drop=False)
        excl = [{"record": "song", "id": r.song_id, "reason": r.exclusion_reason}
                for r in self.catalog[self.catalog["excluded"]].itertuples()]
        self.refs, self.ref_info = {}, {}
        for r in self.catalog[~self.catalog["excluded"]].itertuples():
            if r.midi_abs:
                self.refs[r.song_id], self.ref_info[r.song_id] = rf.load_midi_reference(
                    r.midi_abs, r.lead_track, float(r.excerpt_start_s), float(r.excerpt_end_s))
            else:
                self.refs[r.song_id] = rf.read_notes_csv(r.verified_notes_abs)
                self.ref_info[r.song_id] = {"reference": "verified_notes_path"}
            if self.ref_info[r.song_id].get("excerpt_overlapping_notes"):
                warnings.append(f"{r.song_id}: lead track has overlapping notes (harmony or wrong track?)")
        self.recordings = pd.DataFrame()
        if need_recordings:
            accepted = list(self.cfg["consent"]["accepted_values"]) + (["synthetic"] if self.synthetic else [])
            self.recordings, w2 = cat.load_recordings(cat.resolve(self.data_root, paths["recordings"]),
                                                      self.data_root, self.catalog, accepted)
            warnings += w2
            excl += [{"record": "recording", "id": r.recording_id, "reason": r.exclusion_reason}
                     for r in self.recordings[self.recordings["excluded"]].itertuples()]
            self.corrections = cat.load_corrections(cat.resolve(self.data_root, paths["corrections"]),
                                                    self.data_root)
        for w in warnings:
            self.log.warning("%s", w)
        pd.DataFrame(excl, columns=["record", "id", "reason"]).to_csv(self.out / "exclusions.csv", index=False)
        self.log.info("Catalog: %d songs (%d excluded); recordings: %d (%d excluded)",
                      len(self.catalog), int(self.catalog["excluded"].sum()), len(self.recordings),
                      int(self.recordings["excluded"].sum()) if len(self.recordings) else 0)

    def usable(self, split: str) -> pd.DataFrame:
        r = self.recordings
        return r[~r["excluded"] & (r["split"] == split)].reset_index(drop=True)

    def duration(self, song_id: str) -> float:
        s = self.songs.loc[song_id]
        return float(s["excerpt_end_s"]) - float(s["excerpt_start_s"])

    def reference(self, rec) -> tuple[pd.DataFrame, tuple | None]:
        """Reference notes and optional verified F0, in excerpt time."""
        dur = self.duration(rec.song_id)
        if rec.reference_type == "midi":
            notes = self.refs[rec.song_id]
        else:
            notes = rf.shift_notes(rf.read_notes_csv(rec.reference_abs), rec.audio_offset_s, dur)
        f0 = None
        if rec.reference_f0_abs:
            t, m = rf.read_f0_csv(rec.reference_f0_abs)
            t = t - rec.audio_offset_s
            keep = (t >= 0) & (t < dur)
            f0 = (t[keep], m[keep])
        return notes, f0

    def methods_for(self, kind: str) -> list[str]:
        return [m for m, on in self.cfg["methods"].items() if on and kind in METHODS[m]["kinds"]]

    def label(self, method: str) -> str:
        d = self.cfg["pitch"]["detector"]
        return {"detector_isolated": d, "demucs_detector": f"demucs+{d}", "detector_mix": f"{d}_mix",
                "basic_pitch": "basic_pitch", "demucs_basic_pitch": "demucs+basic_pitch"}[method]

    # ----------------------------------------------------------------- tools
    @property
    def detector(self):
        if self._detector is None:
            self._detector = build_detector(self.cfg["pitch"])
        return self._detector

    @property
    def bp(self) -> BasicPitchTranscriber:
        if self._bp is None:
            self._bp = BasicPitchTranscriber(self.cfg["basic_pitch"])
            self.log.info("Basic Pitch loaded in %.1f s", self._bp.load_time_s)
        return self._bp

    @property
    def demucs(self) -> DemucsSeparator:
        if self._demucs is None:
            self._demucs = DemucsSeparator(self.cfg["demucs"], self.path(self.cfg["paths"]["model_cache"]))
            self.log.info("Demucs %s loaded in %.1f s on %s", self.cfg["demucs"]["model"],
                          self._demucs.load_time_s, self._demucs.device)
        return self._demucs

    def tool_records(self) -> dict:
        rec = {"pitch_detector": {"name": self.cfg["pitch"]["detector"],
                                  "settings": self.cfg["pitch"][self.cfg["pitch"]["detector"]]}}
        if self._bp is not None:
            rec["basic_pitch"] = self._bp.record()
        if self._demucs is not None:
            rec["demucs"] = self._demucs.record()
        return rec

    def cached(self, key: tuple, fn):
        """Compute once per run; returns (value, seconds of the first computation)."""
        if key not in self.cache:
            t0 = time.perf_counter()
            value = fn()
            self.cache[key] = (value, time.perf_counter() - t0)
        return self.cache[key]

    def stem(self, rec) -> tuple[Path, float]:
        """Separated vocal stem, saved so the team can listen for artifacts."""
        demucs = self.demucs  # load outside the timed region
        def run():
            y, sr = demucs.vocals(rec.abs_path, self.seed)
            d = self.out / "stems"
            d.mkdir(exist_ok=True)
            p = d / f"{rec.recording_id}_{self.cfg['demucs']['stem']}.wav"
            sf.write(p, y, sr, subtype="FLOAT")
            return p
        return self.cached(("stem", rec.recording_id), run)

    def run_method(self, rec, method: str, seg_rules: dict, bp_params: dict, lead_rules: dict) -> dict:
        """Notes (and contour for F0 methods) in excerpt time plus per-stage seconds."""
        spec, dur, off = METHODS[method], self.duration(rec.song_id), rec.audio_offset_s
        t = {"load_s": 0.0, "separation_s": 0.0, "pitch_s": 0.0, "notes_s": 0.0}
        src = Path(rec.abs_path)
        if spec["separate"]:
            src, t["separation_s"] = self.stem(rec)
        res = {"contour": None, "raw_notes": None, "midi": None, "lead_counts": None}
        if spec["tool"] == "detector":
            detector = self.detector  # tools load outside the timed region
            (y, sr), t["load_s"] = self.cached(("audio", str(src)), lambda: load_mono(src))
            contour, t["pitch_s"] = self.cached(("contour", str(src)), lambda: detector.contour(y, sr))
            t0 = time.perf_counter()
            notes = segment_contour(contour, seg_rules)
            t["notes_s"] = time.perf_counter() - t0
            c = contour.copy()
            c["time_s"] -= off
            res["contour"] = c[(c["time_s"] >= 0) & (c["time_s"] < dur)].reset_index(drop=True)
            res["contour_audio_time"] = contour
        else:
            bp = self.bp
            output, t["pitch_s"] = self.cached(("bp", str(src)), lambda: bp.infer(src))
            t0 = time.perf_counter()
            res["midi"], raw = self.bp.notes(output, bp_params)
            notes, res["lead_counts"] = select_lead_line(raw, lead_rules)
            t["notes_s"] = time.perf_counter() - t0
            res["raw_notes"] = raw
        res["notes_audio_time"] = notes
        res["notes"] = rf.shift_notes(notes, off, dur)
        res["timing"] = {**t, "total_s": sum(t.values())}
        return res

    def evaluate(self, rec, notes, contour, ref, f0) -> dict:
        return ev.evaluate(ref, notes, self.duration(rec.song_id), self.cfg["evaluation"], f0, contour)

    def environment(self, extra: dict) -> None:
        io_utils.write_json(self.out / "environment.json", io_utils.environment_record(
            self.config_path, self.cfg, {"stage": self.stage, "synthetic_data": self.synthetic,
                                         "tools": self.tool_records(), **extra}))

    # ---------------------------------------------------------------- stages
    def check(self) -> None:
        self.load()
        ref_dir = self.out / "reference_notes"
        ref_dir.mkdir(exist_ok=True)
        midi_rows = []
        for sid, notes in self.refs.items():
            notes.to_csv(ref_dir / f"{sid}.csv", index=False, float_format="%.4f")
            midi_rows.append({"song_id": sid, "excerpt_duration_s": self.duration(sid), **self.ref_info[sid]})
        pd.DataFrame(midi_rows).to_csv(self.out / "midi_check.csv", index=False)

        qc_cfg, audio_rows = self.cfg["audio_qc"], []
        for rec in self.recordings[~self.recordings["excluded"]].itertuples():
            y, sr = load_mono(rec.abs_path)
            qc = audio_qc(y, sr, qc_cfg)
            need = rec.audio_offset_s + self.duration(rec.song_id)
            flags = [f for f, bad in (
                ("shorter_than_excerpt", qc["duration_s"] + 0.05 < need),
                ("clipping", qc["clip_fraction"] > qc_cfg["max_clip_fraction"]),
                ("mostly_silent", qc["silence_fraction"] > qc_cfg["max_silence_fraction"]),
                ("low_sample_rate", sr < qc_cfg["min_sample_rate"])) if bad]
            audio_rows.append({"recording_id": rec.recording_id, "song_id": rec.song_id, "kind": rec.kind,
                               "split": rec.split, "needed_s": round(need, 3), **qc, "qc_flags": ";".join(flags)})
            if rec.reference_type == "notes_csv":
                ref, _ = self.reference(rec)
                ref.to_csv(ref_dir / f"{rec.recording_id}.csv", index=False, float_format="%.4f")
        audio = pd.DataFrame(audio_rows)
        audio.to_csv(self.out / "audio_check.csv", index=False)
        flagged = audio[audio["qc_flags"] != ""] if len(audio) else audio
        if len(flagged):
            self.log.warning("Audio QC flags (listen, then exclude in recordings.csv if needed):\n%s",
                             flagged[["recording_id", "qc_flags"]].to_string(index=False))
        if self.tools:
            self.tool_check()
        self.environment({})
        self.log.info("Check complete: verify midi_check.csv (lead track, low/high note names, tempo map), "
                      "audio_check.csv and reference_notes/ before running dev.")

    def tool_check(self) -> None:
        """Confirm every tool works on one short file before spending time on full runs."""
        recs = self.recordings[~self.recordings["excluded"]]
        mix = recs[recs["kind"].isin(cat.MIX_KINDS)]
        rec = (mix if len(mix) else recs).iloc[0]
        y, sr = load_mono(rec["abs_path"])
        crop = self.out / "tool_check_crop.wav"
        sf.write(crop, y[: int(5 * sr)], sr)
        result = {"file": rec["recording_id"], "crop_s": 5}
        for name, fn in (("pitch_detector", lambda: self.detector.contour(*load_mono(crop))),
                         ("basic_pitch", lambda: self.bp.infer(crop)),
                         ("demucs", lambda: self.demucs.vocals(crop, self.seed))):
            t0 = time.perf_counter()
            try:
                fn()
                result[name] = {"ok": True, "seconds": round(time.perf_counter() - t0, 2)}
            except Exception as e:
                result[name] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            self.log.info("tool check %-15s %s", name, result[name])
        result["records"] = self.tool_records()
        io_utils.write_json(self.out / "tool_check.json", result)

    def dev(self) -> None:
        self.load()
        dev = self.usable("dev")
        if dev.empty:
            raise SystemExit("No dev recordings found.")
        seg_base, bp_base, lead = self.cfg["segmentation"], self.cfg["basic_pitch"], self.cfg["lead_line"]
        grid = self.cfg["dev"]
        seg_cands = [dict(zip(grid["segmentation_grid"], v))
                     for v in itertools.product(*grid["segmentation_grid"].values())]
        bp_cands = [dict(zip(grid["basic_pitch_grid"], v))
                    for v in itertools.product(*grid["basic_pitch_grid"].values())]
        rows = []
        for rec in dev.itertuples():
            ref, f0 = self.reference(rec)
            for method in self.methods_for(rec.kind):
                is_det = METHODS[method]["tool"] == "detector"
                for cand in (seg_cands if is_det else bp_cands):
                    res = self.run_method(rec, method, {**seg_base, **cand} if is_det else seg_base,
                                          bp_base if is_det else {**bp_base, **cand}, lead)
                    m = self.evaluate(rec, res["notes"], res["contour"], ref, f0)
                    rows.append({"tool": METHODS[method]["tool"], "method": self.label(method),
                                 "diagnostic": METHODS[method]["diagnostic"], "recording_id": rec.recording_id,
                                 "kind": rec.kind, "candidate": ";".join(f"{k}={v}" for k, v in cand.items()),
                                 **cand, **m})
                self.log.info("dev %-22s %-14s %d candidates", rec.recording_id, self.label(method),
                              len(seg_cands if is_det else bp_cands))
        per = pd.DataFrame(rows)
        per.to_csv(self.out / "dev_per_recording.csv", index=False)
        best = {}
        for tool, keys, fname in (("detector", list(grid["segmentation_grid"]), "dev_segmentation.csv"),
                                  ("basic_pitch", list(grid["basic_pitch_grid"]), "dev_basic_pitch.csv")):
            sub = per[per["tool"] == tool]
            if sub.empty:
                continue
            agg = (sub.groupby(["candidate", *keys, "method"])[["note_f1", "frame_accuracy", "note_f1_with_offset"]]
                   .mean().reset_index())
            agg.to_csv(self.out / fname, index=False)
            # Choose on non-diagnostic methods only, pooled over recordings.
            pick = (sub[~sub["diagnostic"]].groupby(["candidate", *keys])["note_f1"].mean()
                    .sort_values(ascending=False))
            if len(pick):
                cand, score = pick.index[0], float(pick.iloc[0])
                best[tool] = {"settings": dict(zip(keys, cand[1:])), "mean_dev_note_f1": score}
                self.log.info("dev best %s: %s (mean note F1 %.3f)", tool, cand[0], score)
        io_utils.write_json(self.out / "dev_best.json", best)
        self.environment({"dev_recordings": dev["recording_id"].tolist()})
        self.log.info("Dev results are in-sample on dev songs and only guide the choice. Copy the chosen "
                      "settings into config.yaml (segmentation / basic_pitch), set locked: true, then run test.")

    def test(self) -> None:
        if not self.cfg.get("locked"):
            raise SystemExit("config.yaml is not locked. Finish dev choices, set locked: true, then rerun.")
        self.load()
        test = self.usable("test")
        if test.empty:
            raise SystemExit("No test recordings found.")
        if set(test["song_id"]) & set(self.catalog.loc[self.catalog["split"] == "dev", "song_id"]):
            raise SystemExit("A dev song appears in the test set.")
        cfg, raw_dir, plot_dir = self.cfg, self.out / "raw", self.out / "plots"
        plot_dir.mkdir(exist_ok=True)
        seg, bp, lead = cfg["segmentation"], cfg["basic_pitch"], cfg["lead_line"]
        rel = float(cfg["evaluation"]["reliable_min_note_s"])
        metrics, timing, lead_rows, profile_rows, intended_rows = [], [], [], [], []
        outputs: dict[tuple, dict] = {}

        for rec in test.itertuples():
            song = self.songs.loc[rec.song_id].to_dict()
            ref, f0 = self.reference(rec)
            d = raw_dir / rec.recording_id
            d.mkdir(parents=True, exist_ok=True)
            ref.to_csv(d / "reference_notes.csv", index=False, float_format="%.4f")
            if rec.kind == "isolated_vocal" and rec.reference_type == "notes_csv" and rec.song_id in self.refs:
                m = ev.evaluate(self.refs[rec.song_id], ref, self.duration(rec.song_id), cfg["evaluation"])
                intended_rows.append({"recording_id": rec.recording_id, "song_id": rec.song_id,
                                      "comparison": "sung annotation vs intended MIDI", **m})
            plot_preds = {}
            for method in self.methods_for(rec.kind):
                label = self.label(method)
                try:
                    res = self.run_method(rec, method, seg, bp, lead)
                except Exception as e:  # logged as a failed run, never silently dropped
                    self.log.error("%s failed on %s: %s: %s", label, rec.recording_id, type(e).__name__, e)
                    metrics.append({"recording_id": rec.recording_id, "song_id": rec.song_id, "kind": rec.kind,
                                    "method": label, "version": "raw", "error": f"{type(e).__name__}: {e}"})
                    continue
                tag = label.replace("+", "_")
                res["notes"].to_csv(d / f"{tag}_notes.csv", index=False, float_format="%.4f")
                if res["contour"] is not None:
                    res["contour_audio_time"].to_csv(d / f"{tag}_contour_audio_time.csv", index=False,
                                                     float_format="%.5f")
                if res["midi"] is not None:
                    res["midi"].write(str(d / f"{tag}_raw.mid"))
                    res["raw_notes"].to_csv(d / f"{tag}_raw_notes_audio_time.csv", index=False, float_format="%.4f")
                    lead_rows.append({"recording_id": rec.recording_id, "method": label, **res["lead_counts"]})
                m = self.evaluate(rec, res["notes"], res["contour"], ref, f0)
                flags = ev.quality_flags(m, cfg["flags"])
                metrics.append({"recording_id": rec.recording_id, "song_id": rec.song_id, "kind": rec.kind,
                                "method": label, "version": "raw", "diagnostic": METHODS[method]["diagnostic"],
                                "correction_minutes": np.nan, "quality_flag": ";".join(flags), **m})
                timing.append({"recording_id": rec.recording_id, "kind": rec.kind, "method": label,
                               "audio_s": self.duration(rec.song_id), **res["timing"]})
                profile_rows.append({"recording_id": rec.recording_id, **pf.profile_row(
                    song, res["notes"], rel, METHODS[method]["source_type"], label, "", flags, "raw")})
                outputs[(rec.recording_id, label)] = m
                plot_preds[label] = (res["notes"], res["contour"])

                for c in self.corrections[(self.corrections["recording_id"] == rec.recording_id)
                                          & (self.corrections["method"] == label)].itertuples():
                    corrected = (rf.shift_notes(rf.read_notes_csv(c.corrected_abs), rec.audio_offset_s,
                                                self.duration(rec.song_id)) if c.corrected_abs else res["notes"])
                    mc = self.evaluate(rec, corrected, None, ref, f0)
                    fc = ev.quality_flags(mc, cfg["flags"])
                    metrics.append({"recording_id": rec.recording_id, "song_id": rec.song_id, "kind": rec.kind,
                                    "method": label, "version": "corrected",
                                    "diagnostic": METHODS[method]["diagnostic"],
                                    "correction_minutes": c.correction_minutes, "reviewer": c.reviewer,
                                    "quality_flag": ";".join(fc), **mc})
                    profile_rows.append({"recording_id": rec.recording_id, **pf.profile_row(
                        song, corrected, rel, METHODS[method]["source_type"], label, c.reviewer, fc, "corrected")})
                    plot_preds[f"{label} (corrected)"] = (corrected, None)
            plots.piano_roll(ref, plot_preds, f"{rec.recording_id} ({rec.kind}, {rec.song_id})",
                             plot_dir / f"{rec.recording_id}.png")
            self.log.info("test %s done", rec.recording_id)

        per = pd.DataFrame(metrics)
        per.to_csv(self.out / "per_recording_metrics.csv", index=False)
        ok = per[per["error"].isna()] if "error" in per else per
        tim = pd.DataFrame(timing)
        tim.to_csv(self.out / "timing.csv", index=False)
        pd.DataFrame(lead_rows).to_csv(self.out / "lead_line_selection.csv", index=False)
        pd.DataFrame(intended_rows).to_csv(self.out / "intended_vs_sung.csv", index=False)
        ref_profiles = [pf.profile_row(self.songs.loc[s].to_dict(), self.refs[s], rel, "reference",
                                       "reference", self.songs.loc[s, "verified_by"], [], "reference")
                        for s in sorted(set(test["song_id"]))]
        pd.DataFrame([{"recording_id": "", **p} for p in ref_profiles] + profile_rows).to_csv(
            self.out / "all_profiles.csv", index=False)

        agg = (ok.groupby(["method", "kind", "version"], sort=False)
               .agg(n=("recording_id", "count"), frame_accuracy=("frame_accuracy", "mean"),
                    note_f1=("note_f1", "mean"), note_f1_with_offset=("note_f1_with_offset", "mean"),
                    octave_error_rate=("octave_error_rate", "mean"), low_error_st=("low_error_st", "mean"),
                    high_error_st=("high_error_st", "mean"), p10_error_st=("p10_error_st", "mean"),
                    p90_error_st=("p90_error_st", "mean"), correction_minutes=("correction_minutes", "mean"))
               .reset_index()) if len(ok) else pd.DataFrame()
        agg.to_csv(self.out / "aggregate_metrics.csv", index=False)
        targets = {f"{r.method} | {r.kind}": ev.target_check(
            ok[(ok["method"] == r.method) & (ok["kind"] == r.kind) & (ok["version"] == "raw")], cfg["pilot_target"])
            for r in agg[agg["version"] == "raw"].itertuples()} if len(agg) else {}
        results_table = pd.DataFrame([{
            "Method or condition": f"{r.method} on {r.kind}" + (" (corrected)" if r.version == "corrected" else ""),
            "Frame accuracy": r.frame_accuracy, "Note F1": r.note_f1, "Correction min": r.correction_minutes,
            "n": r.n} for r in agg.itertuples()]) if len(agg) else pd.DataFrame()
        results_table.to_csv(self.out / "results_table.csv", index=False)

        sep = self.separation_comparison(test, outputs)
        sep.to_csv(self.out / "separation_comparison.csv", index=False)
        cost = self.cost_summary(tim)
        cost.to_csv(self.out / "cost_summary.csv", index=False)
        plots.method_summary(agg[agg["version"] == "raw"] if len(agg) else agg, cfg["pilot_target"],
                             self.out / "method_summary.png")
        summary = {"synthetic_data": self.synthetic, "test_recordings": test["recording_id"].tolist(),
                   "test_songs": sorted(set(test["song_id"])), "pilot_targets": targets,
                   "failed_runs": int(per["error"].notna().sum()) if "error" in per else 0}
        io_utils.write_json(self.out / "summary.json", summary)
        self.environment({"test_recordings": test["recording_id"].tolist()})
        (self.out / "report_summary.md").write_text(
            self.report_markdown(test, results_table, targets, ok, sep, cost, pd.DataFrame(intended_rows)),
            encoding="utf-8")
        self.log.info("Test complete. Outputs in %s", self.out)

    def separation_comparison(self, test: pd.DataFrame, outputs: dict) -> pd.DataFrame:
        """Each mix against its paired isolated vocal: what separation costs in accuracy."""
        d = self.cfg["pitch"]["detector"]
        rows = []
        for rec in test[test["kind"] == "mix"].itertuples():
            iso = outputs.get((rec.paired_with, d))
            for label in (f"demucs+{d}", f"{d}_mix"):
                mix = outputs.get((rec.recording_id, label))
                if iso is None or mix is None:
                    continue
                drop = iso["frame_accuracy"] - mix["frame_accuracy"]
                rows.append({"mix_id": rec.recording_id, "isolated_id": rec.paired_with, "method": label,
                             "isolated_frame_accuracy": iso["frame_accuracy"],
                             "mix_frame_accuracy": mix["frame_accuracy"], "frame_accuracy_drop": drop,
                             "isolated_note_f1": iso["note_f1"], "mix_note_f1": mix["note_f1"],
                             "note_f1_drop": iso["note_f1"] - mix["note_f1"],
                             "flag": "separation_loss" if drop > self.cfg["flags"]["separation_loss"] else ""})
        return pd.DataFrame(rows)

    def cost_summary(self, tim: pd.DataFrame) -> pd.DataFrame:
        """One-time preprocessing of the catalog versus repeating the analysis on demand."""
        if tim.empty:
            return pd.DataFrame()
        loads = {"basic_pitch": self._bp.load_time_s if self._bp else 0.0,
                 "demucs": self._demucs.load_time_s if self._demucs else 0.0}
        n_songs = int((~self.catalog["excluded"]).sum())
        rows = []
        for (method, kind), g in tim.groupby(["method", "kind"], sort=False):
            per = float(g["total_s"].mean())
            load = (loads["demucs"] if "demucs" in method else 0.0) + (loads["basic_pitch"] if "basic_pitch" in method else 0.0)
            rows.append({"method": method, "kind": kind, "n": len(g), "mean_s_per_excerpt": per,
                         "real_time_factor": float((g["total_s"] / g["audio_s"]).mean()),
                         "mean_separation_s": float(g["separation_s"].mean()),
                         "mean_pitch_s": float(g["pitch_s"].mean()), "model_load_s": load,
                         "one_time_catalog_s": load + per * n_songs, "catalog_songs": n_songs,
                         "on_demand_s_per_request_warm": per, "on_demand_s_per_request_cold": per + load})
        return pd.DataFrame(rows)

    def report_markdown(self, test, table, targets, per, sep, cost, intended) -> str:
        lines = ["# E3 test run summary", ""]
        if self.synthetic:
            lines += ["> **SYNTHETIC DATA** - these numbers test the code path only and are not evidence.", ""]
        counts = test.groupby("kind")["recording_id"].count().to_dict()
        lines += [f"Held-out songs: {', '.join(sorted(set(test['song_id'])))}; recordings by kind: {counts}.",
                  "Profiles describe excerpts only. The 10th-90th percentile band is a melody concentration "
                  "proxy, not a singer comfort range. Pilot targets justify further testing only.", "",
                  "## Results table (report section)", "", md_table(table) if len(table) else "No results.", "",
                  "## Pilot targets on clean test excerpts (raw outputs)", ""]
        for name, t in targets.items():
            if not t.get("n_excerpts"):
                continue
            lines.append(f"- **{name}** (n={t['n_excerpts']}): frame accuracy {t['mean_frame_accuracy']:.3f} "
                         f"({'met' if t['frame_accuracy_met'] else 'NOT met'}), note F1 {t['mean_note_f1']:.3f} "
                         f"({'met' if t['note_f1_met'] else 'NOT met'}), worst endpoint error "
                         f"{t['worst_endpoint_error_st']:.1f} st "
                         f"({'met' if t['range_endpoints_met'] else 'NOT met'})")
        cols = ["recording_id", "method", "version", "frame_accuracy", "note_f1", "octave_error_rate",
                "low_error_st", "high_error_st", "quality_flag"]
        lines += ["", "## Per recording", "", md_table(per[[c for c in cols if c in per]]) if len(per) else "", ""]
        if len(sep):
            lines += ["## Separation: mix vs paired isolated vocal", "", md_table(sep), ""]
        if len(intended):
            lines += ["## Sung annotation vs intended MIDI (reported separately)", "",
                      md_table(intended[["recording_id", "frame_accuracy", "note_f1", "low_error_st",
                                         "high_error_st"]]), ""]
        if len(cost):
            lines += ["## Cost: one-time preprocessing vs on demand", "", md_table(cost), ""]
        lines += ["Listen to `stems/` for separation artifacts, backing vocals and residual instruments, and "
                  "inspect `plots/` for octave mistakes and fragmented notes before writing the conclusion.", ""]
        return "\n".join(lines)

    def catalog(self) -> None:
        """Handoff catalog from each song's verified melody: verified_notes_path when given
        (for example a reviewer-corrected transcription), otherwise the verified MIDI lead track."""
        self.load(need_recordings=False)
        rel = float(self.cfg["evaluation"]["reliable_min_note_s"])
        d = self.out / "catalog"
        d.mkdir(exist_ok=True)
        prof, notes_rows, hist_rows = [], [], []
        for s in self.catalog[~self.catalog["excluded"]].itertuples():
            song = self.songs.loc[s.song_id].to_dict()
            if s.verified_notes_abs:
                notes, method = rf.read_notes_csv(s.verified_notes_abs), "verified_notes"
            else:
                notes, method = self.refs[s.song_id], "midi_reference"
            flags = [] if s.verified_by else ["unverified"]
            if rf.overlap_count(notes):
                flags.append("overlapping_notes")
            prof.append(pf.profile_row(song, notes, rel, s.source_type, method, s.verified_by, flags,
                                       self.cfg["catalog"]["profile_version"]))
            notes_rows.append(notes.assign(song_id=s.song_id))
            hist_rows.append(pf.histogram(notes).assign(song_id=s.song_id))
            if flags:
                self.log.warning("%s profile flags: %s", s.song_id, flags)
        profiles = pd.DataFrame(prof)
        profiles[pf.PROFILE_FIELDS + ["profile_version"]].to_csv(d / "song_profiles.csv", index=False)
        profiles.to_csv(d / "song_profile_details.csv", index=False)
        pd.concat(notes_rows)[["song_id", *rf.NOTE_COLUMNS]].to_csv(d / "melody_notes.csv", index=False,
                                                                     float_format="%.4f")
        pd.concat(hist_rows)[["song_id", "midi_note", "note_name", "seconds", "fraction"]].to_csv(
            d / "pitch_histogram.csv", index=False, float_format="%.4f")
        self.environment({"songs": profiles["song_id"].tolist()})
        self.log.info("Catalog written to %s (%d songs). MIDI 60 = C4; key and bpm describe the music, "
                      "not vocal range.", d, len(profiles))
