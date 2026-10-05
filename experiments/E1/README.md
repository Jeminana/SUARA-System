# SUARA E1: Pitch Detection Feasibility

E1 tests whether pYIN and CREPE can estimate the fundamental frequency (F0) of solo singing accurately enough to support SUARA vocal profiling. Compare both detectors on the same audio and reference labels. This is a proposed Phase 1 pilot procedure; no experiment results are claimed yet.

E1 develops independently and hands pitch outputs to E2. E3 may initially use its own provisional detector and can adopt E1's selected method later. E1 does not calculate vocal comfort or a singer's full range.

## Proposed pilot

Use three types of material:

- **Synthetic reference:** 12 known tones, three seconds each, including harmonic tones and silence. Their exact F0 and voiced intervals provide ground truth.
- **Human singing:** five singers, three tasks, two takes per task (30 clips). The tasks are a comfortable sustained note, an ascending and descending scale, and a shared team-composed melody.
- **Noise robustness:** copies of recordings at 20 dB and 10 dB SNR.

Record dry vocals in a quiet room at a consistent microphone distance. Use headphones for the guide so it does not leak into the microphone. Do not require uncomfortable fixed notes. Keep original WAVs and make mono 16 kHz floating point working copies.

For human recordings, an intended MIDI note is not ground truth. Prefer independently annotated F0 and voiced intervals. Otherwise, two reviewers should inspect harmonic spacing in a spectrogram and label selected reliable intervals without seeing detector results. Mark ambiguous frames unscored; report annotation coverage and uncertainty. Do not use pYIN output as the reference when comparing pYIN with CREPE.

## Comparison procedure

1. Create a manifest with recording ID, participant, task, duration, sample rate, channels, split, reference path, and consent status. Log rejected audio and reasons.
2. Generate synthetic tones across the supported range with fades, silent gaps, exact F0 labels, and reproducible noise (record the random seed).
3. Run pYIN on mono audio with documented limits; begin with C2-C6 where supported, a 2048 frame length, and hop length 160 at 16 kHz for a 10 ms output grid.
4. Run CREPE on the same audio with a documented model capacity, 10 ms steps, and smoothing choice. Check its supported frequency range. Tune the voicing threshold on development clips only.
5. Save raw timestamps, F0/frequency, voicing, and confidence/probability. Align predictions and references on a common timestamp grid with the same evaluation mask. Do not interpolate across unvoiced gaps; account for centering and reference offsets.
6. Assign complete recordings to development and test sets (about one third/two thirds), balanced by singer and task. Keep every crop and noise variant in its source recording's split. Freeze settings before testing.
7. Evaluate synthetic, clean human, and noise conditions separately. Plot representative tracks. Warm each method once, then time three runs on the same hardware; report median processing time per file and real-time factor separately from model load time.

Use separate Python environments if CREPE/TensorFlow conflicts with the librosa environment. Record package versions, CPU/GPU/RAM, operating system, model settings, random seed, and code commit. Run a short WAV smoke test before collecting the full dataset.

## Metrics and proposed targets

For jointly voiced frames, signed cents error is `1200 * log2(predicted_F0 / reference_F0)`. Report median absolute cents error and the 90th percentile. Invalid or nonpositive predictions are missing.

- **Raw pitch accuracy:** voiced predictions within 50 cents divided by all reference voiced frames; missed frames count as failures.
- **Octave error rate:** reference voiced frames with absolute error within 50 cents of 1200 cents divided by all reference voiced frames.
- **Voicing precision, recall, and F1:** calculate against reference voiced intervals.
- **Annotation coverage:** scored reference duration divided by total test duration.
- **Real-time factor:** processing seconds divided by audio seconds; exclude model load time and report it separately.

Proposed clean human pilot targets are at least 90% raw pitch accuracy, no more than 5% octave errors, and at least 0.90 voicing F1. These are planning targets, not validated SUARA requirements. If annotations are too sparse, report accuracy as inconclusive and expand annotation. Report noise degradation separately. Select the simplest method that meets the pilot needs on the target machine. Flag low confidence, silence, breath, falsetto, rapid transitions, and extreme notes rather than hiding failures.

## E2 handoff

Provide `pitch.csv` with `recording_id`, `time_s`, `f0_hz`, `voiced`, `confidence`, `method`, and `quality_flag`; also provide `config.json`, `manifest.csv`, and `metrics.csv`. Use missing F0 for unvoiced frames, never zero. Preserve raw predictions and report corrections separately. Include split definitions, exclusions, plots, per-recording metrics, environment details, and timing logs so the result can be reproduced.

Use anonymous participant IDs. Keep consent identities separately, restrict recordings to the team, record a deletion date, and do not commit private audio or identity information to a public repository. Prefer team-composed melodies and consented recordings. Verify permissions for external recordings before acquiring or sharing them.
