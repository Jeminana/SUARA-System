"""Normalisation, cosine similarity, pair statistics, enrollment/retrieval and bootstrap.

Cosine similarity = dot(a, b) / (||a|| * ||b||). It is a similarity value, not a
probability or an artist match percentage.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PAIR_CATEGORIES = ["same_singer_same_melody", "same_singer_diff_melody",
                   "diff_singer_same_melody", "diff_singer_diff_melody"]


def l2_normalize(X: np.ndarray, eps: float = 1e-10) -> tuple[np.ndarray, np.ndarray]:
    """Returns (normalised rows, ok mask). Zero-norm or non-finite rows are marked failed."""
    X = np.atleast_2d(np.asarray(X, dtype=np.float64))
    norms = np.linalg.norm(X, axis=1)
    ok = np.isfinite(X).all(axis=1) & np.isfinite(norms) & (norms > eps)
    Xn = np.zeros_like(X)
    Xn[ok] = X[ok] / norms[ok, None]
    return Xn, ok


def aggregate_windows(W: np.ndarray) -> np.ndarray:
    """Normalise each window embedding, average, then normalise the aggregate."""
    Wn, ok = l2_normalize(W)
    if not ok.any():
        raise ValueError("all window embeddings failed")
    mean = Wn[ok].mean(axis=0)
    agg, ok_agg = l2_normalize(mean)
    if not ok_agg[0]:
        raise ValueError("aggregate embedding has zero norm")
    return agg[0]


def similarity_frame(meta: pd.DataFrame, Xn: np.ndarray) -> pd.DataFrame:
    S = Xn @ Xn.T
    return pd.DataFrame(S, index=meta["recording_id"], columns=meta["recording_id"])


def pair_table(meta: pd.DataFrame, Xn: np.ndarray) -> pd.DataFrame:
    S = Xn @ Xn.T
    m = meta.reset_index(drop=True)
    i, j = np.triu_indices(len(m), k=1)
    same_singer = m["participant_id"].values[i] == m["participant_id"].values[j]
    same_melody = m["melody_id"].values[i] == m["melody_id"].values[j]
    category = np.where(same_singer, np.where(same_melody, PAIR_CATEGORIES[0], PAIR_CATEGORIES[1]),
                        np.where(same_melody, PAIR_CATEGORIES[2], PAIR_CATEGORIES[3]))
    involves_dev = (m["split"].values[i] == "dev") | (m["split"].values[j] == "dev")
    return pd.DataFrame({
        "recording_a": m["recording_id"].values[i], "recording_b": m["recording_id"].values[j],
        "singer_a": m["participant_id"].values[i], "singer_b": m["participant_id"].values[j],
        "melody_a": m["melody_id"].values[i], "melody_b": m["melody_id"].values[j],
        "category": category, "scope": np.where(involves_dev, "dev", "test"),
        "cosine_similarity": S[i, j],
    })


def separation_stats(pairs: pd.DataFrame) -> dict:
    """Mean same-singer/different-melody minus mean different-singer/same-melody similarity."""
    stats = {}
    for cat in PAIR_CATEGORIES:
        v = pairs.loc[pairs["category"] == cat, "cosine_similarity"]
        stats[f"{cat}_mean"] = float(v.mean()) if len(v) else None
        stats[f"{cat}_n"] = int(len(v))
    a, b = stats["same_singer_diff_melody_mean"], stats["diff_singer_same_melody_mean"]
    stats["separation"] = a - b if a is not None and b is not None else None
    return stats


def build_profiles(meta: pd.DataFrame, Xn: np.ndarray) -> tuple[list[str], np.ndarray]:
    """One enrollment profile per singer: mean of normalised vectors, renormalised."""
    singers = sorted(meta["participant_id"].unique())
    profiles = []
    for s in singers:
        mask = (meta["participant_id"] == s).values
        profiles.append(aggregate_windows(Xn[mask]))
    return singers, np.vstack(profiles)


def retrieve(query_meta: pd.DataFrame, Xq: np.ndarray, singers: list[str], P: np.ndarray,
             task: str, top_k: list[int]) -> pd.DataFrame:
    S = Xq @ P.T
    rows = []
    for q, (_, r) in enumerate(query_meta.reset_index(drop=True).iterrows()):
        order = np.argsort(-S[q], kind="stable")
        ranked = [singers[k] for k in order]
        true = r["participant_id"]
        true_idx = singers.index(true) if true in singers else None
        row = {
            "task": task, "condition": r.get("condition", "original"),
            "recording_id": r["recording_id"], "true_singer": true,
            "predicted_singer": ranked[0], "top1_score": float(S[q, order[0]]),
            "true_rank": ranked.index(true) + 1 if true_idx is not None else None,
            "true_score": float(S[q, true_idx]) if true_idx is not None else None,
            "ranking": ";".join(f"{singers[k]}:{S[q, k]:.4f}" for k in order),
        }
        if true_idx is not None:
            impostor = np.delete(S[q], true_idx)
            row["best_impostor_score"] = float(impostor.max()) if len(impostor) else None
            row["margin"] = row["true_score"] - row["best_impostor_score"] if len(impostor) else None
        for k in top_k:
            row[f"correct_top{k}"] = bool(row["true_rank"] is not None and row["true_rank"] <= k)
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_retrieval(res: pd.DataFrame, n_profiles: int, top_k: list[int]) -> dict:
    n = len(res)
    out = {"n_queries": n, "n_profiles": n_profiles}
    for k in top_k:
        c = int(res[f"correct_top{k}"].sum()) if n else 0
        out[f"top{k}_correct"] = c
        out[f"top{k}_rate"] = c / n if n else None
        out[f"top{k}_chance"] = min(k, n_profiles) / n_profiles if n_profiles else None
    return out


def per_singer(res: pd.DataFrame, top_k: list[int]) -> pd.DataFrame:
    agg = {"n_queries": ("recording_id", "count"), "mean_margin": ("margin", "mean")}
    for k in top_k:
        agg[f"top{k}_correct"] = (f"correct_top{k}", "sum")
    return res.groupby("true_singer").agg(**agg).reset_index()


def bootstrap_top1(res: pd.DataFrame, n_resamples: int, seed: int) -> dict:
    """Exploratory interval: resample participants (not queries), since a singer's queries are dependent."""
    g = res.groupby("true_singer")["correct_top1"].agg(["sum", "count"])
    if len(g) < 2:
        return {"low": None, "high": None, "n_resamples": 0}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(n_resamples, len(g)))
    acc = g["sum"].values[idx].sum(axis=1) / g["count"].values[idx].sum(axis=1)
    return {"low": float(np.percentile(acc, 2.5)), "high": float(np.percentile(acc, 97.5)),
            "n_resamples": n_resamples, "label": "exploratory participant-level bootstrap 95% interval"}


def pilot_target_check(summary: dict, sep: float | None, singers: pd.DataFrame, cfg: dict) -> dict:
    fully_failed = singers.loc[singers["top1_correct"] == 0, "true_singer"].tolist()
    failures = (singers["n_queries"] - singers["top1_correct"])
    worst_share = float(failures.max() / failures.sum()) if failures.sum() else 0.0
    checks = {
        "top1_met": summary["top1_correct"] >= cfg["min_top1_correct"],
        "separation_met": (sep is not None and sep > 0) or not cfg["require_positive_separation"],
        "no_singer_fully_failed": not fully_failed,
    }
    return {
        **checks,
        "all_met": all(checks.values()),
        "singers_with_zero_top1": fully_failed,
        "largest_single_singer_failure_share": worst_share,
        "query_count_matches_design": summary["n_queries"] == cfg["expected_queries"],
        "note": "Provisional small-sample target; failure concentration needs human review.",
    }
