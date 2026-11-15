# SUARA T12 — Contract-aligned Evaluation Starter

**Status:** Independent evaluation assets and schema tests ready; **real integrated E1/E3/E6 modules have NOT been benchmarked.**

The framework is merged through [PR #6](https://github.com/Jeminana/SUARA-System/pull/6)
(2026-11-10). `scripts/contracts_bridge.py` loads the live
`main_pipeline/src/suara/contracts.py` from this checkout by default. Set
`SUARA_REPO_ROOT` to test a different checkout. No `reference_contracts/` snapshot
is included. Real-module measurements remain T10 work.

## Run on Windows PowerShell (from this folder)

```powershell
python scripts/generate_audio.py
python -m unittest discover -s tests -v
python scripts/run_evaluation.py
```

To use another team repository checkout, from this T12 folder:

```powershell
$env:SUARA_REPO_ROOT = 'C:\path\to\SUARA-System'
python -m unittest discover -s tests -v
python scripts/run_evaluation.py
```

Use a real repo root containing `main_pipeline/src/suara/contracts.py`. To reset: `Remove-Item Env:SUARA_REPO_ROOT`.

## Contents

- `scripts/contracts_bridge.py`: loads live repository contracts (`SCHEMA_VERSION=1.0.0`), using `SUARA_REPO_ROOT` when set or this checkout by default
- `fixtures/*.json`: contract-compatible *synthetic mock* voice profiles and fictional songs
- `tests/test_contract_alignment.py`: strict dataclass validation, nulls, 20 MFCCs, version, deterministic ranking
- `tests/test_evaluation.py`: original pure metrics, audio edge case tests
- `scripts/generate_audio.py`: deterministic WAV generation and manifest
- `scripts/run_evaluation.py`: sample contract-valid inputs and illustrative benchmark calculations
- `docs/EVALUATION_METHODOLOGY.md`: metric definitions; do not treat synthetic scores as empirical model results

## Key distinctions

- All sample profiles and song records declare `mock` provenance; no measured human singing or real catalog is claimed.
- A **missing range is unknown (None)**, not an arbitrarily poor suitability score. For this reason the independent evaluation baseline returns nullable scores, and deliberately does not pretend to implement the production `Recommendation` contract.
- `VoiceProfile` has nested `PitchFeatures` / `TimbreFeatures` with 20 c0–c19 MFCC values; all wire schema versions are 1.0.0.
- Default mock analyzers produce the same fabricated profile for any non-silent valid WAV. The local T04/T05 work adds optional measured timbre, but pitch remains mock; T12 cannot calculate genuine AI pitch accuracy from a mock output.
- Real module quality and latency must be measured later, during T10, using authorized evaluation data and an actual injected adapter. No private recordings should be committed.

## PR-manager verification (2026-11-15)

All **23 tests** passed against the live schema in Python 3.12.10. The generator
produced six WAVs and a manifest with identical SHA-256 hashes on a second run;
the illustrative runner completed. This confirms framework readiness, not real
model performance. Generated data stays ignored by Git.

From the repository root, using the existing pipeline environment:

```powershell
$env:SUARA_REPO_ROOT = (Get-Location).Path
main_pipeline/.venv/Scripts/python.exe -m unittest discover -s evaluation/tests -v
main_pipeline/.venv/Scripts/python.exe evaluation/scripts/generate_audio.py
main_pipeline/.venv/Scripts/python.exe evaluation/scripts/run_evaluation.py
```

In a restricted Windows environment where the system temporary directory is not
writable, set a workspace temporary directory before running the tests:

```powershell
New-Item -ItemType Directory -Force main_pipeline/.smoke | Out-Null
$env:TEMP = (Resolve-Path main_pipeline/.smoke).Path
$env:TMP = $env:TEMP
```

The naive baseline is an evaluation helper with nullable scores, not the T08
production recommender. Frame-level pitch evaluation still requires an
evaluation-only E1 output because PitchFeatures stores aggregate statistics.
