# SUARA task board

Project: SUARA System

Phase: Real AI Module Integration

Phase Start Date: 2026-11-04

Proposed Phase Deadline: 2026-11-29 (tentative, subject to team confirmation)

Last Updated: 2026-11-20 (actual edit date; see [CHANGELOG.md](CHANGELOG.md))

Tracker created: 2026-11-02 (actual edit date; see [CHANGELOG.md](CHANGELOG.md)).

**The Status column below is the only authoritative task status.** Allowed values: Not Started, In Progress, Blocked, In Review, Completed. Checklists below describe acceptance criteria only. Responsible Member values are proposed roles; confirmed names belong in [TEAM_ASSIGNMENTS.md](TEAM_ASSIGNMENTS.md). Foundation start/deadline/completion dates are unknown unless evidence explicitly verifies them.

## PHASE 0 — Main Pipeline Foundation (Completed)

All 15 foundation tasks are supported by the Day 3 report and existing implementation. See [completed-task records](COMPLETED_TASKS.md) for deliverables, evidence and limitations.

| Task ID | Task Name | Description | Why We Need It | Responsible Member | Start Date | Expected Deadline | Status | Dependencies |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F01 | [MVP scope definition](COMPLETED_TASKS.md#f01) | Defined a local WAV-to-profile-and-recommendations MVP, exclusions, ownership and completion gates. | Keeps the team focused on one achievable integration milestone. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F02 | [System architecture design](COMPLETED_TASKS.md#f02) | Documented stage flow, package placement, dependency direction, failure handling and versioning. | Lets modules evolve independently while sharing a clear application design. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F03 | [Integration contract definition](COMPLETED_TASKS.md#f03) | Specified inputs, outputs, units, nullability, errors, provenance and JSON examples. | Prevents teammates from returning incompatible data. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F04 | [GitHub pipeline folder structure](COMPLETED_TASKS.md#f04) | Established the shared source, tests, tools and installable package layout under main_pipeline/. | Separates application integration from existing experiments. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F05 | [Python contracts and data validation schemas](COMPLETED_TASKS.md#f05) | Implemented eight wire contracts, JSON serialization, schema version checks and nested validation. | Catches invalid values before they spread between modules. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F06 | [Audio preprocessing implementation](COMPLETED_TASKS.md#f06) | Implemented PCM WAV reading, mono conversion, resampling, duration and quality checks. | Gives every analyzer a consistent validated waveform. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F07 | [Mock pitch and timbre analyzers](COMPLETED_TASKS.md#f07) | Added deterministic synthetic pitch statistics and a synthetic 20-value MFCC vector/centroid. | Allows interface and orchestration testing before real analyzers are ready. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F08 | [Mock song catalog](COMPLETED_TASKS.md#f08) | Added five fictional SongFeatures records with null melody ranges and mock provenance. | Provides predictable catalog data for pipeline tests. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F09 | [Mock recommendation module](COMPLETED_TASKS.md#f09) | Added deterministic song-ID ordering and fixed demonstration scores with explanations. | Lets the team test recommendation structure, sorting and result limits. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F10 | [Main pipeline orchestration](COMPLETED_TASKS.md#f10) | Connected preprocessing, analyzers, voice profile assembly and ranking with output validation and error mapping. | Turns separate module interfaces into one executable flow. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F11 | [Dependency injection and module interfaces](COMPLETED_TASKS.md#f11) | Implemented callable protocols and PipelineDependencies for substituting analyzers and rankers. | Lets teammates replace mocks without rewriting orchestration. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F12 | [Command-line interface](COMPLETED_TASKS.md#f12) | Implemented local WAV arguments, JSON success/error output, exit codes and the console entry point. | Provides a simple local way to run and demonstrate the pipeline. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F13 | [Automated testing and bug fixes](COMPLETED_TASKS.md#f13) | Added synthetic audio, contract and integration regressions and fixed four adapter-boundary defects. | Detects invalid audio, broken module behavior and regressions before handoff. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F14 | [Performance evaluation](COMPLETED_TASKS.md#f14) | Recorded cold/warm runtime samples, process memory measurements and a profile of validation costs. | Establishes a reproducible baseline before real-model latency is measured. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |
| F15 | [Integration documentation and validation report](COMPLETED_TASKS.md#f15) | Documented setup, interfaces, adapter examples, E6 migration, validation evidence and remaining risks. | Gives teammates a practical handoff and makes limitations visible. | Main Pipeline Lead | Unknown (not verified) | Unknown (not verified) | Completed | Historical dependencies not recorded |

## PHASE 1 — Real AI Module Integration

All start dates and deadlines below are proposed. The 2026-11-18 review used `main` at `774e403`. T01–T09 and T12 are complete. The T09 local changes integrate the merged pitch and timbre adapters, E3 catalog and pitch-range recommender in one CLI command. See the acceptance criteria below for merge and validation evidence.

| Task ID | Task Name | Description | Why We Need It | Responsible Member | Start Date | Expected Deadline | Status | Dependencies |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | [Distribute Integration Contract](#t01) | Share and explain the existing integration contract and team integration guide. | Shared input/output rules let modules work together without changing the main pipeline. | Main Pipeline Lead + All Team Members | 2026-11-04 | 2026-11-05 | Completed | None |
| T02 | [E1 Real Pitch Analysis Adapter](#t02) | Convert the completed E1 pitch experiment into analyze_pitch(audio_data: AudioData) -> PitchFeatures. | Replaces fake pitch values with estimates measured from the user's singing. | E1 Member | 2026-11-04 | 2026-11-10 | Completed | T01 |
| T03 | [Integrate E1 Into Main Pipeline](#t03) | Review E1's pull request, inject its real pitch adapter through PipelineDependencies and run integration tests. | Ensures the real pitch analyzer works with preprocessing and voice profile assembly. | Main Pipeline Lead + E1 Member | 2026-11-11 | 2026-11-12 | Completed | T02 |
| T04 | [E6 Real Timbre Feature Adapter](#t04) | Convert the E6 MFCC/audio feature approach into analyze_timbre(audio_data: AudioData) -> TimbreFeatures. | Adds voice descriptors beyond pitch for later evaluation in song matching. | E6 Member | 2026-11-04 | 2026-11-12 | Completed | T01 |
| T05 | [Integrate E6 Timbre Adapter](#t05) | Connect the real timbre analyzer, verify feature consistency and run integration tests. | Combines actual pitch and timbre measurements in one consistent voice profile. | Main Pipeline Lead + E6 Member | 2026-11-13 | 2026-11-15 | Completed | T04 |
| T06 | [E3 Song Analysis and Catalog Export](#t06) | Convert existing E3 song and melody analysis outputs into a catalog of SongFeatures. | Provides structured song information to compare with the user's vocal characteristics. | E3 Member | 2026-11-04 | 2026-11-14 | Completed | T01 |
| T07 | [Integrate Song Catalog](#t07) | Load the E3 catalog, validate SongFeatures records and test catalog access. | Gives the recommendation algorithm a reliable collection of songs and analyzed features. | Main Pipeline Lead + E3 Member | 2026-11-15 | 2026-11-17 | Completed | T06 |
| T08 | [Implement Basic Recommendation Algorithm](#t08) | Implement an initial rule-based recommendation algorithm. | Makes recommendations respond to the user's measured vocal characteristics. | Recommendation Member (assignment pending) | 2026-11-11 | 2026-11-19 | Completed | T01; T06 for evaluated integration (implementation may start earlier with contract-compatible sample data) |
| T09 | [Integrate Recommendation Algorithm](#t09) | Connect the real ranking function through PipelineDependencies and test recording-to-recommendation behavior. | Enables actual feature-based recommendations in place of fictional fixed rankings. | Main Pipeline Lead + Recommendation Member | 2026-11-20 | 2026-11-22 | Completed | T03, T05, T07, T08 |
| T10 | [End-to-End Integration Testing](#t10) | Test real adapters, authorized recordings and the validated song catalog as a complete system. | Finds failures between modules and checks whether outputs support an initial demonstration. | Main Pipeline Lead + All Team Members | 2026-11-23 | 2026-11-26 | Not Started | T09 |
| T11 | [Final Prototype Demonstration](#t11) | Prepare a local end-to-end SUARA demo with real analyzers and the rule-based recommender. | Demonstrates that the individual experiments form one integrated system. | Main Pipeline Lead + All Team Members | 2026-11-27 | 2026-11-29 | Not Started | T10 |
| T12 | [Evaluation Framework & Test Preparation](#t12) | Prepare a reusable evaluation framework before real AI modules are fully integrated. | Provides consistent evaluation of pitch extraction, voice features, recommendation behavior and processing performance. | Member 5 (Evaluation & Testing) | 2026-11-04 | 2026-11-20 | Completed | T01; integration contract and existing pipeline schemas (F03, F05) |
| T13 | [Minimal SUARA Demo Interface](#t13) | Develop a simple local interface using the mock pipeline first, with support for later real integration. | Lets users, teammates and professors demonstrate the workflow without terminal commands or raw JSON. | Member 6 (Demo Interface Development) | 2026-11-04 | 2026-11-22 | Not Started | Main pipeline foundation (completed); T01 |

## Remaining Phase 1 work

| Task | Remaining deliverable | Proposed deadline |
| --- | --- | --- |
| [T13](#t13) | Build a local WAV-upload interface with profile and recommendation displays, synthetic-result labels and clear errors. | 2026-11-22 |
| [T10](#t10) | After T09, evaluate the integrated pipeline with authorized recordings, measure latency, and compare rankings with the baseline. | 2026-11-26 |
| [T11](#t11) | After T10, prepare and run a reproducible demonstration with actual adapters and summarize the evaluation. | 2026-11-29 |

## Acceptance criteria

Check off individual deliverables here as evidence becomes available. Read current status from the table; do not add a second task-level completion checkbox. Add evidence links beside checked criteria and record blockers or review decisions below the relevant checklist.

### T01

**Distribute Integration Contract**

- [x] All teammates receive the [integration contract](../docs/INTEGRATION_CONTRACT.md) and [team guide](../docs/TEAM_INTEGRATION_GUIDE.md).
- [ ] Each member confirms their module's inputs and outputs.
- [ ] Every task has a confirmed owner; replace Unassigned names in TEAM_ASSIGNMENTS.md.
- [ ] Agree feature branches and PR targets before merging integration work.

**Completion evidence:** User confirmed T01 complete and T02-T09, T12 and T13 distributed; recorded on 2026-11-04. See the [completion record](COMPLETED_TASKS.md#t01). The exact completion date was not provided. Remaining checklist details (individual interface confirmations, recorded owner names and branch/PR agreement) were not separately supplied; unchecked items indicate missing recorded detail, not a reversal of the user's completion confirmation. Existing role assignments are retained.

### T02

**E1 Real Pitch Analysis Adapter**

- [x] Select a suitable method from [E1 results](../experiments/E1/README.md) and adapt the code to the application interface.
- [x] Extract measured pitch from real audio and calculate minimum, maximum, median pitch and voiced ratio.
- [x] Return validated PitchFeatures, with null pitch statistics when no voiced frames exist.
- [x] Add automated and real-worker checks using synthetic tones. See the [T02 validation results](../docs/T02_PITCH_ADAPTER.md#verified-t02-results).
- [ ] Run the documented pitch check on suitable authorized human recordings during T10. Keep private recordings out of Git. See the [authorized recording procedure](../docs/T02_PITCH_ADAPTER.md#optional-authorized-recording-check).
- [x] Document extraction parameters, detector/model version, voicing policy and known limitations.
- [x] Submit a pull request for review.

**Completion evidence (reviewed 2026-11-18):** [PR #11](https://github.com/Jeminana/SUARA-System/pull/11) merged on 2026-11-17 (`adcd30e`). The documented macOS run verified actual CREPE inference on a generated 220 Hz tone. Human-recording validation remains open under T10. See the [completion record](COMPLETED_TASKS.md#t02).

### T03

**Integrate E1 Into Main Pipeline**

- [x] Review the E1 PR and connect the adapter through PipelineDependencies.
- [x] Verify compatibility with actual preprocessing and voice profile assembly.
- [x] Run integration tests for voiced/unvoiced inputs, validated outputs, provenance and safe errors; record evidence.

**Completion evidence (reviewed 2026-11-18):** [PR #13](https://github.com/Jeminana/SUARA-System/pull/13) merged on 2026-11-17 (`774e403`). The documented real-worker test exercises WAV preprocessing, pitch and profile assembly through the Python API, with test doubles for timbre and ranking. See the [completion record](COMPLETED_TASKS.md#t03).

### T04

**E6 Real Timbre Feature Adapter**

- [x] Review [E6 feature extraction](../experiments/E6/README.md) and resolve the convention mismatch described in the [team guide](../docs/TEAM_INTEGRATION_GUIDE.md). See [migration and extraction parameters](../docs/T04_T05_TIMBRE_VALIDATION.md#exact-extraction-convention).
- [x] Re-extract the agreed 20-coefficient c0..c19 mean representation, or document an approved versioned contract change; do not pad, slice or relabel old vectors. See [fresh extraction implementation](../main_pipeline/src/suara/timbre.py).
- [x] Extract MFCC means and spectral centroid; return validated TimbreFeatures. See [adapter](../main_pipeline/src/suara/timbre.py).
- [x] Test with synthetic and authorized real audio. See [9 new tests](../main_pipeline/tests/test_timbre.py) and [42-recording validation](../docs/T04_T05_TIMBRE_VALIDATION.md#reproducible-validation).
- [x] Document extraction parameters, model version and processing version; keep ECAPA embeddings separate from MFCCs. See [implementation and version documentation](../docs/T04_T05_TIMBRE_VALIDATION.md).

**Completion evidence:** 78 pipeline tests, numerical reference comparisons and all 42 authorized E6 recording checks passed on 2026-11-15. [PR #9](https://github.com/Jeminana/SUARA-System/pull/9) merged that day (`61bf89d`). See the [historical record](COMPLETED_TASKS.md#t04).

### T05

**Integrate E6 Timbre Adapter**

- [x] Inject the real timbre analyzer through PipelineDependencies. See [CLI `--timbre real` wiring](../main_pipeline/src/suara/cli.py) and [Python API instructions](../docs/T04_T05_TIMBRE_VALIDATION.md#run-and-inject).
- [x] Verify MFCC dimension, convention, finite values and processing-version consistency. See [numerical and integration tests](../main_pipeline/tests/test_timbre.py).
- [x] Run integration tests with preprocessing and profile assembly, including mixed-mode provenance; record evidence. See [78-test and 42-recording results](../docs/T04_T05_TIMBRE_VALIDATION.md#reproducible-validation).

**Completion evidence:** [PR #9](https://github.com/Jeminana/SUARA-System/pull/9) merged on 2026-11-15 (`61bf89d`). The CLI combines actual preprocessing and optional measured timbre with labeled mock pitch and ranking. The unvoiced test uses a pitch stub. T09 covers wiring the full real flow. See the [historical record](COMPLETED_TASKS.md#t05).

### T06

**E3 Song Analysis and Catalog Export**

- [x] Select an initial authorized song or melody dataset. The [E3 handoff](../experiments/E3/handoff/song_features.json) documents five AI-drafted, team-owned pilot melodies.
- [x] Extract or review vocal melody pitch ranges; preserve interim or unverified status where review is incomplete. The [exporter](../experiments/E3/tools/export_song_features.py) distinguishes verified written melodies from unverified inputs; human-recording re-checks remain pending.
- [x] Convert MIDI notes to Hz where appropriate. [Exporter](../experiments/E3/tools/export_song_features.py): MIDI 69 -> 440 Hz and 57 -> 220 Hz verified during review.
- [x] Preserve metadata, source/excerpt information, feature version and provenance. See all five [handoff records](../experiments/E3/handoff/song_features.json).
- [x] Export records compatible with SongFeatures and test catalog validity. [Export validation](../experiments/E3/tools/export_song_features.py) and [application catalog tests](../main_pipeline/tests/test_catalog.py) pass.
- [x] Do not treat a polyphonic audio spectrum as a vocal pitch range. [Source descriptions](../experiments/E3/handoff/song_features.json) explicitly identify written lead-vocal MIDI excerpts, not full mixes or singer recordings.

**Repository review (2026-11-15):** [PR #7](https://github.com/Jeminana/SUARA-System/pull/7) merged on 2026-11-14 (`dd9c04b`; implementation `6018229`). Five records pass exporter and application contract validation. This verifies the pilot handoff, not completion of E3's pending real-singer annotation re-check. Full E3 model/experiment tests were not rerun during this documentation review. See [completion history](COMPLETED_TASKS.md#t06).

### T07

**Integrate Song Catalog**

- [x] Load the exported E3 catalog without importing its full Python 3.11 experiment stack into the Python 3.12 application. See [standard-library loader](../main_pipeline/src/suara/catalog.py) and [CLI --catalog option](../main_pipeline/src/suara/cli.py).
- [x] Validate all SongFeatures, unique song IDs, Hz units, metadata and provenance. See [catalog tests](../main_pipeline/tests/test_catalog.py); the exporter performs MIDI conversion, while the loader validates values and schema.
- [x] Test catalog access, invalid records and empty catalogs; record evidence. All 7 [catalog tests](../main_pipeline/tests/test_catalog.py) passed in Python 3.12 on 2026-11-15.

**Repository review (2026-11-15):** [PR #8](https://github.com/Jeminana/SUARA-System/pull/8) merged on 2026-11-15 (`7d805ed`; implementation `40174b4`). Tests cover the committed export, empty and malformed catalogs, duplicate/missing fields, safe file errors, CLI selection and pipeline wiring. Real-mode tests use explicitly test-only adapters; production recommendations remain mock. See [completion history](COMPLETED_TASKS.md#t07).

### T08

**Implement Basic Recommendation Algorithm**

- [x] Use pitch-range compatibility as the primary signal. See the [scoring formula](../docs/T08_RECOMMENDER_VALIDATION.md#scoring-formula-pitch-range-fit-v1).
- [x] Document the scoring formula and how missing pitch and missing or unverified song ranges are handled. See the [missing-data policy](../docs/T08_RECOMMENDER_VALIDATION.md#missing-data-provenance-and-ordering).
- [x] Return ranked Recommendation records with bounded scores, deterministic ordering and explanations. See the [recommender tests](../main_pipeline/tests/test_recommender.py).
- [x] Compare ranking results with the T12 naive baseline on the five-song E3 pilot catalog. See the [comparison](../docs/T08_RECOMMENDER_VALIDATION.md#comparison-with-the-t12-naive-baseline).
- [x] Use pitch range and median pitch only. The score describes pitch-range fit. See the [comparison findings](../docs/T08_RECOMMENDER_VALIDATION.md#what-the-comparison-shows).

**Completion evidence (reviewed 2026-11-18):** [PR #10](https://github.com/Jeminana/SUARA-System/pull/10) merged on 2026-11-17 (`c2f510a`). All 13 recommender tests passed on Windows, and the baseline comparison ran on the committed E3 catalog. T09 covers wiring the ranker into the real entry point. See the [completion record](COMPLETED_TASKS.md#t08).

### T09

**Integrate Recommendation Algorithm**

- [x] Inject the rule-based ranker with the real pitch/timbre adapters and validated E3 catalog. See the [CLI wiring](../main_pipeline/src/suara/cli.py).
- [x] Test the complete recording-to-profile-to-recommendation flow, real provenance and safe failure behavior. See [CLI integration tests](../main_pipeline/tests/test_pitch_pipeline.py) and [catalog error tests](../main_pipeline/tests/test_catalog.py).
- [x] Provide an explicit local entry point for selecting real dependencies and catalog. Run the CLI with `--mode real --catalog experiments/E3/handoff/song_features.json`. See the [setup and run instructions](../main_pipeline/README.md#real-pipeline-t09).
- [x] Record integration test results and run instructions. See the [completion record](COMPLETED_TASKS.md#t09) and [real-mode guide](../main_pipeline/README.md#real-pipeline-t09).

**Completion evidence (2026-11-20):** On Ubuntu, the CLI analyzed a generated 1-second, 220 Hz stereo WAV using actual CREPE 0.0.12 and measured timbre. It reported a 220.883 Hz median, 99.01% voiced frames and 20 MFCC means. It ranked E3-S01 (0.4753) and E3-S03 (0.1915) with real provenance and scoring version `pitch-range-fit-v1`. All 108 pipeline tests passed on Ubuntu with actual CREPE enabled. On Windows, 105 pipeline tests and all 23 evaluation-framework tests passed. Windows application control blocked TensorFlow's native DLL on this host. T10 covers authorized recordings, recommendation quality and latency.

### T10

**End-to-End Integration Testing**

- [ ] Test normal, invalid and unvoiced inputs.
- [ ] Run the T02 pitch check on suitable authorized human recordings and record qualitative observations. Use annotated reference F0 for any quantitative pitch-accuracy claim.
- [ ] Verify module compatibility and recommendation validity.
- [ ] Measure real-runtime latency with a documented method and team-agreed demonstration budget.
- [ ] Compare recommendations with a naive baseline.
- [ ] Document evaluation results, failures and limitations without claiming unmeasured suitability.

### T11

**Final Prototype Demonstration**

- [ ] Prepare an authorized example audio input and reproducible local run instructions.
- [ ] Show the extracted vocal profile, ranked songs and recommendation explanations.
- [ ] Present known limitations and a summary of evaluation results.
- [ ] Demonstrate through a CLI or documented local Python runner using actual adapters; a full GUI requires separate approval.

### T12

**Evaluation Framework & Test Preparation**

**Priority:** High

**Description:** Prepare a reusable evaluation framework before the real AI modules are fully integrated.

**Why:** Consistent methods are needed to evaluate pitch extraction, voice features, recommendation behavior and processing performance, and determine whether integrated outputs are correct and meaningful.

**Required work:**

1. Review the [integration contract](../docs/INTEGRATION_CONTRACT.md), [pipeline architecture](../docs/ARCHITECTURE.md) and [existing schemas](../main_pipeline/src/suara/contracts.py).
2. Define evaluation metrics for pitch accuracy, runtime and recommendation ranking.
3. Prepare synthetic WAV recordings with known reference frequencies.
4. Prepare different synthetic VoiceProfile examples for recommendation testing.
5. Prepare SongFeatures examples with known melody ranges.
6. Create reusable test scripts for module outputs and edge cases.
7. Define a naive recommendation baseline for later comparison.
8. Prepare tests for invalid recordings, silence and missing pitch information.
9. Document the evaluation methodology.
10. Ensure evaluation data and scripts can be reused during [T10](#t10).

**Expected deliverables:**

- Evaluation methodology document and defined evaluation metrics.
- Reusable test scripts.
- Synthetic test recordings or reproducible generation scripts.
- Sample VoiceProfile and SongFeatures fixtures.
- Baseline comparison procedure.

**Acceptance criteria:**

- [x] All evaluation metrics are clearly explained. See [methodology](../evaluation/docs/EVALUATION_METHODOLOGY.md) and [metric helpers](../evaluation/scripts/metrics.py).
- [x] Synthetic reference data can be generated reproducibly. [Generator](../evaluation/scripts/generate_audio.py): six WAVs and manifest reproduced identical SHA-256 hashes on a second run during review.
- [x] Test scripts run independently of the final integrated AI modules. All 23 [evaluation tests](../evaluation/tests/) passed against live schema 1.0.0 in Python 3.12 on 2026-11-15.
- [x] No private participant recordings are committed. Tracked evaluation assets are scripts, documentation and synthetic JSON fixtures; [ignore rules](../evaluation/.gitignore) exclude generated WAVs and private audio.
- [x] Evaluation procedures are documented. See [methodology and T10 handoff](../evaluation/docs/EVALUATION_METHODOLOGY.md).
- [x] The framework can be used in T10. [Contract bridge](../evaluation/scripts/contracts_bridge.py), fixtures, metrics and baseline ran against the live repository; real-module measurements remain T10 work.

**Repository review (2026-11-15):** [PR #6](https://github.com/Jeminana/SUARA-System/pull/6) merged on 2026-11-10 (`5948e41`; implementation `e64d996`). The sample runner and reproducible generator work; 23 tests pass. Windows sandbox tests used a writable workspace TEMP/TMP directory. The code loads live repository contracts by default; stale snapshot references were corrected in the evaluation notes. This completes framework preparation, not T10, real-model benchmarking or suitability evaluation. See [completion history](COMPLETED_TASKS.md#t12).

**Relationship to T10:** T12 prepares the tests; T10 runs them on the integrated system and analyzes actual results. Hand off the framework before T10's planned 2026-11-23 start without changing T10's existing dependency row.

### T13

**Minimal SUARA Demo Interface**

**Priority:** Medium

**Description:** Develop a simple local interface demonstrating the SUARA workflow, initially connected to the existing mock pipeline and compatible with later real integration. This is a prototype interface, not a production music streaming application.

**Why:** The current pipeline uses Python commands and JSON outputs. A local interface lets users, teammates and professors demonstrate the product without directly using a terminal.

**Required work:**

1. Review the [pipeline architecture](../docs/ARCHITECTURE.md) and [PipelineResult contract](../docs/INTEGRATION_CONTRACT.md).
2. Select a lightweight interface approach, preferably Streamlit for the first prototype.
3. Create an audio upload interface supporting WAV files.
4. Connect to the existing pipeline without duplicating its logic.
5. Display analyzed pitch information.
6. Display available timbre features.
7. Display ranked song recommendations.
8. Show song titles, artists, scores and explanations.
9. Clearly label all mock results as synthetic.
10. Display understandable error messages for invalid audio.
11. Keep the interface compatible with future real module integration.
12. Document installation and execution instructions.

**Expected deliverables:**

- Minimal working local interface with WAV upload functionality.
- VoiceProfile display and recommendation results display.
- Error handling.
- Instructions for running the demo.

**Acceptance criteria:**

- [ ] The interface starts locally.
- [ ] Users can upload a supported WAV recording.
- [ ] The interface can call the existing main pipeline.
- [ ] Voice profile information is displayed correctly.
- [ ] Recommendation results are displayed correctly.
- [ ] Mock results are clearly identified as synthetic.
- [ ] Invalid files produce understandable error messages.
- [ ] No core pipeline contract changes are made without team approval.

**Later integration:** [T03](#t03), [T05](#t05), [T07](#t07) and [T09](#t09). Initial mock-interface work does not wait for these tasks. T13 covers the minimal local interface; T11 retains its existing real-pipeline demonstration criteria.

## Proposed milestones and schedule risks

| Window | Planned work |
| --- | --- |
| 2026-11-04 to 2026-11-05 | Contract handoff, confirmed owners and branch/PR agreement (T01) |
| 2026-11-04 to 2026-11-14 | E1, E6 and E3 adapter/catalog work (T02, T04, T06), after required handoff |
| 2026-11-04 to 2026-11-20 | Evaluation framework and reusable test preparation ([T12](#t12), Member 5; High priority) |
| 2026-11-04 to 2026-11-22 | Minimal local demo interface, initially using mocks ([T13](#t13), Member 6; Medium priority) |
| 2026-11-11 to 2026-11-19 | Module/catalog integration and baseline ranking (T03, T05, T07, T08) |
| 2026-11-20 to 2026-11-22 | Complete real dependency wiring and local entry point (T09) |
| 2026-11-23 to 2026-11-26 | Real end-to-end testing and evaluation (T10) |
| 2026-11-27 to 2026-11-29 | Local prototype demonstration (T11) |

- **Converging dependencies:** T09 is complete. T10 can use the integrated CLI, and T11 waits for T10.
- **Contract handoff:** T01 is complete per user confirmation recorded on 2026-11-04. Its original planned 2026-11-05 deadline is retained; the handoff no longer blocks successor preparation.
- **T12/T13 preparation:** T12's framework is merged and verified; T13 still has no implementation evidence in fetched main. T13 should label initial mock outputs as synthetic and wait for T03/T05/T07/T09 before demonstrating real results. T12 completion does not complete T10.
- **T08 evaluation:** The five-song comparison used synthetic voice profiles. T10 evaluates real pipeline outputs.
- **E6 representation:** T04 extracts the 20 unscaled c0..c19 means from AudioData. T05 supplies optional measured timbre in mock mode, and the T09 real CLI includes measured timbre by default.
- **E3 readiness:** T06/T07 are merged: five written-melody pilot ranges are exported with excerpt/provenance information and loaded without E3's experiment stack. Real-singer annotation re-checks and broader model evaluation remain pending; catalog delivery does not resolve them.
- **Demo entry point:** The [real-mode CLI](../main_pipeline/README.md#real-pipeline-t09) uses an explicit catalog and an isolated CREPE interpreter.
- **Pitch portability:** The [pitch integration tests](../main_pipeline/tests/test_pitch_pipeline.py) launch the protocol fixture through Python on Windows and Unix. Real mode uses an editable install from the checkout to locate the [CREPE worker](../main_pipeline/tools/crepe_pitch_worker.py).
- **Owners and data:** The user confirms task distribution, but actual member names and any revised role mappings were not supplied. Existing assignments, including Member 5 for T12 and Member 6 for T13, are retained. Record confirmed names when available; authorized recordings, dataset access and model/runtime compatibility still need recorded evidence.
- **Evaluation and latency:** T02/T03 measured actual CREPE on generated tones. T10 still needs a budget and integrated timing from real runs, plus an evaluation of recommendation quality.
- **Deadline:** 2026-11-29 remains tentative. Later gates have no full spare day between them; escalate predecessor delays promptly and record any revised dates.

## Maintenance

Follow [README.md](README.md) when editing status, owners or deadlines. Preserve completed history and record actual edits in [CHANGELOG.md](CHANGELOG.md).
