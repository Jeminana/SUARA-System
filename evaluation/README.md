# SUARA T12 — Contract-aligned Evaluation Starter

**Status:** Independent evaluation assets and schema tests ready; **real integrated E1/E3/E6 modules have NOT been benchmarked.**

This package updates the earlier starter to use the exact `contracts.py` code supplied on November 9, 2026. The included `reference_contracts/contracts.py` is a **snapshot for local testing**, not a substitute for importing the team's live GitHub implementation during final T10 verification.

## Run on Windows PowerShell (from this folder)

```powershell
python scripts/generate_audio.py
python -m unittest discover -s tests -v
python scripts/run_evaluation.py
```

For the current team repository checkout (preferred), from this T12 folder:

```powershell
$env:SUARA_REPO_ROOT = 'C:\path\to\SUARA-System'
python -m unittest discover -s tests -v
python scripts/run_evaluation.py
```

Use a real repo root containing `main_pipeline/src/suara/contracts.py`. To reset: `Remove-Item Env:SUARA_REPO_ROOT`.

## Contents

- `reference_contracts/contracts.py`: exact user-supplied contract implementation (`SCHEMA_VERSION=1.0.0`)
- `scripts/contracts_bridge.py`: loads current repo contract when `SUARA_REPO_ROOT` is set; otherwise snapshot
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
- In the current `run_pipeline`, mock analyzers produce the same fabricated profile for any non-silent valid WAV. T12 cannot calculate genuine AI pitch accuracy from a mock output.
- Real module quality and latency must be measured later, during T10, using authorized evaluation data and an actual injected adapter. No private recordings should be committed.
