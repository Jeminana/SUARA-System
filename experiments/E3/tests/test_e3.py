"""Unit tests for E3 metrics, segmentation, lead line rules and profiles.

    python -m unittest discover -s tests

These use small hand-built inputs and do not load Basic Pitch, Demucs or audio files.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from e3 import evaluation as ev  # noqa: E402
from e3 import profiles as pf  # noqa: E402
from e3 import references as rf  # noqa: E402
from e3.methods import segment_contour, select_lead_line  # noqa: E402

CFG = {"frame_hop_s": 0.01, "pitch_tolerance_cents": 50, "onset_tolerance_s": 0.05, "offset_ratio": 0.2,
       "offset_min_tolerance_s": 0.05, "reliable_min_note_s": 0.15}
RULES = {"smoothing_frames": 5, "pitch_change_semitones": 0.8, "change_frames": 4, "min_note_s": 0.08,
         "merge_gap_s": 0.03}


def notes(rows):
    return rf.clean_notes(pd.DataFrame(rows, columns=["start_s", "end_s", "midi_note"]))


def contour(segments, hop=0.01, vibrato=0.0):
    """segments: (duration_s, midi or None). Returns a pYIN-like contour table."""
    midi = []
    for dur, m in segments:
        n = int(round(dur / hop))
        if m is None:
            midi += [np.nan] * n
        else:
            t = np.arange(n) * hop
            midi += list(m + vibrato * np.sin(2 * np.pi * 5.5 * t))
    midi = np.array(midi)
    return pd.DataFrame({"time_s": np.arange(len(midi)) * hop, "midi": midi,
                         "voiced_prob": np.where(np.isfinite(midi), 0.9, 0.1)})


class ConversionTests(unittest.TestCase):
    def test_hz_to_midi(self):
        out = rf.hz_to_midi(np.array([440.0, 261.6256, 0.0, np.nan]))
        self.assertAlmostEqual(out[0], 69.0)
        self.assertAlmostEqual(out[1], 60.0, places=3)
        self.assertTrue(np.isnan(out[2]) and np.isnan(out[3]))

    def test_middle_c_is_c4(self):
        self.assertEqual(rf.note_name(60), "C4")

    def test_crop_and_shift(self):
        n = notes([(0.5, 1.5, 60), (2.0, 3.0, 62), (9.0, 10.0, 64)])
        c = rf.crop_notes(n, 1.0, 5.0)
        self.assertEqual(c[["start_s", "end_s", "midi_note"]].values.tolist(), [[0.0, 0.5, 60], [1.0, 2.0, 62]])


class SegmentationTests(unittest.TestCase):
    def test_two_notes_with_vibrato_stay_two_notes(self):
        c = contour([(0.5, 60), (0.5, 64)], vibrato=0.3)
        out = segment_contour(c, RULES)
        self.assertEqual(out["midi_note"].tolist(), [60, 64])
        self.assertAlmostEqual(out["start_s"].iloc[1], 0.5, delta=0.05)

    def test_unvoiced_gap_splits_and_short_blip_dropped(self):
        c = contour([(0.4, 67), (0.1, None), (0.04, 70), (0.1, None), (0.4, 67)])
        out = segment_contour(c, RULES)
        self.assertEqual(out["midi_note"].tolist(), [67, 67])

    def test_merge_gap_joins_fragmented_sustain(self):
        c = contour([(0.4, 65), (0.02, None), (0.4, 65)])
        self.assertEqual(len(segment_contour(c, RULES)), 1)


class LeadLineTests(unittest.TestCase):
    RULES = {"priority": "amplitude", "overlap_tolerance_s": 0.03, "min_note_s": 0.06, "merge_gap_s": 0.03}

    def test_chord_duplicate_fragment_and_short_rules(self):
        ev_ = rf.clean_notes(pd.DataFrame([
            (0.0, 1.0, 60, 0.9),   # lead
            (0.0, 1.0, 48, 0.5),   # false chord note under it
            (0.1, 0.9, 60, 0.4),   # duplicate of the lead
            (1.0, 1.5, 62, 0.8),   # fragment 1
            (1.52, 2.0, 62, 0.8),  # fragment 2
            (2.5, 2.52, 70, 0.9),  # too short
        ], columns=rf.NOTE_COLUMNS))
        line, counts = select_lead_line(ev_, self.RULES)
        self.assertEqual(line["midi_note"].tolist(), [60, 62])
        self.assertEqual(counts["chord_notes_removed"], 1)
        self.assertEqual(counts["duplicates_removed"], 1)
        self.assertEqual(counts["fragments_merged"], 1)
        self.assertEqual(counts["short_removed"], 1)


class MetricTests(unittest.TestCase):
    def test_perfect_prediction(self):
        ref = notes([(0.0, 0.5, 60), (0.5, 1.0, 62), (1.2, 2.0, 64)])
        m = ev.evaluate(ref, ref, 2.0, CFG)
        self.assertEqual(m["frame_accuracy"], 1.0)
        self.assertEqual(m["note_f1"], 1.0)
        self.assertEqual(m["low_error_st"], 0.0)

    def test_tolerances(self):
        ref = notes([(0.0, 0.5, 60), (0.6, 1.0, 62)])
        est = notes([(0.04, 0.5, 60), (0.70, 1.0, 62)])  # 40 ms (match) and 100 ms (miss) late
        m = ev.note_metrics(ref, est, CFG)
        self.assertAlmostEqual(m["note_f1"], 0.5)

    def test_missing_frames_fail_and_octaves_are_counted(self):
        ref = np.array([60.0, 60.0, 60.0, 60.0, np.nan])
        est = np.array([60.3, 72.0, np.nan, 60.0, 60.0])
        m = ev.frame_metrics(ref, est, 50)
        self.assertAlmostEqual(m["frame_accuracy"], 0.5)
        self.assertAlmostEqual(m["octave_error_rate"], 0.25)
        self.assertAlmostEqual(m["voicing_false_alarm"], 1.0)

    def test_unresolved_spans_are_left_out(self):
        ref = notes([(0.0, 0.5, 60), (1.5, 2.0, 64)])  # nothing agreed in the disputed 0.6-1.4 s
        est = notes([(0.0, 0.5, 60), (0.7, 1.2, 50), (1.5, 2.0, 64)])  # a low note in the dispute
        plain = ev.evaluate(ref, est, 2.0, CFG)
        skipped = ev.evaluate(ref, est, 2.0, CFG, ignore=np.array([[0.6, 1.4]]))
        self.assertLess(plain["note_precision"], 1.0)
        self.assertEqual(skipped["note_f1"], 1.0)
        self.assertEqual(skipped["voicing_false_alarm"], 0.0)
        self.assertEqual(skipped["low_error_st"], 0.0)  # the disputed low note does not set the range
        self.assertAlmostEqual(skipped["ignored_s"], 0.8)

    def test_empty_prediction_scores_zero(self):
        m = ev.evaluate(notes([(0.0, 1.0, 60)]), rf.empty_notes(), 1.0, CFG)
        self.assertEqual(m["note_f1"], 0.0)
        self.assertEqual(m["frame_accuracy"], 0.0)


def load_tool(name):
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AnnotationComparisonTests(unittest.TestCase):
    def test_resolution_spots_group_touching_disagreements(self):
        rp = load_tool("make_resolution_package")
        log = pd.DataFrame({"issue": ["pitch", "only x", "timing"],
                            "x_start_s": [4.1, 4.5, 9.0], "x_end_s": [4.4, 4.9, 9.5],
                            "y_start_s": [4.1, np.nan, 9.1], "y_end_s": [4.9, np.nan, 9.5]})
        s = rp.spots(log, ("x", "y"))
        self.assertEqual([sorted(x["kinds"]) for x in s], [["only", "pitch"], ["timing"]])
        freq = rp.frequency_table().set_index("note")
        self.assertAlmostEqual(freq.loc["A3", "centre_hz"], 220.0)
        self.assertAlmostEqual(freq.loc["A3", "highest_hz"], freq.loc["A#3", "lowest_hz"])

    def test_verified_keeps_agreed_notes_and_lists_disputes(self):
        bv, ca = load_tool("build_verified"), load_tool("compare_annotations")
        a = notes([(0.0, 0.5, 60), (1.0, 1.5, 62), (2.0, 2.5, 64)])
        b = notes([(0.02, 0.48, 60), (1.0, 1.5, 63), (2.0, 2.6, 64)])
        pairs = ca.match(a, b, 0.05, 50)
        v = bv.verified_notes(a, b, pairs)
        self.assertEqual(v["midi_note"].tolist(), [60, 64])
        self.assertAlmostEqual(v["start_s"].iat[0], 0.01)
        u = bv.unresolved_spots(ca.disagreements(a, b, pairs, ("x", "y")), a, b, ("x", "y"), "test")
        self.assertEqual(len(u), 1)
        self.assertAlmostEqual(u["start_s"].iat[0], 0.95)  # moved earlier by the lead-in
        self.assertEqual((u["x_notes"].iat[0], u["y_notes"].iat[0]), ("D4", "D#4"))

    def test_disagreements_are_paired_by_overlap(self):
        ca = load_tool("compare_annotations")
        a = notes([(0.0, 0.5, 60), (1.0, 1.5, 62), (2.0, 2.5, 64), (4.0, 4.5, 65)])
        b = notes([(0.0, 0.5, 60), (1.0, 1.5, 63), (2.3, 2.6, 64), (3.0, 3.5, 67)])
        log = ca.disagreements(a, b, ca.match(a, b, 0.05, 50), ("x", "y"))
        self.assertEqual(log["issue"].tolist(), ["pitch", "timing", "only y", "only x"])
        self.assertEqual(log.loc[0, "x_note"], "D4")
        self.assertEqual(log.loc[0, "y_note"], "D#4")


class ProfileTests(unittest.TestCase):
    def test_duration_weighted_percentiles_and_reliable_range(self):
        n = notes([(0.0, 0.1, 55), (0.1, 4.1, 62), (4.1, 5.1, 67), (5.1, 5.15, 79)])
        s = pf.profile_stats(n, 0.15)
        self.assertEqual((s["low_midi"], s["high_midi"]), (62.0, 67.0))  # 55 and 79 too short
        self.assertEqual(s["p10_midi"], 62.0)
        self.assertEqual(s["p90_midi"], 67.0)

    def test_unknown_key_and_tempo_are_not_guessed(self):
        row = pf.profile_row({"song_id": "S01", "excerpt_start_s": "0", "excerpt_end_s": "20"},
                             notes([(0.0, 1.0, 60)]), 0.15, "team_composed", "midi_reference", "", [], "v1")
        self.assertEqual((row["verified_key"], row["bpm"], row["verified_by"]), ("unknown", "unknown", "unverified"))
        self.assertTrue(row["quality_flag"].startswith("excerpt"))


class SongFeaturesExportTests(unittest.TestCase):
    SONG = {"song_id": "S01", "title": "Narrow range", "source_type": "ai_drafted_team_approved",
            "creator": "Drafted by a tool; approved by Alice and Bob"}

    def profile(self, **changes):
        row = {"song_id": "S01", "excerpt_start_s": 2.5, "excerpt_end_s": 32.48, "low_midi": 57.0,
               "high_midi": 69.0, "method": "midi_reference", "verified_by": "Alice; Bob",
               "quality_flag": "excerpt", "profile_version": "v1-verified"}
        return {**row, **changes}

    def test_midi_to_hz(self):
        ex = load_tool("export_song_features")
        self.assertEqual(ex.midi_to_hz(69), 440.0)
        self.assertEqual(ex.midi_to_hz(57), 220.0)
        self.assertAlmostEqual(ex.midi_to_hz(60), 261.6256)

    def test_verified_record_has_contract_fields_and_no_names(self):
        ex = load_tool("export_song_features")
        r = ex.song_record(self.profile(), self.SONG, "v")
        ex.check_records([r])
        self.assertEqual(list(r), ex.FIELDS)
        self.assertEqual((r["song_id"], r["provenance"]), ("E3-S01", "verified_melody"))
        self.assertEqual((r["melody_min_pitch_hz"], r["melody_max_pitch_hz"]), (220.0, 440.0))
        text = " ".join(str(v) for v in r.values())
        self.assertNotIn("Alice", text)
        self.assertNotIn("Bob", text)
        self.assertIn("2.50-32.48 s", r["source_description"])

    def test_unverified_or_missing_range_is_never_verified(self):
        ex = load_tool("export_song_features")
        r = ex.song_record(self.profile(verified_by="unverified"), self.SONG, "v")
        self.assertEqual(r["provenance"], "unverified")
        self.assertEqual(r["melody_min_pitch_hz"], 220.0)  # the range is kept, only the label changes
        r = ex.song_record(self.profile(low_midi="", high_midi=""), self.SONG, "v")
        self.assertEqual((r["melody_min_pitch_hz"], r["melody_max_pitch_hz"], r["provenance"]),
                         (None, None, "unverified"))
        ex.check_records([r])

    def test_invalid_records_are_rejected(self):
        ex = load_tool("export_song_features")
        r = ex.song_record(self.profile(), self.SONG, "v")
        with self.assertRaises(SystemExit):
            ex.check_records([r, r])  # duplicate song_id
        with self.assertRaises(SystemExit):
            ex.check_records([{**r, "melody_max_pitch_hz": None}])
        with self.assertRaises(SystemExit):
            ex.check_records([{**r, "melody_min_pitch_hz": 500.0}])  # min above max

    def test_committed_export_builds_app_song_features(self):
        """The app's contracts.py needs only the standard library, so it loads here without E3 changes."""
        import importlib.util
        import json
        root = Path(__file__).resolve().parents[3]
        contracts = root / "main_pipeline" / "src" / "suara" / "contracts.py"
        export = Path(__file__).resolve().parents[1] / "handoff" / "song_features.json"
        if not contracts.is_file():
            self.skipTest("main_pipeline is not in this checkout")
        spec = importlib.util.spec_from_file_location("suara_contracts", contracts)
        module = importlib.util.module_from_spec(spec)
        sys.modules["suara_contracts"] = module
        spec.loader.exec_module(module)
        rows = json.loads(export.read_text(encoding="utf-8"))
        songs = [module.SongFeatures(**r) for r in rows]
        self.assertEqual([s.to_dict() for s in songs], rows)
        self.assertEqual(len({s.song_id for s in songs}), len(songs))


if __name__ == "__main__":
    unittest.main()
