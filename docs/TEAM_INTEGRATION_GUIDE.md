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

E6's current baseline uses 20 MFCCs with `include_c0: false` and development-fitted
z-score scaling. It is NOT equivalent to `mfcc-20-v1` defined here (includes c0,
no fitted scaling). Re-extract under the agreed parameters or propose a versioned
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

The complete pipeline suite is Day 3 work; Day 2 includes basic smoke tests. The
Main Pipeline Lead must not report application or experiment test suites as passed
based solely on schema checks. No pushes, main merges, or branch deletions are
part of this Day 2 task.
