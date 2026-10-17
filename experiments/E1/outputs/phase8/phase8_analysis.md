# Phase 8: Corrected results and failure analysis

## Scope

All quantitative F0 results apply only to 12 synthetic test recordings (72 detector-condition runs). Human recordings have qualitative interval-level listening observations, not scoring-eligible F0 ground truth; no human pitch accuracy is reported. There were no valid development F0 references for tuning. CREPE's confidence cutoff 0.5 was fixed in advance, not tuned. The 12-recording synthetic test set is limited.

This analysis uses only corrected Phase 7 evaluator v2.0.0 results. Each aggregate has 3,600 reference frames and 3,000 reference-voiced frames. Raw accuracy and octave rate use all 3,000 voiced frames. Median/p90 cents error is conditional on jointly voiced valid-F0 frames; its denominator is in `results_table.csv`. Voiced-estimate coverage is shown separately.

## Quantitative findings

CREPE raw pitch accuracy is 99.30%, 99.27%, and 99.03% at clean, 20 dB, and 10 dB. pYIN is 91.67%, 91.67%, and 91.40%. CREPE is higher in each aggregate condition. These results describe this synthetic test set.

From clean to 10 dB, raw accuracy changes by -0.267 percentage points for pYIN and -0.267 points for CREPE. pYIN p90 conditional error changes from 10.0¢ to 40.0¢; CREPE changes from 6.75¢ to 6.64¢. CREPE has zero octave errors across conditions. pYIN octave errors are 250/3000 clean, 250/3000 at 20 dB, and 249/3000 at 10 dB.

At 10 dB, missed voiced frames (FN) are 1/3,000 for pYIN and 28/3,000 for CREPE. False voiced frames (FP) among 600 reference-unvoiced frames are 158 and 2, respectively. CREPE has higher pooled precision and a small number of misses; pYIN has high recall, with false positives reducing precision.

## Representative raw-evidence cases

- **SYN_T01_R012 / pYIN / clean:** 0/250 correct, 250 octave errors, 0 missed voiced and 10 false voiced. At 0.25 s, reference=1046.502 Hz, estimate=523.251 Hz (-1200 cents). CREPE gets 250/250 clean and 20 dB; at 10 dB it gets 249/250 with one miss.
- **SYN_T01_R012 / pYIN / gaussian_white_20db:** 0/250 correct, 250 octave errors, 0 missed voiced and 6 false voiced. At 0.25 s, reference=1046.502 Hz, estimate=523.251 Hz (-1200 cents). CREPE gets 250/250 clean and 20 dB; at 10 dB it gets 249/250 with one miss.
- **SYN_T01_R012 / pYIN / gaussian_white_10db:** 0/250 correct, 249 octave errors, 1 missed voiced and 4 false voiced. At 0.26 s, reference=1046.502 Hz, estimate=523.251 Hz (-1200 cents). CREPE gets 250/250 clean and 20 dB; at 10 dB it gets 249/250 with one miss.
- **SYN_T01_R001 / CREPE / 10 dB:** 244/250 correct, 6 missed voiced, 0 false voiced, 0 octave errors; 244 frames contribute to conditional cents error.
- **SYN_T01_R003 / pYIN / 10 dB:** 248/250 correct, 0 misses and 31 false-voiced frames. Raw false-voiced examples on reference-unvoiced frames: 0.04s (96.9 Hz), 0.05s (96.9 Hz), 0.06s (96.9 Hz).

The SYN_T01_R012 frame shows a pYIN octave-down estimate in raw output; it does not identify a cause. SYN_T01_R001 CREPE at 10 dB shows misses without octave or false-voice errors. SYN_T01_R003 pYIN at 10 dB provides directly checked false-voiced examples on reference-unvoiced grid frames.

## Runtime and limitations

Runtime RTF is Phase 5 runtime divided by 3 s input duration. It includes initialization/JIT effects in the first call; isolated warm-inference RTF was not measured. CREPE clean mean/median observed RTF is 1.464/0.317; pYIN is 0.714/0.594. Do not interpret these as isolated warm-throughput benchmarks.

Limitations: only 12 synthetic test recordings; no valid development F0 references for tuning; CREPE threshold 0.5 was prespecified; human quantitative F0 accuracy was not measured; runtime includes startup/JIT effects. Failure explanations are observational, not causal.

## Figures and validation

See `figure_index.md` for figure names and captions. All figures have PNG and PDF exports. `results_table.csv` contains corrected pooled values and denominators. `validation.json` records source hash verification, pooled metric checks, and raw checks for highlighted cases. The included figures and tables are the corrected Phase 8 outputs. Figure regeneration from raw detector predictions is not possible from this repository copy because raw predictions and the run linkage are excluded. The included aggregate and per-recording result hashes are listed in `../phase7/result_hashes.json`.
