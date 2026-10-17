# E3 annotation guide for reviewers

E3 scores each tool against the notes the singer actually sang, not the notes written in the MIDI. Your job is to correct a draft note list until it matches the recording. Two reviewers do this separately for each recording, then compare.

You need no special music training: you listen, compare and drag notes. Expect roughly 10 to 30 minutes per recording. The first one will be slower.

## What you get

The E3 owner sends you `E3_reviewer_package.zip`. For each song (M01 to M05) it contains:

- the recording: `recordings/M0N.wav`
- the draft: `drafts/M0N_draft.csv`
- `review_log.csv`, for your minutes and uncertain notes

(In the repository these are `data/audio/M0N.wav` and `data/annotations/drafts/P01_M0N_T01_draft_sonic_visualiser.csv`.)

The draft is the written melody moved to the singer's timing. Most notes start close to the right place. Some have the wrong pitch or timing, because the singer did not sing exactly what was written.

These files are private recordings and are not on GitHub. Share them only through the team's private storage, and delete your copies when the project ends.

## Setup (once)

Install **Sonic Visualiser** (free, Windows/Mac/Linux) from sonicvisualiser.org.

## Steps for each recording

1. **Open the recording:** File → Open, then choose `M0N.wav`.
2. **Add a pitch picture:** Layer → Add Melodic Range Spectrogram. Sung notes show as horizontal bright lines, and the lowest bright line is the note that was sung.
   - Do **not** add pYIN, Basic Pitch or any other pitch-tracking plugin layer. Those are the methods being tested, and using them would bias the reference towards them.
3. **Import the draft:** File → Import Annotation Layer, then choose the draft CSV.
   - If a dialog asks what the columns are, choose: Time, Value, Duration, Level, Label, with the layer type **Notes**.
   - If it asks whether values are Hz or MIDI pitch, choose **MIDI pitch**.
   - The draft notes now appear as blocks over the spectrogram.
4. **Listen and compare:** play the recording. The notes layer can also be played as a tone, which makes wrong notes easy to hear against the voice.
5. **Fix what does not match**, using the Edit tool (move and resize) and the Draw tool (add notes):
   - **Start:** where the voice begins the note. For "na", that is where the "n" starts sounding.
   - **End:** where the voice stops or moves to the next note.
   - **Pitch:** the note the singer settles on and holds, not a scoop or slide into it. Use the nearest semitone.
   - **Missing note:** draw it in. **Extra note** (written but not sung): delete it.
   - **Unsure:** keep your best guess and write the time and the reason in your notes.
6. **Export:** File → Export Annotation Layer, saved as CSV. Name it `M0N_<yourname>.csv`, for example `M01_reviewerA.csv`.
7. **Fill in `review_log.csv`:** how many minutes the recording took, and the time and reason for any note you were unsure about.

When all five are done, send your five CSVs and `review_log.csv` back to the E3 owner.

Work **independently**: do not look at the other reviewer's file until both are finished. Ideally neither reviewer is the singer, since the singer knows what they meant to sing.

## After both reviewers finish (the E3 owner runs these)

Save each reviewer's files in `data/annotations/returned/<name>/`, then:

```bash
python tools/build_verified.py --names <a> <b>
```

For each recording this writes `data/annotations/P01_M0N_T01_ambiguity_log.csv` (one row per disagreement), `P01_M0N_T01_verified.csv` (the notes both reviewers agree on) and `P01_M0N_T01_unresolved.csv` (the disputed spots), plus `annotation_summary.csv` with how much sung time each recording loses. It also includes the recording and its mix in `data/recordings.csv`. Scoring leaves the unresolved spots out for the reference and every method alike.

To shrink the unresolved spots, the reviewers either listen together and agree, or do the blind re-check in [RESOLUTION_GUIDE.md](RESOLUTION_GUIDE.md) and return `M0N_<name>_v2.csv` files. Rerun with `--suffix _v2`; the verified and unresolved files are replaced.

For pitch disagreements of one semitone, the singer was usually between the two notes. Decide by measurement rather than by ear: in the plain spectrogram, hover over the steady middle of the note and read the frequency of the lowest bright line, then pick the semitone closer to it (for example, 147 Hz is D3 and 156 Hz is D#3, so 150 Hz is D3). Do not add a pitch-tracking plugin for this.

Unresolved ambiguity is allowed but must be documented: the report states how many spots and how much sung time stayed unresolved, and why.
