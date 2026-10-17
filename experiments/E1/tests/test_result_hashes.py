import csv
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RecordedHashTests(unittest.TestCase):
    def test_phase7_result_hashes_match_committed_files(self):
        recorded = json.loads((ROOT / 'outputs/phase7/result_hashes.json').read_text(encoding='utf-8'))
        for name, expected in recorded['files'].items():
            with self.subTest(file=name):
                self.assertEqual(sha256(ROOT / 'outputs/phase7' / name), expected)

    def test_provenance_hashes_match_committed_inputs(self):
        provenance = json.loads((ROOT / 'outputs/phase7/provenance.json').read_text(encoding='utf-8'))
        self.assertEqual(sha256(ROOT / provenance['configuration_path']), provenance['configuration_sha256'])
        self.assertEqual(sha256(ROOT / 'data/manifests/e1_official_synthetic.csv'), provenance['synthetic_manifest_sha256'])

    def test_reference_hashes_match_committed_references(self):
        with (ROOT / 'outputs/phase7/per_recording_results.csv').open(newline='', encoding='utf-8') as handle:
            recorded = {row['reference_id']: row['reference_sha256'] for row in csv.DictReader(handle)}
        for reference_id, expected in recorded.items():
            with self.subTest(reference=reference_id):
                path = ROOT / 'data/references/synthetic/official' / f'{reference_id}_reference.csv'
                self.assertEqual(sha256(path), expected)


if __name__ == '__main__':
    unittest.main()
