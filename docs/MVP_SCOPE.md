# Local MVP scope

Day 1 foundation with Day 2 implementation status, 2026-11-01. This document governs the current integration
milestone; the root README retains the broader research proposal.

## Deliverable

One local singing WAV file enters the pipeline. A JSON result contains a typed
voice profile and at most five ranked song recommendations, scores, explanations,
versions, provenance, and processing time. The first runnable version will use
real WAV preprocessing and deterministic mock analysis and recommendations.
Mock numbers are fixtures, never measurements of the supplied recording.

The MVP needs no cloud service, API key, database, GUI, streaming integration,
trained recommendation model, identity matching, artist matching, or full catalog.
Key suggestions, rhythm, vibrato, tessitura and accuracy scoring are deferred.
Observed pitch range from a short recording is not total singing capability.
Timbre descriptors alone do not establish song suitability.

## Repository inspection

The initial working tree was clean on `fix/experiment-review-notes` (`1b10fba`).
Git origin is `https://github.com/Jeminana/SUARA-System.git`; fetched `origin/main`
is `9113812`. Its tree matched the starting branch, with one additional merge
commit. `feature/main-pipeline` was created from that integration base. Local
`main` remains unchanged (four commits behind the fetched remote).

Local experiment branches E1 through E9 exist. Their local tips are not uniformly
current: E1 is behind its tracking branch by one commit and E3 by eleven. E6 is
at `b2d1e77`. Integration uses merged main content, not a checkout of a stale
experiment branch. No experiment branch is changed by this work.

| Existing area | What exists | Reuse boundary |
| --- | --- | --- |
| `experiments/E1/` | Synthetic pitch study, scripts, fixtures, reports, results and tests; `suara_e1` is a namespace, not an application analyzer | Detector research and evaluation fixtures inform a future pitch adapter; do not import evaluation scripts into orchestration |
| `experiments/E3/` | Song/reference melody analysis, pYIN/Basic Pitch/Demucs routes, note profiles, catalog tools, tests; interim real-singer results | Teammate maps reviewed melody endpoints and provenance into `SongFeatures` |
| `experiments/E6/` | ECAPA embedding and MFCC baseline, consent-aware manifests, recording/QC pipeline and pilot documentation | Teammate implements a timbre adapter; do not equate ECAPA identity retrieval with suitability |
| Other experiments | Mostly planning READMEs | No production interfaces assumed |
| `main_pipeline/` | Reserved shared pipeline directory with README | Keep all shared application source here |

The prompt's E3/E6 labels differ from repository labels: E3 is song analysis;
E6 is voice embedding using collected participant recordings. Preserve these
existing identities and results. The user reports completed baselines; repository
documentation still calls E3 results interim. Day 1 does not revise that status.

No shared package, packaging configuration, application schemas, CLI, or pipeline
tests existed at inspection. Experiment environments are separate: E1 lists
NumPy/librosa and optional CREPE dependencies; E3 pins a Python 3.11 stack due to
Basic Pitch/TensorFlow; E6 documents Python 3.12 with Torch/SpeechBrain/librosa.
Do not merge their requirement files. Python 3.12.10 is available locally.
Git requires a command-scoped `safe.directory` exception on this filesystem;
no global Git configuration was changed.

## Three-day ownership and completion gates

| Phase | Main Pipeline Lead deliverable | Gate |
| --- | --- | --- |
| Day 1 (complete) | Scope, architecture, contracts, teammate guide, typed schemas and protocols | Import/compile schemas; validate documentation examples and reject representative invalid values |
| Day 2 (implemented; awaiting review) | Lightweight package setup, WAV preprocessing, mock modules/catalog, profile assembly, orchestrator, CLI | Generated WAV reaches explicit mock JSON without external models |
| Day 3 (pending) | Synthetic fixture tests, installation/run documentation, validation report | Full relevant tests and CLI executed with actual counts reported |

Teammates own reusable real pitch/timbre modules, song analysis/catalog, storage,
and evaluated recommendation methods. Main Pipeline Lead owns boundary validation,
error mapping, injection, orchestration, and local CLI integration.

## Acceptance rules for Days 2 and 3

- Default path is offline mock mode. Every mock feature and recommendation has
  explicit provenance; profile warnings say values are synthetic and not measured.
