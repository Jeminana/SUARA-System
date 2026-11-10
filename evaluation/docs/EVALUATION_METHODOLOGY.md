# T12 Evaluation Methodology (proposed, for team review)

## Scope and design

T12 prepares deterministic test assets and reusable procedures. T10 will execute actual pipeline evaluations when E1, E6, E3 and ranking modules have been integrated. Synthetic tones establish correctness for known-frequency inputs; they do not demonstrate real-song or real-singing performance.

## Data and reproducibility

- Generator creates mono 16-bit PCM WAV audio at 16,000 Hz.
- Fixed cases: 220 Hz, 440 Hz, 523.25 Hz, silence, two-tone sequence and white noise (fixed seed).
- Store exact generator configuration in `data/generated/manifest.json`.
- Never commit private singing recordings.
- For real evaluation, report authorized dataset license, annotations, subjects (if permitted), recording devices, sample rate, split, processing versions and exclusions.

## Pitch metrics

For a matched voiced frame with reference f_ref > 0 and estimate f_hat > 0:

- Absolute pitch error (cents): `abs(1200 * log2(f_hat / f_ref))`.
- MAE cents = average absolute cents error across matched voiced frames.
- Within-50-cents accuracy = percentage of reference voiced frames whose matched voiced estimate is within 50 cents (report missed voiced frames separately).
- Voiced precision = TP / (TP+FP); voiced recall = TP / (TP+FN); voiced F1 = harmonic mean. Report zero-denominator handling.
- Report valid frame counts and alignment method; do not compare nonaligned frames.

## Voice-feature consistency

- Across repeated authorized recordings with consistent protocol, compare lowest/highest measured pitch in semitones, median F0 and voiced fraction.
- Absolute difference in semitones: `abs(12 * log2(f1 / f2))` for valid positive frequencies.
- Summarize median, 90th percentile and missing-value rates. A single note cannot establish a comfortable vocal range.
- MFCC/timbre consistency cannot be validated with these synthetic samples alone; later compare the contract's exact 20-coefficient convention and processing versions.

## Ranking metrics

- Baseline: deterministic sort by pitch-range coverage over each song's *verified reference melody range*, then by stable song ID. Unknown melody range receives `None` (unscorable), not a fabricated fit score.
- Coverage = length of intersection(user range, song range) divided by song range length, after converting to MIDI semitone scale. This is a simplistic baseline, **not validated vocal comfort**.
- With graded human judgments 0–3, compute NDCG@K; with binary relevance compute Precision@K. Without judgments, only test structural properties (bounded score, ordering, deterministic ties, missingness and reasons).
- Compare proposed recommender against naïve baseline using the *same eligible set*. Report ties, exclusions and availability of ground truth.

## Runtime

- Use `time.perf_counter()` around a precisely defined operation. Report input duration, device/CPU, model versions, repeated warm runs, and p50/p95 latency. Distinguish cold model loading from warm inference.
- Demonstration time limits must be team-agreed, not retroactively selected.

## Error and edge-case suite

1. Silence (no voiced frames): null pitch statistics, safe fallback.
2. Noise-only audio: detector uncertainty, no unsupported comfort claims.
3. Invalid WAV bytes: safe parse error, not crash.
4. Missing/zero frequency: do not divide by zero; skip or mark unavailable.
5. Missing song melody range: score is unknown, not automatically unsuitable.
6. Empty catalog: stable empty results or documented structured error.
7. Duplicate IDs and nonfinite values: reject according to actual contracts.
8. Deterministic ties, sorting, and bounded recommendation scores.

## T10 handoff procedure

1. Review official contracts and map fixture adapters.
2. Replace synthetic pitch estimates with E1 module output, keeping annotated references.
3. Validate `PitchFeatures`/`TimbreFeatures`/`SongFeatures`/`Recommendation` using actual validators.
4. Run the same metrics on real E3 catalog and authorized recordings.
5. Compare recommendation rankings against baseline; add participant judgments before claims of suitability.
6. Record run commands, commit, environment, results, exclusions and failure modes.

## No fabricated success claims

Do not present these generated outputs as actual E1/E6/E3 performance. Project-level target thresholds require team agreement and a pilot design before the final study.


## Contract-aligned fixture policy (November 9)

Fixtures now use the actual schema 1.0.0 field names and are validated by constructing `PitchFeatures`, `TimbreFeatures`, `VoiceProfile`, and `SongFeatures` objects from the supplied team's contract class source. When using the live repository contract, set `SUARA_REPO_ROOT` to the repo root; this avoids silently diverging from future schema changes.

Pitch MAE is defined on aligned **voiced** reference/prediction frame pairs, measured in cents; report frame alignment and missing/false voicing separately using voiced precision/recall/F1. Directly comparing one aggregate `median_pitch_hz` value to a full time series cannot substitute for frame-level MAE. The contract's `PitchFeatures` stores aggregates only: for true frame accuracy, the E1 tester must expose frame-level predictions through a separate evaluation-only adapter or report, without extending the approved wire schema.

Recommendation evaluation distinguishes synthetic range-coverage baseline (calculable on known synthetic pitch ranges) from listener-judged suitability (not yet measured). Report judged relevance denominators and NDCG@K/Precision@K only when independent labels exist. Unknown pitch or song melody range means **not evaluable**, rather than a user-unsuitable song. `Recommendation.score` is bounded [0,1] and not a probability; the independent baseline's missing `None` values are intentionally not serialized as `Recommendation`.

Run five warm repeats per case and separately record first-run cold wall time, with test machine/platform, Python version, audio duration, sample rate, adapter/model versions and mean/p95. Avoid assigning real runtime performance from mock pipeline measurements.
