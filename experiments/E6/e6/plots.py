"""Figures: similarity matrix, pair category distributions and stress results."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from .evaluation import PAIR_CATEGORIES  # noqa: E402


def similarity_heatmap(sim: pd.DataFrame, title: str, path: Path) -> None:
    order = sorted(sim.index, key=lambda rid: (rid.split("_")[0], rid.split("_")[1:]))
    sim = sim.loc[order, order]
    n = len(sim)
    fig, ax = plt.subplots(figsize=(max(6, n * 0.28), max(5, n * 0.26)))
    im = ax.imshow(sim.values, cmap="viridis", vmin=min(0.0, sim.values.min()), vmax=1.0)
    ax.set_xticks(range(n), sim.columns, rotation=90, fontsize=6)
    ax.set_yticks(range(n), sim.index, fontsize=6)
    ax.set_title(title)
    fig.colorbar(im, ax=ax, label="cosine similarity (not a probability)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def pair_boxplot(pairs: pd.DataFrame, title: str, path: Path) -> None:
    cats = [c for c in PAIR_CATEGORIES if (pairs["category"] == c).any()]
    data = [pairs.loc[pairs["category"] == c, "cosine_similarity"].values for c in cats]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.boxplot(data, showmeans=True)
    ax.set_xticks(range(1, len(cats) + 1), [c.replace("_", "\n") for c in cats], fontsize=8)
    ax.set_ylabel("cosine similarity")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def stress_bars(stress: pd.DataFrame, path: Path) -> None:
    if stress.empty:
        return
    pivot = stress.pivot(index="condition", columns="model", values="top1_rate")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    pivot.plot.bar(ax=ax)
    ax.set_ylabel("top 1 rate")
    ax.set_ylim(0, 1)
    ax.set_title("Cross melody top 1 under stress conditions")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
