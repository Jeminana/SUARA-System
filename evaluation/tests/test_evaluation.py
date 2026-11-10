import json,sys,unittest, tempfile,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from metrics import cents_error,mean_absolute_cents,voicing_scores,pitch_range_coverage,naive_rank,precision_at_k,ndcg_at_k
from generate_audio import write_wav,tone,RATE

class Tests(unittest.TestCase):
    def test_exact_pitch_zero_cents(self): self.assertAlmostEqual(cents_error(440,440),0)
    def test_semitone_is_100_cents(self): self.assertAlmostEqual(cents_error(440,440*2**(1/12)),100)
    def test_invalid_pitch_is_none(self):
        self.assertIsNone(cents_error(0,440));self.assertIsNone(mean_absolute_cents([(None,None)]))
    def test_voicing_f1(self):
        x=voicing_scores([True,True,False],[True,False,True]);self.assertEqual((x['tp'],x['fp'],x['fn']),(1,1,1))
    def test_voicing_alignment(self):
        with self.assertRaises(ValueError): voicing_scores([True],[True,False])
    def test_overlap(self):
        self.assertAlmostEqual(pitch_range_coverage(220,440,220,440),1)
        self.assertAlmostEqual(pitch_range_coverage(110,220,440,880),0)
        self.assertIsNone(pitch_range_coverage(None,220,220,440))
    def test_missing_song_range_ranked_last(self):
        rows=[{'song_id':'x','melody_low_hz':None,'melody_high_hz':None},{'song_id':'a','melody_low_hz':220,'melody_high_hz':440}]
        self.assertEqual([x['song_id'] for x in naive_rank({'low_hz':220,'high_hz':440},rows)],['a','x'])
    def test_stable_ties(self):
        rows=[{'song_id':s,'melody_low_hz':220,'melody_high_hz':440} for s in ['z','a']]
        self.assertEqual([x['song_id'] for x in naive_rank({'low_hz':220,'high_hz':440},rows)],['a','z'])
    def test_precision_ndcg(self):
        self.assertAlmostEqual(precision_at_k(['a','b'],{'a'},2),0.5)
        self.assertAlmostEqual(ndcg_at_k(['a','b'],{'a':3,'b':1},2),1)
        self.assertIsNone(ndcg_at_k(['a'],{},2))
    def test_wav_generated_and_silence(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'silence.wav';write_wav(p,[0.0]*RATE)
            with wave.open(str(p),'rb') as w:
                self.assertEqual(w.getframerate(),RATE);self.assertEqual(w.getnframes(),RATE)
    def test_invalid_wav_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.wav';p.write_bytes(b'not a wav')
            with self.assertRaises((wave.Error,EOFError)):wave.open(str(p),'rb')

if __name__=='__main__': unittest.main()
