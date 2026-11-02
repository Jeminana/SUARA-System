# Main SUARA pipeline

The local pipeline provides real WAV preprocessing followed
by explicitly synthetic pitch/timbre features and fictional song recommendations.
The mock scores do not measure voice suitability. Real AI modules are not included.

The MVP accepts one local WAV and returns a structured voice profile and up to
five ranked recommendations as JSON. No cloud services, API keys, or downloaded
models are required. Experiment code and participant recordings are not used.

## Install and run

From the repository root in PowerShell, using Python 3.12:

```powershell
python -m venv main_pipeline/.venv
main_pipeline/.venv/Scripts/python.exe -m pip install -e main_pipeline
main_pipeline/.venv/Scripts/python.exe main_pipeline/tools/generate_smoke_wav.py
main_pipeline/.venv/Scripts/python.exe -m suara.cli --audio main_pipeline/.smoke/tone.wav --mode mock
```

Replace the generated path with your local recording, or add `--top-k 3`.
On macOS/Linux use `main_pipeline/.venv/bin/python` in place of the Windows path.
The installed `suara` console command accepts the same options. Installation needs
package-index access; runtime is offline. Dependencies are NumPy (PCM array
conversion) and SciPy (anti-aliasing polyphase resampling). Contracts stay standard
library only. Keep this environment separate from all experiment environments.

Success writes PipelineResult JSON to stdout and exits 0. Expected failures write
ErrorInfo JSON to stderr and exit 2. Invalid arguments also return JSON; `--help`
prints usage. The CLI accepts `--mode real` but rejects it because real adapters
can currently be supplied only through the Python API. It never falls back.

## Audio support and mock behavior

Support: little-endian RIFF integer PCM WAV, 8/16/24/32-bit, mono or stereo,
8000–192000 Hz source rate, 0.5–60 seconds. Full-width extensible PCM is supported;
float/compressed WAV, RF64 and big-endian WAV are rejected. Container/chunk sizes,
frame alignment, duration and waveform data are validated before analysis.
Output is mono at 16000 Hz by default. Gain is preserved; clipping is warned,
resampling overshoot is clamped with a warning, and near-silent input is rejected.
No trimming or denoising is applied. See the contract for exact thresholds.

Mock pitch is always 110/330/220 Hz (min/max/median) with fixture voiced_ratio=0.8.
Mock timbre is always 20 zeros and a fixture centroid of 1000 Hz. None of these
numbers is extracted from the input. Five fictional catalog records have null
melody ranges. Ranking sorts song_id ascending and assigns scores 0.9, 0.8, 0.7,
0.6, 0.5 by position, independent of voice features. Every result is labeled mock
and carries synthetic-output warnings/explanations. Real preprocessing warnings
describe transformations actually applied to the audio.

## Validation

```powershell
main_pipeline/.venv/Scripts/python.exe -m unittest discover -s main_pipeline/tests -v
main_pipeline/.venv/Scripts/python.exe -m pip check
main_pipeline/.venv/Scripts/python.exe main_pipeline/tools/validate_day3.py
```

Tests use temporary generated WAVs under ignored `.smoke/`. Day 3 adds PCM width,
rate/channel matrices, duration endpoints, malformed containers, silence/clipping,
anti-aliasing checks, all eight contracts, mutable nested data, injected adapters,
ranking references/order/limits, provenance and safe error JSON. No AI model or
participant recording is used. Test-only real-labeled adapters verify wiring only.

`validate_day3.py` also records ten CLI transcripts, environment/dependency checks,
three cold and three warm timing samples per duration/input configuration, OS peak
memory, and tracked E1/E3/E6 file hashes. Logs are saved in `validation_logs/`;
generated audio stays in `.smoke/day3/`. Cold process wall time includes startup,
imports and measurement/output overhead; `processing_time_s` covers only the
pipeline invocation. These are mock-runtime measurements, not AI inference latency.
See [the Day 3 validation report](../docs/DAY3_VALIDATION_REPORT.md) for actual results.

## Integration documents

- [MVP scope and repository inspection](../docs/MVP_SCOPE.md)
- [Architecture and planned package layout](../docs/ARCHITECTURE.md)
- [Integration contract and JSON examples](../docs/INTEGRATION_CONTRACT.md)
- [Teammate integration guide](../docs/TEAM_INTEGRATION_GUIDE.md)
- [Day 3 validation and remaining integration risks](../docs/DAY3_VALIDATION_REPORT.md)

Shared source lives in `src/suara/`; experiment code remains in `../experiments/`.
For a contracts-only import check without installing audio dependencies:

```powershell
$env:PYTHONPATH = (Resolve-Path main_pipeline/src).Path
python -c "from suara.contracts import SCHEMA_VERSION; print(SCHEMA_VERSION)"
```

Real replacements use `PipelineDependencies` as shown in the teammate guide.
Schema fields remain at 1.0.0. Day 3 hardens runtime boundaries without changing
the callable interfaces. Real analysis, database,
GUI, evaluated recommendation rules and streaming integration remain out of scope.
