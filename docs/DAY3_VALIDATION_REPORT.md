# Day 3 validation report

Validation date: 2026-11-02 (Asia/Seoul). Branch: `feature/main-pipeline`.

## Executive summary

The local pipeline is ready for teammates to integrate real modules through the
existing callable interfaces. Day 3 expands synthetic automated coverage, fixes
four runtime boundary defects, verifies success/error CLI behavior, measures
mock-runtime performance, and documents the E6 feature migration. Real pitch,
timbre and suitability models remain teammate work; these checks do not establish
AI accuracy or recommendation usefulness.

Final verification: **62 tests passed, 0 failed, 0 skipped**. Ten separate CLI
demonstrations returned the expected exit codes and JSON. Dependency checks,
package imports, mock-mode AI import isolation and whitespace checks passed.
Tracked E1/E3/E6 experiment contents remain unchanged. No push, merge, commit,
branch deletion or external publication was performed.

## Implementation status and scope

| Component | Status |
| --- | --- |
| PCM WAV loading, downmix, resampling and QC | Implemented and tested with generated audio |
| Eight wire contracts and JSON serialization | Validated, including invalid nested mutation |
| Sequential orchestration and dependency injection | Implemented; Day 3 hardens adapter boundaries |
| Pitch/timbre analyzers | Explicit deterministic synthetic fixtures only |
| Catalog/recommendation | Fictional catalog and synthetic fixed-score ranker only |
| Real-mode API | Validated using test-only adapters; requires explicit dependencies/catalog |
| Real-mode CLI | Intentionally unavailable; returns structured configuration error |
| Real AI, GUI, training, database | Outside Day 3 scope |

Created:

- `main_pipeline/tests/helpers.py`: synthetic PCM writer and small fixtures.
- `main_pipeline/tests/test_audio.py`: preprocessing and numerical regressions.
- `main_pipeline/tests/test_contracts.py`: all eight contract boundaries.
- `main_pipeline/tests/test_integration.py`: injected adapters, provenance and CLI.
- `main_pipeline/tools/validate_day3.py`: repeatable offline validation/benchmarking.
- `main_pipeline/validation_logs/`: actual command records, outputs and measurements.
- This report.

Modified: `pipeline.py`, the root and pipeline READMEs, integration contract notes
and the team integration guide. Contract fields, schema version 1.0.0, package
version 0.1.0, dependency requirements and the architecture are preserved.
No new runtime framework or AI library was added.

## Environment

The existing editable pipeline installation was used; no dependency download was
needed. Package imports resolved to this workspace's source tree.

| Item | Actual value |
| --- | --- |
| Python | CPython 3.12.10, MSC v.1943, 64-bit AMD64 |
| OS | Windows 11, build 26200 |
| Logical processors | 16 |
| NumPy | 2.5.4 |
| SciPy | 1.18.1 |
| pip | 25.0.1 |
| suara-main-pipeline | 0.1.0, editable installation |
| Interpreter | `main_pipeline/.venv/Scripts/python.exe` |

`pip check` returned `No broken requirements found.` Imports of `suara` and the
contracts loaded no NumPy, SciPy or AI libraries. A full mock invocation, including
resampling, loaded no Torch, TensorFlow, librosa, SpeechBrain, CREPE or Transformers.
No checkpoint was downloaded and no participant recording was opened.

## Tests performed

