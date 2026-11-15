"""Measured mfcc-20-v1 descriptors; independent of the locked E6 experiment."""
from __future__ import annotations

import numpy as np
import scipy
from scipy.fft import dct
from scipy.signal.windows import hann

from suara.contracts import AudioData, DEFAULT_SAMPLE_RATE, MFCC_DIM, TimbreFeatures
from suara.errors import failure

PROCESSING_VERSION = "mfcc-20-v1"
MODEL_VERSION = f"suara-timbre-v1_numpy-{np.__version__}_scipy-{scipy.__version__}"
N_FFT = 512
HOP_LENGTH = 160
N_MELS = 40


def _mel_filters() -> np.ndarray:
    """Slaney scale (linear below 1 kHz), triangular area-normalized filters."""
    # Slaney mel units: 200/3 Hz per unit up to 1000 Hz, then log spacing.
    log_step = np.log(6.4) / 27.0
    max_mel = 15.0 + np.log(8000.0 / 1000.0) / log_step
    mel = np.linspace(0.0, max_mel, N_MELS + 2)
    hz = mel * (200.0 / 3.0)
    logarithmic = mel >= 15.0
    hz[logarithmic] = 1000.0 * np.exp(log_step * (mel[logarithmic] - 15.0))
    bins = np.fft.rfftfreq(N_FFT, 1.0 / DEFAULT_SAMPLE_RATE)
    lower = (bins[None, :] - hz[:-2, None]) / (hz[1:-1] - hz[:-2])[:, None]
    upper = (hz[2:, None] - bins[None, :]) / (hz[2:] - hz[1:-1])[:, None]
    return np.maximum(0.0, np.minimum(lower, upper)) * (2.0 / (hz[2:] - hz[:-2]))[:, None]


def analyze_timbre(audio_data: AudioData) -> TimbreFeatures:
    """Extract raw c0..c19 means and magnitude centroid without modifying input.

    Only complete 512-sample frames are used, starting at sample zero every 160
    samples. No padding, trimming, gain normalization, or voicing gate is applied.
    Silence has finite log-floor MFCCs and a null centroid. Shorter input fails.
    """
    audio_data.validate()
    if audio_data.sample_rate != DEFAULT_SAMPLE_RATE:
        raise failure("invalid_audio", "timbre", "Timbre extraction requires 16000 Hz mono audio.")
    if len(audio_data.waveform) < N_FFT:
        raise failure("audio_too_short", "timbre", "Timbre extraction requires at least 512 samples.")
    waveform = np.asarray(audio_data.waveform, dtype=np.float64)
    frames = np.lib.stride_tricks.sliding_window_view(waveform, N_FFT)[::HOP_LENGTH]
    magnitude = np.abs(np.fft.rfft(frames * hann(N_FFT, sym=False), axis=1))
    mel_power = (magnitude ** 2) @ _mel_filters().T
    log_power = 10.0 * np.log10(np.maximum(mel_power, 1e-10))
    coefficients = dct(log_power, type=2, norm="ortho", axis=1)[:, :MFCC_DIM]
    weights = magnitude.sum(axis=1)
    nonzero = weights > 0.0
    centroid = None
    warnings = []
    if np.any(nonzero):
        frequencies = np.fft.rfftfreq(N_FFT, 1.0 / DEFAULT_SAMPLE_RATE)
        centroid = float(np.mean((magnitude[nonzero] @ frequencies) / weights[nonzero]))
    else:
        warnings.append("No nonzero spectral frames; centroid is unavailable.")
    return TimbreFeatures(
        mfcc_mean=coefficients.mean(axis=0).tolist(),
        spectral_centroid_mean_hz=centroid, mode="real", model_version=MODEL_VERSION,
        processing_version=PROCESSING_VERSION, warnings=warnings,
    )


analyze_timbre.suara_mode = "real"
