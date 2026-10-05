"""SUARA SYSTEM E6 command line.

    python run_e6.py check  [--config config.yaml]
    python run_e6.py dev    [--config config.yaml]
    python run_e6.py test   [--config config.yaml]   (requires locked: true)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from e6.pipeline import Run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stage", choices=["check", "dev", "test"])
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.yaml"))
    parser.add_argument("--run-name", help="output folder prefix (default: timestamp)")
    parser.add_argument("--synthetic", action="store_true",
                        help="accept consent='synthetic' rows and label outputs as code tests only")
    args = parser.parse_args()
    run = Run(args.config, args.stage, args.run_name, args.synthetic)
    getattr(run, args.stage)()


if __name__ == "__main__":
    main()
