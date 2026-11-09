import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from contracts_bridge import load_contracts,construct_profile
from metrics import naive_rank_contract

class ContractAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c,cls.location=load_contracts()
        cls.raw_profiles=json.loads((ROOT/'fixtures/voice_profiles.json').read_text())
        cls.raw_songs=json.loads((ROOT/'fixtures/song_features.json').read_text())

    def test_version(self):
        self.assertEqual(self.c.SCHEMA_VERSION,'1.0.0')
        self.assertEqual(self.c.MFCC_DIM,20)

    def test_profiles_construct_and_serialize(self):
        for data in self.raw_profiles:
            p=construct_profile(self.c,data)
            p.validate(); self.assertEqual(p.to_dict()['schema_version'],'1.0.0')
            self.assertEqual(len(p.timbre.mfcc_mean),20)

    def test_song_features_construct_and_serialize(self):
        for data in self.raw_songs:
            item=self.c.SongFeatures(**data)
            item.validate(); self.assertEqual(item.to_dict()['provenance'],'mock')

    def test_unvoiced_statistics_null(self):
        p=construct_profile(self.c,self.raw_profiles[-1]);self.assertEqual(p.status,'no_voiced_pitch')
        self.assertIsNone(p.pitch.min_pitch_hz)
        self.assertTrue(all(v['score'] is None for v in naive_rank_contract(p,[self.c.SongFeatures(**x) for x in self.raw_songs])))

    def test_unvoiced_with_fabricated_pitch_rejected(self):
        d=dict(self.raw_profiles[-1]['pitch']); d['min_pitch_hz']=110.0;d['max_pitch_hz']=200.0;d['median_pitch_hz']=150.0
        with self.assertRaises(self.c.ContractError): self.c.PitchFeatures(**d)

    def test_mfcc_wrong_dimension_rejected(self):
        d=dict(self.raw_profiles[0]['timbre']);d['mfcc_mean']=[0.0]*19
        with self.assertRaises(self.c.ContractError): self.c.TimbreFeatures(**d)

    def test_verified_song_requires_pitch_range(self):
        d=dict(self.raw_songs[-1]);d['provenance']='verified_melody'
        with self.assertRaises(self.c.ContractError): self.c.SongFeatures(**d)

    def test_extra_fields_rejected(self):
        d=dict(self.raw_songs[0]);d['unapproved_field']='bad'
        with self.assertRaises(TypeError):self.c.SongFeatures(**d)

    def test_schema_version_rejected(self):
        d=dict(self.raw_songs[0]);d['schema_version']='2.0.0'
        with self.assertRaises(self.c.ContractError):self.c.SongFeatures(**d)

    def test_null_range_is_unknown_not_zero(self):
        profile=construct_profile(self.c,self.raw_profiles[0]);catalog=[self.c.SongFeatures(**x) for x in self.raw_songs]
        ranking=naive_rank_contract(profile,catalog)
        self.assertEqual(ranking[-1]['song_id'],'synthetic_unknown');self.assertIsNone(ranking[-1]['score'])

    def test_deterministic_rankings(self):
        profile=construct_profile(self.c,self.raw_profiles[0]);catalog=[self.c.SongFeatures(**x) for x in self.raw_songs]
        a=naive_rank_contract(profile,catalog);b=naive_rank_contract(profile,list(reversed(catalog)))
        self.assertEqual(a,b)

    def test_recommendation_invalid_score_rejected(self):
        with self.assertRaises(self.c.ContractError):
            self.c.Recommendation(song_id='x',title='X',artist='Y',score=float('nan'),explanation='mock',scoring_version='test',mode='mock')