- No silent fallback to mocks when real modules fail or are missing.
- Valid mono/stereo WAV is preprocessed consistently; invalid, silent, empty,
  too-short or too-long audio fails with a stable error code.
- Unvoiced non-silent audio has null pitch statistics and no fabricated range.
- Recommendations are unique, score in [0,1], sorted deterministically, and limited
  to `min(top_k, catalog size)`; fewer or zero results are allowed.
- Tests generate synthetic WAVs; no private E6 recordings or embeddings are committed.
- No accuracy or suitability claim is made from mock integration or the pilot alone.

## Day 1 status and assumptions

Completed: documented boundaries, typed schemas, versions, callable protocols,
injection bundle and error payload. Python 3.12.10 contract smoke checks passed
51 checks: nine documentation JSON round-trips, representative invalid inputs,
nested mutation rejection, no-voiced handling, absence of model imports, and syntax
checks. These were inline development checks, not a committed test suite. No
pipeline or experiment test suite was run at that stage. Runtime implementation
followed in Day 2 as recorded below.

Approved defaults: 16 kHz mono, 0.5–60 s inputs, peak-preserving
preprocessing, 20 MFCC coefficients including c0 under a new processing version,
and five results by default. These are application decisions, not inherited
validated experiment settings. See the contract for exact parameters and risks.

## Day 2 delivery status

Completed: installable `suara-main-pipeline` 0.1.0 package, real PCM WAV ingestion,
mono conversion, anti-aliasing resampling, bounded duration/QC, deterministic mock
analyzers, fictional catalog, fixed-order mock ranking, profile assembly,
dependency-injected orchestration, JSON CLI and console entry point. Day 1's
`contracts.py` and schema 1.0.0 are unchanged. No experiment files were changed.
No real AI, database, GUI or service was implemented.

Validation actually executed on Python 3.12.10 in `main_pipeline/.venv`:

```powershell
main_pipeline/.venv/Scripts/python.exe -m pip install -e main_pipeline
main_pipeline/.venv/Scripts/python.exe -m unittest discover -s main_pipeline/tests -v
main_pipeline/.venv/Scripts/python.exe -m pip check
main_pipeline/.venv/Scripts/python.exe main_pipeline/tools/generate_smoke_wav.py
main_pipeline/.venv/Scripts/python.exe -m suara.cli --audio main_pipeline/.smoke/tone.wav --mode mock
```

The final smoke run passed **13 tests in 7.517 seconds**, including PCM widths,
extensible PCM/header checks, stereo averaging, resampling, basic invalid audio,
determinism, custom injection with test-only stubs, no-voiced fields, module error
mapping, absence of model imports, and CLI JSON streams. `pip check` reported no
broken requirements. Installed NumPy is 2.5.4; SciPy is 1.18.1. Venv/pip initially
hit sandbox temporary-file permissions and completed after permission was granted;
the normal user setup commands above do not require a repository-specific workaround.

The generated one-second stereo 44100 Hz WAV was downmixed/resampled to mono
16000 Hz. CLI exit was 0 with profile status `warning`, mode `mock`, and five
fictional songs scored 0.9 through 0.5. The later CLI run reported 5.270 s pipeline
processing time in this environment; this includes dependency initialization and
is not a performance benchmark. The installed console entry point also returned
three results with `--top-k 3`. Missing input, unavailable real mode and top_k=0
each returned exit 2, no stdout, and the expected error JSON on stderr.

Manual output is available locally at ignored `main_pipeline/.smoke/result.json`.
No generated WAV or result is committed. No experiment test suite was run.

Limitations: all feature numbers/ranks are synthetic; mock voiced_ratio does not
detect singing. Real mode is usable only through explicitly injected Python
adapters/catalog, and the bundled CLI deliberately rejects it. Runtime validation
cannot prove truthful upstream provenance. The PCM parser intentionally rejects
float/compressed, big-endian/RF64, reduced-valid-bit extensible or malformed WAV.
List-based waveform validation and dependency startup have costs; latency is not
yet optimized or benchmarked. Private E6 audio was not opened or used for tests.

Day 3 remains: broaden boundary and regression coverage (duration endpoints/long
files, unusual rate ratios, alias suppression, clipping/overshoot, silence floor,
schema mutations, catalog/ranking/provenance failures), review packaging across
clean environments, and write the final integration validation report. Teammates
still own reusable real analyzers, reviewed song data and evaluated ranking.
