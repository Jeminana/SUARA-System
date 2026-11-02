# Team integration guide

Use [INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md) as the application boundary
and `main_pipeline/src/suara/contracts.py` as its executable definition. Research
outputs remain in their experiment directories. Do not change locked experiments
to make them resemble application modules.

## Module handoff

| Owner | Input | Output | Required work |
| --- | --- | --- | --- |
| Pitch teammate | `AudioData` | `PitchFeatures` | Adapt E1 research into a reusable analyzer; record detector/version, frame grid, search limits, voicing threshold, confidence semantics and range aggregation |
| Timbre teammate | `AudioData` | `TimbreFeatures` | Implement agreed MFCC representation and centroid; record exact processing/model versions; do not reuse ECAPA identity vectors as MFCCs |
| Song analysis/catalog teammate | Licensed/reviewed melody sources outside the runtime | `Sequence[SongFeatures]` | Map reviewed E3 note ranges to Hz; retain source/excerpt/verification information; export without pulling Python 3.11 models into the app |
| Database teammate | Typed song/profile records | Catalog sequence, later persistence adapter | Preserve schema and feature versions; no DB required for the first local pipeline |
| Recommendation teammate | Profile, catalog, `top_k` | `list[Recommendation]` | Return bounded, deterministic scores and evidence-based explanations; document scoring formula and limitations |
| Main Pipeline Lead | WAV plus selected dependencies/catalog | `PipelineResult` | Preprocessing, validation, assembly, orchestration, mode enforcement, error mapping and CLI |

## Implement a callable adapter

Day 1 supplies the protocols; Day 2 supplies the runtime and mock adapters. The
following is a signature sketch for a teammate, not runnable
analysis; the teammate supplies the implementation in their module:

```python
from suara.contracts import AudioData, PitchFeatures

def analyze_pitch(audio_data: AudioData) -> PitchFeatures:
    # Validate input, run the selected detector, aggregate its valid voiced frames,
    # return a validated PitchFeatures(mode="real", model_version=...).
    raise NotImplementedError("teammate implementation")
```

Use exactly the argument names in the protocols to support keyword callers.
Do not mutate the waveform, profile, or catalog. Convert NumPy scalars/arrays
to Python values/lists before constructing contracts. Null statistics are
intentional; never substitute zero Hz or NaN. Explicitly distinguish no voiced
frames (valid result) from algorithm failure (exception).

E3 MIDI conversion, when the upstream values are MIDI semitones, is
`Hz = 440 * 2 ** ((midi - 69) / 12)`. Preserve excerpt scope and reviewed-source
information in `source_description`. An instrumental/polyphonic spectrum is not
a vocal melody range. Unverified data must retain `provenance="unverified"`.

E6's current baseline is incompatible with `mfcc-20-v1`; see the exact migration
table below. Re-extract under the agreed parameters or propose a versioned
contract change. Never relabel old coefficients or embeddings to pass validation.

## Replace mocks without changing orchestration (Day 2 API)

```python
from suara.contracts import PipelineDependencies
# Day 2 runtime; my_team imports are supplied by teammates.
from suara.pipeline import run_pipeline
from suara.audio.preprocessing import preprocess_audio
from my_team.pitch import analyze_pitch
from my_team.timbre import analyze_timbre
from my_team.recommender import recommend_songs

dependencies = PipelineDependencies(
    preprocess_audio=preprocess_audio,
    analyze_pitch=analyze_pitch,
    analyze_timbre=analyze_timbre,
    recommend_songs=recommend_songs,
)
result = run_pipeline(
    "local.wav", mode="real", dependencies=dependencies,
    song_catalog=reviewed_catalog, top_k=5,
)
```

`reviewed_catalog` is a teammate-provided sequence, not a global service. First
replace one component in mock mode and check its individual provenance. Enable
real mode only with all required real implementations and an explicit catalog.
No real model loading or checkpoint download may occur in mock mode imports/tests.
An algorithm that is real but unvalidated must still document its limitations.

