# SUARA E1: Pitch Detection Feasibility

E1 compares pYIN and CREPE for fundamental-frequency estimation. The completed Phase 7 evaluation uses corrected evaluator v2.0.0 with strict integer 10 ms frame alignment. Phase 8 reports the corrected aggregate results and seven figures. Quantitative claims apply only to 12 synthetic test recordings; no human F0 accuracy is claimed because there are no scoring-eligible human frame references.

## Completed evaluation

CREPE raw pitch accuracy within 50 cents was 99.30%, 99.27%, and 99.03% at clean, 20 dB, and 10 dB. pYIN was 91.67%, 91.67%, and 91.40%. CREPE had no octave errors; pYIN had approximately 8.3% in each condition. At 10 dB, CREPE missed 28 of 3,000 voiced reference frames and had 2 false-voiced frames; pYIN missed 1 and had 158 false-voiced frames. Runtime observations include first-call initialization/JIT and are not warm-inference benchmarks. See [Phase 8 analysis](outputs/phase8/phase8_analysis.md), [results table](outputs/phase8/results_table.csv), and [figure index](outputs/phase8/figure_index.md).

## Contents

- `scripts/`: synthetic fixture generation and validation, general data helpers, environment reporting, and WAV smoke check.
- `src/` and `tests/`: package namespace and evaluator tests.
- `config/`: synthetic tone design and frozen Phase 6 evaluation configuration. Do not edit the frozen configuration to reinterpret completed results.
- `data/raw/synthetic/official/` and `data/references/synthetic/official/`: 12 official synthetic WAV fixtures and exact references; `data/manifests/` contains their manifest.
- `data/smoke/`: software-only sine fixtures.
- `outputs/phase7/`: corrected aggregate and per-recording results, provenance, and hashes. Source-path fields were removed from the per-recording table for portability.
- `outputs/phase8/`: corrected aggregate analysis, validation records, and seven figures in PNG and PDF formats.
- `docs/SUARA_E1_Pitch_Detection_Final_Report.docx`: repository copy with author and affiliation removed from the text and personal editor/date fields removed from metadata. The authoritative original remains in the separate experiment source directory.

No human audio, consent records, reviewer worksheets, identity links, raw human predictions, or invalidated Phase 7 outputs are included.

## Portable setup

Use a Python version supported by the selected dependency stack. Create environments in this experiment directory (the environment directories are local and should not be committed). From `experiments/E1`:

```sh
python3 -m venv .venv-pyin
.venv-pyin/bin/python -m pip install --upgrade pip
.venv-pyin/bin/python -m pip install -r environment/requirements-base.txt

python3 -m venv .venv-crepe
.venv-crepe/bin/python -m pip install --upgrade pip
.venv-crepe/bin/python -m pip install -r environment/requirements-crepe.txt
PYTHONPATH="$PWD/environment/compat" .venv-crepe/bin/python -m pip install --no-build-isolation -r environment/requirements-crepe-algorithm.txt
```

The CREPE environment is separate because TensorFlow and its NumPy constraints differ from the pYIN stack. The compatibility shim is used only to build legacy CREPE 0.0.12. Its optional smoothing dependencies are omitted because the recorded experiment used `viterbi=False`. The dependency files pin package versions; they do not freeze Python, operating system, or hardware. The original machine-specific lock snapshots are not part of this portable copy.

Run the included software smoke checks with `.venv-pyin/bin/python scripts/wav_smoke_test.py --detector pyin` and `.venv-crepe/bin/python scripts/wav_smoke_test.py --detector crepe`. They write smoke outputs under `outputs/smoke/` and do not reproduce experimental metrics.

The synthetic fixtures can be regenerated with `.venv-pyin/bin/python scripts/generate_e1_synthetic.py` and checked with `.venv-pyin/bin/python scripts/validate_e1_synthetic.py`. The exact frozen configuration and existing fixtures are included. Corrected results and figure exports are included as artifacts. The raw detector prediction set and Phase 5 run manifest are intentionally excluded, so re-running the full Phase 7 scoring or regenerating the Phase 8 figures from raw predictions requires those source artifacts from restricted experiment storage.

## Interpretation limits

There are 12 synthetic test recordings, no valid development F0 references for threshold tuning, and no quantitative human evaluation. CREPE's 0.5 confidence cutoff was prespecified. These results are feasibility evidence for the synthetic setup, not validated performance on human singing or a warm-throughput benchmark.
