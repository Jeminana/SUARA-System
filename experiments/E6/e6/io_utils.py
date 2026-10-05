"""Config, logging and environment records."""
from __future__ import annotations

import hashlib
import json
import logging
import platform
import subprocess
import sys
from datetime import datetime
from importlib import metadata
from pathlib import Path

import yaml

PACKAGES = [
    "numpy", "pandas", "scipy", "torch", "torchaudio", "speechbrain", "librosa",
    "soundfile", "soxr", "matplotlib", "huggingface_hub", "PyYAML",
]


def load_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def setup_logging(out_dir: Path) -> logging.Logger:
    logger = logging.getLogger("e6")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (logging.FileHandler(out_dir / "run_log.txt", encoding="utf-8"),
                    logging.StreamHandler(sys.stdout)):
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger


def package_versions() -> dict:
    versions = {}
    for pkg in PACKAGES:
        try:
            versions[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            versions[pkg] = None
    return versions


def git_commit(path: Path) -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True,
                             text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def environment_record(config_path: Path, cfg: dict, extra: dict) -> dict:
    import torch

    return {
        "created": datetime.now().isoformat(timespec="seconds"),
        "python": sys.version,
        "platform": platform.platform(),
        "cuda_available": torch.cuda.is_available(),
        "packages": package_versions(),
        "code_commit": git_commit(Path(__file__).resolve().parent),
        "config_path": str(config_path),
        "config_sha256": file_sha256(config_path),
        "config_locked": bool(cfg.get("locked")),
        "seed": cfg["seed"],
        **extra,
    }


def write_json(path: Path, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)
