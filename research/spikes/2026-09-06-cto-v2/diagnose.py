#!/usr/bin/env python3
"""Read-only CPU diagnosis of previously encoded features and trained weights; no fitting."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[k]='2'
import collections,gzip,hashlib,json,math,re,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
P=ROOT/'research/spikes/2026-09-06-field-aware'
B=Path('/home/mike/.cache/guidefold/corpora/skillret/data')

def mean(a): return float(np.mean(a)) if len(a) else None
def summ(a):
    a=np.asarray(a)
    return {'n':len(a),'min':float(a.min()),'p50':float(np.median(a)),'p95':float(np.quantile(a,.95)),'max':float(a.max())} if len(a) else {'n':0}
def top(x,n): return np.argsort(-x,kind='stable')[:n]
def write(n,o): (OUT/n).write_text(json.dumps(o,indent=2,allow_nan=False)+'\n')

def main():
    started=time.time();m=json.loads((P/'manifest.json').read_text())
    qs={q['id']:q for q in map(json.loads,(B/'queries/train.jsonl').open())}
    skills=sorted(list(map(json.loads,(B/'skills/train.jsonl').open())),key=lambda x:x['id'])
    row={s['id']:i for i,s in enumerate(skills)}
    train=[qs[i] for i in m['train_ids']];dev=[qs[i] for i in m['dev_ids']]
    features=np.memmap(P/'cache/features.f32',dtype='float32',mode='r',shape=(3000,10123,8))
    predictions=collections.defaultdict(dict)
    for r in map(json.loads,gzip.open(P/'dev-rankings.jsonl.gz','rt')):predictions[r['arm']][r['query_id']]=r
    strata={}
    for arm,rows in predictions.items():
        strata[arm]={}
        for k in (1,2,3):
            sub=[q for q in dev if len(set(q['skill_ids']))==k]
            vs=[rows[q['id']]['metrics'] for q in sub]
            first=[int(q['skill_ids'][0] in rows[q['id']]['ranked']) for q in sub]
            companions=[int(s in rows[q['id']]['ranked']) for q in sub for s in q['skill_ids'][1:]]
            strata[arm][str(k)]={'n_queries':len(sub),'metrics':dict(zip(('hit1','recall10','ndcg10_binary','all_gold4'),np.mean(vs,axis=0).tolist())),'first_gold_recall10':mean(first),'companion_gold_micro_recall10':mean(companions),'all_gold_in_top10':mean([int(set(q['skill_ids'])<=set(rows[q['id']]['ranked'])) for q in sub])}
    transitions={}
    for role in ('first','companion'):
        bits=[]
        for q in dev:
            for sid in q['skill_ids'][:1] if role=='first' else q['skill_ids'][1:]:
                bits.append((sid in predictions['flat_mlp'][q['id']]['ranked'],sid in predictions['field_mlp'][q['id']]['ranked']))
        transitions[role]={'n_gold_instances':len(bits),'lost_flat_to_field':sum(a and not b for a,b in bits),'gained_flat_to_field':sum(b and not a for a,b in bits)}
    weights={a:json.loads((P/(a+'-weights.json')).read_text()) for a in ('flat_mlp','field_mlp','sparse_field_mlp')}
    gradients={};channel_gold={};names=['tfidf_name','tfidf_description','tfidf_body','dense_name','dense_description','dense_body','tfidf_flat','dense_flat']
    goldf=[]
    for j,q in enumerate(dev):
        goldf.extend(np.asarray(features[2000+j,[row[s] for s in q['skill_ids']],:]))
    goldf=np.asarray(goldf)
    for arm,w in weights.items():
        cols=w['columns'];w1=np.asarray(w['state']['0.weight']);b1=np.asarray(w['state']['0.bias']);w2=np.asarray(w['state']['2.weight'])[0]
        z=(goldf[:,cols]-w['mean'])/w['scale'];act=z@w1.T+b1
        grad=((act>0)*w2)@w1/np.asarray(w['scale'])
        gradients[arm]={names[c]:{'negative_derivative_fraction':mean(grad[:,j]<0),'raw_score_derivative':summ(grad[:,j])} for j,c in enumerate(cols)}
    devceil={str(k):[] for k in (1,2,3)};channelhits={str(k):[[] for _ in range(8)] for k in (1,2,3)}
    for j,q in enumerate(dev):
        g={row[s] for s in q['skill_ids']};k=str(len(g));f=features[2000+j]
        ts=[set(top(f[:,c],20)) for c in range(8)];un=set().union(*ts)
        devceil[k].append(len(g&un)/len(g))
        for c,t in enumerate(ts):channelhits[k][c].append(len(g&t)/len(g))
    blocked={row[s] for q in dev for s in q['skill_ids']}
    assert len(blocked)==m['excluded_skill_ids_including_exact_duplicates']==1832
    rng=np.random.default_rng(m['seed']);pairs=[];ex=0
    for j,q in enumerate(train):
        g={row[s] for s in q['skill_ids']};f=features[j]
        hard=set().union(*(set(top(f[:,c],20)) for c in range(8)))
        proposed=g|hard|set(rng.choice(len(skills),20,replace=False));ex+=len(proposed&blocked)
        candidates=proposed-blocked
        pairs.append({'id':q['id'],'k':len(g),'negative_count':len(candidates-g),'positive_count':len(g),'n_pairs':len(candidates)})
    n=sum(p['n_pairs'] for p in pairs);positive=sum(p['positive_count'] for p in pairs);pw=(n-positive)/positive
    pairdist={}
    for k in (1,2,3):
        ps=[p for p in pairs if p['k']==k]
        mass=sum(p['negative_count']+pw*p['positive_count'] for p in ps)
        pairdist[str(k)]={'n_queries':len(ps),'n_pairs':sum(p['n_pairs'] for p in ps),'positive_pairs':sum(p['positive_count'] for p in ps),'negative_count_per_query':summ([p['negative_count'] for p in ps]),'fraction_global_BCE_weight_mass':mass/(2*(n-positive)),'mean_BCE_weight_mass_per_query':mass/len(ps)}
    # Inventory only already-written query IDs, not new labels or predictions.
    exposures={};allids=set()
    paths=list((ROOT/'docs/reports/bakeoff/validation').rglob('*'))+list((ROOT/'research/spikes').rglob('*'))
    for p in paths:
        if not p.is_file() or '/cache/' in str(p) or p.suffix not in ('.json','.gz','.jsonl'):continue
        try:
            data=gzip.open(p,'rb').read() if p.suffix=='.gz' else p.read_bytes()
        except OSError:continue
        ids={s.decode() for s in re.findall(rb'q-train-\d{6}',data)}
        if ids: exposures[str(p.relative_to(ROOT))]=len(ids);allids|=ids
    poolids=set(qs);eligible_unexposed=poolids-allids
    out={'kind':'posthoc CPU-only diagnosis; no retraining, no new treatment or holdout evaluation','source_run_manifest_sha256':hashlib.sha256((P/'manifest.json').read_bytes()).hexdigest(),'strata_by_gold_k':strata,'flat_to_field_gold_recall_transitions':transitions,'local_derivatives_at_dev_gold_vectors':gradients,'top20_channel_union_gold_recall_ceiling':{k:mean(v) for k,v in devceil.items()},'top20_channel_gold_recall':{k:{names[c]:mean(v) for c,v in enumerate(vs)} for k,vs in channelhits.items()},'training_pair_reconstruction':{'pairs':n,'positives':positive,'excluded':ex,'positive_BCE_weight':pw,'by_k':pairdist},'recorded_query_exposure_inventory':{'scope':'committed validation outputs and current research JSON/gzip excluding caches; unknown external logs not covered','unique_recorded_qtrain_ids':len(allids),'raw_train_query_ids':len(poolids),'unrecorded_train_query_ids':len(eligible_unexposed),'unrecorded_by_k':dict(collections.Counter(len(qs[q]['skill_ids']) for q in eligible_unexposed)),'files':exposures},'elapsed_seconds':time.time()-started}
    assert (n,positive,ex)==(186673,3774,36953)
    write('diagnostics.json',out)
    write('recorded-exposure-ids.json',{'ids':sorted(allids),'scope':out['recorded_query_exposure_inventory']['scope']})
    print(json.dumps({k:v for k,v in out.items() if k not in ('local_derivatives_at_dev_gold_vectors','recorded_query_exposure_inventory','top20_channel_gold_recall')},indent=2))

if __name__=='__main__':main()
