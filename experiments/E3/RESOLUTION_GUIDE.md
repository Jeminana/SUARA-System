# E3 re-check guide for reviewers

You and the other reviewer annotated the same five recordings. Most notes match. At some spots you chose different notes, often one semitone apart because the singer held the note between two semitones. This round settles those spots by measuring instead of judging by ear.

Work **alone**. Do not discuss the spots with the other reviewer, and do not ask what they chose: the point is that two people reach the answer independently. Your sheet shows only your own notes.

Expect roughly 1 to 2 hours in total. M05 has the most spots.

## What you get

`E3_resolution_<yourname>.zip` contains:

- `recordings/M0N.wav`: the same five recordings
- `your_first_round/M0N_<yourname>.csv`: the note layers you sent last time
- `recheck_sheet_<yourname>.csv`: the spots to re-check, one row each
- `note_frequencies.csv`: which frequency range belongs to which note

The sheet columns:

- `spot`, `recording`, `look_from_s`, `look_to_s`: where to look
- `what_to_check`: pitch, start time, or whether each note there is really a separate note
- `your_notes_there`: what you wrote last time in that window
- `measured_hz`, `changed (yes/no)`, `comment`: you fill these in

## Setup for each recording

1. Open `recordings/M0N.wav` in Sonic Visualiser.
2. Layer → Add Spectrogram (the plain one, not the melodic range one, because it measures frequency more precisely). In the layer's settings, set **Bins** to **Frequencies** if that option is offered.
3. File → Import Annotation Layer, then choose `your_first_round/M0N_<yourname>.csv`, as Notes, with MIDI pitch values, the same as last time. If you kept your Sonic Visualiser session (`.sv`) from last time, you can open that instead.

Do not add pYIN, Basic Pitch or any other pitch-tracking plugin.

## Practice first

The first row of your sheet is a practice spot: M01, 2.91 to 4.07 s, a note both reviewers agree is A3. Hover the mouse over the middle of the lowest bright line in that window and read the frequency in the information box. It should be close to 220 Hz, which `note_frequencies.csv` lists as A3 (213.7 to 226.4 Hz). Write it in `measured_hz`. If you get a very different number, you are probably on the second line (about 440 Hz), so move down to the lowest one.

## Each spot

1. Go to `look_from_s` and play to `look_to_s` a few times.
2. Do what `what_to_check` says:
   - **pitch**: hover over the steady middle of the note, not the scoop at the start or the fall at the end. Read the frequency of the lowest bright line. If the lowest line is faint, read the second line and divide by 2. Find the row of `note_frequencies.csv` whose range contains it: that is the note. Write the Hz in `measured_hz`.
   - **start**: zoom in and put the start where the voice begins the note (for "na", where the "n" starts sounding).
   - **notes**: decide whether each note there is really sung separately. Delete a note that is not there, or draw one that is missing.
3. If your note layer was wrong, fix it at that spot only, and write `yes` in `changed`. If it was right, leave the layer alone and write `no`.
4. If it is still genuinely unclear, keep your best answer and say why in `comment`, for example "measured 151 Hz, right on the D3/D#3 border".

Do not change notes outside the listed spots.

## Send back

For every recording, export your note layer (File → Export Annotation Layer, CSV) as `M0N_<yourname>_v2.csv`, even if you changed nothing in it. Send the five `_v2` files and your filled `recheck_sheet_<yourname>.csv` to the E3 owner.

## What happens next (the E3 owner runs this)

`tools/build_verified.py --suffix _v2` compares the two `_v2` files again. Spots where you now agree are settled and scored. Any spot still split is decided by a third person with the same frequency rule, or recorded as unresolved with the reason, and the report says which.
