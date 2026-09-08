#!/usr/bin/env python3
"""Frozen DEV-only field-aware fusion spike; see PROTOCOL.md before interpreting."""
import os
for key in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE'): os.environ[key]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import collections, gzip, hashlib, json, platform, random, re, subprocess, sys, time
from pathlib import Path
import numpy as np
import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/eval'))
import corpora, dev_sparse
OUT=Path(__file__).resolve().parent
CACHE=OUT/'cache'
CACHE.mkdir(exist_ok=True)
SEED=20260906
MODEL=Path('/home/mike/.cache/guidefold/models/Qwen__Qwen3-Embedding-0.6B/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3')
PROMPT='Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:'
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
torch.set_num_threads(4)

def norm(s): return ' '.join(s.lower().split())
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def log(s): print(s,flush=True)
def write(name,obj): (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def top(scores,n): return np.argsort(-scores,kind='stable')[:n]

def pair_ci(a,b):
    ds=np.array(b)-np.array(a); rng=np.random.default_rng(SEED)
    bs=np.array([ds[rng.integers(0,len(ds),len(ds))].mean() for _ in range(2000)])
    return {'n':len(ds),'delta_pp':float(ds.mean()*100),'ci95_pp':(np.quantile(bs,[.025,.975])*100).tolist()}

def metric(rank,inj,gold):
    hits=[int(i in gold) for i in rank[:10]]
    dcg=sum(v/np.log2(j+2) for j,v in enumerate(hits))
    idcg=sum(1/np.log2(j+2) for j in range(min(10,len(gold))))
    return [float(hits[0]),sum(hits)/len(gold),float(dcg/idcg),float(gold<=set(inj))]

def main():
    started=time.time()
    base=corpora.corpus_dir('skillret')/'data'
    sf=base/'skills/train.jsonl'; qf=base/'queries/train.jsonl'
    skills=sorted([json.loads(s) for s in sf.open()],key=lambda s:s['id'])
    queries=[json.loads(s) for s in qf.open()]
    devids=set(json.loads(corpora.DEV_SPLIT.read_text())['query_ids'])
    dev=sorted([q for q in queries if q['id'] in devids],key=lambda q:q['id'])
    assert len(skills)==10123 and len(dev)==1000
    cards,nodes,id_to_urn,_=dev_sparse.corpus_to_cards(skills)
    sid_to_row={s['id']:i for i,s in enumerate(skills)}
    urns=[id_to_urn[s['id']] for s in skills]; urn_to_row={u:i for i,u in enumerate(urns)}
    texts=[[s['name'] for s in skills],[s['description'] for s in skills],[cards[u]['_body'] for u in urns]]
    texts.append(['\n'.join(row) for row in zip(*texts)])
    devgold=set().union(*(set(q['skill_ids']) for q in dev))
    fingerprints={s['id']:hashlib.sha256(norm(texts[3][i]).encode()).hexdigest() for i,s in enumerate(skills)}
    blockedprints={fingerprints[i] for i in devgold}
    blocked=devgold|{i for i,h in fingerprints.items() if h in blockedprints}
    devtext={norm(q['query']) for q in dev}
    eligible=[q for q in queries if q['id'] not in devids and norm(q['query']) not in devtext and not(set(q['skill_ids'])&blocked)]
    train=sorted(eligible,key=lambda q:hashlib.sha256(q['id'].encode()).hexdigest())[:2000]
    assert len(train)==2000 and not(set().union(*(set(q['skill_ids']) for q in train))&blocked)
    qs=train+dev; qtexts=[q['query'] for q in qs]
    source_hashes={str(p):digest(p) for p in (sf,qf,corpora.DEV_SPLIT,Path(__file__),OUT/'PROTOCOL.md')}
    manifest={'status':'frozen feasibility, no test corpus read','model':str(MODEL),'seed':SEED,'max_seq_length':1024,'training_queries':len(train),'dev_queries':len(dev),'candidate_skills':len(skills),'eligible_training_queries':len(eligible),'dev_gold_skills':len(devgold),'excluded_skill_ids_including_exact_duplicates':len(blocked),'train_dev_gold_id_overlap':0,'train_ids':[q['id'] for q in train],'dev_ids':[q['id'] for q in dev],'source_hashes':source_hashes,'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'versions':{'python':platform.python_version(),'numpy':np.__version__,'torch':torch.__version__},'model_config_sha256':digest(MODEL/'config.json')}
    write('manifest.json',manifest)
    log(f'SPLIT train={len(train)} dev={len(dev)} pool={len(skills)} disjoint_gold=0')
    configkey=hashlib.sha256(json.dumps(source_hashes,sort_keys=True).encode()).hexdigest()
    prior=json.loads((CACHE/'pretraining-cache.json').read_text()) if (CACHE/'pretraining-cache.json').exists() else None
    if prior and prior['train_ids']==manifest['train_ids'] and prior['dev_ids']==manifest['dev_ids'] and all(prior['source_hashes'].get(str(p))==source_hashes[str(p)] for p in (sf,qf,corpora.DEV_SPLIT)):
        configkey=prior['key']  # reviewed pre-training correction affects negative labels only, never encoded inputs
    (CACHE/'config-key.txt').write_text(configkey)
    model=SentenceTransformer(str(MODEL),device='cuda',trust_remote_code=False,model_kwargs={'dtype':torch.float16})
    model.max_seq_length=1024; model.eval()
    timings={}; truncation={}
    def encode(name,strings,query=False):
        key=hashlib.sha256((configkey+name+str(query)+'1024').encode()).hexdigest()
        path=CACHE/(key+'.npy')
        t=time.time()
        if path.exists(): out=np.load(path); log(f'CACHE {name} {out.shape}')
        else:
            chunks=[]; clipped=0
            for start in range(0,len(strings),256):
                batch=strings[start:start+256]
                lengths=[len(ids) for ids in model.tokenizer(batch,add_special_tokens=True,truncation=False)['input_ids']]
                clipped+=sum(n>1024 for n in lengths)
                with torch.inference_mode():
                    chunks.append(model.encode(batch,batch_size=8,prompt=PROMPT if query else '',normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False))
                if start%1024==0: log(f'ENCODE {name} {min(start+256,len(strings))}/{len(strings)} elapsed={time.time()-t:.1f}s')
                if time.time()-started>1800: raise RuntimeError('fixed 30-minute compute budget exhausted')
            out=np.concatenate(chunks).astype(np.float32); np.save(path,out)
            truncation[name]={'over_1024_tokens':clipped,'n':len(strings)}
        timings['encode_'+name]=time.time()-t
        return out
    docs=[encode(name,ts) for name,ts in zip(('name','description','body','flat'),texts)]
    qvec=encode('queries',qtexts,True)
    del model; torch.cuda.empty_cache()
    log('SCORING sparse and dense channels')
    features=np.memmap(CACHE/'features.f32',dtype='float32',mode='w+',shape=(len(qs),len(skills),8))
    # Columns: three sparse fields, three dense fields, flat sparse, flat dense.
    t=time.time()
    for f,ts in enumerate(texts):
        vec=TfidfVectorizer(lowercase=True,sublinear_tf=True,dtype=np.float32)
        dm=vec.fit_transform(ts); qm=vec.transform(qtexts)
        col=f if f<3 else 6
        dcol=f+3 if f<3 else 7
        dmat=torch.from_numpy(docs[f]).to('cuda')
        for start in range(0,len(qs),64):
            end=min(start+64,len(qs))
            features[start:end,:,col]=(qm[start:end]@dm.T).toarray()
            with torch.inference_mode():
                features[start:end,:,dcol]=(torch.from_numpy(qvec[start:end]).to('cuda')@dmat.T).cpu().numpy()
        del dm,qm,vec,dmat
        log(f'SCORED field={f}')
    features.flush();timings['feature_scoring_total']=time.time()-t
    log('BUILD training pairs')
    xx=[]; yy=[]; rng=np.random.default_rng(SEED)
    blocked_rows={sid_to_row[s] for s in blocked}
    excluded_negative_pairs=0
    for i,q in enumerate(train):
        gold={sid_to_row[s] for s in q['skill_ids']}
        hard=set().union(*(set(top(features[i,:,c],20)) for c in range(8)))
        proposed=gold|hard|set(rng.choice(len(skills),20,replace=False))
        excluded_negative_pairs+=len(proposed & blocked_rows)
        candidates=sorted(proposed-blocked_rows)
        assert not(set(candidates)&blocked_rows) and gold<=set(candidates)
        xx.append(np.asarray(features[i,candidates,:])); yy.extend(int(c in gold) for c in candidates)
    x=np.concatenate(xx);y=np.asarray(yy,dtype=np.float32)
    mean=x.mean(0);scale=x.std(0);scale[scale<1e-6]=1
    log(f'TRAIN pairs={len(y)} positives={int(y.sum())} excluded_DEV_negative_pairs={excluded_negative_pairs}')
    write('training-overlap-audit.json',{'excluded_negative_pairs':excluded_negative_pairs,'dev_skill_label_exposure_positive_or_negative':0,'blocked_skill_rows':len(blocked_rows),'negative_sampling_note':'top20 channels +20random drawn then blocked removed; no refill'})
    heads={}; headcols={'flat_mlp':[6,7],'field_mlp':[0,1,2,3,4,5],'sparse_field_mlp':[0,1,2]}
    for name,cols in headcols.items():
        torch.manual_seed(SEED)
        net=torch.nn.Sequential(torch.nn.Linear(len(cols),16),torch.nn.ReLU(),torch.nn.Linear(16,1)).to('cuda')
        opt=torch.optim.Adam(net.parameters(),lr=.003)
        xt=torch.from_numpy((x[:,cols]-mean[cols])/scale[cols]).to('cuda'); yt=torch.from_numpy(y).to('cuda')
        lossfn=torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor((len(y)-y.sum())/y.sum(),device='cuda'))
        t=time.time()
        for epoch in range(30):
            order=torch.randperm(len(y),device='cuda')
            for b in order.split(4096):
                opt.zero_grad();loss=lossfn(net(xt[b]).squeeze(1),yt[b]);loss.backward();opt.step()
        net.eval();heads[name]=net
        timings['train_'+name]=time.time()-t
        write(name+'-weights.json',{'columns':cols,'mean':mean[cols].tolist(),'scale':scale[cols].tolist(),'state':{k:v.detach().cpu().tolist() for k,v in net.state_dict().items()},'parameter_count':sum(p.numel() for p in net.parameters())})
        log(f'TRAINED {name} loss={loss.item():.4f} seconds={timings["train_"+name]:.1f}')
    cli=dev_sparse._load_cli()
    idx=cli.Index.from_cards(cards,nodes,weights={'w_dense':0})
    router=cli.Router(idx)
    arms=['flat_uniform','field_uniform']+list(heads)
    vals={a:[] for a in arms};records=[];head_ms={a:[] for a in heads}
    for j,q in enumerate(dev):
        f=np.asarray(features[len(train)+j]);scores={'flat_uniform':f[:,[6,7]].mean(1),'field_uniform':f[:,:6].mean(1)}
        for a,net in heads.items():
            cols=headcols[a];inp=torch.from_numpy((f[:,cols]-mean[cols])/scale[cols]).to('cuda')
            torch.cuda.synchronize(); t=time.perf_counter()
            with torch.inference_mode(): scores[a]=net(inp).squeeze(1).cpu().numpy()
            head_ms[a].append((time.perf_counter()-t)*1000)
        admissible,_=router.policy_filter('_root',q['query'])
        allowed=set(admissible)
        assert len(allowed)==len(skills)
        gold={sid_to_row[s] for s in q['skill_ids']}
        for a,s in scores.items():
            ranked=top(s,200)
            scored=[{'urn':urns[int(r)],'score':20000-k} for k,r in enumerate(ranked) if urns[int(r)] in allowed]
            chosen=router.select(scored,k=4,abstain_threshold=0,admissible=allowed,query=q['query'])
            injection=[urn_to_row[c['urn']] for c in chosen]
            v=metric(ranked,injection,gold);vals[a].append(v)
            records.append({'query_id':q['id'],'arm':a,'ranked':[skills[int(r)]['id'] for r in ranked[:10]],'injected':[skills[r]['id'] for r in injection],'metrics':v})
        if j%200==0:log(f'EVAL {j}/{len(dev)}')
    replay=ROOT/'docs/reports/bakeoff/validation/dev-decompose-d0.jsonl.gz'
    rs={r['query_id']:r for r in (json.loads(s) for s in gzip.open(replay,'rt'))}
    reference=[]
    for q in dev:
        r=rs[q['id']]
        ranked=[urn_to_row[u if isinstance(u,str) else u['urn']] for u in r['ranked']]
        inj=[urn_to_row[u] for u in r.get('injected',r.get('injection',[]))]
        reference.append(metric(ranked,inj,{sid_to_row[s] for s in q['skill_ids']}))
    vals['shipped_sparse_replay']=reference
    names=['hit1','recall10','ndcg10_binary','all_gold_injected4']
    summary={a:dict(zip(names,np.asarray(v).mean(0).tolist())) for a,v in vals.items()}
    comparisons={}
    for basearm,newarm in [('flat_mlp','field_mlp'),('flat_uniform','field_uniform'),('field_uniform','field_mlp'),('sparse_field_mlp','field_mlp')]:
        comparisons[newarm+' minus '+basearm]={m:pair_ci(np.asarray(vals[basearm])[:,k],np.asarray(vals[newarm])[:,k]) for k,m in enumerate(names)}
    with gzip.open(OUT/'dev-rankings.jsonl.gz','wt') as f:
        for r in records:f.write(json.dumps(r)+'\n')
    delta=comparisons['field_mlp minus flat_mlp']
    result={'status':'DEV feasibility only, not admission or paper reproduction','metrics':summary,'paired_differences':comparisons,'advance_fixed_gate':delta['recall10']['delta_pp']>=2 and delta['recall10']['ci95_pp'][0]>0 and delta['all_gold_injected4']['delta_pp']>=-1,'timings_seconds':timings,'wall_seconds':time.time()-started,'truncation':truncation,'head_only_gpu_ms_10123_pairs':{a:{'p50':float(np.median(v)),'p95':float(np.quantile(v,.95))} for a,v in head_ms.items()},'training_pairs':len(y),'positives':int(y.sum()),'caveats':['No test-A/test-B or user outcomes.','Per-field encoding uses more aggregate tokens than flat; max1024 may truncate key body evidence.','Conditional on known public train skill bank; semantic near-duplicates and encoder pretraining contamination unverified.','MLP standardization fit only on training pairs; unlabelled negatives may be relevant.','Abstention disabled for five new arms, no NO_SKILL evidence.','Shared policy/select but exact full-bank score channels replace production candidate/scorer; product rollout still requires an adapter.','Head-only GPU timing excludes query embedding, feature construction, network and hook.','Query bootstrap ignores shared-skill clusters and multiple comparisons.','Sparse replay historical and previously studied on this DEV; descriptive reference only.']}
    write('results.json',result);log(json.dumps(result,indent=2))

if __name__=='__main__': main()
