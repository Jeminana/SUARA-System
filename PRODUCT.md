# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: lecturers and examiners at the SUARA capstone's final prototype demonstration (task T11, 27-29 November 2026). A team member runs the local demo on a laptop or projector while the examiners watch; they need to understand at a glance what the system took in, what it measured and why it recommends each song. Secondary: the capstone team, who present and test it.

## Product Purpose

SUARA (Malay for "voice") listens to a short singing recording, builds a vocal profile (observed pitch range and timbre descriptors) and recommends songs whose lead melody sits within that range. The demo exists to show that the separate experiments (E1 pitch, E6 timbre, E3 song melodies) work as one system. Success at T11 is an examiner who can say what the recording's range was, which songs fit it and why, and what is still synthetic.

## Positioning

Recommendations come from comparing the singer's measured pitch range with each song's verified lead-melody range, with a stated reason per song. They do not come from genre, popularity or listening history, and a full-mix spectrum is never treated as a vocal range.

## Operating Context

- Local Streamlit app (`main_pipeline/demo/app.py`) on the presenter's machine; offline at runtime. Input is one WAV upload (integer PCM, 0.5-60 s); output is a `PipelineResult` (voice profile, up to five recommendations).
- The demo interface runs the mock pipeline: synthetic pitch and timbre, five fictional catalog songs with no melody ranges, and fixed mock scores. Mock values must always be labelled as synthetic.
- The real pipeline exists alongside it: the E3 catalog (`experiments/E3/handoff/song_features.json`, five team-approved pilot melodies, A2–E4), the T08 pitch-range recommender (`pitch-range-fit-v1`) and CREPE pitch, which needs a separate worker environment.

## Capabilities and Constraints

- Pipeline contracts (schema 1.0.0) are fixed; the UI reads `PipelineResult` and must not change analysis or ranking behaviour.
- Scores are bounded 0-1 range-fit values, not probabilities and not measures of suitability. Songs with no or unverified ranges are left out; a recording with no voiced pitch yields no recommendations.
- Errors arrive as `ErrorInfo` (code, stage, message) and must be shown without file paths.
- Streamlit is the UI framework; custom styling goes through Streamlit's theming and injected CSS/HTML. No new runtime dependencies without the team's agreement.

## Brand Commitments

The team has a logo direction in `logo/` (vinyl-record mark with a wavy sound-wave line; burgundy, purple, lavender and cream; Cormorant Garamond SemiBold wordmark). The user asked for one demo redesign to draw on it; it is not yet adopted project-wide.

## Evidence on Hand

- Real: the five E3 pilot songs and their ranges; the T08 recommender and its baseline comparison (`docs/T08_RECOMMENDER_VALIDATION.md`); the pipeline's measured timbre.
- Absent and not to be fabricated: listener judgements of suitability, accuracy claims for real singers, user counts, testimonials, commercial songs or artists.

## Product Principles

1. Show the mechanism: the voice range set against each song's range is the core of the screen, not a footnote.
2. Honest by construction: synthetic, mock or unverified data is always labelled where it appears, once and clearly.
3. Every recommendation carries its reason.
4. Readable from across a room: the presenter's screen must work for people watching, not only the person at the keyboard.
