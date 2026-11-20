# T02 Real Pitch Analysis Adapter

`suara.pitch.analyze_pitch(audio_data)` implements the existing `AudioData ->
PitchFeatures` interface. It runs CREPE in a separate Python process so the
application environment can keep NumPy 2.x while the proven E1 CREPE environment
uses NumPy 1.26.4. No detector or TensorFlow import occurs in the default mock
path. The adapter is injected through `PipelineDependencies`; it does not change
the pipeline or CLI defaults.

## Detector and voicing policy

The worker uses CREPE 0.0.12 and the `tiny` model, following E1's frozen
configuration: normalized mono 16 kHz audio, centered frames, 10 ms step,
`viterbi=False`, CPU inference, and prediction batch size 32. CREPE's public
`predict` function does not expose the batch-size parameter, so the worker pins
it at the underlying Keras `Model.predict` call. CREPE
confidence is its native maximum activation. A frame counts as voiced only when
frequency is finite and positive and confidence is finite, in `[0,1]`, and at
least `0.5`. This is E1's prespecified evaluation cutoff; it was not tuned on
human singing.

`voiced_ratio` is accepted voiced frames divided by every detector frame,
including frames rejected by confidence or value validation. Pitch min, max and
median are calculated with equal frame weights over accepted F0 values. The
`PitchFeatures.confidence` value is the arithmetic mean of accepted-frame
confidence values. Invalid frequency or confidence values are serialized as
JSON `null` by the worker and rejected by the application adapter. When no
frames pass, the result is valid with ratio zero, null pitch statistics, null
confidence, and a warning. Worker/protocol failures raise a safe
pitch-stage `module_failure`; they are never represented as silence and never
fall back to mocks.

`model_version` is `crepe-0.0.12-tiny-16khz-10ms-v1`. The worker request protocol
is versioned independently as `suara-crepe-worker-v1`.

## Environment setup (macOS)

Keep the existing `main_pipeline` Python 3.12 environment. Create a separate
Python 3.12 worker environment from the repository root, using the existing E1
pins without editing E1 files:

```sh
python3.12 -m venv experiments/E1/.venv-crepe
experiments/E1/.venv-crepe/bin/python -m pip install --upgrade pip
experiments/E1/.venv-crepe/bin/python -m pip install -r experiments/E1/environment/requirements-crepe.txt
PYTHONPATH="$PWD/experiments/E1/environment/compat" \
  experiments/E1/.venv-crepe/bin/python -m pip install --no-build-isolation \
  --no-deps crepe==0.0.12
```

TensorFlow 2.16.2 has CPU macOS wheels for Python 3.12 on Apple Silicon and
Intel; wheel availability depends on macOS version. CREPE's legacy package
build may fetch model weights, so setup needs network access. Do not put either
environment, model caches, or recordings in Git.

Point the application at the worker's absolute interpreter path and optionally
set a timeout in seconds (default 120):

```sh
export SUARA_CREPE_PYTHON="$PWD/experiments/E1/.venv-crepe/bin/python"
export SUARA_CREPE_TIMEOUT_S=120
```

Use `suara.pitch.analyze_pitch` in the existing Python API:

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

