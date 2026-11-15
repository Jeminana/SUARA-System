# T04/T05 timbre adapter and integration

Implementation and validation date: 2026-11-15 (Asia/Seoul).

## Delivered behavior

[`suara.timbre.analyze_timbre`](../main_pipeline/src/suara/timbre.py) implements
`analyze_timbre(audio_data: AudioData) -> TimbreFeatures`. It measures descriptors
from the supplied waveform, returns `mode="real"`, validates via the contract
constructor, and treats the input as read-only. It has no model checkpoint,
network access, experiment imports, or new dependencies.

The locked E6 baseline is preserved. Its 38 values contain c1..c19 means and
standard deviations with development scaling, followed by L2 normalization for
retrieval. They cannot be converted into the application's raw c0..c19 means.
This adapter re-extracts from `AudioData`. ECAPA embeddings remain separate.

## Exact extraction convention

| Setting | `mfcc-20-v1` implementation |
| --- | --- |
| Waveform | Validated mono 16000 Hz; pipeline gain preserved; no trimming, pre-emphasis, normalization or voicing gate |
| Framing | 512 samples, hop 160; first frame at sample 0; complete frames only; no centering or padding; drop incomplete tail |
| Window and FFT | Periodic Hann; unnormalized real FFT; float64 computation |
| Mel spectrum | Squared FFT magnitude; 40 triangular filters over 0..8000 Hz; Slaney frequency scale and area normalization |
| Slaney scale | Linear at 200/3 Hz per mel below 1000 Hz, then logarithmic with step ln(6.4)/27; filter weights multiplied by 2/(upper edge - lower edge) |
| Log power | 10 log10(max(mel power, 1e-10)); reference 1; no top-dB cap |
| MFCC | Orthonormal DCT-II; retain c0..c19; no lifter, z-score or L2 normalization |
| Pooling | Arithmetic means across all complete frames, including silent frames |
| Centroid | FFT magnitude-weighted frequency in Hz per frame, averaged only over frames with positive magnitude sum; null if none |
| Short input | Fewer than 512 samples: `audio_too_short` at timbre stage; wrong rate: `invalid_audio` |
| Silence | Standalone extractor returns finite log-floor MFCCs and null centroid with warning; the actual pipeline rejects silent recordings during preprocessing |

`processing_version` is exactly `mfcc-20-v1`. `model_version` records
`suara-timbre-v1_numpy-<installed version>_scipy-<installed version>`; the measured
environment was Python 3.12.10, NumPy 2.5.4, SciPy 1.18.1. Unsupported rates are
rejected rather than silently resampled under this processing version. Use the
pipeline preprocessor to handle source rates and stereo. Never compare vectors
from different processing versions as if they used the same representation.

## Run and inject

From the repository root, after the installation in the pipeline README:

```powershell
main_pipeline/.venv/Scripts/python.exe main_pipeline/tools/generate_smoke_wav.py
main_pipeline/.venv/Scripts/python.exe -m suara.cli --audio main_pipeline/.smoke/tone.wav --timbre real
```

The CLI explicitly injects measured timbre alongside mock pitch and ranking.
Nested timbre provenance is real; profile/result and recommendations remain mock.
Default mock runs do not import `suara.timbre`. `--mode real` still requires the
other actual implementations through the Python API and has no mock fallback.

To replace only the timbre callback in an existing dependency bundle:

```python
from dataclasses import replace
from suara.pipeline import run_pipeline
from suara.timbre import analyze_timbre

# team_dependencies is the caller's existing PipelineDependencies bundle.
dependencies = replace(team_dependencies, analyze_timbre=analyze_timbre)
result = run_pipeline("local.wav", mode="mock", dependencies=dependencies)
```

Once T03 and T09 provide actual pitch/ranking, use the same timbre callback in a
complete real dependency bundle, pass an explicit catalog, and select real mode.
No E1 algorithm is supplied or claimed by this work.

## Reproducible validation

```powershell
$env:PYTHONPATH = (Resolve-Path main_pipeline/src).Path
main_pipeline/.venv/Scripts/python.exe -m unittest discover -s main_pipeline/tests -v
main_pipeline/.venv/Scripts/python.exe -m pip check
main_pipeline/.venv/Scripts/python.exe main_pipeline/tools/validate_timbre_recordings.py --manifest experiments/E6/data/manifest.csv --audio-root experiments/E6/data/raw
git diff --check
```

The full pipeline suite passed: **78 tests**, including **9 new timbre tests**.
The independent numerical oracle uses scalar Slaney filter construction, an
explicit cosine transform and independently generated Hann window; coefficient
comparisons pass with absolute/relative tolerances of 1e-10. It covers seeded
noise, a tone and silence without loading librosa or the E6 environment.

Additional checks cover centroid accuracy on a bin-centered 1000 Hz tone, retained
gain effects, incomplete-tail handling, determinism, waveform sensitivity, no
mutation, invalid/nonfinite input, unsupported rate, short input, actual stereo
preprocessing/resampling, strict JSON, matching standalone/integrated versions,
mixed-mode provenance, unvoiced profile assembly with a test-only pitch stub,
finite-output validation, safe module failures and mock import isolation.
`pip check` reported no broken requirements.

The local E6 real-audio validation passed **42 recordings, 0 skipped, 0 failed**
using the existing manifest's consented, non-excluded source recordings (authorized
again by the user in this session). Every recording passed actual preprocessing,
standalone extraction and pipeline execution with mock pitch/ranking. Checks
confirmed unchanged input, identical standalone/integrated timbre, strict JSON,
the exact model/processing versions and correct mixed-mode provenance. No private
recordings or individual feature vectors were added to the repository.

## Limitations

These checks establish extraction convention and integration behavior. They do
not validate listener-perceived timbre similarity, singer identity or song
suitability. MFCCs and centroid depend on recording device, pitch, gain, noise
and silence. No human pitch accuracy or fully real recommendation result is
claimed. Real-audio checks use only recordings the user authorized in this
session. Private audio, per-recording descriptors, identities and embeddings
must remain outside Git; the recording validator prints only aggregate counts
and version strings.
