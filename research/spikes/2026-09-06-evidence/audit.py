#!/usr/bin/env python3
"""Audit saved reference rankings, plus exact pilot-design calculations. No model execution."""
import collections, gzip, hashlib, json, math, random, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/eval'))
import corpora
OUT=Path(__file__).resolve().parent
RAW=ROOT/'docs/reports/bakeoff/validation/skillretbench-r1-encoder.jsonl.gz'
SEED=20260906

def paired(a,b,rounds=2000):
    if not a: return None
    assert len(a)==len(b)
    ds=[y-x for x,y in zip(a,b)]
    rng=random.Random(SEED)
    boot=sorted(sum(rng.choices(ds,k=len(ds)))/len(ds) for _ in range(rounds))
    return dict(n=len(a),baseline=sum(a)/len(a),encoder=sum(b)/len(b),delta_pp=100*sum(ds)/len(ds),ci95_pp=[100*boot[int(rounds*.025)],100*boot[int(rounds*.975)]],metric_increases=sum(x<y for x,y in zip(a,b)),metric_decreases=sum(x>y for x,y in zip(a,b)))

def metrics(ids,rows,labels):
    def selected(r): return {u.rsplit(':',1)[-1] for u in r['injection'][:4]}
    def complete(r,i): return int(bool(labels[i]['gold_skills']) and set(labels[i]['gold_skills'])<=selected(r))
    def hit(r,i): return int(bool(r['retrieval']) and r['retrieval'][0]['urn'].rsplit(':',1)[-1] in labels[i]['gold_skills'])
    def calc(fn,subset): return paired([fn(rows['F0'][i],i) for i in subset],[fn(rows['R1-encoder'][i],i) for i in subset])
    answered=[i for i in ids if rows['F0'][i]['injection'] and rows['R1-encoder'][i]['injection']]
    harms=[i for i in ids if labels[i].get('distractor_skills')]
    return dict(n=len(ids),abstentions={arm:sum(not rows[arm][i]['injection'] for i in ids) for arm in rows},hit1_all_queries=calc(hit,ids),all_gold_injected4_all_queries=calc(complete,ids),all_gold_injected4_both_answered=calc(complete,answered),labelled_distractor_exposure4=calc(lambda r,i:int(bool(set(labels[i]['distractor_skills']) & selected(r))),harms))

def pilot_design():
    def binom(n,k,p): return math.comb(n,k)*p**k*(1-p)**(n-k)
    def reject(d,w): return min(1.,2*sum(math.comb(d,k) for k in range(min(w,d-w)+1))/2**d)<=.05
    scenarios=[]
    for n in (20,40,100,200):
        for plus,minus in ((.15,.05),(.20,.05),(.25,.05)):
            discordance=plus+minus
            power=sum(binom(n,d,discordance)*sum(binom(d,w,plus/discordance) for w in range(d+1) if reject(d,w)) for d in range(n+1))
            scenarios.append(dict(n_pairs=n,p_improvement=plus,p_regression=minus,true_net_lift_pp=100*(plus-minus),power_two_sided_exact_005=power))
    return dict(status='exact design calculation, NOT user evidence',assumptions='Independent paired binary outcomes; two-sided exact sign/McNemar, alpha=.05; no multiplicity adjustment. Shared developer/skill clustering reduces effective n.',scenarios=scenarios,zero_harm_bounds=[dict(n_independent_pairs=n,one_sided_95_upper_harm_if_zero_observed=1-.05**(1/n)) for n in (20,40,100,200)],minimum_zero_harm_pairs_to_bound_rate_below_5pct=math.ceil(math.log(.05)/math.log(.95)),warning='20-40 tasks establish usability, not a guaranteed small efficacy/harm effect.')

def main():
    problems={n:corpora.verify(n) for n in corpora.manifest()['corpora']}
    if any(problems.values()): raise RuntimeError(problems)
    labels={q['query_id']:q for q in corpora.load_skillretbench()['queries']['queries']}
    assert len(labels)==1250
    groups=collections.defaultdict(dict)
    for r in (json.loads(s) for s in gzip.open(RAW,'rt') if s.strip()):
        key=(r['node_key'],r['arm'])
        assert r['query_id'] not in groups[key]
        assert len(r['injection'])<=4
        groups[key][r['query_id']]=r
    assert len(groups)==4 and all(set(rs)==set(labels) for rs in groups.values())
    strata=dict(all_queries=list(labels),card_budget_feasible=[i for i,q in labels.items() if 0<len(set(q['gold_skills']))<=4],card_budget_impossible=[i for i,q in labels.items() if len(set(q['gold_skills']))>4],distractor=[i for i,q in labels.items() if q['setting']=='distractor'])
    results={scope:{s:metrics(ids,{arm:groups[scope,arm] for arm in ('F0','R1-encoder')},labels) for s,ids in strata.items()} for scope in ('node_root','node_scoped')}
    sources=[RAW,corpora.MANIFEST,corpora.corpus_dir('skillretbench')/'skillretbench_queries.json',Path(__file__)]
    result=dict(as_of='2026-09-06',status='exploratory post-hoc audit of saved historical reference; NOT model admission',commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sources=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sources],corpus_verification=problems,seed=SEED,bootstrap_resamples=2000,unit='query paired within scope; bootstrap ignores shared-skill clustering',definition='Any-gold hit@1. All annotated gold must appear in injected first 4. No reply scores zero.',gold_cardinality=dict(sorted(collections.Counter(len(set(q['gold_skills'])) for q in labels.values()).items())),empty_gold_queries=sum(not q['gold_skills'] for q in labels.values()),strata={s:len(ids) for s,ids in strata.items()},results=results,caveats=['Reference comparator is shipped F0; flat is an unadmitted experimental alternative.','node_scoped uses category from first gold label, not measured cwd.','Gold lists interpreted as AND by historical adapter; validate alternatives for paper.','No empty-gold cases: this corpus cannot validate NO_SKILL.','No causal ID/OOD or distillation claim follows from this corpus.','Post-hoc strata: no retrieval, tuning, or new configurations were run.','Historical aggregates may condition on answered queries; our headline includes all.'])
    (OUT/'audit-results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    power=pilot_design()
    (OUT/'pilot-power.json').write_text(json.dumps(power,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(strata=result['strata'],gold_cardinality=result['gold_cardinality'],root=results['node_root'],pilot_power=power),indent=2))

if __name__=='__main__':
    assert paired([0,1],[1,0],100)['delta_pp']==0
    assert paired([],[]) is None
    assert paired([0]*5,[1]*5,100)['ci95_pp']==[100,100]
    main()
