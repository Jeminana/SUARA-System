"""Pitch-range recommender (T08): formula, missing data, ordering and pipeline validity."""
import json
import random
from dataclasses import replace

from helpers import ROOT, SyntheticTestCase, dependencies
from suara.catalog import load_song_catalog
from suara.contracts import PitchFeatures, SongFeatures, TimbreFeatures, VoiceProfile
from suara.pipeline import _validate_recommendations, run_pipeline
from suara.recommender import SCORING_VERSION, fit, hz_to_midi, note_name, recommend_songs
from test_integration import stub_pitch, stub_timbre

E3_EXPORT = ROOT.parent / 'experiments' / 'E3' / 'handoff' / 'song_features.json'


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def profile(low, high, median, mode='real'):
    """A voice profile with the given MIDI range; timbre is a fixture and unused by the ranker."""
    warnings = [] if mode == 'real' else ['Synthetic fixture.']
    pitch = PitchFeatures(min_pitch_hz=hz(low), max_pitch_hz=hz(high), median_pitch_hz=hz(median),
                          voiced_ratio=0.8, confidence=None, mode=mode, model_version='test-fixture',
                          warnings=warnings)
    timbre = TimbreFeatures(mfcc_mean=[0.0] * 20, spectral_centroid_mean_hz=1000.0, mode=mode,
                            model_version='test-fixture', processing_version='test-fixture', warnings=warnings)
    return VoiceProfile(pitch=pitch, timbre=timbre, analysis_mode=mode,
                        status='ok' if mode == 'real' else 'warning', warnings=warnings)


def unvoiced():
    p = profile(45, 64, 55)
    return replace(p, pitch=replace(p.pitch, voiced_ratio=0.0, min_pitch_hz=None, max_pitch_hz=None,
                                    median_pitch_hz=None), status='no_voiced_pitch')


def song(song_id, low, high, provenance='verified_melody'):
    return SongFeatures(song_id=song_id, title=f'Song {song_id}', artist='Test fixture',
                        melody_min_pitch_hz=None if low is None else hz(low),
                        melody_max_pitch_hz=None if high is None else hz(high),
                        feature_version='test-fixture', provenance=provenance,
                        source_description='Synthetic test-only record.')


class FormulaTests(SyntheticTestCase):
    def test_note_conversion(self):
        self.assertEqual(hz_to_midi(440.0), 69.0)
        self.assertEqual(note_name(60), 'C4')
        self.assertEqual(note_name(hz_to_midi(110.0)), 'A2')

    def test_fully_inside_scores_on_centre_only(self):
        score, above, below, centre = fit(45, 64, 55, 50, 57)  # centre 53.5 is 1.5 below the median
        self.assertEqual((above, below, centre), (0.0, 0.0, 1.5))
        self.assertEqual(score, round(0.8 + 0.2 * (1 - 1.5 / 12), 4))

    def test_each_semitone_outside_costs_a_twelfth_of_the_range_weight(self):
        score, above, below, centre = fit(55, 72, 64, 50, 57)  # 5 below, centre 10.5 away
        self.assertEqual((above, below, centre), (0.0, 5.0, 10.5))
        self.assertEqual(score, round(0.8 * (1 - 5 / 12) + 0.2 * (1 - 10.5 / 12), 4))
        self.assertEqual(fit(55, 60, 58, 58, 62)[1:3], (2.0, 0.0))  # above only

    def test_score_is_bounded_and_floors_at_zero(self):
        self.assertEqual(fit(80, 90, 85, 30, 40)[0], 0.0)
        rng = random.Random(0)
        for _ in range(500):
            v0, s0 = rng.uniform(30, 90), rng.uniform(30, 90)
            v1, s1 = v0 + rng.uniform(0, 30), s0 + rng.uniform(0, 30)
            score = fit(v0, v1, rng.uniform(v0, v1), s0, s1)[0]
            self.assertTrue(0.0 <= score <= 1.0)