T09 uses the same adapter in the [real-mode CLI](../main_pipeline/README.md#real-pipeline-t09).

## Process boundary and errors

The application validates `AudioData` and sends a length-prefixed JSON header
followed by little-endian float32 mono samples over stdin. The worker returns
strict JSON frames on stdout and diagnostics on stderr. It creates no audio
files. The worker path is resolved from the installed source tree, the Python
path is configured through `SUARA_CREPE_PYTHON`, and the subprocess uses
`shell=False`. Its response is size-limited and strictly schema-checked.

Missing/invalid worker configuration is `invalid_configuration`. Unsupported
sample rate is `invalid_audio`. Startup errors, nonzero exit, malformed data,
oversized response, or timeout are safe pitch-stage `module_failure`s; worker
stderr and exception details are not included in public error output. The
one-shot process loads TensorFlow and model weights for each analysis, so it has
startup overhead. Benchmark on team machines before setting a tighter timeout
or making latency claims. A persistent worker could amortize startup but would
need a separate lifecycle and crash-recovery design.

## Testing and validation

Run the fast suite without installing TensorFlow or CREPE:

```sh
main_pipeline/.venv/bin/python -m unittest discover -s main_pipeline/tests -p 'test_pitch.py' -v
```

The unit tests use generated tones and fake subprocess responses for aggregation,
rejected frames, no-voiced output, malformed protocol, worker failure, timeout,
immutability, and contract validation. To run the opt-in real-worker tone check
after setting up the separate environment (set both variables; setting only the
worker path does not opt in):

```sh
SUARA_CREPE_INTEGRATION=1 \
SUARA_CREPE_PYTHON="$PWD/experiments/E1/.venv-crepe/bin/python" \
  main_pipeline/.venv/bin/python -m pytest main_pipeline/tests/test_pitch.py -v -s
```

Run the complete application suite with the real CREPE test enabled:

```sh
SUARA_CREPE_INTEGRATION=1 \
SUARA_CREPE_PYTHON="$PWD/experiments/E1/.venv-crepe/bin/python" \
  main_pipeline/.venv/bin/python -m pytest main_pipeline/tests -v
```

## Verified T02 results

On macOS with Python 3.12.15 in the application and isolated worker
environments:

- Full application suite with real CREPE integration enabled: **88 passed**,
  including **241 subtests**, in 50.77 seconds; no skipped tests.
- The focused pitch suite with real integration enabled: **10 passed**, including
  the generated tone integration test.
- A generated 1 second, 220 Hz sine produced minimum **219.727 Hz**, maximum
  **221.064 Hz**, median **220.883 Hz**, voiced ratio **0.9901**, and mean
  accepted-frame confidence **0.8065**. `PitchFeatures.validate()` passed.
- The direct adapter call for that generated tone took **35.975 seconds**. This
  is a local observed run, not a latency guarantee or warm-throughput benchmark.
- An earlier first-use integration attempt exceeded the 120 second timeout. A
  subsequent direct worker run completed in **72.801 seconds** while TensorFlow,
  model and local Matplotlib/font caches initialized. Later integration runs
  passed below the timeout. First-run startup can therefore be long and
  environment-dependent; larger recordings may need a separately measured
  timeout setting.

These are generated synthetic-tone integration results only. They demonstrate
worker execution and contract wiring; they do **not** establish human singing
accuracy. E1's 12 synthetic recordings also do not validate performance on
human singing.

## Optional authorized recording check

There is no existing T02 pitch-specific authorized-recording validation
procedure or checked-in human recording set. E1's data README says human audio
and consent materials are excluded. The existing
`main_pipeline/tools/validate_timbre_recordings.py` is for T04/T05: it runs
measured timbre but explicitly supplies mock pitch, so its results are not pitch
validation.

If the team has a recording whose consent explicitly permits this analysis, keep
it outside Git and run the adapter locally. For example, with the main package
installed in its normal environment:

```sh
export SUARA_PITCH_RECORDING="/absolute/path/outside/repository/authorized.wav"
main_pipeline/.venv/bin/python -c 'import json, os; from suara.audio.preprocessing import preprocess_audio; from suara.pitch import analyze_pitch; result=analyze_pitch(preprocess_audio(os.environ["SUARA_PITCH_RECORDING"])); result.validate(); print(json.dumps({"min_pitch_hz":result.min_pitch_hz,"max_pitch_hz":result.max_pitch_hz,"median_pitch_hz":result.median_pitch_hz,"voiced_ratio":result.voiced_ratio,"confidence":result.confidence,"model_version":result.model_version}))'
```

This command prints only the feature summary and writes no audio or prediction
files. Do not commit the recording, its path, identifiers, consent records, or
derived private outputs. Without frame-level reference F0 annotations, treat
observations as qualitative behavior only and make no accuracy claim.

## Limitations

E1's quantitative comparison covers 12 synthetic recordings and does not
validate pitch accuracy on human singing. A short recording's observed pitch
range is not total vocal capability or tessitura. CREPE's 0.5 voicing cutoff is
an E1 evaluation rule, not a human-optimized operating point. Results may vary
with vocal style, noise, accompaniment and recording conditions. The current
one-shot worker design favors dependency isolation and predictable failure
handling over low latency; first-use initialization has exceeded the default
timeout in one run, as recorded above.
