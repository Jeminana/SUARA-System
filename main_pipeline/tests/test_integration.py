"""Test adapters exercise wiring only; real-labeled stubs are not validated AI."""
import json
import subprocess
import sys
from dataclasses import replace

from helpers import SyntheticTestCase, dependencies, tiny_audio
from suara.audio.preprocessing import preprocess_audio
from suara.contracts import SongFeatures
from suara.mocks.catalog import mock_song_catalog
from suara.mocks.pitch import analyze_pitch
from suara.mocks.timbre import analyze_timbre
from suara.mocks.recommender import recommend_songs
from suara.pipeline import run_pipeline


def stub_pitch(audio):
    return replace(analyze_pitch(audio), mode='real', model_version='test-only-stub',
                   warnings=['Test-only wiring stub; not measured AI.'])


def stub_timbre(audio):
    return replace(analyze_timbre(audio), mode='real', model_version='test-only-stub',
                   processing_version='test-only-stub', warnings=['Test-only wiring stub.'])


def stub_catalog():
    return [replace(song, provenance='unverified', source_description='Synthetic test-only metadata.')
            for song in mock_song_catalog()]


def stub_rank(profile, catalog, top_k=5):
    return [replace(rec, mode='real', scoring_version='test-only-stub',
                    explanation='Test-only wiring rank; no suitability claim.')
            for rec in recommend_songs(profile, catalog, top_k)]


