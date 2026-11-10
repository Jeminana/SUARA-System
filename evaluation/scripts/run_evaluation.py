"""Contract-aligned illustrative evaluation; never report as real AI performance."""
import json
from pathlib import Path
from contracts_bridge import load_contracts,construct_profile
from metrics import naive_rank_contract,mean_absolute_cents,precision_at_k,ndcg_at_k
ROOT=Path(__file__).resolve().parents[1]

def main():
    cls, location=load_contracts()
    print('Validated against contract:',location,'schema',cls.SCHEMA_VERSION)
    profiles=[construct_profile(cls,d) for d in json.loads((ROOT/'fixtures/voice_profiles.json').read_text())]
    songs=[cls.SongFeatures(**d) for d in json.loads((ROOT/'fixtures/song_features.json').read_text())]
    for profile, raw in zip(profiles,json.loads((ROOT/'fixtures/voice_profiles.json').read_text())):
        ranking=naive_rank_contract(profile,songs)
        print(raw['fixture_id'],[(x['song_id'],round(x['score'],3) if x['score'] is not None else None) for x in ranking])
    print('Artificial pitch MAE (cents):',mean_absolute_cents([(440.,441.),(220.,220.)]))
    print('Artificial Precision@2:',precision_at_k(['a','b','c'],{'a'},2))
    print('Artificial NDCG@2:',ndcg_at_k(['a','b'],{'a':3,'b':1},2))
    print('NOTE: No SUARA model inference or suitability study has been evaluated.')
if __name__=='__main__': main()
