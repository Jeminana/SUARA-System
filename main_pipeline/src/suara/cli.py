"""CLI for local mock and real analysis, with JSON results and public errors."""
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from suara.catalog import load_song_catalog
from suara.contracts import PipelineDependencies, PipelineError
from suara.errors import failure
from suara.pipeline import run_pipeline


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's raw message can contain private argument values/paths.
        raise failure("invalid_configuration", "configuration",
                      "Invalid command arguments. Use --audio WAV, --mode mock|real, --top-k 1..5, optionally --catalog JSON and --timbre mock|real; see --help.")


def _measured_dependencies(mode: str) -> PipelineDependencies:
    from suara.audio.preprocessing import preprocess_audio
    from suara.timbre import analyze_timbre

    if mode == "real":
        from suara.pitch import analyze_pitch
        from suara.recommender import recommend_songs
    else:
        from suara.mocks.pitch import analyze_pitch
        from suara.mocks.recommender import recommend_songs

    return PipelineDependencies(
        preprocess_audio=preprocess_audio, analyze_pitch=analyze_pitch,
        analyze_timbre=analyze_timbre, recommend_songs=recommend_songs,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _Parser(description="SUARA local integration prototype. Mock features are synthetic, not audio measurements.")
    parser.add_argument("--audio", required=True, help="Local integer PCM WAV recording (0.5 to 60 seconds).")
    parser.add_argument("--mode", default="mock", choices=("mock", "real"),
                        help="Default mock. Real uses CREPE, measured timbre and pitch-range ranking; requires --catalog.")
    parser.add_argument("--top-k", type=int, default=5, help="Maximum number of recommendations, from 1 to 5.")
    parser.add_argument("--timbre", choices=("mock", "real"),
                        help="In mock mode, opt into measured timbre. Real mode always uses measured timbre.")
    parser.add_argument("--catalog", help="SongFeatures JSON list, e.g. experiments/E3/handoff/song_features.json. "
                                          "Mock mode defaults to the fictional catalog.")
    try:
        args = parser.parse_args(argv)
        if args.mode == "real":
            if args.catalog is None:
                raise failure("invalid_configuration", "configuration", "Real mode requires --catalog JSON.")
            if args.timbre == "mock":
                raise failure("invalid_configuration", "configuration", "Real mode requires measured timbre.")
        catalog = None if args.catalog is None else load_song_catalog(args.catalog)
        dependencies = None
        if args.mode == "real" or args.timbre == "real":
            dependencies = _measured_dependencies(args.mode)
        result = run_pipeline(args.audio, mode=args.mode, top_k=args.top_k,
                              song_catalog=catalog, dependencies=dependencies)
        print(result.to_json())
        return 0
    except PipelineError as exc:
        print(exc.error.to_json(), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
