# SUARA E3: Song Analysis Feasibility

E3 tests whether SUARA can prepare reliable lead-vocal melody profiles for a small song catalog, and identifies which parts need manual verification. It compares a known symbolic reference, transcription from isolated vocals, and source separation followed by pitch extraction. A full mix's most prominent pitch is not necessarily the lead singer's melody.

This is a proposed Phase 1 pilot procedure; no experiment results are claimed yet. E3 starts independently with a provisional pYIN baseline and can rerun using E1's selected detector later. Its catalog supports E4 song matching and E5 key recommendation.

## Proposed pilot material

Begin with five team-composed excerpts of 20-40 seconds. Include a narrow and wide range, sustained high notes, large jumps, and fast notes. Create MIDI with note start, end, and pitch, plus optional accompaniment. Record a consented singer performing isolated vocals, then mix those vocals with the accompaniment to create paired isolated and mixed audio.

The MIDI gives exact notes for controlled synthesized checks, but intended notes are not exact ground truth for a human performance. For human vocals, use verified annotations of the actual sung F0 or note events. Two reviewers should verify sung note pitches and boundaries and document unresolved ambiguity. Optional licensed excerpts can test external validity after checking each recording's terms.

Use two excerpts for development and three held-out excerpts for testing. Keep paired stems, mixtures, and alternate crops in the same split. Do not tune settings separately for each test excerpt.

## Comparison procedure

1. Create a catalog and rights manifest with song ID, source, licence or permission, excerpt boundaries, singer ID, audio paths, and reference path.
2. Import and verify the known MIDI lead track, pitch convention, tempo map, and duration. Export reference notes as `start_s`, `end_s`, and `midi_note`.
3. Run Basic Pitch on the isolated melody or vocal. Export note events and MIDI; inspect false chords, duplicate notes, fragmented sustained notes, and document rules for selecting one lead line.
4. Run provisional pYIN on isolated human vocals. Convert valid F0 to MIDI pitch with `69 + 12 * log2(F0 / 440)` and retain the continuous contour.
5. Run Demucs on the paired mix, select its vocal stem, and run the same pitch detector with identical settings. Listen for separation artifacts, backing vocals, and residual instruments. Also run pitch detection directly on the mix as a diagnostic baseline.
6. For note metrics, segment voiced contours into note events using duration and pitch-change rules chosen on development excerpts. Preserve and compare raw and corrected outputs separately.
7. Build verified profiles and evaluate on held-out excerpts. Measure each processing stage and manual correction time per excerpt. Record unknown key or tempo as unknown instead of guessing.

Use separate environments for tools when needed. The report proposes librosa, soundfile, NumPy, pandas, a MIDI reader such as pretty_midi, Basic Pitch, and Demucs. Test each tool on a short file first, preserve originals, and record package versions, hardware, model/checkpoint details, random seed, and code commit. Basic Pitch is general note transcription and works best on one instrument; do not assume it isolates the lead melody in a mix. Record the exact Demucs environment and checkpoint.

## Metrics and proposed targets

- **Frame pitch accuracy:** reference voiced frames with prediction within 50 cents; missing predictions count as failures.
- **Note precision, recall, and F1:** one-to-one note match within 50 cents and 50 ms onset tolerance; report offset accuracy separately.
- **Range endpoint error:** absolute low and high endpoint differences in semitones.
- **Concentration band error:** difference in duration-weighted 10th and 90th pitch percentiles.
- **Runtime and correction effort:** seconds per excerpt for each stage and manual correction minutes per item.

Proposed pilot targets are at least 85% frame accuracy, at least 0.80 note F1, and each reliable range endpoint within one semitone on clean test excerpts. These provisional targets justify further testing only. Flag outliers, octave mistakes, harmonies, and separation artifacts. Do not publish a difficulty label without a defined rule and later human evaluation.

## Song profiles and handoff

Provide `song_profiles.csv` with `song_id`, `excerpt_start_s`, `excerpt_end_s`, `low_midi`, `high_midi`, `p10_midi`, `p90_midi`, `verified_key`, `bpm`, `source_type`, `method`, `verified_by`, and `quality_flag`. Include `melody_notes.csv` with `start_s`, `end_s`, `midi_note`, and `confidence`, plus duration-weighted histogram bins. MIDI 60 is C4. Key and BPM describe the music and are separate from vocal range.

The duration-weighted 10th-90th percentile band is a melody concentration proxy, not a singer comfort range. Label every profile as an excerpt; validate full songs before recommending them as complete songs. Keep raw and manually corrected profiles as distinct versions. Compare one-time preprocessing cost with repeated on-demand cost. If automatic melody recovery fails, a manually verified MIDI catalog is an acceptable restricted prototype outcome.

