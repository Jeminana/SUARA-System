"""E6 stages.

check : validate the manifest, preprocess and write quality-control logs.
dev   : M01 only. Compare candidate settings (ECAPA whole vs windows, MFCC c0/scaling)
        to choose the configuration before locking.
test  : locked run. Embeddings, handoff files, similarity, retrieval, stress, timing.
"""
from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf
import torch

from . import audio, evaluation as ev, io_utils, manifest as mf, plots
from .models import SAMPLE_RATE, EcapaEmbedder, MfccEmbedder


def md_table(df: pd.DataFrame) -> str:
    def fmt(v):
        return f"{v:.4f}" if isinstance(v, float) else str(v)
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    rule = "|" + "---|" * len(df.columns)
    body = ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([head, rule, *body])


class Run:
    def __init__(self, config_path: Path, stage: str, run_name: str | None, synthetic: bool):
        self.config_path = config_path.resolve()
        self.cfg = io_utils.load_config(config_path)
        self.base = self.config_path.parent
        self.stage = stage
        self.synthetic = synthetic
        name = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.out = self.path(self.cfg["paths"]["output_root"]) / f"{name}_{stage}"
        self.out.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.config_path, self.out / "config_used.yaml")
        self.log = io_utils.setup_logging(self.out)
        self.seed = int(self.cfg["seed"])
        np.random.seed(self.seed)
        torch.manual_seed(self.seed)
        self.window_rows: list[dict] = []
        if synthetic:
            self.log.warning("SYNTHETIC DATA MODE: outputs test the code only and are not experimental evidence.")

    def path(self, p: str) -> Path:
        p = Path(p)
        return p if p.is_absolute() else self.base / p

    # ------------------------------------------------------------------ data
    def load_manifest(self) -> pd.DataFrame:
        accepted = list(self.cfg["consent"]["accepted_values"]) + (["synthetic"] if self.synthetic else [])
        df = mf.load_manifest(self.path(self.cfg["paths"]["manifest"]),
                              self.path(self.cfg["paths"]["audio_root"]), accepted)
        df = mf.assign_splits(df, self.cfg["splits"])
        excl = df[df["excluded"]]
        excl[["recording_id", "exclusion_reason"]].to_csv(self.out / "exclusions.csv", index=False)
        self.log.info("Manifest: %d rows, %d excluded, splits %s", len(df), len(excl),
                      df.loc[~df["excluded"], "split"].value_counts().to_dict())
        return df

    def preprocess(self, rows: pd.DataFrame) -> tuple[dict[str, np.ndarray], dict[str, list[str]]]:
        pp = self.cfg["preprocessing"]
        wav_dir = self.out / "preprocessed"
        wav_dir.mkdir(exist_ok=True)
        clips, flags, log_rows = {}, {}, []
        for r in rows.itertuples():
            y_raw, sr0 = audio.load_mono(r.abs_path)
            y = audio.resample(y_raw, sr0, SAMPLE_RATE, pp["resample_type"])
            qc = audio.quality_metrics(y, SAMPLE_RATE, pp["qc"])
            start, end = 0, len(y)
            if pp["trim_edges"]:
                y, start, end = audio.trim_edges(y, pp["trim_top_db"])
            y, gain = audio.apply_gain(y, pp["gain"]["mode"], pp["gain"]["target_dbfs"])
            f = audio.qc_flags(qc, pp["qc"])
            sf.write(wav_dir / f"{r.recording_id}.wav", y, SAMPLE_RATE, subtype="FLOAT")
            clips[r.recording_id], flags[r.recording_id] = y, f
            log_rows.append({"recording_id": r.recording_id, "source_sr": sr0,
                             "manifest_duration_s": r.duration_s, **qc,
                             "trim_start_s": start / SAMPLE_RATE, "trim_end_s": end / SAMPLE_RATE,
                             "processed_duration_s": len(y) / SAMPLE_RATE, "gain": gain,
                             "qc_flags": ";".join(f)})
        pd.DataFrame(log_rows).to_csv(self.out / "preprocessing_log.csv", index=False)
        flagged = {k: v for k, v in flags.items() if v}
        if flagged:
            self.log.warning("QC flags (review, then set excluded in the manifest if needed): %s", flagged)
        return clips, flags

    # ------------------------------------------------------------ embedding
    def embed_raw(self, model, y: np.ndarray, rid: str, ecapa_cfg: dict, log_windows: bool = True) -> np.ndarray:
        if model.name == "ecapa" and ecapa_cfg["segmentation"] == "windows":
            wins = audio.fixed_windows(y, SAMPLE_RATE, ecapa_cfg["window_s"],
                                       ecapa_cfg["min_active_ratio"], self.cfg["activity"])
            if log_windows:
                self.window_rows += [{"recording_id": rid, **{k: w[k] for k in
                                      ("start_s", "end_s", "active_ratio", "accepted", "rule")}} for w in wins]
            accepted = [w for w in wins if w["accepted"]]
            if not accepted:
                raise ValueError("no window passed the activity rule")
            W = np.vstack([model.embed(y[w["start"]:w["end"]]) for w in accepted])
            return ev.aggregate_windows(W)
        return model.embed(y)

    def extract(self, model, clips: dict[str, np.ndarray], ecapa_cfg: dict) -> tuple[dict, dict, dict]:
        vecs, errors, seconds = {}, {}, {}
        for rid, y in clips.items():
            t0 = time.perf_counter()
            try:
                vecs[rid] = self.embed_raw(model, y, rid, ecapa_cfg)
            except Exception as e:  # logged as a failed vector, never silently dropped
                errors[rid] = f"{type(e).__name__}: {e}"
                self.log.error("%s embedding failed for %s: %s", model.name, rid, errors[rid])
            seconds[rid] = time.perf_counter() - t0
        return vecs, errors, seconds

    def finalize(self, model, meta: pd.DataFrame, vecs: dict, errors: dict) -> tuple[pd.DataFrame, np.ndarray]:
        """Apply frozen scaling and L2 normalisation; zero-norm / non-finite vectors become errors."""
        meta = meta[meta["recording_id"].isin(vecs)].reset_index(drop=True)
        X = model.postprocess(np.vstack([vecs[r] for r in meta["recording_id"]]))
        Xn, ok = ev.l2_normalize(X)
        for rid in meta.loc[~ok, "recording_id"]:
            errors[rid] = "zero-norm or non-finite vector"
            self.log.error("%s vector invalid for %s", model.name, rid)
        return meta[ok].reset_index(drop=True), Xn[ok]

    def load_models(self) -> list:
        mcfg, models = self.cfg["models"], []
        if mcfg["ecapa"]["enabled"]:
            models.append(EcapaEmbedder(mcfg["ecapa"], self.path(self.cfg["paths"]["model_cache"]), self.log))
        if mcfg["mfcc"]["enabled"]:
            models.append(MfccEmbedder(mcfg["mfcc"]))
        return models

    def fit_mfcc_scaler(self, model, dev_rows: pd.DataFrame, clips: dict) -> None:
        if model.name != "mfcc" or model.cfg["scaling"] == "none":
            return
        if dev_rows.empty:
            raise RuntimeError("MFCC z-score scaling needs dev (M01) clips to fit statistics")
        model.fit_scaler(np.vstack([model.embed(clips[r]) for r in dev_rows["recording_id"]]))
        self.log.info("MFCC scaler fitted on %d dev clips", len(dev_rows))

    # ---------------------------------------------------------------- stages
    def check(self) -> None:
        df = self.load_manifest()
        self.preprocess(df[~df["excluded"]])
        self.log.info("Check complete: review preprocessing_log.csv and listen to preprocessed/ clips.")

    def dev(self) -> None:
        df = self.load_manifest()
        dev_cfg = self.cfg["splits"]["dev"]
        dev = df[~df["excluded"] & (df["condition"] == "original") & (df["split"] == "dev")].reset_index(drop=True)
        if dev.empty:
            raise SystemExit("No dev recordings found.")
        clips, _ = self.preprocess(dev)
        top_k = self.cfg["evaluation"]["top_k"]
        rows = []

        def evaluate(label: str, model, settings: dict) -> None:
            vecs, errors, _ = self.extract(model, clips, settings.get("ecapa", self.cfg["models"]["ecapa"]))
            meta, Xn = self.finalize(model, dev, vecs, errors)
            enroll = (meta["take"] == dev_cfg["enroll_take"]).values
            singers, P = ev.build_profiles(meta[enroll], Xn[enroll])
            res = ev.retrieve(meta[~enroll], Xn[~enroll], singers, P, "dev_same_melody", top_k)
            summ = ev.summarize_retrieval(res, len(singers), top_k)
            pairs = ev.pair_table(meta, Xn)
            same = pairs.loc[pairs["category"] == "same_singer_same_melody", "cosine_similarity"].mean()
            diff = pairs.loc[pairs["category"] == "diff_singer_same_melody", "cosine_similarity"].mean()
            rows.append({"candidate": label, **{k: v for k, v in settings.items() if k != "ecapa"},
                         **summ, "same_singer_same_melody_mean": same,
                         "diff_singer_same_melody_mean": diff, "dev_gap": same - diff,
                         "failed_vectors": len(errors)})
            self.log.info("dev %-28s top1 %d/%d gap %.4f", label, summ["top1_correct"], summ["n_queries"], same - diff)

        for model in self.load_models():
            if model.name == "ecapa":
                for seg in ("whole", "windows"):
                    ecfg = {**self.cfg["models"]["ecapa"], "segmentation": seg}
                    evaluate(f"ecapa_{seg}", model, {"segmentation": seg, "ecapa": ecfg})
            else:
                base = dict(self.cfg["models"]["mfcc"])
                for c0 in (False, True):
                    for scaling in ("none", "zscore"):
                        cand = MfccEmbedder({**base, "include_c0": c0, "scaling": scaling})
                        self.fit_mfcc_scaler(cand, dev, clips)
                        evaluate(f"mfcc_c0-{c0}_{scaling}", cand, {"include_c0": c0, "scaling": scaling})

        pd.DataFrame(rows).to_csv(self.out / "dev_candidates.csv", index=False)
        pd.DataFrame(self.window_rows).to_csv(self.out / "window_log.csv", index=False)
        io_utils.write_json(self.out / "environment.json",
                            io_utils.environment_record(self.config_path, self.cfg, {"stage": "dev"}))
        self.log.info("Dev results are in-sample on M01 and only guide the choice. Update config.yaml, "
                      "set locked: true, then run the test stage.")

    def test(self) -> None:
        if not self.cfg.get("locked"):
            raise SystemExit("config.yaml is not locked. Finish dev choices, set locked: true, then rerun.")
        cfg, top_k = self.cfg, self.cfg["evaluation"]["top_k"]
        df = self.load_manifest()
        usable = df[~df["excluded"] & (df["split"] != "unused")].reset_index(drop=True)
        originals = usable[usable["condition"] == "original"].reset_index(drop=True)
        variants = usable[usable["condition"] != "original"].reset_index(drop=True)
        mf.check_no_leakage(originals[originals["split"] == "enroll"],
                            usable[usable["split"].isin(["query", "same_melody"])])
        clips, qc_flags = self.preprocess(usable)

        summaries, stress_frames, timing_rows, all_errors = {}, [], [], []
        env_extra = {"stage": "test", "models": {}}
        for model in self.load_models():
            mdir = self.out / model.name
            mdir.mkdir(exist_ok=True)
            self.fit_mfcc_scaler(model, originals[originals["split"] == "dev"], clips)
            vecs, errors, seconds = self.extract(model, {r: clips[r] for r in originals["recording_id"]},
                                                 cfg["models"]["ecapa"])
            meta, Xn = self.finalize(model, originals, vecs, errors)
            all_errors += [{"model": model.name, "recording_id": k, "error": v} for k, v in errors.items()]
            env_extra["models"][model.name] = {"model_revision": model.model_revision,
                                               "load_time_s": model.load_time_s}
            if model.name == "mfcc":
                io_utils.write_json(mdir / "mfcc_scaler_dev_only.json", model.scaler_record())

            # Handoff to E7
            np.save(mdir / "embeddings.npy", Xn.astype(np.float32))
            handoff = pd.DataFrame({
                "recording_id": meta["recording_id"], "singer_id": meta["participant_id"],
                "melody_id": meta["melody_id"], "split": meta["split"],
                "model_revision": model.model_revision, "vector_index": np.arange(len(meta)),
                "quality_flag": [";".join(qc_flags[r]) or "ok" for r in meta["recording_id"]],
            })
            handoff.to_csv(mdir / "embedding_manifest.csv", index=False)
            sim = ev.similarity_frame(meta, Xn)
            sim.to_csv(mdir / "similarity.csv")

            pairs = ev.pair_table(meta, Xn)
            pairs.to_csv(mdir / "pairs.csv", index=False)
            sep = ev.separation_stats(pairs[pairs["scope"] == "test"])

            is_enroll = (meta["split"] == "enroll").values
            singers, P = ev.build_profiles(meta[is_enroll], Xn[is_enroll])
            results = []
            for task, split in (("cross_melody", "query"), ("same_melody", "same_melody")):
                mask = (meta["split"] == split).values
                results.append(ev.retrieve(meta[mask], Xn[mask], singers, P, task, top_k))
            retrieval = pd.concat(results, ignore_index=True)
            retrieval.to_csv(mdir / "retrieval_results.csv", index=False)
            cross = retrieval[retrieval["task"] == "cross_melody"]
            same = retrieval[retrieval["task"] == "same_melody"]
            cross_summary = ev.summarize_retrieval(cross, len(singers), top_k)
            singer_table = ev.per_singer(cross, top_k)
            singer_table.to_csv(mdir / "per_singer.csv", index=False)

            stress = self.stress(model, originals, variants, clips, singers, P, cross_summary,
                                 float(cross["true_score"].mean()))
            stress_frames.append(stress)
            timing_rows.append(self.timing(model, originals, clips, seconds))

            plots.similarity_heatmap(sim, f"{model.name} cosine similarity", mdir / "similarity_matrix.png")
            plots.pair_boxplot(pairs[pairs["scope"] == "test"], f"{model.name} pair similarity (test scope)",
                               mdir / "pair_categories.png")

            summaries[model.name] = {
                "model_revision": model.model_revision,
                "n_vectors": len(meta), "n_failed": len(errors), "n_profiles": len(singers),
                "cross_melody": cross_summary,
                "same_melody": ev.summarize_retrieval(same, len(singers), top_k),
                "separation": sep,
                "bootstrap_top1": ev.bootstrap_top1(cross, cfg["evaluation"]["bootstrap_resamples"], self.seed),
                "pilot_target": ev.pilot_target_check(cross_summary, sep["separation"], singer_table,
                                                      cfg["pilot_target"]),
                "per_singer": singer_table.to_dict(orient="records"),
            }
            self.log.info("%s cross melody top1 %d/%d top3 %d/%d separation %s", model.name,
                          cross_summary["top1_correct"], cross_summary["n_queries"],
                          cross_summary.get("top3_correct", 0), cross_summary["n_queries"], sep["separation"])

        stress_all = pd.concat(stress_frames, ignore_index=True) if stress_frames else pd.DataFrame()
        stress_all.to_csv(self.out / "stress_results.csv", index=False)
        plots.stress_bars(stress_all, self.out / "stress_results.png")
        pd.DataFrame(timing_rows).to_csv(self.out / "timing.csv", index=False)
        pd.DataFrame(all_errors, columns=["model", "recording_id", "error"]).to_csv(
            self.out / "embedding_errors.csv", index=False)
        pd.DataFrame(self.window_rows).to_csv(self.out / "window_log.csv", index=False)

        table = pd.DataFrame([{
            "method": name,
            "top1_count": f"{s['cross_melody']['top1_correct']}/{s['cross_melody']['n_queries']}",
            "top3_count": f"{s['cross_melody'].get('top3_correct')}/{s['cross_melody']['n_queries']}",
            "mean_gap": s["separation"]["separation"],
        } for name, s in summaries.items()])
        table.to_csv(self.out / "results_table.csv", index=False)
        io_utils.write_json(self.out / "summary.json", {"synthetic_data": self.synthetic, "models": summaries})
        io_utils.write_json(self.out / "environment.json",
                            io_utils.environment_record(self.config_path, cfg, env_extra))
        (self.out / "report_summary.md").write_text(
            self.report_markdown(summaries, table, stress_all, pd.DataFrame(timing_rows)), encoding="utf-8")
        self.log.info("Test complete. Outputs in %s", self.out)

    # ---------------------------------------------------------- test helpers
    def stress(self, model, originals, variants, clips, singers, P, clean_summary,
               clean_true_score: float) -> pd.DataFrame:
        """Perturb query clips only; enrollment profiles stay clean. Variants keep their parent's split."""
        scfg, pp, top_k = self.cfg["stress"], self.cfg["preprocessing"], self.cfg["evaluation"]["top_k"]
        queries = originals[originals["split"] == "query"].reset_index(drop=True)
        conditions = [(f"noise_snr{snr:g}dB", "noise", snr) for snr in scfg["noise_snr_db"]]
        conditions += [(f"crop_{sec:g}s", "crop", sec) for sec in scfg["crop_seconds"]]
        rows = [{"model": model.name, "condition": "clean", "n_queries": clean_summary["n_queries"],
                 **{f"top{k}_rate": clean_summary[f"top{k}_rate"] for k in top_k}, "n_failed": 0,
                 "mean_true_score": clean_true_score}]
        ecfg = self.cfg["models"]["ecapa"]

        def run(label: str, meta: pd.DataFrame, make_clip) -> None:
            vecs, errors = {}, {}
            for r in meta["recording_id"]:
                try:
                    y = make_clip(r)
                    y, _ = audio.apply_gain(y, pp["gain"]["mode"], pp["gain"]["target_dbfs"])
                    vecs[r] = self.embed_raw(model, y, r, ecfg, log_windows=False)
                except Exception as e:
                    errors[r] = str(e)
            if not vecs:
                rows.append({"model": model.name, "condition": label, "n_queries": 0, "n_failed": len(errors)})
                return
            m, Xn = self.finalize(model, meta, vecs, errors)
            res = ev.retrieve(m, Xn, singers, P, label, top_k)
            summ = ev.summarize_retrieval(res, len(singers), top_k)
            rows.append({"model": model.name, "condition": label, "n_queries": summ["n_queries"],
                         **{f"top{k}_rate": summ[f"top{k}_rate"] for k in top_k}, "n_failed": len(errors),
                         "mean_true_score": res["true_score"].mean()})

        for label, kind, value in conditions:
            if kind == "noise":
                run(label, queries, lambda r, v=value, lb=label: audio.add_white_noise(
                    clips[r], v, audio.stable_rng(self.seed, f"{r}|{lb}")))
            else:
                run(label, queries, lambda r, v=value: audio.centre_crop(clips[r], SAMPLE_RATE, v))
        if scfg["include_manifest_variants"] and not variants.empty:
            qv = variants[variants["split"] == "query"]
            for cond, group in qv.groupby("condition"):
                run(f"manifest_{cond}", group.reset_index(drop=True), lambda r: clips[r])
        return pd.DataFrame(rows)

    def timing(self, model, originals, clips, first_seconds: dict) -> dict:
        """Repeat extraction on query clips: seconds per clip and determinism (max abs difference)."""
        ecfg = self.cfg["models"]["ecapa"]
        rids = originals.loc[originals["split"] == "query", "recording_id"].tolist()
        per_clip, max_diff, reference = [], 0.0, {}
        for _ in range(int(self.cfg["runtime"]["timing_repeats"])):
            for r in rids:
                t0 = time.perf_counter()
                try:
                    v = self.embed_raw(model, clips[r], r, ecfg, log_windows=False)
                except Exception:
                    continue
                per_clip.append(time.perf_counter() - t0)
                if r in reference:
                    max_diff = max(max_diff, float(np.max(np.abs(v - reference[r]))))
                else:
                    reference[r] = v
        audio_s = sum(len(clips[r]) for r in rids) / SAMPLE_RATE
        return {"model": model.name, "load_time_s": model.load_time_s,
                "first_pass_mean_s_per_clip": float(np.mean(list(first_seconds.values()))),
                "repeat_mean_s_per_clip": float(np.mean(per_clip)) if per_clip else None,
                "repeat_clips_timed": len(per_clip), "query_audio_s": audio_s,
                "repeat_max_abs_diff": max_diff,
                "device": getattr(model, "device", "cpu")}

    def report_markdown(self, summaries, table, stress, timing) -> str:
        lines = ["# E6 test run summary", ""]
        if self.synthetic:
            lines += ["> **SYNTHETIC DATA** - these numbers test the code path only and are not evidence.", ""]
        n_queries = max((s["cross_melody"]["n_queries"] for s in summaries.values()), default=0)
        lines += ["Cosine similarity values are similarities, not probabilities or artist match percentages.",
                  f"{n_queries} cross melody queries is small-sample evidence; the bootstrap interval is exploratory.", "",
                  "## Results table", "", md_table(table), ""]
        for name, s in summaries.items():
            cm, sep, pt, bs = s["cross_melody"], s["separation"], s["pilot_target"], s["bootstrap_top1"]
            lines += [f"## {name}", "", f"- Model revision: `{s['model_revision']}`",
                      f"- Vectors: {s['n_vectors']} (failed: {s['n_failed']}), profiles: {s['n_profiles']}",
                      f"- Cross melody top 1: {cm['top1_correct']}/{cm['n_queries']} "
                      f"(chance {cm['top1_chance']:.3f})" if cm["n_queries"] else "- No cross melody queries",
                      f"- Cross melody top 3: {cm.get('top3_correct')}/{cm['n_queries']}"
                      + (f" (chance {cm['top3_chance']:.3f})" if cm.get("top3_chance") is not None else ""),
                      f"- Same melody top 1 (M02 T02): {s['same_melody']['top1_correct']}/{s['same_melody']['n_queries']}",
                      f"- Similarity separation (test scope): {sep['separation']}",
                      f"  - same singer / different melody mean: {sep['same_singer_diff_melody_mean']} (n={sep['same_singer_diff_melody_n']})",
                      f"  - different singer / same melody mean: {sep['diff_singer_same_melody_mean']} (n={sep['diff_singer_same_melody_n']})",
                      f"  - different singer / different melody mean: {sep['diff_singer_diff_melody_mean']} (n={sep['diff_singer_diff_melody_n']})",
                      f"- Exploratory top 1 interval: {bs['low']} - {bs['high']}",
                      f"- Pilot target: top1 {'met' if pt['top1_met'] else 'NOT met'}, separation "
                      f"{'met' if pt['separation_met'] else 'NOT met'}, singers with zero top 1: "
                      f"{pt['singers_with_zero_top1'] or 'none'} (largest single-singer failure share "
                      f"{pt['largest_single_singer_failure_share']:.2f})", "",
                      md_table(pd.DataFrame(s["per_singer"])), ""]
        if not stress.empty:
            lines += ["## Stress tests (query clips only)", "", md_table(stress), ""]
        lines += ["## Runtime", "", md_table(timing), ""]
        return "\n".join(lines)
