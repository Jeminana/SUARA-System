# Integration contract 1.0.0

This is the Day 1 agreement for the local MVP. Schemas and protocols are implemented
in `main_pipeline/src/suara/contracts.py`. Day 2 implements preprocessing, mock
analysis/ranking, assembly and orchestration without changing these schemas.
Runtime rules are enforced by those implementations; dataclasses cannot verify
how audio was measured. Real analysis/ranking implementations remain teammate work.

## Common conventions

- Python 3.12; keyword-only dataclass construction; `str | Path` local paths.
- JSON uses snake_case, UTF-8, arrays for lists, finite JSON numbers, and `null`
  for unavailable values. Booleans are not numeric values. No NaN/Infinity.
- Every wire object has `schema_version="1.0.0"`. This is the only constructor
  default; every other field below must be supplied, even nullable fields and
  empty warning lists. Output JSON always includes all fields.
- All listed fields are required on the wire. Nullable fields are explicitly
  labeled. Fields not labeled nullable cannot be null. There are no arbitrary
  extra fields; constructors reject unknown/missing arguments with `TypeError`.
- Text identifiers/versions/messages must be nonempty. Version strings identify
  actual implementations; `model_version`, `processing_version`, `feature_version`
  and `scoring_version` are separate from `schema_version`.
- Contract classes expose `validate()`, `to_dict()` and `to_json()`. Constructors
  validate; serialization validates again, recursively. JSON loading is not
  implemented: deserialize nested contracts explicitly before construction.
- Containers are lists for a simple dependency-free boundary. Frozen dataclasses
  prevent field reassignment but do not freeze lists; adapters must not mutate
  inputs. Validate again at every module boundary.
  Day 3 also revalidates AudioData after each analyzer and enforces the requested
  16000 Hz preprocessing output rate. Invalid input mutation fails at that analyzer
  stage; valid edits are not automatically detected and remain prohibited.
- `mode`/`analysis_mode` is exactly `mock` or `real`. Mock means synthetic fixtures,
  never audio measurements. Real means produced by a real algorithm, not proven
  accurate. Profile and result aggregate provenance conservatively.

## Callable interfaces

| Protocol | Signature | Responsibility |
| --- | --- | --- |
| `PreprocessAudio` | `preprocess_audio(audio_path: str | Path, *, target_sample_rate: int = 16000) -> AudioData` | Real decode/mono/resample/QC |
| `AnalyzePitch` | `analyze_pitch(audio_data: AudioData) -> PitchFeatures` | Detector adapter or explicit mock |
| `AnalyzeTimbre` | `analyze_timbre(audio_data: AudioData) -> TimbreFeatures` | Descriptor adapter or explicit mock |
| `BuildVoiceProfile` | `build_voice_profile(pitch_features: PitchFeatures, timbre_features: TimbreFeatures) -> VoiceProfile` | Validated assembly and status/mode derivation |
| `RecommendSongs` | `recommend_songs(voice_profile: VoiceProfile, song_catalog: Sequence[SongFeatures], top_k: int = 5) -> list[Recommendation]` | Unique ranked subset with provenance |
| `RunPipeline` | `run_pipeline(audio_path: str | Path, *, mode: Mode = "mock", top_k: int = 5, song_catalog: Sequence[SongFeatures] | None = None, dependencies: PipelineDependencies | None = None) -> PipelineResult` | Boundary validation and orchestration |

These declarations are callable `Protocol`s. The matching runtime functions now
exist in `audio/preprocessing.py`, `mocks/`, and `pipeline.py`. `PipelineDependencies`
holds `preprocess_audio`, `analyze_pitch`, `analyze_timbre`, `recommend_songs`;
it is an injection container, not serialized JSON. `top_k` must be an integer
(not bool) from 1 through 5; reject other values with `invalid_configuration`.
Target rate must be a positive integer in [8000, 48000]. Built-in default
analysis will use 16000 Hz; adapters may reject unsupported rates explicitly.

## AudioData and preprocessing policy

| Field | Python type / units | Rules |
| --- | --- | --- |
| waveform | `list[float]`, normalized full-scale amplitude | Nonempty, one-dimensional, finite, each sample in [-1,1]; Python floats, no channel axis |
| sample_rate | `int`, samples/second | Positive; default preprocessing target 16000 |
| duration_s | `float`, seconds | Equals `len(waveform)/sample_rate`, absolute tolerance 1e-9 |
| warnings | `list[str]` | QC/transformation descriptions; empty allowed |
| schema_version | `str` | Exactly 1.0.0 |

