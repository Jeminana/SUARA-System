"""Strict construction, nesting, mutation and JSON regression tests."""
import json
import unittest
from dataclasses import fields, replace

from helpers import tiny_audio
from suara.contracts import (ContractError, ErrorInfo, PipelineResult, PitchFeatures,
                             Recommendation, SongFeatures, TimbreFeatures, VoiceProfile)
from suara.mocks.catalog import mock_song_catalog
from suara.mocks.pitch import analyze_pitch
from suara.mocks.timbre import analyze_timbre
from suara.mocks.recommender import recommend_songs
from suara.pipeline import build_voice_profile


def fixtures():
    audio = tiny_audio()
    pitch, timbre = analyze_pitch(audio), analyze_timbre(audio)
    profile = build_voice_profile(pitch, timbre)
    song = mock_song_catalog()[0]
    rec = recommend_songs(profile, [song])[0]
    result = PipelineResult(voice_profile=profile, recommendations=[rec],
                            pipeline_version='test', analysis_mode='mock', processing_time_s=None)
    error = ErrorInfo(code='module_failure', message='Safe public message.', stage='pitch')
    return [audio, pitch, timbre, profile, song, rec, result, error]


class ContractTests(unittest.TestCase):
    def setUp(self):
        (self.audio, self.pitch, self.timbre, self.profile, self.song,
         self.rec, self.result, self.error) = fixtures()

    def assert_invalid(self, obj, **changes):
        with self.assertRaises(ContractError):
            replace(obj, **changes)

    def test_all_contracts_required_and_unknown_fields(self):
        for obj in fixtures():
            values = {field.name: getattr(obj, field.name) for field in fields(obj)}
            for name in values.keys() - {'schema_version'}:
                with self.subTest(contract=type(obj).__name__, missing=name):
                    without = dict(values)
                    del without[name]
                    with self.assertRaises(TypeError):
                        type(obj)(**without)
            with self.assertRaises(TypeError):
                type(obj)(**values, unexpected=True)

    def test_all_contracts_versions_and_roundtrip(self):
        for obj in fixtures():
            for version in ('2.0.0', None, 1):
                self.assert_invalid(obj, schema_version=version)
            self.assertEqual(json.loads(obj.to_json()), obj.to_dict())
            self.assertEqual(json.loads(obj.to_json())['schema_version'], '1.0.0')

    def test_nonnullable_fields_reject_null(self):
        nullable = {
            'PitchFeatures': {'min_pitch_hz', 'max_pitch_hz', 'median_pitch_hz', 'confidence'},
            'TimbreFeatures': {'spectral_centroid_mean_hz'},
            'SongFeatures': {'melody_min_pitch_hz', 'melody_max_pitch_hz'},
            'PipelineResult': {'processing_time_s'},
        }
        for obj in fixtures():
            for field in fields(obj):
                if field.name not in nullable.get(type(obj).__name__, set()):
                    with self.subTest(contract=type(obj).__name__, field=field.name):
                        self.assert_invalid(obj, **{field.name: None})

    def test_audio_types_bounds_and_duration(self):
        for waveform in (None, [], [0], [True], [[0.]], [float('nan')], [float('inf')], [1.01]):
            self.assert_invalid(self.audio, waveform=waveform)
        for sample_rate in (None, True, 0, -1, 16000.):
            self.assert_invalid(self.audio, sample_rate=sample_rate)
        for duration in (None, True, float('inf'), -1, 1):
            self.assert_invalid(self.audio, duration_s=duration)

    def test_pitch_ranges_and_voicing_nullability(self):
        for changes in (dict(min_pitch_hz=None), dict(max_pitch_hz=None),
                dict(min_pitch_hz=0), dict(min_pitch_hz=-1), dict(min_pitch_hz=400),
                dict(median_pitch_hz=None), dict(median_pitch_hz=99), dict(median_pitch_hz=400),
                dict(voiced_ratio=0), dict(voiced_ratio=-0.1), dict(voiced_ratio=1.1),
                dict(min_pitch_hz=None, max_pitch_hz=None, median_pitch_hz=None)):
            self.assert_invalid(self.pitch, **changes)
        unvoiced = replace(self.pitch, voiced_ratio=0, min_pitch_hz=None,
                           max_pitch_hz=None, median_pitch_hz=None, confidence=None)
        unvoiced.validate()
        self.assert_invalid(unvoiced, median_pitch_hz=220)
        self.assert_invalid(unvoiced, min_pitch_hz=100, max_pitch_hz=200)
        replace(self.pitch, confidence=None).validate()

    def test_all_numeric_fields_reject_nonfinite_and_bool(self):
        targets = ((self.audio, 'duration_s'), (self.pitch, 'voiced_ratio'),
                   (self.pitch, 'confidence'), (self.pitch, 'min_pitch_hz'),
                   (self.pitch, 'max_pitch_hz'), (self.pitch, 'median_pitch_hz'),
                   (self.timbre, 'spectral_centroid_mean_hz'),
                   (self.song, 'melody_min_pitch_hz'), (self.rec, 'score'),
                   (self.result, 'processing_time_s'))
        for obj, name in targets:
            for value in (float('nan'), float('inf'), -float('inf'), True, '0.5', 10**1000):
                with self.subTest(contract=type(obj).__name__, field=name, value_type=type(value).__name__):
                    self.assert_invalid(obj, **{name: value})

    def test_timbre_dimension_and_scalars(self):
        for vector in (None, (), [0.]*19, [0.]*21, [float('nan')]*20,
                       [True]*20, [[0.]]*20):
            self.assert_invalid(self.timbre, mfcc_mean=vector)
        self.assert_invalid(self.timbre, spectral_centroid_mean_hz=-1)
        replace(self.timbre, spectral_centroid_mean_hz=None).validate()

    def test_text_warnings_and_enum_types(self):
        targets = ((self.pitch, 'model_version'), (self.timbre, 'processing_version'),
                   (self.song, 'song_id'), (self.song, 'title'), (self.song, 'artist'),
                   (self.song, 'feature_version'), (self.song, 'source_description'),
                   (self.rec, 'explanation'), (self.rec, 'scoring_version'),
                   (self.result, 'pipeline_version'), (self.error, 'message'))
        for obj, name in targets:
            for value in (None, '', ' ', 1, []):
                self.assert_invalid(obj, **{name: value})
        for obj in (self.audio, self.pitch, self.timbre, self.profile):
            for warnings in (None, 'warning', [''], [1]):
                self.assert_invalid(obj, warnings=warnings)
        for obj, field in ((self.pitch, 'mode'), (self.timbre, 'mode'), (self.rec, 'mode'),
                           (self.profile, 'analysis_mode'), (self.result, 'analysis_mode'),
                           (self.profile, 'status'), (self.song, 'provenance'),
                           (self.error, 'code'), (self.error, 'stage')):
            for value in (None, 'invalid', 1, []):
                self.assert_invalid(obj, **{field: value})

    def test_profile_nesting_modes_status(self):
        self.assert_invalid(self.profile, pitch={})
        self.assert_invalid(self.profile, timbre={})
        self.assert_invalid(self.profile, analysis_mode='real')
        self.assert_invalid(self.profile, status='ok')
        self.assert_invalid(self.profile, warnings=[])
        self.assert_invalid(self.profile, status='no_voiced_pitch')
        unvoiced = replace(self.pitch, voiced_ratio=0, min_pitch_hz=None,
                           max_pitch_hz=None, median_pitch_hz=None)
        profile = build_voice_profile(unvoiced, self.timbre)
        self.assertEqual(profile.status, 'no_voiced_pitch')
        self.assert_invalid(profile, status='warning')

    def test_song_nullable_range_and_provenance(self):
        for changes in (dict(melody_min_pitch_hz=100), dict(melody_max_pitch_hz=200),
                dict(melody_min_pitch_hz=200, melody_max_pitch_hz=100),
                dict(melody_min_pitch_hz=0, melody_max_pitch_hz=100),
                dict(provenance='verified_melody')):
            self.assert_invalid(self.song, **changes)
        replace(self.song, provenance='verified_melody', melody_min_pitch_hz=100,
                melody_max_pitch_hz=200).validate()

    def test_score_bounds(self):
        for score in (None, -0.001, 1.001):
            self.assert_invalid(self.rec, score=score)
        for score in (0, 1):
            replace(self.rec, score=score).validate()

    def test_result_ranking_duplicates_nesting_mode(self):
        second = replace(self.rec, song_id='z', score=0.8)
        replace(self.result, recommendations=[self.rec, second]).validate()
        for recommendations in (None, (), [{}], [self.rec, self.rec],
                                 [second, self.rec], [replace(self.rec, song_id='z'), self.rec]):
            self.assert_invalid(self.result, recommendations=recommendations)
        self.assert_invalid(self.result, voice_profile={})
        self.assert_invalid(self.result, analysis_mode='real')
        self.assert_invalid(self.result, processing_time_s=-1)
        replace(self.result, recommendations=[]).validate()

    def test_nested_mutation_is_revalidated_before_serialization(self):
        mutations = (lambda items: items[0].waveform.append(float('nan')),
                     lambda items: items[2].mfcc_mean.pop(),
                     lambda items: items[1].warnings.append(None),
                     lambda items: items[3].warnings.clear(),
                     lambda items: items[6].recommendations.append(items[5]))
        for index, mutate in enumerate(mutations):
            items = fixtures()
            mutate(items)
            # Serialize each relevant root; nested children must be revisited.
            root = items[0] if index == 0 else items[6]
            with self.assertRaises(ContractError):
                root.to_dict()
            with self.assertRaises(ContractError):
                root.to_json()
