import unittest

from scripts.evaluate_phase7 import grid_index, index_rows, require_indices, score


class IntegerGridTests(unittest.TestCase):
    def test_float_representation_difference_maps_to_same_index(self):
        reference_time = round(35 * 0.01, 2)
        prediction_time = 35 * 0.01
        self.assertNotEqual(reference_time, prediction_time)
        self.assertEqual(grid_index(reference_time), 35)
        self.assertEqual(grid_index(prediction_time), 35)

    def test_missing_prediction_frame_is_rejected_by_grid_validation(self):
        with self.assertRaisesRegex(ValueError, r'missing=\[1\]'):
            require_indices({0: {}, 2: {}}, {0, 1, 2}, 'test prediction')

    def test_duplicate_grid_indices_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate grid index 35'):
            index_rows([{'time_s': '0.35'}, {'time_s': '0.35000000000000003'}], 'time_s')

    def test_off_grid_timestamp_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'off-grid timestamp'):
            grid_index('0.295')

    def test_endpoint_is_indexed_but_not_scored(self):
        raw = index_rows([{'time_s': f'{i / 100:.2f}'} for i in range(301)], 'time_s')
        self.assertEqual(set(raw), set(range(301)))
        scored = {k: v for k, v in raw.items() if k < 300}
        self.assertEqual(set(scored), set(range(300)))
        self.assertNotIn(300, scored)

    def test_known_answer_metrics_and_missing_prediction(self):
        ref = {
            0: {'voiced': True, 'reference_f0_hz': 100.0},
            1: {'voiced': True, 'reference_f0_hz': 100.0},
            2: {'voiced': False, 'reference_f0_hz': None},
        }
        pred = {
            0: {'f0_hz': '100', 'voiced_flag': '1', 'confidence': '1'},
            1: {'f0_hz': '200', 'voiced_flag': '1', 'confidence': '1'},
            2: {'f0_hz': '', 'voiced_flag': '0', 'confidence': '0'},
        }
        m, errors = score(ref, pred, 'pyin')
        self.assertEqual(m['raw_pitch_accuracy_50c_correct'], 1)
        self.assertEqual(m['raw_pitch_accuracy_50c_denominator'], 2)
        self.assertEqual(m['octave_errors'], 1)
        self.assertEqual((m['voicing_tp'], m['voicing_fp'], m['voicing_fn']), (2, 0, 0))
        self.assertEqual(m['voicing_f1'], 1.0)
        self.assertEqual(len(errors), 2)
        missing, _ = score(ref, {0: pred[0], 2: pred[2]}, 'pyin')
        self.assertEqual(missing['voicing_fn'], 1)
        self.assertEqual(missing['raw_pitch_accuracy_50c_correct'], 1)


if __name__ == '__main__':
    unittest.main()