Runtime policy for Day 2:

1. Only a local regular `.wav` file; do not fetch URLs or follow directory inputs.
   Validate header/content as WAV, not only extension. Initially support uncompressed
   integer PCM 8/16/24/32-bit WAV, mono or stereo, source rates 8000–192000 Hz.
   Reject compressed WAV, float WAV, malformed frames, unsupported channels/rates
   and invalid metadata. This deliberately narrow support can expand with tests.
   Day 2 accepts RIFF PCM and full-width WAVE_FORMAT_EXTENSIBLE PCM; RF64, RIFX,
   reduced-valid-bit extensible PCM and multiple data chunks are unsupported.
   RIFF size must match physical file size; malformed/trailing container bytes
   are rejected. Unknown bounded metadata chunks are skipped. An absent pad byte
   is tolerated only after the final odd-sized chunk, as emitted by some writers.
2. Validate file/header frame counts and duration before allocating the full
   waveform. Reject zero frames as `invalid_audio`, <0.5 s as `audio_too_short`,
   and >60 s as `audio_too_long`; endpoints accepted. Reject unreadable/corrupt or
   nonfinite/out-of-range data as `invalid_audio`. No cropping to make input pass.
3. Convert unsigned 8-bit samples using `(x-128)/128`; signed b-bit PCM using
   `x / 2**(b-1)`. Check source-channel peak/clipping before downmix so stereo
   cancellation does not hide it. Average channels arithmetically, without gain.
4. Resample only when needed with an anti-aliasing resampler, not naive decimation
   or linear interpolation. Record implementation/settings in warnings/adapter
   documentation. Output length is `max(1, round(source_frames * target/source_rate))`;
   trim/pad resampler rounding only, not user content. Recompute duration.
   Day 2 uses SciPy `resample_poly`, reduced integer up/down factors, Kaiser
   beta=5.0 and constant-zero padding; its version/settings appear in warnings.
5. Preserve gain and silence; no automatic denoising, trimming or normalization.
   If resampling causes overshoot, clamp to [-1,1] and emit a warning describing
   clamped samples. Source samples with abs amplitude >=0.999 generate a clipping
   warning (not rejection). Reject otherwise out-of-range source floats.
6. Reject final waveform RMS <=1e-5 full scale (-100 dBFS) as `silent_audio`;
   this is an engineering floor, not a voicing detector. Partial silence stays.
   Non-silent noise may have no voiced pitch and is a valid analyzer input.
7. Emit warnings for stereo conversion, resampling, clipping and overshoot if
   applicable. Adapters consume exactly this waveform and do not mutate it.

The schema validates the representation, not all ingestion policies. For example,
its sample JSON below uses four samples to avoid publishing thousands of values;
that example passes the schema but is too short for file preprocessing.

## PitchFeatures

| Field | Type / units | Rules |
| --- | --- | --- |
| min_pitch_hz | `float | None`, Hz | Nullable; positive observed voiced minimum |
| max_pitch_hz | `float | None`, Hz | Nullable; positive observed voiced maximum |
| median_pitch_hz | `float | None`, Hz | Nullable; within min/max when voiced |
| voiced_ratio | `float`, unitless | [0,1], voiced accepted frames / all analysis frames |
| confidence | `float | None`, unitless | Nullable; [0,1]; null when unavailable, not automatically voiced_ratio |
| mode | `Mode` | mock or real |
| model_version | `str` | Algorithm/config identity; mock fixture version when synthetic |
| warnings | `list[str]` | Empty allowed; mocks must disclose synthetic origin in runtime output |
| schema_version | `str` | 1.0.0 |

At voiced_ratio=0 all three Hz statistics MUST be null. At voiced_ratio>0 all
three MUST be present, with `0 < min <= median <= max`. An empty set of valid
voiced frames returns ratio=0, null statistics, and a warning, not an exception.
Adapters record frame size, hop, search bounds, confidence threshold and rejected
frame policy in model-version documentation. For v1 use min/max and median of
accepted finite positive voiced-frame frequencies (equal frame weights).
Short clips estimate observed range only, never total capability or tessitura.

## TimbreFeatures