## Local Day 1 check

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = (Resolve-Path main_pipeline/src).Path
python -c "from suara.contracts import SCHEMA_VERSION; print(SCHEMA_VERSION)"
```

Use Python 3.12. No pip installation is required for these schemas. Day 2 adds
the installable package; see [the pipeline README](../main_pipeline/README.md)
for editable installation, CLI and smoke-test commands. Use a separate pipeline
virtual environment. The tests include a custom dependency bundle and test-only
stubs to exercise the API; those stubs are not real analysis implementations.

Known mock callables expose an optional `suara_mode="mock"` marker and are rejected
before invocation in real mode. All analyzer/recommendation output modes are also
validated. Marker-free teammate implementations must label their output truthfully;
runtime validation cannot prove that a claimed real algorithm actually ran.
The preprocessor must honor the requested 16000 Hz rate. Audio is revalidated
after each analyzer, so invalid nested mutation fails at the responsible stage
with `invalid_audio`. This catches invalid values, not every possible valid edit:
adapters must still treat inputs as read-only. A declared mock ranker must return
mock recommendations even when its inputs are real-labeled.

Expected `PipelineError` payloads are preserved: adapters must use safe public
messages, keep private paths/traces in the exception cause, and never silently
return mocks on failure.

## Adapter tests and pull requests

1. Branch from the team's current integration base. Keep experiment assets intact
   and scope changes to the adapter and its dependencies/tests.
2. Add isolated tests for normal input, finite values, no voiced frames, failure
   mapping, deterministic behavior where promised, and exact model/processing
   versions. Use generated tones/noise/WAVs, never private E6 recordings.
3. Check `validate()` and strict JSON output. Reject unsupported rates or parameters
   explicitly rather than returning a vector under the wrong version.
4. Exercise the adapter through `PipelineDependencies` in mock mode, then real mode
   if the other required components are available. Check no mutation, ranking
   count/order/IDs, provenance and understandable error payloads.
5. Record actual commands/results, runtime requirements, offline/checkpoint needs,
   algorithm limitations and any experiment-to-application transformations.
6. Review `git diff --check`, `git diff`, and `git status`; exclude recordings,
   caches, embeddings, credentials and virtual environments. Open a PR to the
   agreed integration branch, identifying contract versions and sample input/output.
   Coordinate contract changes before changing field meanings or dimensions.

The Day 3 suite and actual measurements are recorded in
[DAY3_VALIDATION_REPORT.md](DAY3_VALIDATION_REPORT.md). Application validation
does not establish experiment/model accuracy. Pushes and merges require explicit
approval; keep this handoff on `feature/main-pipeline` until review.

## Install and test an adapter independently

From the repository root, use a dedicated Python 3.12 environment:

```powershell
python -m venv main_pipeline/.venv
main_pipeline/.venv/Scripts/python.exe -m pip install -e main_pipeline
main_pipeline/.venv/Scripts/python.exe main_pipeline/tools/generate_smoke_wav.py
main_pipeline/.venv/Scripts/python.exe -m unittest discover -s main_pipeline/tests -v
main_pipeline/.venv/Scripts/python.exe -m pip check
```

Install a teammate adapter's pinned optional dependencies into its own development
environment first. Do not add E1/E3/E6 dependency stacks to the default mock path.
E3 uses Python 3.11; export typed metadata across that boundary rather than importing
the experiment into this Python 3.12 package.

For a pitch adapter, an independent smoke check looks like this; change the import
to the teammate module. Repeat for timbre and call `validate()`/`to_json()` on its
output. This checks structure only; detector accuracy needs separate evaluation.

```python
from suara.audio.preprocessing import preprocess_audio
from suara.contracts import PitchFeatures
from my_team.pitch import analyze_pitch