| Area | Coverage |
| --- | --- |
| PCM support | All 32 combinations of 8/16/24/32-bit, 8/16/44.1/48 kHz, mono/stereo; signed sample decoding and exact arithmetic downmix |
| Durations | 0.5 and 60 seconds accepted; one frame outside each endpoint rejected; zero frames rejected |
| Audio quality | Silence, near-silence below/above floor, clipping warnings, preserved gain, stereo cancellation |
| Containers | Corruption, truncation, RIFF/chunk bounds, trailing bytes, wrong headers, missing/duplicate chunks, unknown metadata chunks, frame/byte-rate errors, final odd-byte data, extensible PCM and invalid extensions |
| Unsupported inputs | Float/compressed WAV, RF64/RIFX, wrong extension, unsupported bit depths/channels/rates, directory input, missing file, invalid target rates |
| Resampling | 16 kHz output, rounded fractional lengths, preserved passband amplitude, finite bounded output and warned overshoot |
| Aliasing | 48 -> 16 kHz with 1 kHz passband + 12 kHz stopband tones; interior error RMS below 0.001, over 49 dB suppression relative to stopband input |
| Contracts | Required/unknown fields, nonnullable fields, null semantics, types, bool/nonfinite/overflow numbers, pitch ranges, MFCC dimension, schema versions, scores, nested object types |
| Mutability | Revalidate changed waveform, warning lists, MFCC lists and recommendation lists; reject invalid adapter mutations |
| Pipeline | Actual preprocessing input shared with analyzers; profile assembly and warnings; catalog identity; top_k 1..5; empty catalog; deterministic sorted unique references/metadata |
| Provenance | Synthetic disclosures; mixed analyzers; explicit real-mode dependencies; reject declared mocks and hidden mock outputs; reject mock catalogs in real mode |
| Adapter handoff | Test-only pitch/timbre/ranking adapters; unvoiced pitch with null statistics; synthetic MIDI 69/81 -> 440/880 Hz export, source description retained |
| Failures/privacy | Wrong return types and unexpected exceptions at every injected stage; private-looking exception details retained only as local causes; safe expected PipelineError preserved |
| CLI | JSON output channels, success/error exits, top_k, invalid arguments, real-mode rejection; fresh-process import isolation |

All recordings are generated synthetically under ignored `main_pipeline/.smoke/`.
Subtests exercise parameter matrices; the test count is unittest test methods,
not a claim that every subcase is a separately counted test.

Observed progression:

| Run | Passed | Failed | Errors | Skipped |
| --- | ---: | ---: | ---: | ---: |
| Original Day 2 smoke suite | 13 | 0 | 0 | 0 |
| Expanded suite before runtime fixes | 53 | 3 | 1 | 0 |
| First run after fixes | 57 | 0 | 0 | 0 |
| Final suite, including additional handoff/nullability checks | 62 | 0 | 0 | 0 |

The original experiments' model suites were not run: Day 3 concerns the local
pipeline, and experiment/model dependencies and participant data are excluded.
There are no skipped tests in the relevant pipeline suite.

## Actual commands and evidence

Run from the repository root in PowerShell:

```powershell
main_pipeline/.venv/Scripts/python.exe -m unittest discover -s main_pipeline/tests -v
main_pipeline/.venv/Scripts/python.exe -m pip check
main_pipeline/.venv/Scripts/python.exe main_pipeline/tools/validate_day3.py
main_pipeline/.venv/Scripts/python.exe main_pipeline/tools/validate_day3.py --checks-only
main_pipeline/.venv/Scripts/python.exe -m suara.cli --audio main_pipeline/.smoke/day3/1s_48000hz_2ch.wav --mode mock
git -c safe.directory=D:/hy-edu-2026/SUARA-System diff --check
git -c safe.directory=D:/hy-edu-2026/SUARA-System status --short
git -c safe.directory=D:/hy-edu-2026/SUARA-System diff --exit-code HEAD -- experiments/E1 experiments/E3 experiments/E6
```

The full runner generates fixtures, executes the suite/CLI/import/dependency
checks, benchmarks eight input configurations and records Git checks. The final
`--checks-only` run refreshes verification while retaining the original performance
samples and their timestamp. Import probe commands and exact subprocess arguments
are recorded in each JSON log. `tests.txt` contains the complete final unittest
output; `before_fixes.txt` preserves the failing regression evidence.

Git initially refused this filesystem's ownership metadata. Commands use a
per-command `safe.directory` value for this exact repository; no global Git
configuration was changed. No permission-blocked task remains.

Evidence links:

- [Final test output](../main_pipeline/validation_logs/tests.txt)
- [Environment, performance samples and check summary](../main_pipeline/validation_logs/summary.json)
- [Successful CLI transcript](../main_pipeline/validation_logs/cli_success.json)
- [Example failure transcript](../main_pipeline/validation_logs/cli_corrupt.json)
- [Dependency check](../main_pipeline/validation_logs/dependencies.json)
- [AI import isolation](../main_pipeline/validation_logs/mock_imports.json)