| Field | Type / units | Rules |
| --- | --- | --- |
| mfcc_mean | `list[float]`, log-mel cepstral coefficients | Exactly 20 finite values, c0 through c19 |
| spectral_centroid_mean_hz | `float | None`, Hz | Nullable; finite >=0; runtime value <=sample_rate/2 |
| mode | `Mode` | mock or real |
| model_version | `str` | Implementation/fixture version |
| processing_version | `str` | Exact parameter convention, initial real convention `mfcc-20-v1` |
| warnings | `list[str]` | Empty allowed; synthetic disclosure for mocks |
| schema_version | `str` | 1.0.0 |

Proposed `mfcc-20-v1` real extraction convention (not implemented or evaluated):
16 kHz mono; 512-point periodic Hann STFT, hop 160 samples, center=false, no
pre-emphasis; 40 Slaney-normalized mel filters, Slaney frequency scale, 0–8000 Hz;
power spectrum; `10*log10(max(power,1e-10))`, reference 1.0, no top-dB truncation;
orthonormal DCT-II, retain c0–c19, no lifter or fitted z-score scaling. Arithmetic
mean over all complete frames, including silent frames; drop incomplete tail.
Centroid uses magnitude-spectrum weights, mean over nonzero-magnitude frames;
null if none. A library adapter must record its version and verify parity with
these settings. Do not compare vectors across processing versions.

Mock processing_version must identify a synthetic fixture, such as
`mock-mfcc-20-v1`, not claim real extraction. MFCCs have representation-dependent
units, not Hz; only centroid is Hz. This convention intentionally differs from
E6's development-scaled, c0-excluded baseline. ECAPA embeddings are not MFCCs.
Timbre descriptors must not imply singer suitability without evaluation.

## VoiceProfile

| Field | Type | Rules |
| --- | --- | --- |
| pitch | `PitchFeatures` | Required nested validated contract |
| timbre | `TimbreFeatures` | Required nested validated contract |
| analysis_mode | `Mode` | mock if either analyzer is mock; real only if both real |
| status | `Status` | `ok`, `warning`, or `no_voiced_pitch` |
| warnings | `list[str]` | Consolidated analyzer + preprocessing warnings |
| schema_version | `str` | 1.0.0 |

Status priority: no_voiced_pitch if voiced_ratio=0; otherwise warning for mock
analysis or any QC/module warning; otherwise ok. A mock profile must have a
nonempty warning list explaining values are synthetic, not measured. Schemas
check mode consistency and the no-voiced/mock status rules; assembly must enforce
the full warning policy. Preprocessing warnings are merged by the orchestrator
because the two-input profile builder does not receive AudioData.

## SongFeatures

| Field | Type / units | Rules |
| --- | --- | --- |
| song_id | `str` | Unique nonempty catalog key |
| title | `str` | Nonempty display title |
| artist | `str` | Nonempty display artist, mock display names clearly fictional |
| melody_min_pitch_hz | `float | None`, Hz | Nullable; observed lead-vocal/melody endpoint |
| melody_max_pitch_hz | `float | None`, Hz | Nullable; observed lead-vocal/melody endpoint |
| feature_version | `str` | Source/feature extraction version |
| provenance | `Literal["mock", "unverified", "verified_melody"]` | Mock catalog explicitly mock |
| source_description | `str` | Source type, excerpt boundaries, review/verification context; no private paths |
| schema_version | `str` | 1.0.0 |

Endpoints are either both null or both finite and `0 < min <= max`.
verified_melody requires endpoints plus evidence described by the source owner;
the constructor cannot verify the evidence. A full polyphonic spectrum is NOT
equivalent to a vocal melody range. Verified excerpts describe only those excerpts.
Optional future descriptors require a reviewed schema extension, not ad hoc keys.

## Recommendation

| Field | Type / units | Rules |
| --- | --- | --- |
| song_id | `str` | Must exist in input catalog (runtime check) |
| title | `str` | Matches catalog metadata (runtime check) |
| artist | `str` | Matches catalog metadata (runtime check) |
| score | `float`, unitless | Finite normalized [0,1], not a probability of suitability |
| explanation | `str` | Meaning and limitations of score; synthetic disclosure for mock |
| scoring_version | `str` | Reproducible ranking rule identity |
| mode | `Mode` | mock when profile, catalog item, or ranking implementation is mock |
| schema_version | `str` | 1.0.0 |

