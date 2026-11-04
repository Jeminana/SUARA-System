# SUARA task board

Project: SUARA System

Phase: Real AI Module Integration

Phase Start Date: 2026-11-04

Proposed Phase Deadline: 2026-11-29 (tentative, subject to team confirmation)

Last Updated: 2026-11-04 (actual edit date; see [CHANGELOG.md](CHANGELOG.md))

Tracker created: 2026-11-02 (actual edit date; see [CHANGELOG.md](CHANGELOG.md)).

**The Status column below is the only authoritative task status.** Allowed values: Not Started, In Progress, Blocked, In Review, Completed. Checklists below describe acceptance criteria only. Responsible Member values are proposed roles; confirmed names belong in [TEAM_ASSIGNMENTS.md](TEAM_ASSIGNMENTS.md). Foundation start/deadline/completion dates are unknown unless evidence explicitly verifies them.

## PHASE 0 — Main Pipeline Foundation (Completed)

All 15 foundation tasks are supported by repository evidence. These cover the three-day foundation effort; real AI integration remains pending. See [completed-task records](COMPLETED_TASKS.md) for deliverables, evidence and limitations. Older planning snapshots are superseded for foundation completion by the Day 3 report and existing implementation.

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

All start dates and deadlines below are proposed. T01's handoff is complete per the user's update recorded on 2026-11-04; its original planned dates are retained. T02-T09, T12 and T13 have been distributed to the team. Distribution alone does not confirm implementation has begun, so their work statuses remain Not Started pending progress updates. T10 and T11 have not started. Existing downstream dependencies still apply.