## End-to-end results

Each invocation uses `python -m suara.cli`; its complete argv/stdout/stderr/exit
code is in the corresponding `validation_logs/cli_*.json` file.

| Case | Exit | JSON result |
| --- | ---: | --- |
| 1 s, 48 kHz stereo, mock mode | 0 | Mono/resampling warnings, synthetic profile, five fictional recommendations |
| 1 s, 16 kHz mono, top_k=2 | 0 | Synthetic profile, two recommendations |
| Silence | 2 | `silent_audio`, preprocessing |
| 0.1 s input | 2 | `audio_too_short`, preprocessing |
| 60 s + one frame | 2 | `audio_too_long`, preprocessing |
| Corrupted WAV | 2 | `invalid_audio`, preprocessing |
| MP3 extension | 2 | `unsupported_audio`, preprocessing |
| Missing local WAV | 2 | `audio_not_found`, preprocessing |
| Real CLI mode without injected adapters | 2 | `invalid_configuration`, configuration |
| Nonnumeric top_k | 2 | `invalid_configuration`, configuration |

Success is JSON on stdout with empty stderr; failures are ErrorInfo JSON on
stderr with empty stdout. No waveform or supplied audio path appears in the public
result. The CLI is a local demo, not a web API.

## Performance measurements

These are **mock pipeline timings, not AI inference latency**. Synthetic PCM16
inputs are generated before timing. Each configuration uses three fresh Python
processes and, in one shared process, one untimed warmup followed by three calls.
The table gives medians in seconds; raw samples and min/max are in `summary.json`.

Cold process wall time includes process launch, imports, first call, post-call
memory measurement helper, JSON output and exit. Cold first-call wall time is
measured around `run_pipeline()` inside the child and includes lazy NumPy/SciPy
loading. Warm wall time is measured around the call in the warmed parent.
`processing_time_s` is the pipeline's internal monotonic timer, evaluated before
the final result constructor/validation and return; it excludes interpreter
startup, fixture generation, CLI serialization and output. OS file caches are not
flushed, so a fresh process does not imply cold disk caches. This is a development
machine measurement with no dedicated-load or cross-machine benchmark guarantee.

| Duration/input | Cold process wall | Cold first call | Warm call wall | Warm processing_time_s | Peak working set MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 s / 16 kHz mono | 0.5611 | 0.2928 | 0.0989 | 0.0987 | 33.6 |
| 1 s / 48 kHz stereo | 3.4552 | 3.1604 | 0.0984 | 0.0979 | 94.6 |
| 10 s / 16 kHz mono | 1.5809 | 1.2526 | 1.0656 | 1.0640 | 36.0 |
| 10 s / 48 kHz stereo | 4.6570 | 4.3714 | 1.0849 | 1.0836 | 109.3 |
| 30 s / 16 kHz mono | 3.5819 | 3.3175 | 2.9261 | 2.9209 | 54.1 |
| 30 s / 48 kHz stereo | 6.6139 | 6.3298 | 2.9756 | 2.9713 | 142.6 |
| 60 s / 16 kHz mono | 6.6164 | 6.3385 | 5.8472 | 5.8380 | 81.1 |
| 60 s / 48 kHz stereo | 9.9166 | 9.6600 | 5.9972 | 5.9892 | 192.2 |

Memory is the median OS lifetime peak working set from each fresh child process
(`GetProcessMemoryInfo` on Windows). It includes interpreter, native libraries and
the post-timing helper; it is approximate, not incremental Python allocation size.
The 192 kHz stereo/32-bit worst-case accepted source was not memory-benchmarked.

Profiling a synthetic 10-second mono invocation identified six full waveform
validations and approximately 960,000 scalar `_number` calls as the main cost.
Validation scales with output length; first resampling also pays SciPy startup.
No leak was established by these short measurements. No performance target was
specified, and no unsafe validation shortcut or representation redesign was added.
Before real-model performance work, set a latency/memory budget and profile the
complete adapters; any optimized waveform boundary needs separate review.

## Bugs discovered and fixed

1. A pitch adapter could leave invalid waveform data for the next analyzer. The
   pipeline now revalidates AudioData immediately after pitch and timbre calls;
   invalid mutation fails with `invalid_audio` at the responsible analyzer stage.