Return at most top_k unique entries, ordered by descending score then ascending
song_id (lexical tie-break). Empty catalog returns an empty list. Do not invent
pitch matches for null pitch or unverified melody ranges. Initial Day 2 mock
ranking uses fictional catalog entries, ascending song_id order and fixed fixture
scores 0.9, 0.8, 0.7, 0.6, 0.5 by position (at most five). Reordering an input
catalog does not change rank. It does not evaluate pitch or timbre suitability. No actual
range-matching formula is proposed in Day 1. A later real rule must document its
formula, missing-data behavior, normalization and evaluation limitations.

## PipelineResult

| Field | Type / units | Rules |
| --- | --- | --- |
| voice_profile | `VoiceProfile` | Required validated profile |
| recommendations | `list[Recommendation]` | May be empty; unique and sorted; runtime enforces top_k/catalog linkage |
| pipeline_version | `str` | Initial planned runtime version `0.1.0` |
| analysis_mode | `Mode` | mock if profile or any recommendation is mock; otherwise real |
| processing_time_s | `float | None`, seconds | Nullable; nonnegative monotonic wall duration for whole invocation |
| schema_version | `str` | 1.0.0 |

Deterministic mock behavior means identical feature values/rankings for identical
settings; processing_time_s and preprocessing metadata are not fixture outputs.
No waveform or local input path appears in PipelineResult. The runtime must
add provenance warnings and enforce mode="real" requirements independently of
these structural schema checks.

## Failure contract

`ContractError(ValueError)` signals an invalid field/invariant during construction
or validation. Wrong/unknown constructor arguments raise `TypeError`. Runtime
modules expose `PipelineError` containing `.error: ErrorInfo`; the orchestrator
translates constructor failures instead of leaking them to CLI users.

ErrorInfo requires nonempty `message`, `code`, `stage`, and schema_version=1.0.0.
stage is one of configuration, preprocessing, pitch, timbre, profile,
recommendation. No field is nullable. The CLI emits the ErrorInfo object directly
to stderr with exit 2; no PipelineResult or partial recommendations on failure.

| Code | Trigger / stage |
| --- | --- |
| audio_not_found | Missing local path / preprocessing |
| unsupported_audio | Extension, codec, channel count or source rate not supported / preprocessing |
| invalid_audio | Not a file, unreadable, malformed, zero frames, invalid header/data / preprocessing |
| audio_too_short | Nonempty recording shorter than 0.5 s / preprocessing |
| audio_too_long | Recording longer than 60 s / preprocessing |
| silent_audio | Final waveform below agreed RMS floor / preprocessing |
| invalid_features | Analyzer or profile schema violation / pitch, timbre or profile |
| invalid_catalog | Malformed catalog, duplicate IDs, invalid recommender output/catalog references / recommendation |
| invalid_configuration | Unsupported mode, top_k, target rate, missing real dependencies, provenance incompatible with real mode / configuration |
| module_failure | Unexpected decoder/adapter exception after input checks / failing stage |

Known decode errors map to invalid_audio, not generic module_failure. No voiced
pitch is a valid result, not an error. Day 3 additionally reports invalid_audio
at pitch/timbre when an analyzer leaves its AudioData input invalid, and at
preprocessing when an injected preprocessor ignores the requested sample rate.
Declared mock rankers must label their recommendations mock regardless of input
provenance; contradictory outputs fail with invalid_catalog.

No automatic fallback, fabricated fields,
or success-shaped error objects. Runtime adapters preserve causes for debugging
locally without putting paths, traces or personal data in public messages.

## Sample JSON

The examples below are schema-valid fixtures, not measured participant data.
AudioData is deliberately abbreviated by using a tiny valid representation;
all other examples are complete, including nested contracts and nullable fields.

### AudioData

```json
{
  "waveform": [
    0.0,
    0.25,
    -0.25,
    0.0
  ],
  "sample_rate": 16000,
  "duration_s": 0.00025,
  "warnings": [],
  "schema_version": "1.0.0"
}
```

### PitchFeatures

```json
{
  "min_pitch_hz": 110.0,
  "max_pitch_hz": 330.0,
  "median_pitch_hz": 220.0,
  "voiced_ratio": 0.8,
  "confidence": null,
  "mode": "mock",
  "model_version": "mock-pitch-v1",
  "warnings": [
    "Synthetic fixture values; not measured from audio."
  ],
  "schema_version": "1.0.0"
}
```

