"""Figures: per-excerpt piano rolls (reference vs methods) and the method summary."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def piano_roll(ref: pd.DataFrame, preds: dict[str, tuple[pd.DataFrame, pd.DataFrame | None]],
               title: str, path: Path, ignore: np.ndarray | None = None) -> None:
    """One panel per method: reference notes in grey, predicted notes in colour, contour as a line,
    and spans left out of scoring shaded."""
    n = max(len(preds), 1)
    fig, axes = plt.subplots(n, 1, figsize=(12, 2.4 * n), sharex=True, squeeze=False)
    pitches = [ref["midi_note"]] + [p["midi_note"] for p, _ in preds.values() if not p.empty]
    allp = pd.concat(pitches) if pitches else pd.Series([60.0])
    lo, hi = (allp.min() - 3, allp.max() + 3) if len(allp) else (48, 84)
    for ax, (label, (notes, contour)) in zip(axes[:, 0], preds.items()):
        for s, e in (ignore if ignore is not None else []):
            ax.axvspan(s, e, color="tab:orange", alpha=0.12, lw=0)
        for r in ref.itertuples():
            ax.add_patch(plt.Rectangle((r.start_s, r.midi_note - 0.45), r.end_s - r.start_s, 0.9,
                                       color="0.75", lw=0))
        for r in notes.itertuples():
            ax.add_patch(plt.Rectangle((r.start_s, r.midi_note - 0.3), r.end_s - r.start_s, 0.6,
                                       color="tab:blue", alpha=0.8, lw=0))
        if contour is not None and len(contour):
            ax.plot(contour["time_s"], contour["midi"], color="tab:red", lw=0.7)
        ax.set_ylim(max(lo, 0), min(hi, 127))
        ax.set_ylabel("MIDI")
        ax.set_title(label, fontsize=9, loc="left")
    axes[-1, 0].set_xlabel("excerpt time (s)")
    end = max([ref["end_s"].max() if len(ref) else 1.0] +
              [p["end_s"].max() for p, _ in preds.values() if not p.empty])
    axes[-1, 0].set_xlim(0, end)
    key = "grey = reference, blue = notes, red = contour" + (", orange = not scored" if ignore is not None else "")
    fig.suptitle(f"{title}  ({key})", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def method_summary(agg: pd.DataFrame, targets: dict, path: Path) -> None:
    if agg.empty:
        return
    labels = agg["method"] + "\n" + agg["kind"] + "\n" + agg["version"]
    x = np.arange(len(agg))
    fig, ax = plt.subplots(figsize=(max(7, 1.3 * len(agg)), 4.5))
    ax.bar(x - 0.2, agg["frame_accuracy"], 0.4, label="frame accuracy")
    ax.bar(x + 0.2, agg["note_f1"], 0.4, label="note F1")
    ax.axhline(targets["min_frame_accuracy"], color="tab:blue", ls="--", lw=0.8)
    ax.axhline(targets["min_note_f1"], color="tab:orange", ls="--", lw=0.8)
    ax.set_xticks(x, labels, fontsize=7)
    ax.set_ylim(0, 1)
    ax.set_title("Held-out test excerpts (dashed = provisional pilot targets)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