audio = preprocess_audio('main_pipeline/.smoke/tone.wav')
before = audio.to_dict()
features = analyze_pitch(audio)
assert isinstance(features, PitchFeatures)
assert features.mode == 'real'
features.validate()
features.to_json()
assert audio.to_dict() == before
```

`test_integration.py` contains small test-only adapters for every injection point,
including unvoiced pitch, missing melody information and an empty catalog. These
are wiring tests, not real algorithms or evaluated models.

## Minimal module examples

The following adapter sketches wrap teammate-owned implementations. Imports from
`my_team` are placeholders to replace; no detector, MFCC extractor or suitability
model is supplied by these examples.

### E1 pitch

The detector wrapper supplies accepted positive finite F0 values and a voiced ratio
using its documented frame grid, confidence threshold and rejection policy.
`confidence` is nullable; do not substitute voiced ratio for detector confidence.

```python
from statistics import median
from suara.contracts import AudioData, PitchFeatures
from my_team.detector import accepted_frames

def analyze_pitch(audio_data: AudioData) -> PitchFeatures:
    audio_data.validate()
    hz, ratio, confidence = accepted_frames(audio_data)
    # accepted_frames returns Python floats in Hz; no NaN or zero sentinels.
    return PitchFeatures(
        min_pitch_hz=min(hz) if hz else None,
        max_pitch_hz=max(hz) if hz else None,
        median_pitch_hz=float(median(hz)) if hz else None,
        voiced_ratio=float(ratio), confidence=confidence, mode='real',
        model_version='replace-with-detector-checkpoint-and-config-version',
        warnings=[] if hz else ['No accepted voiced frames.'],
    )
```

If no frames are accepted, the wrapper must return ratio zero and all three pitch
statistics null. Record the model version, frame size/hop, search bounds, confidence
interpretation, threshold and equal-weight min/max/median aggregation in the PR.

### E6 timbre

The upstream function below must implement and verify the exact convention in
[INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md#timbrefeatures). Giving the version
string to an incompatible vector does not make it compatible.

```python
from suara.contracts import AudioData, TimbreFeatures
from my_team.descriptors import extract_mfcc20_v1

def analyze_timbre(audio_data: AudioData) -> TimbreFeatures:
    audio_data.validate()
    coefficients, centroid = extract_mfcc20_v1(audio_data)
    return TimbreFeatures(
        mfcc_mean=[float(value) for value in coefficients],
        spectral_centroid_mean_hz=None if centroid is None else float(centroid),
        mode='real', model_version='replace-with-extractor-and-library-version',
        processing_version='mfcc-20-v1', warnings=[],
    )
```

| Setting | Locked E6 baseline | Pipeline `mfcc-20-v1` | Required action |
| --- | --- | --- | --- |
| Waveform | 16 kHz mono, soxr_hq resampling, edge trim at 40 dB, peak gain to -1 dBFS | Pipeline waveform, gain preserved, no trim, polyphase resampling when needed | Extract from `AudioData`; do not run E6 trim/gain policy again |
| Coefficients | `n_mfcc=20`, then remove c0: c1..c19 | c0..c19 | Re-extract c0 and all agreed coefficients |
| Pooling/dimension | 19 means + 19 standard deviations = 38 values | 20 arithmetic means only | Do not slice/pad the saved 38-vector |
| Scaling | Development-fitted z-score, then evaluation L2 normalization | Neither fitted scaling nor L2 normalization | Re-extract raw means; saved normalized embeddings cannot restore c0 |
| STFT | `n_fft=512`, hop=160; other settings inherited from librosa defaults | Periodic Hann, 512, hop=160, `center=False`, complete frames only | Explicitly set every parameter; remove centered padding |
| Mel/log/DCT | 40 mel bands; remaining settings inherited from librosa, including its default dB behavior | 40 Slaney-normalized filters, Slaney scale, 0..8000 Hz; power; log floor 1e-10, ref=1, no top-dB cap; orthonormal DCT-II, no lifter | Set explicitly and verify numerical parity; do not rely on defaults |
| Centroid | No centroid in the saved embedding | Magnitude-weighted centroid, mean over nonzero frames, null if none | Extract separately; enforce Nyquist bound |
| ECAPA | Separate identity embedding | No embedding field in schema 1.0.0 | Keep separate; propose a schema change before using embeddings |

Evidence: `experiments/E6/config.yaml`, `e6/models.py` (`embed`, `postprocess`),
`e6/audio.py`, and the E6 README. These files were inspected only. The locked
baseline's librosa defaults must be confirmed against its actual environment if
reproducing that experiment; no E6 model or private recording is loaded here.
Implement the application adapter separately and preserve locked E6 outputs.

### E3 song features

The catalog is passed separately to `run_pipeline`; it is not an analysis callback
inside `PipelineDependencies`. Export reviewed vocal/melody ranges, not extrema of
a full mix's spectrum. Convert MIDI semitones to Hz exactly once.

```python
from suara.contracts import SongFeatures