class RankingTests(SyntheticTestCase):
    def test_e3_catalog_for_a_voice_above_the_pilot_songs(self):
        songs = load_song_catalog(E3_EXPORT)
        recs = recommend_songs(profile(55, 72, 64), songs)  # G3-C5, median E4
        self.assertEqual([r.song_id for r in recs], ['E3-S03', 'E3-S01', 'E3-S02', 'E3-S04', 'E3-S05'])
        self.assertTrue(all(r.mode == 'real' and r.scoring_version == SCORING_VERSION for r in recs))
        self.assertEqual(recs[2].score, recs[3].score)  # S02 and S04 share A2-D4; tie sorts by song_id
        self.assertIn('Melody E3-E4; your recorded range G3-C5', recs[0].explanation)
        self.assertIn('3 semitones below your lowest note', recs[0].explanation)
        self.assertIn('does not measure how well the song suits your voice', recs[0].explanation)

    def test_order_ignores_catalog_order_and_inputs_are_untouched(self):
        songs = load_song_catalog(E3_EXPORT)
        voice = profile(55, 72, 64)
        before = ([s.to_dict() for s in songs], voice.to_dict())
        expected = recommend_songs(voice, songs)
        shuffled = songs[::-1]
        self.assertEqual(recommend_songs(voice, shuffled), expected)
        self.assertEqual(([s.to_dict() for s in songs], voice.to_dict()), before)

    def test_unscorable_songs_and_unvoiced_profiles_are_left_out(self):
        catalog = [song('a', 50, 57), song('b', None, None, 'unverified'), song('c', 50, 57, 'unverified'),
                   song('d', None, None, 'mock')]
        self.assertEqual([r.song_id for r in recommend_songs(profile(45, 64, 55), catalog)], ['a'])
        self.assertEqual(recommend_songs(unvoiced(), catalog), [])
        self.assertEqual(recommend_songs(profile(45, 64, 55), []), [])

    def test_mock_inputs_are_labelled_mock(self):
        recs = recommend_songs(profile(45, 64, 55, mode='mock'), [song('a', 50, 57)])
        self.assertEqual(recs[0].mode, 'mock')
        self.assertIn('Synthetic mock input', recs[0].explanation)
        recs = recommend_songs(profile(45, 64, 55), [song('m', 50, 57, 'mock')])
        self.assertEqual(recs[0].mode, 'mock')

    def test_top_k(self):
        songs = load_song_catalog(E3_EXPORT)
        self.assertEqual(len(recommend_songs(profile(45, 64, 55), songs, top_k=2)), 2)
        for bad in (0, 6, True, 2.0):
            with self.subTest(bad):
                self.assert_error('invalid_configuration',
                                  lambda: recommend_songs(profile(45, 64, 55), songs, top_k=bad))


class PipelineTests(SyntheticTestCase):
    def test_output_passes_the_pipeline_validator(self):
        songs = load_song_catalog(E3_EXPORT)
        for voice in (profile(43, 64, 55), profile(55, 72, 64), profile(60, 79, 69), profile(45, 64, 55, 'mock')):
            for top_k in range(1, 6):
                recs = recommend_songs(voice, songs, top_k=top_k)
                self.assertEqual(_validate_recommendations(recs, voice, songs, top_k), recs)

    def test_real_and_mock_pipeline_runs(self):
        songs = load_song_catalog(E3_EXPORT)
        real = run_pipeline('unused', mode='real', song_catalog=songs, dependencies=dependencies(
            analyze_pitch=stub_pitch, analyze_timbre=stub_timbre, recommend_songs=recommend_songs))
        self.assertEqual(real.analysis_mode, 'real')
        self.assertEqual(len(real.recommendations), 5)
        mock = run_pipeline('unused', song_catalog=songs, dependencies=dependencies(recommend_songs=recommend_songs))
        self.assertTrue(all(r.mode == 'mock' for r in mock.recommendations))
        self.assertEqual(mock.analysis_mode, 'mock')

    def test_unvoiced_pipeline_returns_no_recommendations(self):
        def silent_pitch(audio):
            return replace(stub_pitch(audio), voiced_ratio=0, min_pitch_hz=None, max_pitch_hz=None,
                           median_pitch_hz=None, confidence=None)
        result = run_pipeline('unused', mode='real', song_catalog=load_song_catalog(E3_EXPORT),
                              dependencies=dependencies(analyze_pitch=silent_pitch, analyze_timbre=stub_timbre,
                                                        recommend_songs=recommend_songs))
        self.assertEqual(result.voice_profile.status, 'no_voiced_pitch')
        self.assertEqual(result.recommendations, [])

    def test_t12_voice_fixtures_rank_without_errors(self):
        fixtures = json.loads((ROOT.parent / 'evaluation' / 'fixtures' / 'voice_profiles.json').read_text())
        songs = load_song_catalog(E3_EXPORT)
        for data in fixtures:
            with self.subTest(data['fixture_id']):
                voice = VoiceProfile(pitch=PitchFeatures(**data['pitch']), timbre=TimbreFeatures(**data['timbre']),
                                     analysis_mode=data['analysis_mode'], status=data['status'],
                                     warnings=data['warnings'], schema_version=data['schema_version'])
                recs = recommend_songs(voice, songs)
                self.assertEqual(len(recs), 0 if data['pitch']['voiced_ratio'] == 0 else 5)
                self.assertTrue(all(r.mode == 'mock' for r in recs))  # T12 fixtures are synthetic