2. A timbre adapter could mutate audio warnings so profile assembly raised an
   uncaught ContractError. The same post-adapter check converts this to a structured
   PipelineError before assembly.
3. An injected preprocessor could ignore `target_sample_rate=16000` and return an
   otherwise valid 8 kHz object. The preprocessing boundary now rejects that output.
4. A callable declared `suara_mode='mock'` could return real-labeled recommendations
   for real-labeled inputs in mock execution. Its output must now remain mock;
   contradictory recommendations fail with `invalid_catalog`.

The regression log shows three assertions failing and one uncaught error before
the fixes. All pass afterward. No PCM decoder defect was found in the tested
cases, and the working preprocessing architecture was preserved.

## Integration readiness and remaining risks

| Module | Boundary readiness | Remaining teammate work |
| --- | --- | --- |
| E1 pitch | Ready; voiced and unvoiced adapters tested | Actual detector/checkpoint, thresholds, model version, confidence interpretation and human/reference evaluation |
| E6 timbre | Ready for a new compatible adapter | Re-extract the exact c0..c19 mean convention and centroid; verify numerical parity |
| E3 song features | Ready for a typed catalog export | Reviewed vocal/melody Hz ranges, excerpt/source provenance; bridge the Python 3.11 experiment without importing its stack |
| Recommendation | Ready; IDs, metadata, count, order, score and mode validated | Real scoring formula, missing-data policy and suitability evaluation |

E6's locked baseline removes c0 from 20 MFCCs, pools 19 means plus 19 standard
deviations (38 values), uses development-fitted z-scoring and evaluation L2
normalization, and applies different preprocessing/framing/dB behavior. It cannot
be sliced, padded or relabeled into the pipeline's 20 unscaled c0..c19 means.
Re-extract from the agreed AudioData waveform. The exact comparison and module
examples are in [TEAM_INTEGRATION_GUIDE.md](TEAM_INTEGRATION_GUIDE.md).

Other limitations:

- Dataclass validation proves representation, not that an algorithm truthfully
  labels its origin or that source review/model accuracy claims are correct.
- Test-only real-labeled stubs prove wiring only; no real AI was integrated.
- Frozen dataclasses still contain lists. Invalid mutation is caught by boundary
  checks; valid-but-unwanted changes are not detected automatically. Adapters must
  be read-only with respect to their inputs.
- Expected PipelineError messages are preserved by design. Adapter authors must
  keep them public-safe; unexpected exceptions are mapped to generic messages.
- MFCC processing_version is an identifier, not proof of parameter parity.
- No melody-range inference should be made from a full polyphonic spectrum; null
  pitch and unverified song ranges require explicit scoring behavior.
- Default mocks report synthetic values regardless of input tone/noise. Fixture
  voiced_ratio is not a singing detector and fixed scores are not suitability.
- The supported file format is deliberately narrow. Float/compressed WAV, MP3,
  RF64, GUI/API, streaming and persistence remain outside this implementation.

## Final verification and review preparation

The final pipeline suite, all ten CLI invocations, dependency checks, package
imports, AI import isolation, `git diff --check` and experiment diff checks passed.
The full benchmark run hashed all 119 tracked E1/E3/E6 files before and after:

```text
2850a1a463157306d8f789875b5538f7e4ea60837465b4b42f8edc5324c2e519
```

The matching digest and empty experiment diff confirm preserved tracked contents;
no experiment code was executed and no experimental files were changed.
Generated WAVs, caches and the virtual environment remain ignored. Changes are
left in the working tree on `feature/main-pipeline` for review, without staging
or committing on the user's behalf. Review the changed source/tests/docs and
captured logs before any approved push.

Main Pipeline Lead next steps: review these changes, coordinate adapter versions,
set real-runtime acceptance budgets and re-run validation after each integration.
Teammates should implement E1 pitch, E6 timbre re-extraction, E3 catalog export and
then the recommendation rule, in that order. Connect them through
`PipelineDependencies`; run mixed mode checks first and explicit real mode only
when actual implementations are available. User/reference evaluation remains
necessary after structural integration succeeds.
