"""Catalog file loading (T07): the committed E3 export plus synthetic malformed files."""
import json
import subprocess
import sys

from helpers import ROOT, SyntheticTestCase, dependencies
from suara.catalog import SONG_FIELDS, load_song_catalog
from suara.pipeline import run_pipeline
from test_integration import stub_pitch, stub_rank, stub_timbre

E3_EXPORT = ROOT.parent / 'experiments' / 'E3' / 'handoff' / 'song_features.json'
SONG = dict(song_id='synthetic-a3-a4', title='Synthetic melody', artist='Test fixture',
            melody_min_pitch_hz=220.0, melody_max_pitch_hz=440.0, feature_version='test-only-export',
            provenance='unverified', source_description='Synthetic test-only record.', schema_version='1.0.0')


def real_deps():
    return dependencies(analyze_pitch=stub_pitch, analyze_timbre=stub_timbre, recommend_songs=stub_rank)


class CatalogLoadingTests(SyntheticTestCase):
    def catalog_file(self, text, name='private-secret-catalog.json'):
        path = self.folder / name
        path.write_text(text, encoding='utf-8')
        return path

    def assert_invalid(self, path):
        error = self.assert_error('invalid_catalog', lambda: load_song_catalog(path), stage='recommendation')
        self.assertNotIn('private-secret', error.error.message)

    def test_e3_export_loads_as_verified_hz_ranges(self):
        songs = load_song_catalog(E3_EXPORT)
        rows = json.loads(E3_EXPORT.read_text(encoding='utf-8'))
        self.assertEqual([s.to_dict() for s in songs], rows)
        self.assertEqual([s.song_id for s in songs], [f'E3-S0{n}' for n in range(1, 6)])
        self.assertTrue(all(s.provenance == 'verified_melody' for s in songs))
        s02 = songs[1]
        self.assertEqual(s02.melody_min_pitch_hz, 110.0)  # A2 = MIDI 45
        self.assertAlmostEqual(s02.melody_max_pitch_hz, 293.6648, places=4)  # D4 = MIDI 62

    def test_e3_catalog_runs_through_mock_and_real_wiring(self):
        songs = load_song_catalog(E3_EXPORT)
        mock = run_pipeline('unused', song_catalog=songs, dependencies=dependencies())
        self.assertEqual(mock.analysis_mode, 'mock')
        self.assertEqual([r.song_id for r in mock.recommendations], [s.song_id for s in songs])
        real = run_pipeline('unused', mode='real', top_k=3, song_catalog=songs, dependencies=real_deps())
        self.assertEqual(real.analysis_mode, 'real')
        self.assertEqual(len(real.recommendations), 3)

    def test_empty_catalog_is_valid_and_yields_no_recommendations(self):
        songs = load_song_catalog(self.catalog_file('[]'))
        self.assertEqual(songs, [])
        result = run_pipeline('unused', mode='real', song_catalog=songs, dependencies=real_deps())
        self.assertEqual(result.recommendations, [])

    def test_malformed_catalogs_are_rejected(self):
        missing = {k: v for k, v in SONG.items() if k != 'schema_version'}
        cases = {
            'not JSON': 'not json',
            'object, not list': json.dumps(SONG),
            'non-object record': '[1]',
            'missing schema_version': json.dumps([missing]),
            'extra field': json.dumps([{**SONG, 'key': 'C major'}]),
            'duplicate song_id': json.dumps([SONG, {**SONG, 'title': 'Other'}]),
            'NaN': json.dumps([SONG]).replace('220.0', 'NaN'),
            'Infinity': json.dumps([SONG]).replace('440.0', 'Infinity'),
            'repeated field': json.dumps([SONG])[:-2] + ', "title": "Again"}]',
            'one endpoint': json.dumps([{**SONG, 'melody_max_pitch_hz': None}]),
            'min above max': json.dumps([{**SONG, 'melody_min_pitch_hz': 62.0, 'melody_max_pitch_hz': 45.0}]),
            'boolean Hz': json.dumps([{**SONG, 'melody_min_pitch_hz': True}]),
            'text Hz': json.dumps([{**SONG, 'melody_min_pitch_hz': '220'}]),
            'zero Hz': json.dumps([{**SONG, 'melody_min_pitch_hz': 0.0}]),
            'verified without range': json.dumps([{**SONG, 'provenance': 'verified_melody',
                                                    'melody_min_pitch_hz': None, 'melody_max_pitch_hz': None}]),
            'unknown provenance': json.dumps([{**SONG, 'provenance': 'reviewed'}]),
            'empty title': json.dumps([{**SONG, 'title': ' '}]),
            'wrong schema_version': json.dumps([{**SONG, 'schema_version': '2.0.0'}]),
        }
        for label, text in cases.items():
            with self.subTest(label):
                self.assert_invalid(self.catalog_file(text))

    def test_unreadable_catalog_files_are_rejected_safely(self):
        self.assert_invalid(self.folder / 'private-secret-missing.json')
        self.assert_invalid(self.folder)  # a directory, not a file
        bad = self.folder / 'private-secret-latin1.json'
        bad.write_bytes(b'["\xe9"]')
        self.assert_invalid(bad)

    def test_loader_requires_every_contract_field(self):
        self.assertEqual(set(SONG_FIELDS), set(SONG))

    def test_cli_catalog_option(self):
        audio = self.wav()
        ok = subprocess.run([sys.executable, '-m', 'suara.cli', '--audio', str(audio), '--top-k', '2',
                             '--catalog', str(E3_EXPORT)], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        ids = [r['song_id'] for r in json.loads(ok.stdout)['recommendations']]
        self.assertEqual(ids, ['E3-S01', 'E3-S02'])
        bad = self.catalog_file('{"not": "a list"}')
        for args, code in ((['--catalog', str(bad)], 'invalid_catalog'),
                           (['--catalog', str(self.folder / 'private-secret-none.json')], 'invalid_catalog'),
                           (['--catalog', str(E3_EXPORT), '--mode', 'real'], 'invalid_configuration')):
            with self.subTest(args):
                result = subprocess.run([sys.executable, '-m', 'suara.cli', '--audio', str(audio), *args],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertEqual(json.loads(result.stderr)['code'], code)
                self.assertNotIn('private-secret', result.stderr)
