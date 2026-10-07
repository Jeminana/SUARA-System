"""SUARA SYSTEM E3 command line.

    python run_e3.py check   [--config config.yaml] [--tools]
    python run_e3.py dev     [--config config.yaml]
    python run_e3.py test    [--config config.yaml]   (requires locked: true)
    python run_e3.py catalog [--config config.yaml]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stage", choices=["check", "dev", "test", "catalog"])
    parser.add_argument("--config", type=Path, default=HERE / "config.yaml")
    parser.add_argument("--run-name", help="output folder prefix (default: timestamp)")
    parser.add_argument("--data-root", help="override paths.data_root, e.g. data/synthetic")
    parser.add_argument("--tools", action="store_true", help="check: run every tool on a 5 s crop")
    parser.add_argument("--synthetic", action="store_true",
                        help="accept consent='synthetic' rows and label outputs as code tests only")
    args = parser.parse_args()

    # Model downloads stay inside this experiment (gitignored); must be set before the
    # HuggingFace and TensorFlow libraries are imported.
    from e3.io_utils import load_config
    cache = Path(load_config(args.config)["paths"]["model_cache"])
    cache = cache if cache.is_absolute() else args.config.resolve().parent / cache
    os.environ.setdefault("HF_HOME", str(cache))
    os.environ.setdefault("TORCH_HOME", str(cache / "torch"))
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

    from e3.pipeline import Run
    run = Run(args.config, args.stage, args.run_name, args.synthetic, args.data_root, args.tools)
    getattr(run, args.stage)()


if __name__ == "__main__":
    main()
