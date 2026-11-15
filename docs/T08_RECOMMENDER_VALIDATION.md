# T08 pitch-range recommender

Implementation and validation date: 2026-11-15 (Asia/Seoul).

## Delivered behavior

[`suara.recommender.recommend_songs`](../main_pipeline/src/suara/recommender.py) implements
`recommend_songs(voice_profile, song_catalog, top_k=5) -> list[Recommendation]`, the same
signature as the mock ranker, so T09 can inject it through `PipelineDependencies`. It uses only
the standard library, treats its inputs as read-only and declares `suara_mode = "real"`.
It is not yet wired into the CLI or the default pipeline; that is T09.

## Scoring formula (`pitch-range-fit-v1`)

The rule uses the profile's observed pitch range (`min_pitch_hz`, `max_pitch_hz`,
`median_pitch_hz`) and each song's melody range. Timbre is not used: MFCC similarity is not
evidence that a song suits a singer. All distances are in semitones (MIDI = 69 + 12 log2(Hz/440)),
so an octave counts the same at any pitch.

| Term | Definition |
| --- | --- |
| outside | semitones the melody goes above the singer's highest observed pitch, plus semitones it goes below the lowest |
| range_fit | max(0, 1 - outside / 12) |
| centre_fit | max(0, 1 - \|melody centre - singer median\| / 12), where the melody centre is the midpoint of its range in semitones |
| score | 0.8 x range_fit + 0.2 x centre_fit, rounded to 4 decimals; always within [0, 1] |

Each semitone outside the sung range costs 1/12 of the range weight. A melody an octave or more
outside scores 0 on that part. The centre term separates songs that all fit. The 0.8/0.2 weights
and the 12-semitone scale are **unvalidated starting values** chosen for transparency. The score is
not a probability, and it is not evidence that a song suits a voice.

Each explanation states the melody range, the recorded range and how far the melody goes outside
it, and the centre distance. It also says that a short recording shows only the notes sung and
that the score does not measure suitability. Recommendations with mock inputs say so.

## Missing data, provenance and ordering

| Case | Behavior |
| --- | --- |
| Profile has no voiced pitch (`voiced_ratio = 0`) | Returns `[]`; the profile's `no_voiced_pitch` status explains why |
| Song melody range is null | Left out; no fit is invented |
| Song provenance `unverified` | Left out, even with a range; the contract forbids pitch matches on unverified ranges |
| Song provenance `mock` with a range | Scored, labelled `mode="mock"` with a synthetic-input note |
| Profile `analysis_mode = "mock"` | Every recommendation is `mode="mock"`, as the pipeline requires |
| Empty catalog | Returns `[]` |
| Ordering | Descending score, then ascending `song_id`; catalog order has no effect |
| `top_k` | Integer 1-5 (not bool), else `invalid_configuration` |

## Comparison with the T12 naive baseline

The baseline is `evaluation/scripts/metrics.py:naive_rank_contract`: the share of the song's
range covered by the singer's range. Both rules were run on the five E3 catalog songs with the four
synthetic T12 voice fixtures. Reproduce with:

```bash
main_pipeline/.venv/bin/python main_pipeline/tools/compare_recommender_baseline.py
```

### low_voice: A2-E4, median G3

| Proposed rank | Song | Melody | Proposed score | Baseline score | Baseline rank |
|---|---|---|---|---|---|
| 1 | E3-S01 | D3-A3 | 0.9832 | 1.0000 | 1 |
| 2 | E3-S02 | A2-D4 | 0.9832 | 1.0000 | 2 |
| 3 | E3-S04 | A2-D4 | 0.9832 | 1.0000 | 4 |
| 4 | E3-S03 | E3-E4 | 0.9418 | 1.0000 | 3 |
| 5 | E3-S05 | A2-A3 | 0.9415 | 1.0000 | 5 |

Same top song: yes; songs in the same position: 3 of 5; distinct scores: proposed 3 of 5, baseline 1 of 5.

### mid_voice: G3-C5, median E4

| Proposed rank | Song | Melody | Proposed score | Baseline score | Baseline rank |
|---|---|---|---|---|---|
| 1 | E3-S03 | E3-E4 | 0.7083 | 0.7500 | 1 |
| 2 | E3-S01 | D3-A3 | 0.5000 | 0.2857 | 4 |
| 3 | E3-S02 | A2-D4 | 0.1667 | 0.4118 | 2 |
| 4 | E3-S04 | A2-D4 | 0.1667 | 0.4118 | 3 |
| 5 | E3-S05 | A2-A3 | 0.1333 | 0.1666 | 5 |

Same top song: yes; songs in the same position: 2 of 5; distinct scores: proposed 4 of 5, baseline 4 of 5.

### high_voice: C4-G5, median A#4

| Proposed rank | Song | Melody | Proposed score | Baseline score | Baseline rank |
|---|---|---|---|---|---|
| 1 | E3-S03 | E3-E4 | 0.2750 | 0.3333 | 1 |
| 2 | E3-S01 | D3-A3 | 0.1333 | 0.0000 | 4 |
| 3 | E3-S02 | A2-D4 | 0.0000 | 0.1176 | 2 |
| 4 | E3-S04 | A2-D4 | 0.0000 | 0.1176 | 3 |
| 5 | E3-S05 | A2-A3 | 0.0000 | 0.0000 | 5 |

Same top song: yes; songs in the same position: 2 of 5; distinct scores: proposed 3 of 5, baseline 3 of 5.

### unvoiced

No voiced pitch: the proposed rule returns no songs; the baseline marks 5 of 5 songs not evaluable.

### What the comparison shows

- Both rules pick the same top song for every voice.
- They disagree on wide songs that go far outside the singer's range. For mid_voice (G3-C5), the
  baseline ranks S02/S04 (A2-D4) above S01 (D3-A3) because 41% of their range is covered. The
  proposed rule ranks S01 higher because it goes 5 semitones below the voice, against 10 for
  S02/S04. Coverage ignores how far outside the range the uncovered part lies.
- When every song fits (low_voice), the baseline ties all five at 1.0. The proposed rule separates
  them only by the centre term (0.94-0.98), so its ordering there is weak.
- The 12-semitone floor is a limitation. For high_voice, S02, S04 and S05 are all more than an
  octave outside, score 0, and tie in song ID order, while the baseline still separates S02/S04
  (0.12) from S05 (0). A larger scale would keep separating such songs at the cost of penalizing
  out-of-range notes less.
- There are no listener judgments, so neither ordering can be called better; NDCG@K and
  Precision@K were not computed. The five pilot songs were written for one singer (G2-E4), so this
  catalog has little range variety. The voices are synthetic T12 fixtures, not measured singers.

## Tests

`main_pipeline/tests/test_recommender.py` (13 tests) covers the formula with hand-computed values,
bounds over 500 seeded random cases, the E3 ranking for a G3-C5 voice, tie order, catalog-order
independence, unmodified inputs, every missing-data and provenance case, `top_k`, the pipeline's
own recommendation validator for four profiles and every `top_k`, real- and mock-mode pipeline
runs, the unvoiced pipeline path and the T12 fixtures. Run on Python 3.12.14, NumPy 2.5.4,
SciPy 1.18.1: the full suite is 91 tests (78 existing + 13 new), all passing.

## Not done here

- Wiring into the CLI and a real-mode entry point (T09).
- Real pitch input: the pipeline's pitch analyzer is still mock until T02/T03.
- Tuning the weights or scale, and any listener study to judge suitability.
