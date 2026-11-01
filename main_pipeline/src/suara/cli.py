"""CLI: success JSON on stdout, public error JSON on stderr, no model loading."""
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from suara.contracts import PipelineError
from suara.errors import failure
from suara.pipeline import run_pipeline


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's raw message can contain private argument values/paths.
        raise failure("invalid_configuration", "configuration",
                      "Invalid command arguments. Use --audio WAV, --mode mock|real, and --top-k 1..5; see --help.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _Parser(description="SUARA local integration prototype. Mock features are synthetic, not audio measurements.")
    parser.add_argument("--audio", required=True, help="Local integer PCM WAV recording (0.5 to 60 seconds).")
    parser.add_argument("--mode", default="mock", choices=("mock", "real"),
                        help="Default mock. Real mode requires Python API injection and is unavailable in this CLI.")
    parser.add_argument("--top-k", type=int, default=5, help="Maximum number of recommendations, from 1 to 5.")
    try:
        args = parser.parse_args(argv)
        result = run_pipeline(args.audio, mode=args.mode, top_k=args.top_k)
        print(result.to_json())
        return 0
    except PipelineError as exc:
        print(exc.error.to_json(), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
