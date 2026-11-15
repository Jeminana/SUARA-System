"""Compare the T08 recommender with the T12 naive baseline on the E3 catalog.

    main_pipeline/.venv/bin/python main_pipeline/tools/compare_recommender_baseline.py

Voice profiles are the synthetic T12 fixtures (evaluation/fixtures/voice_profiles.json);
the baseline is evaluation/scripts/metrics.py:naive_rank_contract (range coverage).
No listener judgments exist, so this shows how the two rules order songs, not which
order suits a singer. Prints a Markdown report to stdout.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from suara.catalog import load_song_catalog
from suara.contracts import PitchFeatures, TimbreFeatures, VoiceProfile
from suara.recommender import SCORING_VERSION, hz_to_midi, note_name, recommend_songs

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "experiments" / "E3" / "handoff" / "song_features.json"
FIXTURES = REPO / "evaluation" / "fixtures" / "voice_profiles.json"
METRICS = REPO / "evaluation" / "scripts" / "metrics.py"


def load_metrics():
    spec = importlib.util.spec_from_file_location("t12_metrics", METRICS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def voice(data: dict) -> VoiceProfile:
    return VoiceProfile(pitch=PitchFeatures(**data["pitch"]), timbre=TimbreFeatures(**data["timbre"]),
                        analysis_mode=data["analysis_mode"], status=data["status"],
                        warnings=data["warnings"], schema_version=data["schema_version"])


def span(low_hz: float | None, high_hz: float | None) -> str:
    if low_hz is None:
        return "none"
    return f"{note_name(hz_to_midi(low_hz))}-{note_name(hz_to_midi(high_hz))}"


def main() -> None:
    metrics = load_metrics()
    songs = load_song_catalog(CATALOG)
    by_id = {s.song_id: s for s in songs}
    lines = [f"Catalog: {len(songs)} songs from experiments/E3/handoff/song_features.json; "
             f"proposed rule {SCORING_VERSION}; baseline naive_rank_contract (range coverage).", ""]
    for data in json.loads(FIXTURES.read_text(encoding="utf-8")):
        profile = voice(data)
        pitch = profile.pitch
        baseline = metrics.naive_rank_contract(profile, songs)
        proposed = recommend_songs(profile, songs)
        base_rank = {row["song_id"]: i + 1 for i, row in enumerate(baseline) if row["score"] is not None}
        base_score = {row["song_id"]: row["score"] for row in baseline}
        lines.append(f"### {data['fixture_id']}: {span(pitch.min_pitch_hz, pitch.max_pitch_hz)}"
                     + (f", median {note_name(hz_to_midi(pitch.median_pitch_hz))}" if pitch.median_pitch_hz else ""))
        lines.append("")
        if not proposed:
            excluded = sum(row["score"] is None for row in baseline)
            lines += [f"No voiced pitch: the proposed rule returns no songs; the baseline marks "
                      f"{excluded} of {len(songs)} songs not evaluable.", ""]
            continue
        lines += ["| Proposed rank | Song | Melody | Proposed score | Baseline score | Baseline rank |",
                  "|---|---|---|---|---|---|"]
        for rank, rec in enumerate(proposed, 1):
            s = by_id[rec.song_id]
            lines.append(f"| {rank} | {rec.song_id} | {span(s.melody_min_pitch_hz, s.melody_max_pitch_hz)} | "
                         f"{rec.score:.4f} | {base_score[rec.song_id]:.4f} | {base_rank[rec.song_id]} |")
        top_scores = [r.score for r in proposed]
        base_values = [row["score"] for row in baseline if row["score"] is not None]
        lines += ["", f"Same top song: {'yes' if proposed[0].song_id == baseline[0]['song_id'] else 'no'}; "
                      f"songs in the same position: {sum(base_rank[r.song_id] == i for i, r in enumerate(proposed, 1))} "
                      f"of {len(proposed)}; distinct scores: proposed {len(set(top_scores))} of {len(top_scores)}, "
                      f"baseline {len(set(base_values))} of {len(base_values)}.", ""]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
