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
