# SUARA E6: Singing Voice Embedding Feasibility

E6 is a Phase 1 feasibility study. It asks whether a numerical voice representation stays consistent when the same person sings different melodies, while separating different singers performing the same melody. The experiment also checks whether results may be driven by melody, pitch, or microphone.

The procedure and decision targets are a team proposal, not a published benchmark standard. The locked seven-singer pilot test has been run and met the provisional continuation target; see [Pilot results](#pilot-results). E6 is independent of E1 and E2 and is intended to provide evidence for E7 singer matching. Passing E6 does not establish similarity to artists or listener-perceived timbre similarity.

## Methods

Compare two approaches using identical data splits:

- **ECAPA-TDNN** from SpeechBrain's VoxCeleb checkpoint, a speech speaker-verification model whose usefulness for singing is an open question.
- **MFCC baseline**, using time-averaged features from librosa to describe short-term spectral shape.

Extract one embedding per accepted recording and L2-normalize it. Compare vectors with cosine similarity, reported as a similarity value (not a probability or artist-match score). Keep ECAPA, MFCC, and different model revisions in separate vector spaces.

## Pilot and split

The report proposed six consented singers; the pilot that was run used seven, each singing three shared team-composed melodies with two independent takes per melody: 42 clips, with query clips averaging about 19 seconds. Use dry vocals, consistent recording distance, and each singer's comfortable key. Record key and microphone. Where comfortable, include a shared-key subset to check that separation is not explained only by pitch register. Optional stress tests use a second device, added noise, and shorter crops of the same source clips.

Use M1 for development and method choices. After locking preprocessing and settings, enroll each singer with M2 take 1 and test on both M3 takes (14 held-out queries). M2 take 2 is a separate same-melody comparison. No query recording or crop may contribute to its enrollment profile. Stress variants inherit their source recording's split; do not split overlapping windows across enrollment and test.

## Evaluation and proposed decision target

Report top-1 and top-3 cross-melody retrieval, similarity separation, per-singer counts, robustness, and runtime. Similarity separation is the mean same-singer/different-melody similarity minus the mean different-singer/same-melody similarity. Also report different-singer/different-melody similarity to expose melody effects. With seven singers, chance levels are 1/7 for top-1 and 3/7 for top-3.

The provisional continuation target is at least 11 of 14 correct at top-1 (the proposed 9 of 12, or 75%, scaled to seven singers), positive similarity separation, and no obvious failure concentrated in one singer. Report exact counts, per-singer results, and uncertainty; fourteen queries do not support broad accuracy claims. If uncertainty intervals are included, resample participants and label the interval exploratory because pairs and windows share recordings.

Even successful identity retrieval does not show that different people with similar-sounding voices have nearby vectors. E7 must separately test cross-person vocal similarity with listener judgments. If E6 does not meet the target, document the limitation and consider interpretable features or a singing-specific embedding.

## Pilot results

The locked test ran on 2026-10-07 with the configuration in `config.yaml` (SHA-256 recorded in `environment.json`) and ECAPA revision `0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`; a rerun on 2026-10-09 reproduced the same results. All 42 clips were accepted, with no exclusions and no failed embeddings. Development on M1 selected whole-clip ECAPA embeddings and an MFCC baseline of 20 coefficients (mean and standard deviation, c0 excluded, z-scored on development clips).

| Method | Cross-melody top-1 | Top-3 | Same-melody top-1 | Separation | Target |
|---|---|---|---|---|---|
| ECAPA-TDNN | 14/14 | 14/14 | 7/7 | 0.314 | Met |
| MFCC baseline | 13/14 | 14/14 | 7/7 | 0.500 | Met |

Chance is 2/14 for top-1 and 6/14 for top-3. For ECAPA, same-singer/different-melody similarity averaged 0.685 against 0.371 for different-singer/same-melody pairs and 0.343 for different-singer/different-melody pairs. Every singer was retrieved correctly on both queries, but per-singer margins ranged from 0.081 (P04) to 0.428 (P07). The single MFCC miss was a P04 query, the singer with the smallest ECAPA margin, so P04 was the hardest singer to separate for both methods.

Stress tests on query clips (top-1 out of 14):

| Condition | ECAPA | MFCC |
|---|---|---|
| Clean | 14 | 13 |
| White noise, 20 / 10 / 5 dB SNR | 13 / 12 / 11 | 12 / 4 / 4 |
| Centre crop, 10 / 5 / 3 s | 14 / 13 / 13 | 12 / 10 / 10 |

ECAPA kept top-3 retrieval at 14/14 in every condition, while MFCC degraded sharply with noise. ECAPA embedding took about 0.02 s per clip after a 0.57 s model load on CUDA.

**Conclusion: Feasible for the stated scope.** ECAPA met the continuation target and was more robust than the MFCC baseline. MFCC's larger separation value comes from the z-scoring, which pushes different-singer similarity close to zero, so separation values should not be compared across vector spaces. These are small-sample results from seven singers and 14 queries; the exploratory bootstrap interval for ECAPA top-1 (1.0–1.0) reflects the absence of errors, not certainty. Device and pitch register were not controlled: six singers recorded on the same iPad, but P05 recorded all six clips on their own device, so P05's retrieval may partly reflect the microphone. Keys were not recorded, no shared-key subset was run, and the manifest has no second-device stress variants. Identity retrieval does not show that different people with similar voices have nearby vectors; E7 must test that separately.

## Setup

From this directory:

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
```

Record package versions, the model revision, random seed, and code commit for each locked run. The test command requires `locked: true` in `config.yaml`.

## Data and privacy

```text
data/reference/   guide tracks (not analysis recordings)
data/raw/         consented participant recordings
data/manifest.csv recording metadata and split inputs
```

Use anonymous participant IDs, such as `P01_M01_T01`. Keep consent identities separately. Record participant, melody, take, key, device, duration, and consent in the manifest. Listen for accompaniment, other voices, clipping, and excessive silence; log exclusions. Reference tracks belong outside `data/raw/`. Prefer team-composed melodies and consented recordings. Verify rights and permissions for any external source.

Recordings, embeddings, model downloads, virtual environments, and generated outputs must not be committed. The local `.gitignore` excludes `data/`, `outputs/`, and `pretrained_models/`. Restrict recordings and embeddings to the team and follow the consent record's deletion date.

## Workflow

```bash
python run_e6.py check   # validate manifest, preprocess, and review quality flags
python run_e6.py dev     # use M1 only to choose settings
# Lock the chosen settings and pin the ECAPA model revision in config.yaml.
python run_e6.py test    # run the held-out test after setting locked: true
```

The implementation converts audio to mono and 16 kHz for ECAPA; `encode_batch` does not resample automatically. Silence trimming is conservative and applied consistently. Optional five-second, non-overlapping windows use a logged voiced-ratio rule; normalize each accepted vector, average, then normalize the aggregate. MFCC coefficient inclusion and scaling are chosen on M1 only and frozen for testing. Failed or zero-norm vectors are logged as errors.

The locked run records configuration hash, package versions, model revision, seed, and code commit in `environment.json`. Synthetic tones can be used only to smoke-test code; never report their results as findings.

## E7 handoff and report

The test run writes summary tables, similarity and retrieval results, plots, stress-test and timing results, plus audit logs under `outputs/<run>_test/`. E7 handoff files include:

- `embeddings.npy` and `embedding_manifest.csv` with recording ID, singer ID, melody ID, split, model revision, vector index, and quality flag
- `similarity.csv` and `retrieval_results.csv`

Complete the report with measured results, exact counts, exclusions, plots/logs, limitations, and a conclusion of Feasible, Partially feasible, or Not feasible for the stated scope. Keep unsuccessful runs and exclusions in the run log.