Hand off verified profiles and note distributions to E4 and E5, along with actual test counts, splits, exclusions, rights evidence, versions, settings, raw outputs, metrics, plots, timing, and correction logs. Document departures from the proposed procedure and conclude Feasible, Partially feasible, or Not feasible for the stated scope.

Use anonymous participant IDs. Keep consent identities separately, restrict recordings to the team, state a deletion date, and do not commit private audio or identity information to a public repository. Prefer team-composed melodies and consented recordings. Verify permissions for external recordings before acquiring or sharing them.

## Setup

From this directory, with Python 3.11 (basic-pitch 0.4.0 needs TensorFlow < 2.15.1, which has no wheels for Python 3.12 or newer):

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
python -m unittest discover -s tests
```

One environment holds every tool. `setuptools<81` is pinned because basic-pitch's resampy still imports `pkg_resources`. Demucs downloads its `htdemucs` checkpoint from HuggingFace into `pretrained_models/` on first use; every run records the snapshot commit and file hashes in `environment.json`. Record `pip freeze > requirements.lock.txt` for each locked run.

## Data and manifests

```text
data/catalog.csv      one row per catalog item: split, excerpt, MIDI reference, rights record
data/recordings.csv   one row per audio item and its reference
data/corrections.csv  optional manual correction log
data/midi/ data/audio/ data/annotations/
```

Blank templates with every column are in `templates/`. Paths inside the manifests are relative to `data/`.

- **catalog.csv**: `song_id` (S01), `split` (`dev` or `test`), excerpt boundaries in song time, `midi_path` and `lead_track` (track name or index), and the rights record (`source_type`, `creator`, `licence_or_permission`, plus `source_url`, `item_id`, `allowed_uses`, `access_date` and `redistribution_restrictions` for external items). Items without a recorded licence or permission are excluded and logged. `verified_key`, `bpm` and `verified_by` come from people; blank key or tempo is reported as `unknown`, never guessed from the MIDI file.
- **recordings.csv**: `kind` is `synth_melody` (rendered from the MIDI), `isolated_vocal` (consented human take, named like `P01_M01_T01`), `mix` (that take plus accompaniment, with `paired_with` set to the isolated take), or `licensed_mix`. `audio_offset_s` is where the excerpt starts in the audio file. `reference_type` is `midi` for synthesized material or `notes_csv` for the two-reviewer verified annotation of what was actually sung; an optional `reference_f0_path` (`time_s`, `f0_hz`) gives a verified F0 track for frame accuracy, and an optional `unresolved_path` (`start_s`, `end_s`) lists spans the reviewers could not agree on, which every metric leaves out for the reference and all methods alike. A mix inherits its reference, singer and consent from its paired take. Human recordings need `consent = yes`.
- **corrections.csv**: `recording_id`, `method` (as labelled in the outputs, e.g. `pyin`, `basic_pitch`, `demucs+pyin`), `reviewer`, `correction_minutes` and `corrected_notes_path`. Corrected notes are scored as a separate `corrected` version; raw outputs are never overwritten.

Splits are assigned per song, so paired stems, mixtures and alternate crops always share a split. Annotation and note files use `start_s`, `end_s` and `midi_note` in the recording's audio time; MIDI 60 is C4. Use `tools/compare_annotations.py a.csv b.csv --names a b` to compare two reviewers and produce an ambiguity log, one row per disagreement, to resolve or document.

## Workflow

```bash
python run_e3.py check --tools   # validate manifests and rights, verify MIDI, audio QC, try each tool on a 5 s crop
python run_e3.py dev             # dev songs only: sweep segmentation rules and Basic Pitch thresholds
# Copy the chosen settings into config.yaml (dev_best.json lists them), then set locked: true.
python run_e3.py test            # held-out songs; refuses to run until locked: true
python run_e3.py catalog         # E4/E5 handoff profiles from verified reference melodies
```

`check` writes `midi_check.csv` (lead track, low/high note names to confirm the pitch convention, tempo map, key signatures, overlapping notes), `audio_check.csv` and the exported `reference_notes/`. `dev` writes per-candidate results and `dev_best.json`, chosen on note F1 over non-diagnostic methods only. The diagnostic pitch-on-mix baseline is never used to choose settings.

Routes (`methods` in `config.yaml`) run on the recording kinds they apply to:

| Label | Input | Steps |
|---|---|---|
| `basic_pitch` | isolated melody or vocal | Basic Pitch note events, then the lead-line rules |
| `pyin` | isolated melody or vocal | pYIN contour, then segmentation into notes |
| `demucs+pyin` | paired mix | Demucs vocal stem, then the same detector with identical settings |
| `demucs+basic_pitch` | paired mix | optional; off by default |
| `pyin_mix` | paired mix | diagnostic baseline directly on the mix |

The lead-line rules (`lead_line`) drop short notes, keep the loudest note where notes overlap (counting rejected notes as duplicates or false chord notes), and merge fragmented sustained notes. `lead_line_selection.csv` records how often each rule fired. The pitch detector sits behind a small interface in `e3/methods.py`; when E1 selects a detector, add it there and set `pitch.detector`.

## Test outputs

`outputs/<run>_test/` contains:

- `results_table.csv` and `report_summary.md`: the report's results table, pilot target checks, per-recording metrics, separation comparison, sung-vs-intended differences and cost summary
- `per_recording_metrics.csv` and `aggregate_metrics.csv`: frame accuracy, voicing, octave error rate, note P/R/F1 (onset-only and with offsets), onset/offset errors, range endpoint and concentration band errors, quality flags
- `raw/<recording>/`: reference notes, each method's notes, continuous contours, Basic Pitch raw MIDI and note events
- `stems/`: Demucs vocal stems, to listen for separation artifacts, backing vocals and residual instruments
- `plots/`: per-recording piano rolls of reference against each method, plus `method_summary.png`
- `separation_comparison.csv`: each mix against its paired isolated take
- `intended_vs_sung.csv`: verified sung annotation against the intended MIDI on MIDI time, so it mixes timing with pitch; prefer `intended_vs_sung_aligned.csv` below
- `timing.csv` and `cost_summary.csv`: per-stage seconds per excerpt, model load time, one-time catalog preprocessing against on-demand cost
- `all_profiles.csv`: raw, corrected and reference profiles as distinct versions
- `environment.json`: config hash, package versions, hardware, seed, code commit, Basic Pitch model and Demucs checkpoint

`python tools/report_tables.py outputs/<run>_test --names <a> <b>` adds supporting tables from a finished run without rerunning any tool: `reviewer_sensitivity.csv` (methods scored against the agreed notes with unresolved spots left out, and against each reviewer's full annotation), `frame_error_breakdown.csv` (correct, missed, near-miss and wrong frames per contour method) and `intended_vs_sung_aligned.csv` (sung against intended pitch note by note on the singer's timing).

`catalog` writes `catalog/song_profiles.csv` (the handoff fields above plus `profile_version`), `melody_notes.csv`, `pitch_histogram.csv` (duration-weighted, one bin per semitone) and `song_profile_details.csv` (note names and interval statistics). Profiles come from the verified MIDI lead track, or from `verified_notes_path` when the catalog points at a reviewer-corrected transcription. Songs without a `verified_by` reviewer are flagged `unverified`.

## Pilot data preparation

```bash
python tools/make_pilot_songs.py --out data        # five pilot MIDI songs + practice audio (G2-E4 singer)
# record one isolated vocal per song as data/audio/M01.wav ... M05.wav
python tools/prepare_pilot_data.py --data data      # synth melodies, mixes, annotation drafts, manifests
```

`prepare_pilot_data.py` aligns each MIDI melody to its recording with chroma-based dynamic time warping (none of the tested methods is involved). It renders the accompaniment on the singer's timing for the mix and writes annotation drafts with MIDI pitches on the singer's timing. Original recordings are never modified. Human recordings stay excluded as "awaiting verified annotation" until `tools/build_verified.py --names <a> <b>` builds the verified file (the notes both reviewers agree on) and the unresolved spots from the two reviewers' exports, and includes them; see [ANNOTATION_GUIDE.md](ANNOTATION_GUIDE.md). `tools/import_annotation.py` converts a single Sonic Visualiser export into an E3 note file. If the reviewers cannot meet to resolve disagreements, `tools/make_resolution_package.py --names <a> <b>` builds a blind re-check package for each reviewer from the ambiguity logs; see [RESOLUTION_GUIDE.md](RESOLUTION_GUIDE.md).

## Synthetic smoke test

```bash
python tools/make_synthetic_data.py --out data/synthetic
python run_e3.py check --data-root data/synthetic --synthetic --tools
python run_e3.py dev   --data-root data/synthetic --synthetic
```

This builds five MIDI songs covering narrow range, wide range, sustained high notes, large jumps and fast notes, with a synthesized melody, a voice-like take with its exact annotation, and a paired mix. It only proves the code runs. Demucs does not treat the additive synthetic "voice" as vocals, so the separation results on this data say nothing about real singing. Never report synthetic results as findings.

`data/`, `outputs/`, `pretrained_models/` and virtual environments are gitignored.
