# SUARA System

SUARA (from *Sesuai Suara*, “suitable for the voice”) is a proposed AI-powered vocal profile and music recommendation service. It analyzes a short singing sample and aims to recommend songs, artists, and song keys that fit the singer. The primary product direction is an analysis and recommendation engine that can integrate with a music streaming service; a web demonstration will validate the idea first. This project is a capstone feasibility prototype, not a complete streaming platform.

The proposal describes intended capabilities. They are not validated product claims, and the main pipeline has not been implemented yet.

## Project goals

The planned analysis turns a short vocal sample into an explainable profile that may include:

- Observed vocal range and, with enough appropriate recordings, comfortable range (tessitura)
- Pitch accuracy, stability, rhythm, timing, vibrato, dynamics, and broad phrasing features
- A singing voice embedding for comparisons between prepared singer profiles

The recommendation engine is intended to combine these measurements with music preferences. It would return suitable songs, suggest a key shift when useful, and show the reasons behind its recommendations. Artist results are profile similarities, not identity claims. A short sample estimates observed performance; it cannot establish a user's full capability or comfortable range on its own.

## Phase 1 prototype scope

The proposed capstone prototype is a controlled web demonstration with guided recording, vocal analysis, explainable recommendations, and a basic structured interface for future platform requests. Its planned catalog is approximately five to ten prepared songs and ten to twenty artist profiles. The demo aims to show a vocal profile, song recommendations, key guidance, and up to three similar artist profiles.

The initial prototype does not include a commercial streaming catalog, unrestricted uploads, real-time analysis of every song, clinical voice assessment, or guaranteed training outcomes. A partner integration is not secured. Any streaming-style integration will use authorized test material or a simulated partner interface until permitted content access and an agreement exist.

## Proposed system flow

1. The user selects a supported song or guided vocal prompt and records a short sample.
2. SUARA checks the recording and extracts pitch, timing, range, stability, timbre, and selected musical features.
3. The service compares the user's profile with song and artist profiles prepared and reviewed in advance.
4. The service returns ranked songs, key suggestions, and artist profile matches with explanations.
5. With permission, approved feedback and history may improve later recommendations.

Catalog preparation and review are separate from analysis of a user's recording. The prototype should store audio separately from searchable profile records and apply consent, access, and retention controls. A Python analysis service and structured API are proposed; FastAPI, SQLite, and PostgreSQL are implementation candidates, not completed components.

## Experiment programme

Experiments evaluate the analysis methods and recommendations before the project commits to the full feature set. The proposal identifies E1, E3, and E6 as active; other work depends on feasibility results.

| ID | Experiment | Evidence sought | Proposal status |
|---|---|---|---|
| E1 | Pitch detection | Compare pYIN and CREPE for pitch error, voicing, noise robustness, and runtime | Active |
| E2 | Vocal profile extraction | Repeatability of range, tessitura, stability, vibrato, and dynamics | Planned |
| E3 | Song and reference melody analysis | Note errors and manual effort for MIDI, isolated vocals, and separated mixes | Active |
| E4 | Vocal-to-song matching | Compare rankings with range-only matching and participant suitability ratings | Planned |
| E5 | Automatic key recommendation | Test range coverage after transposition and participant comfort ratings | Planned |
| E6 | Timbre and singing voice embedding | Same-singer and different-singer similarity across melodies and takes | Active |
| E7 | Similar artist or singer matching | Test ranking repeatability and plausibility; compare embeddings with combined features | Planned |
| E8 | Pitch accuracy and rhythm analysis | Test alignment against references and tolerance to performance variation | Planned |
| E9 | End-to-end feasibility | Evaluate the full flow, response time, robustness, usefulness, and usability | Planned |

Each experiment should record its data, configuration, measured results, failures, and conclusion. Set acceptance thresholds before final evaluation. No successful result is claimed by the proposal; findings should guide technology selection and reduce or defer features that do not meet agreed criteria.

## Repository layout

- `main_pipeline/` — reserved for the shared pipeline; implementation has not started
- `experiments/E1/` through `experiments/E9/` — experiment workspaces and documentation
- `experiments/E3/` — song and reference melody analysis implementation and its README
- `experiments/E6/` — current voice embedding implementation and its README

E1, E3, and E6 have report-based procedure summaries in their experiment READMEs. Other experiment folders are placeholders until work begins.

## Data, privacy, and limitations

Voice recordings and embeddings are sensitive personal data. Obtain informed consent, explain how data will be used and retained, restrict access, and provide deletion controls. Keep consent identities separate from anonymous participant IDs. Do not commit private recordings, embeddings, credentials, model downloads, virtual environments, or generated outputs.

Use consented or appropriately licensed audio, melodies, lyrics, metadata, and artist material. Access to a streaming API does not itself grant permission to analyze full audio. Model availability, checkpoint terms, and processing requirements need review before adoption. Results may vary across languages, voice types, and singing styles; prototype recommendations and measurements need user evaluation and should not be presented as clinical advice.

## Working together

Contributors should work on separate branches and push them to this repository, then open a pull request to `main` for integration. Keep experiment-specific code and notes in that experiment's folder, and shared pipeline code in `main_pipeline/`. Each contributor needs write access to the GitHub repository.

```bash
git push -u origin <branch-name>
```