def reviewed_song(row) -> SongFeatures:
    def hz(note):
        return 440.0 * 2 ** ((note - 69) / 12)
    # row is a reviewed, licensed excerpt export; no audio loading here.
    return SongFeatures(
        song_id=row['song_id'], title=row['title'], artist=row['artist'],
        melody_min_pitch_hz=hz(row['min_midi']),
        melody_max_pitch_hz=hz(row['max_midi']),
        feature_version=row['feature_version'], provenance='verified_melody',
        source_description=row['public_review_and_excerpt_description'],
    )
```

Only use `verified_melody` when review evidence supports it. For unknown ranges,
use both endpoints null and `unverified`. No private file paths or identities
belong in source descriptions. Unit-test MIDI 69 -> 440 Hz and preserve excerpt
boundaries, extraction version, source type and review status.

### Recommendation

The teammate's rule supplies finite normalized scores and explanations, skips
unsupported missing-data comparisons, and records its formula and limitations.
Scores are not probabilities. The adapter returns a ranked unique catalog subset.

```python
from suara.contracts import Recommendation, SongFeatures, VoiceProfile
from suara.errors import validate_top_k
from my_team.scoring import score_supported_songs

def recommend_songs(voice_profile: VoiceProfile,
                    song_catalog: list[SongFeatures], top_k: int = 5):
    validate_top_k(top_k)
    voice_profile.validate()
    for song in song_catalog:
        song.validate()
    # Each eligible song occurs once; missing pitch must be handled in this rule.
    scored = score_supported_songs(voice_profile, song_catalog)
    ranked = sorted(scored, key=lambda item: (-item[1], item[0].song_id))[:top_k]
    return [Recommendation(
        song_id=song.song_id, title=song.title, artist=song.artist,
        score=float(score), explanation=explanation,
        scoring_version='replace-with-reviewed-rule-version',
        mode='mock' if voice_profile.analysis_mode == 'mock' or song.provenance == 'mock' else 'real',
    ) for song, score, explanation in ranked]
```

An empty catalog must produce `[]`. Do not infer vocal suitability from unavailable
pitch or unverified song melody ranges. A synthetic scorer must label itself and
its outputs mock, disclose synthetic ranking in explanations, and never use the
real-rule sketch to hide synthetic origin.

## Recommended integration order

1. E1 pitch: implement measured F0 and the unvoiced path; validate standalone.
2. E6 timbre: re-extract the agreed descriptors; verify parameter parity.
3. E3 catalog: export reviewed Hz melody ranges and public source provenance.
4. Recommendation: implement missing-data handling and an evaluated scoring rule.
5. Main Pipeline Lead: connect each through `PipelineDependencies`, check mixed
   provenance in mock mode, then run real mode with all actual implementations.

Each teammate should open a reviewable PR targeting the agreed integration branch,
include isolated synthetic tests and measured environment/model requirements, and
avoid changing experiment assets. Re-run the full pipeline suite after each
adapter lands. End-to-end real-mode success will verify integration; separate
human/reference evaluation is still needed for accuracy and recommendation value.