class IntegrationTests(SyntheticTestCase):
    def test_actual_preprocessor_and_injected_module_inputs(self):
        seen = {}
        def pre(path, *, target_sample_rate):
            self.assertEqual(target_sample_rate, 16000)
            seen['audio'] = preprocess_audio(path, target_sample_rate=target_sample_rate)
            return seen['audio']
        def pitch(audio):
            self.assertIs(audio, seen['audio'])
            seen['pitch'] = analyze_pitch(audio)
            return seen['pitch']
        def timbre(audio):
            self.assertIs(audio, seen['audio'])
            seen['timbre'] = analyze_timbre(audio)
            return seen['timbre']
        catalog = mock_song_catalog()
        def rank(profile, songs, top_k=5):
            self.assertIs(profile.pitch, seen['pitch'])
            self.assertIs(profile.timbre, seen['timbre'])
            self.assertIs(songs, catalog)
            self.assertEqual(top_k, 2)
            self.assertTrue(any('Stereo' in warning for warning in profile.warnings))
            return recommend_songs(profile, songs, top_k)
        result = run_pipeline(self.wav(channels=2, rate=44100), top_k=2, song_catalog=catalog,
                              dependencies=dependencies(preprocess_audio=pre, analyze_pitch=pitch,
                                                        analyze_timbre=timbre, recommend_songs=rank))
        self.assertEqual(len(result.recommendations), 2)
        self.assertEqual(json.loads(result.to_json())['analysis_mode'], 'mock')

    def test_top_k_and_catalog_order(self):
        for top_k in (1, 2, 3, 4, 5):
            result = run_pipeline('unused', top_k=top_k, song_catalog=mock_song_catalog()[::-1],
                                  dependencies=dependencies())
            self.assertEqual(len(result.recommendations), top_k)
            self.assertEqual([r.song_id for r in result.recommendations],
                             [s.song_id for s in mock_song_catalog()[:top_k]])
        for top_k in (True, 0, 6, None, 1., '2'):
            self.assert_error('invalid_configuration', lambda: run_pipeline('unused', top_k=top_k))

    def test_catalog_errors_before_preprocessing(self):
        song = mock_song_catalog()[0]
        for catalog in ({}, 'songs', [object()], [song, song]):
            self.assert_error('invalid_catalog', lambda: run_pipeline('unused', song_catalog=catalog,
                              dependencies=dependencies(preprocess_audio=lambda *a, **kw: self.fail('called'))))

    def test_invalid_recommendation_references_metadata_ranking_and_count(self):
        profile_result = run_pipeline('unused', dependencies=dependencies())
        a, b = profile_result.recommendations[:2]
        for recs in ([replace(a, song_id='missing')], [replace(a, title='wrong')],
                     [replace(a, artist='wrong')], [a, a], [b, a], {}, [object()]):
            with self.subTest(recs_type=type(recs).__name__):
                self.assert_error('invalid_catalog', lambda: run_pipeline('unused',
                    dependencies=dependencies(recommend_songs=lambda *args, **kw: recs)))
        self.assert_error('invalid_catalog', lambda: run_pipeline('unused', top_k=1,
            dependencies=dependencies(recommend_songs=lambda *args, **kw: [a, b])))

    def test_module_exceptions_are_safe_at_every_stage(self):
        def broken(*args, **kwargs):
            raise RuntimeError('C:/private/participant-secret/voice.wav')
        for name, stage in (('preprocess_audio', 'preprocessing'), ('analyze_pitch', 'pitch'),
                            ('analyze_timbre', 'timbre'), ('recommend_songs', 'recommendation')):
            error = self.assert_error('module_failure', lambda: run_pipeline('unused',
                dependencies=dependencies(**{name: broken})), stage)
            self.assertNotIn('participant-secret', error.error.to_json())
            self.assertNotIn('C:/private', error.error.to_json())
            self.assertIsInstance(error.__cause__, RuntimeError)

    def test_wrong_module_contract_types(self):
        for name, code in (('preprocess_audio', 'invalid_audio'), ('analyze_pitch', 'invalid_features'),
                           ('analyze_timbre', 'invalid_features'), ('recommend_songs', 'invalid_catalog')):
            self.assert_error(code, lambda: run_pipeline('unused', dependencies=dependencies(
                **{name: lambda *args, **kwargs: {}})))

    def test_real_mode_has_no_fallback_or_declared_mock_components(self):
        self.assert_error('invalid_configuration', lambda: run_pipeline('unused', mode='real'))
        self.assert_error('invalid_configuration', lambda: run_pipeline('unused', mode='invalid'))
        for name, mock in (('analyze_pitch', analyze_pitch), ('analyze_timbre', analyze_timbre),
                           ('recommend_songs', recommend_songs)):
            deps = dict(analyze_pitch=stub_pitch, analyze_timbre=stub_timbre, recommend_songs=stub_rank)
            deps[name] = mock
            self.assert_error('invalid_configuration', lambda: run_pipeline('unused', mode='real',
                song_catalog=stub_catalog(), dependencies=dependencies(**deps)))

    def test_real_mode_rejects_hidden_mock_outputs_and_mock_catalog(self):
        real_deps = dependencies(analyze_pitch=stub_pitch, analyze_timbre=stub_timbre,
                                 recommend_songs=stub_rank)
        self.assert_error('invalid_configuration', lambda: run_pipeline('unused', mode='real',
            dependencies=real_deps, song_catalog=mock_song_catalog()))
        for name, wrapped in (('analyze_pitch', lambda a: analyze_pitch(a)),
                              ('analyze_timbre', lambda a: analyze_timbre(a)),
                              ('recommend_songs', lambda p, c, top_k=5: recommend_songs(p, c, top_k))):
            self.assert_error('invalid_configuration', lambda: run_pipeline('unused', mode='real',
                song_catalog=stub_catalog(), dependencies=replace(real_deps, **{name: wrapped})))

    def test_test_only_adapters_accept_real_mode_and_empty_catalog(self):
        deps = dependencies(analyze_pitch=stub_pitch, analyze_timbre=stub_timbre, recommend_songs=stub_rank)
        for catalog in ([], stub_catalog()):
            result = run_pipeline('unused', mode='real', dependencies=deps, song_catalog=catalog)
            self.assertEqual(result.analysis_mode, 'real')
            self.assertEqual(len(result.recommendations), len(catalog))
            self.assertIn('Test-only', result.voice_profile.pitch.warnings[0])

    def test_song_export_adapter_hz_units_and_source_preserved(self):
        def export_song(row):
            return SongFeatures(
                song_id=row['id'], title='Synthetic melody', artist='Test fixture',
                melody_min_pitch_hz=440 * 2 ** ((row['low_midi'] - 69) / 12),
                melody_max_pitch_hz=440 * 2 ** ((row['high_midi'] - 69) / 12),
                provenance='unverified', feature_version='test-only-export',
                source_description=row['source'])
        source = 'Synthetic MIDI fixture, seconds 0..1; not a reviewed human melody.'
        song = export_song(dict(id='synthetic-a4-a5', low_midi=69, high_midi=81, source=source))
        self.assertEqual((song.melody_min_pitch_hz, song.melody_max_pitch_hz), (440, 880))
        result = run_pipeline('unused', mode='real', song_catalog=[song], dependencies=dependencies(
            analyze_pitch=stub_pitch, analyze_timbre=stub_timbre, recommend_songs=stub_rank))
        self.assertEqual(result.recommendations[0].song_id, song.song_id)
        self.assertEqual(song.source_description, source)
        self.assertEqual(song.provenance, 'unverified')

    def test_real_mode_unvoiced_test_adapter_has_no_fabricated_pitch(self):
        def unvoiced(audio):
            return replace(stub_pitch(audio), voiced_ratio=0, min_pitch_hz=None,
                           max_pitch_hz=None, median_pitch_hz=None, confidence=None)
        result = run_pipeline('unused', mode='real', song_catalog=[], dependencies=dependencies(
            analyze_pitch=unvoiced, analyze_timbre=stub_timbre, recommend_songs=stub_rank))
        self.assertEqual(result.voice_profile.status, 'no_voiced_pitch')
        self.assertEqual(result.recommendations, [])
        self.assertIsNone(result.voice_profile.pitch.max_pitch_hz)

    def test_invalid_dependency_bundles(self):
        for bundle in ({}, dependencies(analyze_pitch=None)):
            self.assert_error('invalid_configuration', lambda: run_pipeline('unused', dependencies=bundle))

    def test_safe_expected_module_error_is_preserved(self):
        from suara.errors import failure
        expected = failure('module_failure', 'pitch', 'Detector is unavailable offline.')
        def broken(audio):
            raise expected
        actual = self.assert_error('module_failure', lambda: run_pipeline('unused',
            dependencies=dependencies(analyze_pitch=broken)), 'pitch')
        self.assertIs(actual, expected)

    def test_mixed_analyzer_provenance(self):
        for pitch, timbre in ((stub_pitch, analyze_timbre), (analyze_pitch, stub_timbre)):
            result = run_pipeline('unused', dependencies=dependencies(analyze_pitch=pitch, analyze_timbre=timbre))
            self.assertEqual(result.analysis_mode, 'mock')
            self.assertTrue(all(r.mode == 'mock' for r in result.recommendations))
            self.assertTrue(any('synthetic' in w.lower() for w in result.voice_profile.warnings))

    def test_mock_ranker_provenance_cannot_be_overridden(self):
        def dishonest(profile, catalog, top_k=5):
            return stub_rank(profile, catalog, top_k)
        dishonest.suara_mode = 'mock'
        self.assert_error('invalid_catalog', lambda: run_pipeline('unused', song_catalog=stub_catalog(),
            dependencies=dependencies(analyze_pitch=stub_pitch, analyze_timbre=stub_timbre,
                                      recommend_songs=dishonest)))

    def test_audio_mutation_caught_before_next_analyzer(self):
        def mutating(audio):
            result = analyze_pitch(audio)
            audio.waveform.append(float('nan'))
            return result
        def ignores_audio(audio):
            self.fail('Timbre must not receive invalid audio')
        self.assert_error('invalid_audio', lambda: run_pipeline('unused',
            dependencies=dependencies(analyze_pitch=mutating, analyze_timbre=ignores_audio)), 'pitch')

    def test_timbre_audio_mutation_caught_even_if_return_value_valid(self):
        def mutating(audio):
            result = analyze_timbre(audio)
            audio.warnings.append(None)
            return result
        self.assert_error('invalid_audio', lambda: run_pipeline('unused',
            dependencies=dependencies(analyze_timbre=mutating)), 'timbre')

    def test_preprocessor_must_honor_requested_rate(self):
        wrong_rate = replace(tiny_audio(), sample_rate=8000, duration_s=2/8000)
        self.assert_error('invalid_audio', lambda: run_pipeline('unused', dependencies=dependencies(
            preprocess_audio=lambda *args, **kwargs: wrong_rate)), 'preprocessing')

    def test_nyquist_limit(self):
        def above_nyquist(audio):
            return replace(analyze_timbre(audio), spectral_centroid_mean_hz=8000.1)
        self.assert_error('invalid_features', lambda: run_pipeline('unused',
            dependencies=dependencies(analyze_timbre=above_nyquist)), 'timbre')

    def test_mutated_nested_features_profile_and_catalog(self):
        saved = {}
        def pitch(audio):
            saved['pitch'] = analyze_pitch(audio)
            return saved['pitch']
        def timbre(audio):
            saved['pitch'].warnings.append(None)
            return analyze_timbre(audio)
        self.assert_error('invalid_features', lambda: run_pipeline('unused',
            dependencies=dependencies(analyze_pitch=pitch, analyze_timbre=timbre)), 'profile')
        def rank(profile, catalog, top_k=5):
            profile.timbre.mfcc_mean.clear()
            return []
        self.assert_error('invalid_catalog', lambda: run_pipeline('unused',
            dependencies=dependencies(recommend_songs=rank)))
        catalog = mock_song_catalog()
        def bad_catalog(profile, songs, top_k=5):
            songs.append(songs[0])
            return []
        self.assert_error('invalid_catalog', lambda: run_pipeline('unused', song_catalog=catalog,
            dependencies=dependencies(recommend_songs=bad_catalog)))

    def test_unvoiced_pitch_and_missing_melody_are_safe(self):
        def unvoiced(audio):
            return replace(stub_pitch(audio), voiced_ratio=0, min_pitch_hz=None,
                           max_pitch_hz=None, median_pitch_hz=None, confidence=None)
        result = run_pipeline('unused', dependencies=dependencies(analyze_pitch=unvoiced),
                              song_catalog=stub_catalog())
        self.assertEqual(result.voice_profile.status, 'no_voiced_pitch')
        self.assertIsNone(result.voice_profile.pitch.median_pitch_hz)
        self.assertTrue(all('No pitch/timbre suitability' in r.explanation for r in result.recommendations))

    def test_cli_success_errors_and_no_ai_imports(self):
        path = self.wav()
        for args, code, error_code in ((['--audio', str(path)], 0, None),
                (['--audio', str(path), '--top-k', '1'], 0, None),
                (['--audio', str(path), '--mode', 'real'], 2, 'invalid_configuration'),
                ([], 2, 'invalid_configuration'),
                (['--audio', 'private-secret.wav'], 2, 'audio_not_found'),
                (['--audio', str(path), '--top-k', 'bad-private-secret'], 2, 'invalid_configuration'),
                (['--audio', str(path), '--mode', 'unknown'], 2, 'invalid_configuration')):
            result = subprocess.run([sys.executable, '-m', 'suara.cli', *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, code, result.stderr)
            payload = json.loads(result.stderr if code else result.stdout)
            self.assertEqual(result.stdout if code else result.stderr, '')
            if code:
                self.assertEqual(payload['code'], error_code)
                self.assertNotIn('private-secret', result.stderr)
        probe = subprocess.run([sys.executable, '-c',
            "import sys; from suara.contracts import SCHEMA_VERSION; "
            "assert not ({'numpy','scipy','torch','tensorflow','librosa'} & sys.modules.keys()); "
            "from suara.pipeline import run_pipeline; run_pipeline(sys.argv[1]); "
            "assert not ({'torch','tensorflow','librosa','speechbrain','crepe','transformers'} & sys.modules.keys())",
            str(path)], capture_output=True, text=True)
        self.assertEqual(probe.returncode, 0, probe.stderr)
