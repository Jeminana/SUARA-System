"""Embedding extractors: SpeechBrain ECAPA-TDNN and a time-averaged MFCC baseline.

Both return raw (unnormalised) vectors from `embed(y)`; `postprocess(X)` applies any
frozen scaling, and L2 normalisation happens in evaluation.
"""
from __future__ import annotations

import time
from pathlib import Path

import librosa
import numpy as np
import torch

SAMPLE_RATE = 16000


def resolve_device(requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return requested


def resolve_hf_revision(source: str, revision: str | None) -> str | None:
    """Commit hash actually served for source@revision (None if offline)."""
    try:
        from huggingface_hub import HfApi

        return HfApi().model_info(source, revision=revision).sha
    except Exception:
        return None


class EcapaEmbedder:
    name = "ecapa"

    def __init__(self, cfg: dict, cache_dir: Path, logger):
        try:
            from speechbrain.inference.speaker import EncoderClassifier
        except ImportError:  # speechbrain < 1.0
            from speechbrain.pretrained import EncoderClassifier

        self.device = resolve_device(cfg["device"])
        requested = cfg.get("revision")
        self.revision = resolve_hf_revision(cfg["source"], requested) or requested or "unresolved"
        if not requested:
            logger.warning("ECAPA revision is not pinned in config; recorded served revision %s", self.revision)
        t0 = time.perf_counter()
        source = cfg["source"]
        if requested:
            # Pin the exact checkpoint commit: download that snapshot and load it locally.
            from huggingface_hub import snapshot_download

            source = snapshot_download(cfg["source"], revision=requested,
                                       local_dir=str(Path(cache_dir) / f"snapshot_{requested}"))
        kwargs = {"source": source, "savedir": str(cache_dir), "run_opts": {"device": self.device}}
        try:  # copy instead of symlinking: Windows needs special rights for symlinks
            from speechbrain.utils.fetching import LocalStrategy

            kwargs["local_strategy"] = LocalStrategy.COPY
        except ImportError:
            pass
        self.model = EncoderClassifier.from_hparams(**kwargs)
        self.model.mods.eval()
        for p in self.model.mods.parameters():
            p.requires_grad_(False)
        self.load_time_s = time.perf_counter() - t0
        self.model_revision = f"{cfg['source']}@{self.revision}"
        logger.info("Loaded ECAPA %s on %s in %.2f s", self.model_revision, self.device, self.load_time_s)

    @torch.inference_mode()
    def embed(self, y: np.ndarray) -> np.ndarray:
        # Input must already be mono 16 kHz: encode_batch does not resample tensors.
        wav = torch.from_numpy(np.ascontiguousarray(y, dtype=np.float32)).unsqueeze(0).to(self.device)
        emb = self.model.encode_batch(wav, wav_lens=torch.ones(1, device=self.device))
        return emb.squeeze().detach().cpu().numpy().astype(np.float64)

    def postprocess(self, X: np.ndarray) -> np.ndarray:
        return X


class MfccEmbedder:
    name = "mfcc"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.load_time_s = 0.0
        self.model_revision = (f"mfcc{cfg['n_mfcc']}_meanstd_c0-{cfg['include_c0']}_"
                               f"{cfg['scaling']}_librosa-{librosa.__version__}")
        self.mean = self.std = None

    def embed(self, y: np.ndarray) -> np.ndarray:
        c = self.cfg
        mfcc = librosa.feature.mfcc(y=y, sr=SAMPLE_RATE, n_mfcc=c["n_mfcc"], n_fft=c["n_fft"],
                                    hop_length=c["hop_length"], n_mels=c["n_mels"])
        if not c["include_c0"]:
            mfcc = mfcc[1:]
        return np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1)]).astype(np.float64)

    def fit_scaler(self, X_dev: np.ndarray) -> None:
        """Fit z-score statistics on development clips only; frozen afterwards."""
        self.mean = X_dev.mean(axis=0)
        self.std = X_dev.std(axis=0) + 1e-8

    def postprocess(self, X: np.ndarray) -> np.ndarray:
        if self.cfg["scaling"] == "none":
            return X
        if self.mean is None:
            raise RuntimeError("MFCC z-score scaling requested but no dev statistics were fitted")
        return (X - self.mean) / self.std

    def scaler_record(self) -> dict | None:
        if self.mean is None:
            return None
        return {"mean": self.mean.tolist(), "std": self.std.tolist()}