### PitchFeatures (no voiced frames)

```json
{
  "min_pitch_hz": null,
  "max_pitch_hz": null,
  "median_pitch_hz": null,
  "voiced_ratio": 0.0,
  "confidence": null,
  "mode": "real",
  "model_version": "example-detector-config-v1",
  "warnings": [
    "No accepted voiced frames."
  ],
  "schema_version": "1.0.0"
}
```

### TimbreFeatures

```json
{
  "mfcc_mean": [
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0
  ],
  "spectral_centroid_mean_hz": 1000.0,
  "mode": "mock",
  "model_version": "mock-timbre-v1",
  "processing_version": "mock-mfcc-20-v1",
  "warnings": [
    "Synthetic fixture values; not measured from audio."
  ],
  "schema_version": "1.0.0"
}
```

### VoiceProfile

```json
{
  "pitch": {
    "min_pitch_hz": 110.0,
    "max_pitch_hz": 330.0,
    "median_pitch_hz": 220.0,
    "voiced_ratio": 0.8,
    "confidence": null,
    "mode": "mock",
    "model_version": "mock-pitch-v1",
    "warnings": [
      "Synthetic fixture values; not measured from audio."
    ],
    "schema_version": "1.0.0"
  },
  "timbre": {
    "mfcc_mean": [
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0
    ],
    "spectral_centroid_mean_hz": 1000.0,
    "mode": "mock",
    "model_version": "mock-timbre-v1",
    "processing_version": "mock-mfcc-20-v1",
    "warnings": [
      "Synthetic fixture values; not measured from audio."
    ],
    "schema_version": "1.0.0"
  },
  "analysis_mode": "mock",
  "status": "warning",
  "warnings": [
    "Synthetic pitch and timbre; not measured from the supplied recording."
  ],
  "schema_version": "1.0.0"
}
```

### SongFeatures

```json
{
  "song_id": "mock-001",
  "title": "Demo Song One (fictional)",
  "artist": "Mock Artist",
  "melody_min_pitch_hz": null,
  "melody_max_pitch_hz": null,
  "feature_version": "mock-catalog-v1",
  "provenance": "mock",
  "source_description": "Fictional catalog fixture; no verified melody range.",
  "schema_version": "1.0.0"
}
```

### Recommendation

```json
{
  "song_id": "mock-001",
  "title": "Demo Song One (fictional)",
  "artist": "Mock Artist",
  "score": 0.9,
  "explanation": "Fixed mock rank; does not measure suitability for your voice.",
  "scoring_version": "mock-fixed-v1",
  "mode": "mock",
  "schema_version": "1.0.0"
}
```

### PipelineResult

```json
{
  "voice_profile": {
    "pitch": {
      "min_pitch_hz": 110.0,
      "max_pitch_hz": 330.0,
      "median_pitch_hz": 220.0,
      "voiced_ratio": 0.8,
      "confidence": null,
      "mode": "mock",
      "model_version": "mock-pitch-v1",
      "warnings": [
        "Synthetic fixture values; not measured from audio."
      ],
      "schema_version": "1.0.0"
    },
    "timbre": {
      "mfcc_mean": [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0
      ],
      "spectral_centroid_mean_hz": 1000.0,
      "mode": "mock",
      "model_version": "mock-timbre-v1",
      "processing_version": "mock-mfcc-20-v1",
      "warnings": [
        "Synthetic fixture values; not measured from audio."
      ],
      "schema_version": "1.0.0"
    },
    "analysis_mode": "mock",
    "status": "warning",
    "warnings": [
      "Synthetic pitch and timbre; not measured from the supplied recording."
    ],
    "schema_version": "1.0.0"
  },
  "recommendations": [
    {
      "song_id": "mock-001",
      "title": "Demo Song One (fictional)",
      "artist": "Mock Artist",
      "score": 0.9,
      "explanation": "Fixed mock rank; does not measure suitability for your voice.",
      "scoring_version": "mock-fixed-v1",
      "mode": "mock",
      "schema_version": "1.0.0"
    }
  ],
  "pipeline_version": "0.1.0",
  "analysis_mode": "mock",
  "processing_time_s": null,
  "schema_version": "1.0.0"
}
```

### ErrorInfo

```json
{
  "code": "silent_audio",
  "message": "Recording is below the silence floor.",
  "stage": "preprocessing",
  "schema_version": "1.0.0"
}
```
