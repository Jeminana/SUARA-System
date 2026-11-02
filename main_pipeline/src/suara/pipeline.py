"""Local sequential orchestration; analysis and ranking enter through callables."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import TypeVar

from suara.contracts import (
    AudioData, Contract, ContractError, DEFAULT_SAMPLE_RATE, ErrorCode, Mode,
    PIPELINE_VERSION, PipelineDependencies, PipelineError, PipelineResult,
    PitchFeatures, Recommendation, SongFeatures, TimbreFeatures, VoiceProfile,
)
from suara.errors import Stage, failure, validate_top_k

T = TypeVar("T")
C = TypeVar("C", bound=Contract)


def _invoke(stage: Stage, invalid_code: ErrorCode, action: Callable[[], T]) -> T:
    try:
        return action()
    except PipelineError:
        raise
    except (ContractError, TypeError) as exc:
        raise failure(invalid_code, stage, f"{stage.capitalize()} returned invalid contract data.") from exc
    except Exception as exc:
        raise failure("module_failure", stage, f"{stage.capitalize()} module failed; no result was produced.") from exc


def _checked(value: object, contract_type: type[C]) -> C:
    if not isinstance(value, contract_type):
        raise ContractError(f"Expected {contract_type.__name__}")
    value.validate()
    return value


def build_voice_profile(pitch_features: PitchFeatures, timbre_features: TimbreFeatures) -> VoiceProfile:
    def assemble() -> VoiceProfile:
        pitch = _checked(pitch_features, PitchFeatures)
        timbre = _checked(timbre_features, TimbreFeatures)
        mode: Mode = "mock" if "mock" in (pitch.mode, timbre.mode) else "real"
        warnings = list(dict.fromkeys([*pitch.warnings, *timbre.warnings]))
        if mode == "mock":
            warnings.append("Profile contains synthetic mock features; mock values are not measured from the supplied audio.")
        status = "no_voiced_pitch" if pitch.voiced_ratio == 0 else ("warning" if warnings else "ok")
        return VoiceProfile(pitch=pitch, timbre=timbre, analysis_mode=mode,
                            status=status, warnings=warnings)
    return _invoke("profile", "invalid_features", assemble)


def _default_dependencies() -> PipelineDependencies:
    # These imports are intentionally absent from the real-mode selection path.
    from suara.audio.preprocessing import preprocess_audio
    from suara.mocks.pitch import analyze_pitch
    from suara.mocks.recommender import recommend_songs
    from suara.mocks.timbre import analyze_timbre
    return PipelineDependencies(preprocess_audio=preprocess_audio, analyze_pitch=analyze_pitch,
                                analyze_timbre=analyze_timbre, recommend_songs=recommend_songs)


def _validate_catalog(catalog: Sequence[SongFeatures]) -> None:
    if not isinstance(catalog, Sequence) or isinstance(catalog, (str, bytes)):
        raise ContractError("Catalog must be a sequence of SongFeatures")
    ids: set[str] = set()
    for song in catalog:
        _checked(song, SongFeatures)
        if song.song_id in ids:
            raise ContractError("Duplicate catalog song_id")
        ids.add(song.song_id)


def _validate_recommendations(recommendations: object, profile: VoiceProfile,
                              catalog: Sequence[SongFeatures], top_k: int) -> list[Recommendation]:
    _validate_catalog(catalog)
    if not isinstance(recommendations, list) or len(recommendations) > min(top_k, len(catalog)):
        raise ContractError("Invalid recommendation list or count")
    songs = {song.song_id: song for song in catalog}
    for value in recommendations:
        rec = _checked(value, Recommendation)
        song = songs.get(rec.song_id)
        if song is None or (rec.title, rec.artist) != (song.title, song.artist):
            raise ContractError("Recommendation metadata must match the catalog")
        if (profile.analysis_mode == "mock" or song.provenance == "mock") and rec.mode != "mock":
            raise ContractError("Mock inputs require mock recommendation provenance")
    keys = [(-r.score, r.song_id) for r in recommendations]
    if keys != sorted(keys) or len({r.song_id for r in recommendations}) != len(recommendations):
        raise ContractError("Recommendations must be unique and correctly ranked")
    return recommendations


def run_pipeline(audio_path: str | Path, *, mode: Mode = "mock", top_k: int = 5,
                 song_catalog: Sequence[SongFeatures] | None = None,
                 dependencies: PipelineDependencies | None = None) -> PipelineResult:
    started = perf_counter()
    validate_top_k(top_k)
    if mode not in ("mock", "real"):
        raise failure("invalid_configuration", "configuration", "Mode must be mock or real.")
    if mode == "real" and (dependencies is None or song_catalog is None):
        raise failure("invalid_configuration", "configuration", "Real mode requires explicit dependencies and a song catalog; no mock fallback is available.")
    if dependencies is None:
        dependencies = _default_dependencies()
    if not isinstance(dependencies, PipelineDependencies):
        raise failure("invalid_configuration", "configuration", "Dependencies must be a PipelineDependencies bundle.")
    components = (dependencies.preprocess_audio, dependencies.analyze_pitch,
                  dependencies.analyze_timbre, dependencies.recommend_songs)
    if not all(callable(component) for component in components):
        raise failure("invalid_configuration", "configuration", "Every dependency must be callable.")
    if mode == "real" and any(getattr(component, "suara_mode", None) == "mock" for component in components):
        raise failure("invalid_configuration", "configuration", "Real mode cannot use a declared mock implementation.")
    if song_catalog is None:
        from suara.mocks.catalog import mock_song_catalog
        song_catalog = mock_song_catalog()
    _invoke("recommendation", "invalid_catalog", lambda: _validate_catalog(song_catalog))
    if mode == "real" and any(song.provenance == "mock" for song in song_catalog):
        raise failure("invalid_configuration", "configuration", "Real mode cannot use a mock catalog.")

    audio = _invoke("preprocessing", "invalid_audio", lambda: _checked(
        dependencies.preprocess_audio(audio_path, target_sample_rate=DEFAULT_SAMPLE_RATE), AudioData))
    if audio.sample_rate != DEFAULT_SAMPLE_RATE:
        raise failure("invalid_audio", "preprocessing", "Preprocessor did not return the requested sample rate.")
    pitch = _invoke("pitch", "invalid_features", lambda: _checked(dependencies.analyze_pitch(audio), PitchFeatures))
    # Frozen dataclasses still contain mutable lists. Stop invalid input mutation
    # at the responsible adapter, before another module consumes that input.
    _invoke("pitch", "invalid_audio", audio.validate)
    if mode == "real" and pitch.mode != "real":
        raise failure("invalid_configuration", "configuration", "Pitch analyzer returned mock features in real mode.")
    timbre = _invoke("timbre", "invalid_features", lambda: _checked(dependencies.analyze_timbre(audio), TimbreFeatures))
    _invoke("timbre", "invalid_audio", audio.validate)
    if mode == "real" and timbre.mode != "real":
        raise failure("invalid_configuration", "configuration", "Timbre analyzer returned mock features in real mode.")
    if timbre.spectral_centroid_mean_hz is not None and timbre.spectral_centroid_mean_hz > audio.sample_rate / 2:
        raise failure("invalid_features", "timbre", "Spectral centroid must not exceed the audio Nyquist frequency.")
    profile = build_voice_profile(pitch, timbre)
    warnings = list(dict.fromkeys([*audio.warnings, *profile.warnings]))
    profile = replace(profile, warnings=warnings,
                      status="warning" if warnings and profile.status == "ok" else profile.status)

    def rank() -> list[Recommendation]:
        values = dependencies.recommend_songs(profile, song_catalog, top_k=top_k)
        checked = _validate_recommendations(values, profile, song_catalog, top_k)
        if (getattr(dependencies.recommend_songs, "suara_mode", None) == "mock" and
                any(rec.mode != "mock" for rec in checked)):
            raise ContractError("A declared mock ranker must return mock recommendations")
        return checked
    recommendations = _invoke("recommendation", "invalid_catalog", rank)
    if mode == "real" and any(rec.mode != "real" for rec in recommendations):
        raise failure("invalid_configuration", "configuration", "Recommender returned mock results in real mode.")
    result_mode: Mode = "mock" if (profile.analysis_mode == "mock" or
                                    any(rec.mode == "mock" for rec in recommendations)) else "real"
    return _invoke("recommendation", "invalid_catalog", lambda: PipelineResult(
        voice_profile=profile, recommendations=recommendations, pipeline_version=PIPELINE_VERSION,
        analysis_mode=result_mode, processing_time_s=perf_counter() - started,
    ))
