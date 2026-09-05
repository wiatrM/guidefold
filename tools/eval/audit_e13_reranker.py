import sys, json, math, time, datetime, hashlib, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"tools/bakeoff"),str(ROOT/"tools/eval")]
import numpy as np, torch
import arms, metrics
from corpus import load_corpus
from run_golden import load_cases
import argparse
parser=argparse.ArgumentParser(description='Exploratory 22-case stale reranker audit; requires local pinned models and bakeoff dependencies.')
parser.add_argument('--out', type=Path, required=True)
args=parser.parse_args()
out=args.out
out.parent.mkdir(parents=True, exist_ok=True)
corpus=load_corpus()
byurn={r.urn:r for r in corpus}
deprecated={r.urn for r in corpus if r.status=="deprecated"}
cases=[c for c in load_cases() if c["category"]=="stale_adversarial"]
def safe(o):
    if isinstance(o,float) and (math.isnan(o) or math.isinf(o)): return None
    if isinstance(o,dict): return {k:safe(v) for k,v in o.items()}
    if isinstance(o,(list,tuple)): return [safe(v) for v in o]
    return o
report={"kind":"Exploratory, current fresh GPU run, existing golden cases, not held out.",
"created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
"git_sha":subprocess.check_output(["git","-c","safe.directory="+str(ROOT),"rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
"device":arms.DEVICE,"dtype":str(arms.DTYPE),"torch":torch.__version__,"n":len(cases),
"filter_semantics":"Remove status=deprecated from the same B5 top20 scores, without refill. Same pairwise scores isolate filtering from numeric batch variation. No node visibility filtering in any arm.",
"cases":[],"summary":{},
"corpus_sha256":hashlib.sha256(json.dumps([r.__dict__ for r in corpus],sort_keys=True,default=list).encode()).hexdigest(),
"cases_sha256":hashlib.sha256(json.dumps(cases,sort_keys=True).encode()).hexdigest()}
variants=["B5_no_deprecated","B5","B6_default","B6_full_body","B6_no_deprecated","B6_full_body_no_deprecated"]
results={v:[] for v in variants}
reranker=arms.Reranker()
beg=time.perf_counter()
for ci,case in enumerate(cases):
    q=case["query"]
    t=time.perf_counter()
    base=arms.arm_b5(q,corpus,limit=20)
    baseline_s=time.perf_counter()-t
    records=[byurn[u] for u in base]
    t=time.perf_counter()
    default=reranker.score_batch(q,records)
    ds=time.perf_counter()-t
    t=time.perf_counter()
    full=reranker.score_batch(q,records,body_max=20000,desc_max=500,max_length=4096)
    fs=time.perf_counter()-t
    rank=lambda scores,filtered=False:[u for s,u in sorted(zip(scores,base),key=lambda su:(-su[0],su[1])) if not filtered or u not in deprecated]
    ranks={"B5_no_deprecated":[u for u in base if u not in deprecated],"B5":base,"B6_default":rank(default),"B6_full_body":rank(full),"B6_no_deprecated":rank(default,True),"B6_full_body_no_deprecated":rank(full,True)}
    row={"id":case["id"],"query":q,"node":case["node"],"relevant":case.get("relevant"),"distractors":case.get("distractors"),"seconds":{"B5":baseline_s,"B6_default":ds,"B6_full_body":fs},"rankings":ranks,
    "pair_scores":[{"urn":u,"default":d,"full_body":f,"deprecated":u in deprecated} for u,d,f in zip(base,default,full)],"per_case":{}}
    grade=metrics.graded(case)
    must={u for u,g in grade.items() if g==3}
    required={u for u,g in grade.items() if g>=2}
    for v,r in ranks.items():
        results[v].append((r,case))
        row["per_case"][v]={"hit_ge2_at1":metrics.hit_at_1(r,case) if grade else None,
        "strict_grade3_at1":int(bool(r) and r[0] in must) if must else None,
        "all_grade_ge2_at4":int(required <= set(r[:4])) if required else None,
        "all_grade_ge2_at8":int(required <= set(r[:8])) if required else None,
        "deprecated_at1":int(bool(r) and r[0] in deprecated),
        "deprecated_at4":int(bool(deprecated & set(r[:4]))),
        "correct_abstention":int(not r) if not grade else None}
    report["cases"].append(row)
    out.write_text(json.dumps(safe(report),indent=2))
    print(f"{ci+1}/{len(cases)} {case['id']} B5={baseline_s:.2f}s default={ds:.2f}s full={fs:.2f}s elapsed={time.perf_counter()-beg:.1f}s",flush=True)
for v,rs in results.items():
    s=metrics.evaluate(rs)
    pc=[r["per_case"][v] for r in report["cases"]]
    for key in ["strict_grade3_at1","all_grade_ge2_at4","all_grade_ge2_at8","deprecated_at1","deprecated_at4","correct_abstention"]:
        vals=[r[key] for r in pc if r[key] is not None]
        s[key]={"successes":sum(vals),"n":len(vals),"rate":sum(vals)/len(vals) if vals else None}
    report["summary"][v]=s
# Independent inference efficiency check on exactly the final default candidate list.
orig=reranker._model.forward
t=time.perf_counter()
old_scores=reranker.score_batch(q,records)
old_s=time.perf_counter()-t
def last_only(*args,**kwargs):
    return orig(*args,**kwargs,logits_to_keep=1)
reranker._model.forward=last_only
t=time.perf_counter()
new_scores=reranker.score_batch(q,records)
new_s=time.perf_counter()-t
reranker._model.forward=orig
report["last_token_logits_check"]={"case":case["id"],"default_s":old_s,"logits_to_keep_1_s":new_s,"max_abs_score_diff":float(np.max(np.abs(np.array(old_scores)-np.array(new_scores)))),"identical_ranking":rank(old_scores)==rank(new_scores),"old_scores":old_scores,"new_scores":new_scores}
report["total_seconds"]=time.perf_counter()-beg
out.write_text(json.dumps(safe(report),indent=2))
print(json.dumps(safe({"summary":report["summary"],"last_token_logits_check":report["last_token_logits_check"],"total_seconds":report["total_seconds"],"out":str(out)}),indent=2),flush=True)


