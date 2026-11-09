"""Pure evaluation helpers; not coupled to SUARA contracts."""
import math
import statistics
import time

def cents_error(reference_hz, predicted_hz):
    if not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in (reference_hz,predicted_hz)):
        return None
    return abs(1200*math.log2(predicted_hz/reference_hz))

def mean_absolute_cents(pairs):
    values=[v for r,p in pairs if (v:=cents_error(r,p)) is not None]
    return statistics.mean(values) if values else None

def voicing_scores(reference, predicted):
    if len(reference)!=len(predicted):
        raise ValueError('frame arrays must be aligned and equal length')
    tp=sum(bool(a) and bool(b) for a,b in zip(reference,predicted))
    fp=sum(not bool(a) and bool(b) for a,b in zip(reference,predicted))
    fn=sum(bool(a) and not bool(b) for a,b in zip(reference,predicted))
    precision=tp/(tp+fp) if tp+fp else 0.0
    recall=tp/(tp+fn) if tp+fn else 0.0
    f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
    return {'tp':tp,'fp':fp,'fn':fn,'precision':precision,'recall':recall,'f1':f1}

def hz_to_midi(frequency):
    if frequency is None or not isinstance(frequency,(int,float)) or not math.isfinite(frequency) or frequency<=0:
        return None
    return 69+12*math.log2(frequency/440.0)

def pitch_range_coverage(user_low_hz,user_high_hz,song_low_hz,song_high_hz):
    values=[hz_to_midi(v) for v in (user_low_hz,user_high_hz,song_low_hz,song_high_hz)]
    if any(v is None for v in values): return None
    u0,u1,s0,s1=values
    if u0>u1 or s0>=s1: return None
    return max(0.0, min(u1,s1)-max(u0,s0))/(s1-s0)

def naive_rank(user,songs):
    """Conceptual fixtures only; None = missing suitability evidence."""
    ranked=[]
    for song in songs:
        score=pitch_range_coverage(user.get('low_hz'),user.get('high_hz'),song.get('melody_low_hz'),song.get('melody_high_hz'))
        ranked.append({'song_id':song['song_id'],'score':score,'reason':'range overlap baseline' if score is not None else 'melody range unavailable'})
    return sorted(ranked,key=lambda x:(x['score'] is None,-x['score'] if x['score'] is not None else 0,x['song_id']))

def precision_at_k(ranked_ids,relevant_ids,k):
    if k<=0: raise ValueError('k must be positive')
    return sum(song in relevant_ids for song in ranked_ids[:k])/k

def ndcg_at_k(ranked_ids,judgments,k):
    if k<=0: raise ValueError('k must be positive')
    def dcg(gains): return sum((2**g-1)/math.log2(i+2) for i,g in enumerate(gains))
    actual=dcg([judgments.get(song,0) for song in ranked_ids[:k]])
    ideal=dcg(sorted(judgments.values(),reverse=True)[:k])
    return actual/ideal if ideal else None

def timed_run(fn,*args,**kwargs):
    start=time.perf_counter()
    result=fn(*args,**kwargs)
    return result,time.perf_counter()-start


def naive_rank_contract(profile, songs):
    """Independent evaluation baseline, not a SUARA production recommender.

    Uses contract field names. Returns optional scores, not Recommendations,
    because the Recommendation contract forbids null scores. Any absent range
    is reported as not evaluable rather than invented as zero suitability.
    """
    pitch = profile.pitch
    out = []
    for song in songs:
        value = pitch_range_coverage(pitch.min_pitch_hz, pitch.max_pitch_hz,
                                     song.melody_min_pitch_hz, song.melody_max_pitch_hz)
        if pitch.voiced_ratio == 0:
            value = None
        out.append({"song_id":song.song_id, "score":value,
                    "reason":"illustrative range coverage only" if value is not None else "insufficient evidence"})
    return sorted(out, key=lambda x: (x['score'] is None,
                    -x['score'] if x['score'] is not None else 0, x['song_id']))
