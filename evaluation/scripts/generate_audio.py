"""Generate public-safe synthetic WAV input; fixed random seed."""
from pathlib import Path
import json,math,random,wave,struct
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'generated'
RATE=16000

def write_wav(path,samples):
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(RATE)
        w.writeframes(b''.join(struct.pack('<h',max(-32768,min(32767,round(32767*max(-1,min(1,x)))))) for x in samples))

def tone(freq,seconds=2.0):
    return [0.4*math.sin(2*math.pi*freq*i/RATE) for i in range(int(seconds*RATE))]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rng=random.Random(12345)
    cases={'A3_220Hz.wav':('single_tone',220.0,tone(220)),
           'A4_440Hz.wav':('single_tone',440.0,tone(440)),
           'C5_523p25Hz.wav':('single_tone',523.25,tone(523.25)),
           'silence.wav':('silence',None,[0.0]*RATE),
           'two_tones.wav':('sequence',[220.0,440.0],tone(220,1)+tone(440,1)),
           'noise.wav':('noise',None,[rng.uniform(-0.15,0.15) for _ in range(RATE)])}
    manifest=[]
    for name,(kind,ref,samples) in cases.items():
        write_wav(OUT/name,samples)
        manifest.append({'file':name,'type':kind,'reference_hz':ref,'sample_rate':RATE,'duration_sec':len(samples)/RATE,'seed':12345 if kind=='noise' else None})
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(f'Created {len(manifest)} WAV files in {OUT}')
if __name__=='__main__': main()
