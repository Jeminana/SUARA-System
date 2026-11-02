"""Version 1 application boundary; no experiment, audio, or model imports.

Constructors validate values. Lists remain mutable: call validate() again at
module boundaries. to_dict()/to_json() revalidate the entire object graph.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import ClassVar, Literal, Protocol, Sequence, TypeAlias

SCHEMA_VERSION = "1.0.0"
PIPELINE_VERSION = "0.1.0"
MFCC_DIM = 20
DEFAULT_SAMPLE_RATE = 16000
Mode: TypeAlias = Literal["mock", "real"]
Status: TypeAlias = Literal["ok", "warning", "no_voiced_pitch"]
ErrorCode: TypeAlias = Literal[
    "audio_not_found", "unsupported_audio", "invalid_audio", "audio_too_short",
    "audio_too_long", "silent_audio", "invalid_features", "invalid_catalog",
    "invalid_configuration", "module_failure",
]


class ContractError(ValueError):
    """A schema/type/value invariant failed; never substitute fabricated values."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _number(value: object, name: str, low: float | None = None,
            high: float | None = None) -> None:
    _require(type(value) in (int, float), f"{name} must be a finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    _require(finite, f"{name} must be finite")
    _require(low is None or value >= low, f"{name} must be >= {low}")
    _require(high is None or value <= high, f"{name} must be <= {high}")


def _text(value: object, name: str) -> None:
    _require(isinstance(value, str) and bool(value.strip()), f"{name} must be nonempty text")


def _mode(value: object) -> None:
    _require(value in ("mock", "real"), "mode must be mock or real")


def _range(low: float | None, high: float | None, name: str) -> None:
    _require((low is None) == (high is None), f"{name} endpoints must both be null or present")
    if low is not None and high is not None:
        _number(low, name)
        _number(high, name)
        _require(0 < low <= high, f"{name} must satisfy 0 < minimum <= maximum")


@dataclass(frozen=True, kw_only=True)
class Contract:
    """Strict JSON output helpers, not a general JSON deserializer."""
    VERSION: ClassVar[str] = SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, Contract):
                value.validate()
        if hasattr(self, "schema_version"):
            _require(self.schema_version == self.VERSION, "unsupported schema_version")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), allow_nan=False, indent=2)


@dataclass(frozen=True, kw_only=True)
class AudioData(Contract):
    waveform: list[float]
    sample_rate: int
    duration_s: float
    warnings: list[str]
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> None:
        super().validate()
        _require(type(self.sample_rate) is int and self.sample_rate > 0, "invalid sample_rate")
        _require(isinstance(self.waveform, list) and bool(self.waveform), "waveform must be nonempty mono list")
        for value in self.waveform:
            _require(type(value) is float, "waveform samples must be floats")
            _number(value, "sample", -1, 1)
        _number(self.duration_s, "duration_s", 0)
        _require(math.isclose(self.duration_s, len(self.waveform) / self.sample_rate,
                              rel_tol=0, abs_tol=1e-9), "duration_s must equal samples / sample_rate")
        _strings(self.warnings, "warnings")


def _strings(value: object, name: str) -> None:
    _require(isinstance(value, list), f"{name} must be a list")
    for item in value:
        _text(item, name)


@dataclass(frozen=True, kw_only=True)
class PitchFeatures(Contract):
    min_pitch_hz: float | None
    max_pitch_hz: float | None
    median_pitch_hz: float | None
    voiced_ratio: float
    confidence: float | None
    mode: Mode
    model_version: str
    warnings: list[str]
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> None:
        super().validate()
        _mode(self.mode)
        _text(self.model_version, "model_version")
        _strings(self.warnings, "warnings")
        _number(self.voiced_ratio, "voiced_ratio", 0, 1)
        if self.confidence is not None:
            _number(self.confidence, "confidence", 0, 1)
        _range(self.min_pitch_hz, self.max_pitch_hz, "pitch")
        if self.voiced_ratio == 0:
            _require(self.min_pitch_hz is None and self.median_pitch_hz is None,
                     "unvoiced pitch statistics must be null")
        else:
            _require(self.min_pitch_hz is not None and self.max_pitch_hz is not None,
                     "voiced pitch requires endpoints")
            _number(self.median_pitch_hz, "median_pitch_hz", self.min_pitch_hz, self.max_pitch_hz)


@dataclass(frozen=True, kw_only=True)
class TimbreFeatures(Contract):
    mfcc_mean: list[float]
    spectral_centroid_mean_hz: float | None
    mode: Mode
    model_version: str
    processing_version: str
    warnings: list[str]
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> None:
        super().validate()
        _mode(self.mode)
        _text(self.model_version, "model_version")
        _text(self.processing_version, "processing_version")
        _strings(self.warnings, "warnings")
        _require(isinstance(self.mfcc_mean, list) and len(self.mfcc_mean) == MFCC_DIM,
                 f"mfcc_mean must contain {MFCC_DIM} coefficients")
        for value in self.mfcc_mean:
            _number(value, "mfcc_mean coefficient")
        if self.spectral_centroid_mean_hz is not None:
            _number(self.spectral_centroid_mean_hz, "spectral_centroid_mean_hz", 0)


