# T03 E1 Pitch Adapter Pipeline Integration

T03 connects the T02 `suara.pitch.analyze_pitch` adapter through the existing
`PipelineDependencies` API. It does not add a new real-mode CLI path or change
the application contracts and orchestration. The CREPE worker remains isolated
in the Python environment prepared for E1.

## Runtime flow

```text
generated/local PCM WAV
       |
       v
preprocess_audio(target_sample_rate=16000) -> validated mono AudioData
       |
       v
PipelineDependencies.analyze_pitch -> suara.pitch.analyze_pitch
       |                                 |
       |                                 +-> configured E1 CREPE worker
       v
PitchFeatures + test/real TimbreFeatures -> VoiceProfile -> PipelineResult
```

The adapter is supplied in the ordinary dependency bundle:

```python
from suara.audio.preprocessing import preprocess_audio
from suara.contracts import PipelineDependencies
from suara.pitch import analyze_pitch
from suara.pipeline import run_pipeline

dependencies = PipelineDependencies(
    preprocess_audio=preprocess_audio,
    analyze_pitch=analyze_pitch,
    analyze_timbre=real_timbre_adapter,
    recommend_songs=real_recommender,
)
result = run_pipeline(
    "local.wav", mode="real", song_catalog=reviewed_catalog,
    dependencies=dependencies,
)
```

Real mode requires all dependency outputs and the catalog to be labeled and
validated consistently. The integration tests use explicit test-only timbre
and ranking functions plus an empty catalog to isolate pitch wiring. Those
doubles are not production validated and their passing tests do not evaluate
timbre or recommendation behavior. Default mock mode remains unchanged.

## Test coverage

`main_pipeline/tests/test_pitch_pipeline.py` uses generated PCM WAVs and the
actual `preprocess_audio`, `suara.pitch.analyze_pitch`, `PipelineDependencies`,
and `run_pipeline` implementations. Its fast tests configure a small fake
worker executable with `SUARA_CREPE_PYTHON`; they still exercise the real T02
adapter, framed audio transfer, pipeline validation and profile assembly. The
fake worker validates the request framing and returns controlled frames so
voiced, unvoiced, malformed-response, worker-exit and timeout behavior can be
tested without TensorFlow startup.

The unvoiced test uses a non-silent generated WAV that passes preprocessing and
a response with no accepted pitch frames. It checks null statistics and
`no_voiced_pitch` profile status. A fully silent WAV is rejected by
preprocessing's RMS policy before pitch analysis and is not an unvoiced detector
test.

The opt-in test uses the actual isolated CREPE worker and checks the full path
from generated 220 Hz WAV through preprocessing, pitch extraction, profile
assembly and pipeline serialization. Its test-only timbre and ranker isolate
the integration under test; they are not claims of a complete production real
pipeline.

## Environment and reproducible commands

Install the main application in its Python 3.12 environment. For real CREPE
validation, prepare the separate E1-compatible worker environment using
`experiments/E1/environment/requirements-crepe.txt` and
`experiments/E1/environment/requirements-crepe-algorithm.txt`, as described in
[T02 setup instructions](T02_PITCH_ADAPTER.md#environment-setup-macos). Keep
the versions isolated: the application uses Python 3.12 and NumPy `>=2.0,<3`;
the E1 worker uses Python 3.12, TensorFlow 2.16.2, NumPy 1.26.4, and CREPE
0.0.12. CREPE and TensorFlow are not installed in the application environment.

Run fast pipeline tests without CREPE/TensorFlow:

```sh
main_pipeline/.venv/bin/python -m pytest main_pipeline/tests/test_pitch_pipeline.py -v
```

Run the actual CREPE end-to-end test (set both variables; only the integration
flag enables the test):

```sh
SUARA_CREPE_INTEGRATION=1 \
SUARA_CREPE_PYTHON="$PWD/experiments/E1/.venv-crepe/bin/python" \
  main_pipeline/.venv/bin/python -m pytest main_pipeline/tests/test_pitch_pipeline.py -v -s
```

Run the whole application suite with both real-worker tests enabled:

```sh
SUARA_CREPE_INTEGRATION=1 \
SUARA_CREPE_PYTHON="$PWD/experiments/E1/.venv-crepe/bin/python" \
  main_pipeline/.venv/bin/python -m pytest main_pipeline/tests -v
```

No private recording is needed or included. This integration evidence is based
on generated synthetic WAVs. It verifies adapter execution and pipeline
contracts, not human singing accuracy. E1 also reports synthetic feasibility
results only; there are no scoring-eligible human frame-level F0 references.

## Execution record

Verified on macOS using `main_pipeline/.venv` (Python 3.12):

- Fast T03 tests: `main_pipeline/.venv/bin/python -m pytest
  main_pipeline/tests/test_pitch_pipeline.py -v` — **4 passed, 1 skipped** in
  2.11 seconds. The skip is the actual CREPE worker test when the opt-in flag is
  absent.
- Full application suite: `main_pipeline/.venv/bin/python -m pytest
  main_pipeline/tests -v` — **91 passed, 2 skipped, 241 subtests passed** in
  11.56 seconds. The two skipped tests are the opt-in real CREPE adapter and
  T03 pipeline tests.
- T03 actual-worker integration:
  `SUARA_CREPE_INTEGRATION=1 SUARA_CREPE_PYTHON=<E1 worker interpreter>
  main_pipeline/.venv/bin/python -m pytest
  main_pipeline/tests/test_pitch_pipeline.py -k
  generated_220_hz_wav_runs_through_real_pipeline -v -s` — **1 passed, 4
  deselected** in 36.62 seconds. This exercised generated WAV preprocessing,
  the actual T02 adapter and CREPE worker, `run_pipeline`, and `VoiceProfile`
  validation/serialization. Test-only timbre and ranking doubles were used.

- Final full application suite with `SUARA_CREPE_INTEGRATION=1` and
  `SUARA_CREPE_PYTHON="$PWD/experiments/E1/.venv-crepe/bin/python"`:
  `main_pipeline/.venv/bin/python -m pytest main_pipeline/tests -v` — **93
  passed, 0 skipped, 241 subtests passed** in 92.19 seconds. Both
  `CrepeIntegrationTests.test_generated_220_hz_tone_runs_in_isolated_worker`
  (T02) and
  `RealCrepePipelineIntegrationTests.test_generated_220_hz_wav_runs_through_real_pipeline`
  (T03) ran and passed using the actual CREPE worker. Other timbre and ranking
  components in T03 remain test-only doubles.

The actual-worker run confirms this synthetic pipeline path and contract wiring;
it does not measure or claim human singing accuracy. The fast path tests
explicitly exercise voiced aggregation, no accepted voiced frames, malformed
detector output, worker exit, and timeout propagation. **Human singing
accuracy and production timbre and recommendation behavior remain unvalidated.**

## Limitations

CREPE worker startup can take tens of seconds and an earlier cold run exceeded
the 120 second default timeout. The final full opt-in suite, which starts both
T02 and T03 workers, took 92.19 seconds on the recorded machine. Timing depends
on machine and cache state; the opt-in tests require the separately installed
worker and model weights. The fast fake-worker tests do not measure detector
accuracy. Synthetic tone results do not establish human singing performance,
and no human accuracy claim is made here.