| Task ID | Task Name | Description | Why We Need It | Responsible Member | Start Date | Expected Deadline | Status | Dependencies |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | [Distribute Integration Contract](#t01) | Share and explain the existing integration contract and team integration guide. | Shared input/output rules let modules work together without changing the main pipeline. | Main Pipeline Lead + All Team Members | 2026-11-04 | 2026-11-05 | Completed | None |
| T02 | [E1 Real Pitch Analysis Adapter](#t02) | Convert the completed E1 pitch experiment into analyze_pitch(audio_data: AudioData) -> PitchFeatures. | Replaces fake pitch values with estimates measured from the user's singing. | E1 Member | 2026-11-04 | 2026-11-10 | Not Started | T01 |
| T03 | [Integrate E1 Into Main Pipeline](#t03) | Review E1's pull request, inject its real pitch adapter through PipelineDependencies and run integration tests. | Ensures the real pitch analyzer works with preprocessing and voice profile assembly. | Main Pipeline Lead + E1 Member | 2026-11-11 | 2026-11-12 | Not Started | T02 |
| T04 | [E6 Real Timbre Feature Adapter](#t04) | Convert the E6 MFCC/audio feature approach into analyze_timbre(audio_data: AudioData) -> TimbreFeatures. | Adds voice descriptors beyond pitch for later evaluation in song matching. | E6 Member | 2026-11-04 | 2026-11-12 | Not Started | T01 |
| T05 | [Integrate E6 Timbre Adapter](#t05) | Connect the real timbre analyzer, verify feature consistency and run integration tests. | Combines actual pitch and timbre measurements in one consistent voice profile. | Main Pipeline Lead + E6 Member | 2026-11-13 | 2026-11-15 | Not Started | T04 |
| T06 | [E3 Song Analysis and Catalog Export](#t06) | Convert existing E3 song and melody analysis outputs into a catalog of SongFeatures. | Provides structured song information to compare with the user's vocal characteristics. | E3 Member | 2026-11-04 | 2026-11-14 | Not Started | T01 |
| T07 | [Integrate Song Catalog](#t07) | Load the E3 catalog, validate SongFeatures records and test catalog access. | Gives the recommendation algorithm a reliable collection of songs and analyzed features. | Main Pipeline Lead + E3 Member | 2026-11-15 | 2026-11-17 | Not Started | T06 |
| T08 | [Implement Basic Recommendation Algorithm](#t08) | Replace fixed mock rankings with an initial rule-based recommendation algorithm. | Makes recommendations respond to the user's measured vocal characteristics. | Recommendation Member (assignment pending) | 2026-11-11 | 2026-11-19 | Not Started | T01; T06 for evaluated integration (implementation may start earlier with contract-compatible sample data) |
| T09 | [Integrate Recommendation Algorithm](#t09) | Connect the real ranking function through PipelineDependencies and test recording-to-recommendation behavior. | Enables actual feature-based recommendations in place of fictional fixed rankings. | Main Pipeline Lead + Recommendation Member | 2026-11-20 | 2026-11-22 | Not Started | T03, T05, T07, T08 |
| T10 | [End-to-End Integration Testing](#t10) | Test real adapters, authorized recordings and the validated song catalog as a complete system. | Finds failures between modules and checks whether outputs support an initial demonstration. | Main Pipeline Lead + All Team Members | 2026-11-23 | 2026-11-26 | Not Started | T09 |
| T11 | [Final Prototype Demonstration](#t11) | Prepare a local end-to-end SUARA demo with real analyzers and the rule-based recommender. | Demonstrates that the individual experiments form one integrated system. | Main Pipeline Lead + All Team Members | 2026-11-27 | 2026-11-29 | Not Started | T10 |
| T12 | [Evaluation Framework & Test Preparation](#t12) | Prepare a reusable evaluation framework before real AI modules are fully integrated. | Provides consistent evaluation of pitch extraction, voice features, recommendation behavior and processing performance. | Member 5 (Evaluation & Testing) | 2026-11-04 | 2026-11-20 | Not Started | T01; integration contract and existing pipeline schemas (F03, F05) |
| T13 | [Minimal SUARA Demo Interface](#t13) | Develop a simple local interface using the mock pipeline first, with support for later real integration. | Lets users, teammates and professors demonstrate the workflow without terminal commands or raw JSON. | Member 6 (Demo Interface Development) | 2026-11-04 | 2026-11-22 | Not Started | Main pipeline foundation (completed); T01 |

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

- [ ] Select a suitable method from [E1 results](../experiments/E1/README.md) and adapt the code to the application interface.
- [ ] Extract measured pitch from real audio and calculate minimum, maximum, median pitch and voiced ratio.
- [ ] Return validated PitchFeatures, with null pitch statistics when no voiced frames exist.
- [ ] Add tests using synthetic tones and suitable authorized recordings; keep private recordings out of Git.
- [ ] Document extraction parameters, detector/model version, voicing policy and known limitations.
- [ ] Submit a pull request for review.

### T03

**Integrate E1 Into Main Pipeline**

- [ ] Review the E1 PR and connect the adapter through PipelineDependencies.
- [ ] Verify compatibility with actual preprocessing and voice profile assembly.
- [ ] Run integration tests for voiced/unvoiced inputs, validated outputs, provenance and safe errors; record evidence.

### T04

**E6 Real Timbre Feature Adapter**

- [ ] Review [E6 feature extraction](../experiments/E6/README.md) and resolve the convention mismatch described in the [team guide](../docs/TEAM_INTEGRATION_GUIDE.md).
- [ ] Re-extract the agreed 20-coefficient c0..c19 mean representation, or document an approved versioned contract change; do not pad, slice or relabel old vectors.
- [ ] Extract MFCC means and spectral centroid; return validated TimbreFeatures.
- [ ] Test with synthetic and authorized real audio.
- [ ] Document extraction parameters, model version and processing version; keep ECAPA embeddings separate from MFCCs.

### T05

**Integrate E6 Timbre Adapter**

- [ ] Inject the real timbre analyzer through PipelineDependencies.
- [ ] Verify MFCC dimension, convention, finite values and processing-version consistency.
- [ ] Run integration tests with preprocessing and profile assembly, including mixed-mode provenance; record evidence.

### T06

**E3 Song Analysis and Catalog Export**

- [ ] Select an initial authorized song or melody dataset.
- [ ] Extract or review vocal melody pitch ranges; preserve interim or unverified status where review is incomplete.
- [ ] Convert MIDI notes to Hz where appropriate.
- [ ] Preserve metadata, source/excerpt information, feature version and provenance.
- [ ] Export records compatible with SongFeatures and test catalog validity.
- [ ] Do not treat a polyphonic audio spectrum as a vocal pitch range.

### T07

**Integrate Song Catalog**

- [ ] Load the exported E3 catalog without importing its full Python 3.11 experiment stack into the Python 3.12 application.
- [ ] Validate all SongFeatures, unique song IDs, Hz units, metadata and provenance.
- [ ] Test catalog access, invalid records and empty catalogs; record evidence.

### T08

**Implement Basic Recommendation Algorithm**

- [ ] Use pitch-range compatibility as the primary baseline signal.
- [ ] Define and document a transparent scoring formula and safe missing-pitch/missing-song-range policy.
- [ ] Return validated, ranked Recommendation records with bounded scores, deterministic ordering and a reason for each ranking.
- [ ] Compare results with a simple naive baseline using the E3 catalog for evaluated integration.
- [ ] Do not assume MFCC similarity proves song suitability.

### T09

**Integrate Recommendation Algorithm**

- [ ] Inject the rule-based ranker with the real pitch/timbre adapters and validated E3 catalog.
- [ ] Test the complete recording-to-profile-to-recommendation flow, real provenance and safe failure behavior.
- [ ] Provide an explicit local entry point for selecting real dependencies/catalog: update CLI wiring or supply a documented Python runner for T11. The current CLI rejects real mode.
- [ ] Record integration test results and run instructions.

### T10

**End-to-End Integration Testing**

- [ ] Test normal, invalid and unvoiced inputs.
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

- [ ] All evaluation metrics are clearly explained.
- [ ] Synthetic reference data can be generated reproducibly.
- [ ] Test scripts run independently of the final integrated AI modules.
- [ ] No private participant recordings are committed.
- [ ] Evaluation procedures are documented.
- [ ] The framework can be used in T10.

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

- **Converging dependencies:** T09 waits for T03, T05, T07 and T08; T10 then waits for T09 and T11 for T10. T08 finishes last in the proposed predecessor schedule, with no full spare day before T09.
- **Contract handoff:** T01 is complete per user confirmation recorded on 2026-11-04. Its original planned 2026-11-05 deadline is retained; the handoff no longer blocks successor preparation.
- **T12/T13 preparation:** Both tasks have been distributed and their T01 handoff dependency is satisfied. Implementation progress is not yet reported. T12 prepares evaluation assets before T10, while T13 labels initial mock outputs as synthetic and waits for T03/T05/T07/T09 before demonstrating real results.
- **T08 evaluation:** Ranking code may use compatible sample records from 2026-11-11, but evaluated integration waits for T06's catalog, due 2026-11-14.
- **E6 representation:** Existing development-scaled, c0-excluded pooled features cannot be relabeled as the agreed 20 unscaled c0..c19 means. T04 needs re-extraction or an approved versioned migration.
- **E3 readiness:** The repository describes interim results and pending review. T06 must preserve verification/provenance, secure authorized data, and export compatible records without importing the full experiment stack.
- **Demo entry point:** The current CLI rejects real mode. T09 must provide explicit real dependency/catalog wiring through the CLI or a documented local Python runner before T11.
- **Owners and data:** The user confirms task distribution, but actual member names and any revised role mappings were not supplied. Existing assignments, including Member 5 for T12 and Member 6 for T13, are retained. Record confirmed names when available; authorized recordings, dataset access and model/runtime compatibility still need recorded evidence.
- **Evaluation and latency:** Prior measurements concern mocks only. Agree real-runtime budgets and a naive comparison before T10; feature validity does not prove recommendation usefulness.
- **Deadline:** 2026-11-29 remains tentative. Later gates have no full spare day between them; escalate predecessor delays promptly and record any revised dates.

## Maintenance

Follow [README.md](README.md) when editing status, owners or deadlines. Preserve completed history and record actual edits in [CHANGELOG.md](CHANGELOG.md).