@dataclass(frozen=True, kw_only=True)
class VoiceProfile(Contract):
    pitch: PitchFeatures
    timbre: TimbreFeatures
    analysis_mode: Mode
    status: Status
    warnings: list[str]
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> None:
        _require(isinstance(self.pitch, PitchFeatures), "pitch must be PitchFeatures")
        _require(isinstance(self.timbre, TimbreFeatures), "timbre must be TimbreFeatures")
        super().validate()
        _mode(self.analysis_mode)
        expected = "mock" if "mock" in (self.pitch.mode, self.timbre.mode) else "real"
        _require(self.analysis_mode == expected, "profile must be mock if any analyzer is mock")
        _require(self.status in ("ok", "warning", "no_voiced_pitch"), "invalid profile status")
        if self.pitch.voiced_ratio == 0:
            _require(self.status == "no_voiced_pitch", "unvoiced profile must have no_voiced_pitch status")
        else:
            _require(self.status != "no_voiced_pitch", "voiced profile cannot have no_voiced_pitch status")
        _strings(self.warnings, "warnings")
        if self.analysis_mode == "mock":
            _require(self.status != "ok" and bool(self.warnings), "mock profile requires warning")


@dataclass(frozen=True, kw_only=True)
class SongFeatures(Contract):
    song_id: str
    title: str
    artist: str
    melody_min_pitch_hz: float | None
    melody_max_pitch_hz: float | None
    feature_version: str
    provenance: Literal["mock", "unverified", "verified_melody"]
    source_description: str
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> None:
        super().validate()
        for name in ("song_id", "title", "artist", "feature_version", "source_description"):
            _text(getattr(self, name), name)
        _range(self.melody_min_pitch_hz, self.melody_max_pitch_hz, "melody")
        _require(self.provenance in ("mock", "unverified", "verified_melody"), "invalid song provenance")
        if self.provenance == "verified_melody":
            _require(self.melody_min_pitch_hz is not None, "verified melody requires endpoints")


@dataclass(frozen=True, kw_only=True)
class Recommendation(Contract):
    song_id: str
    title: str
    artist: str
    score: float
    explanation: str
    scoring_version: str
    mode: Mode
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> None:
        super().validate()
        for name in ("song_id", "title", "artist", "explanation", "scoring_version"):
            _text(getattr(self, name), name)
        _number(self.score, "score", 0, 1)
        _mode(self.mode)


@dataclass(frozen=True, kw_only=True)
class PipelineResult(Contract):
    voice_profile: VoiceProfile
    recommendations: list[Recommendation]
    pipeline_version: str
    analysis_mode: Mode
    processing_time_s: float | None
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> None:
        _require(isinstance(self.voice_profile, VoiceProfile), "invalid voice_profile")
        super().validate()
        _text(self.pipeline_version, "pipeline_version")
        _mode(self.analysis_mode)
        _require(isinstance(self.recommendations, list), "recommendations must be a list")
        for item in self.recommendations:
            _require(isinstance(item, Recommendation), "invalid recommendation")
            item.validate()
        ids = [item.song_id for item in self.recommendations]
        _require(len(ids) == len(set(ids)), "duplicate recommendation song_id")
        keys = [(-item.score, item.song_id) for item in self.recommendations]
        _require(keys == sorted(keys), "recommendations must sort by descending score then song_id")
        expected = "mock" if (self.voice_profile.analysis_mode == "mock" or
                               any(r.mode == "mock" for r in self.recommendations)) else "real"
        _require(self.analysis_mode == expected, "pipeline mode inconsistent with outputs")
        if self.processing_time_s is not None:
            _number(self.processing_time_s, "processing_time_s", 0)


@dataclass(frozen=True, kw_only=True)
class ErrorInfo(Contract):
    code: ErrorCode
    message: str
    stage: Literal["configuration", "preprocessing", "pitch", "timbre", "profile", "recommendation"]
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> None:
        super().validate()
        _require(self.code in ("audio_not_found", "unsupported_audio", "invalid_audio", "audio_too_short",
                              "audio_too_long", "silent_audio", "invalid_features", "invalid_catalog",
                              "invalid_configuration", "module_failure"), "invalid error code")
        _require(self.stage in ("configuration", "preprocessing", "pitch", "timbre", "profile",
                               "recommendation"), "invalid error stage")
        _text(self.message, "message")


class PipelineError(Exception):
    """Runtime modules raise this with a serializable public error payload."""

    def __init__(self, error: ErrorInfo) -> None:
        error.validate()
        self.error = error
        super().__init__(error.message)


class PreprocessAudio(Protocol):
    def __call__(self, audio_path: str | Path, *,
                 target_sample_rate: int = DEFAULT_SAMPLE_RATE) -> AudioData: ...


class AnalyzePitch(Protocol):
    def __call__(self, audio_data: AudioData) -> PitchFeatures: ...


class AnalyzeTimbre(Protocol):
    def __call__(self, audio_data: AudioData) -> TimbreFeatures: ...


class BuildVoiceProfile(Protocol):
    def __call__(self, pitch_features: PitchFeatures,
                 timbre_features: TimbreFeatures) -> VoiceProfile: ...


class RecommendSongs(Protocol):
    def __call__(self, voice_profile: VoiceProfile, song_catalog: Sequence[SongFeatures],
                 top_k: int = 5) -> list[Recommendation]: ...


@dataclass(frozen=True, kw_only=True)
class PipelineDependencies:
    """Explicit injection bundle; not a wire contract or serialized model."""
    preprocess_audio: PreprocessAudio
    analyze_pitch: AnalyzePitch
    analyze_timbre: AnalyzeTimbre
    recommend_songs: RecommendSongs


class RunPipeline(Protocol):
    def __call__(self, audio_path: str | Path, *, mode: Mode = "mock", top_k: int = 5,
                 song_catalog: Sequence[SongFeatures] | None = None,
                 dependencies: PipelineDependencies | None = None) -> PipelineResult: ...
