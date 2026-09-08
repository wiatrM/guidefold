#!/usr/bin/env python3
"""Independent CPU QA. Does not import the experiment or expose real query text."""
from pathlib import Path
import json,gzip,hashlib,math,collections,sys,datetime,re
import numpy as np
P=Path(__file__).resolve().parent
ARMS=['A_original','B_metadata','C_metadata_queries']
NAMES=['hit1','recall10','ndcg10','all_gold_selected4']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(name,obj):(P/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def query_gold_only():
    # The review process never prints or uses the real query text.
    out=[]
    for line in (P/'cache/evaluation-queries.jsonl').open():
        row=json.loads(line);out.append((row['id'],set(row['skill_ids'])))
    return out

def cohort():
    m=read(P/'manifest.json');q=query_gold_only()
    assert sha(P/'cache/evaluation-queries.jsonl')==m['evaluation_queries_sha256']
    assert [x[0] for x in q]==m['query_ids'] and len(q)==len(set(x[0] for x in q))==2048
    assigned=set(m['selected_skill_ids']);strata=collections.defaultdict(list)
    for i,(qid,g) in enumerate(q):
        assert g
        strata['overall'].append(i)
        strata['any_gold_selected' if g&assigned else 'no_gold_selected'].append(i)
        strata['k='+str(len(g))].append(i)
        if g<=assigned:strata['all_gold_selected'].append(i)
    return m,q,strata

def component_ids(q):
    parent=list(range(len(q)))
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    first={}
    for i,(_,gold) in enumerate(q):
        for sid in sorted(gold):
            if sid in first:
                a,b=find(i),find(first[sid]);parent[max(a,b)]=min(a,b)
            else:first[sid]=i
    return [find(i) for i in range(len(q))]

def groups_for(indices,comp):
    groups=collections.defaultdict(list)
    for i in indices:groups[comp[i]].append(i)
    return list(groups.values())

def group_stats(groups):
    sizes=np.asarray([len(g) for g in groups],dtype=np.int64);n=int(sizes.sum());count=len(sizes)
    return {'queries':n,'components':count,'singleton_components':int((sizes==1).sum()),'minimum_size':int(sizes.min()),'median_size':float(np.median(sizes)),'p95_size':float(np.quantile(sizes,.95)),'maximum_size':int(sizes.max()),'largest_query_fraction':float(sizes.max()/n),'effective_component_count':float(n*n/(sizes@sizes)),'unstable_regime':bool(count<10 or sizes.max()/n>.5)}

def components():
    assert not (P/'results.json').exists() and not(P/'rankings.jsonl.gz').exists()
    m,q,strata=cohort();comp=component_ids(q)
    obj={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before_outcomes':True,'evaluation_query_sha256':sha(P/'cache/evaluation-queries.jsonl'),'strata':{name:group_stats(groups_for(ii,comp)) for name,ii in strata.items()},'query_components':[{'query_id':q[i][0],'component':comp[i]} for i in range(len(q))]}
    write('gold-sharing-components.json',obj)
    print(json.dumps({'component_stats':obj['strata']},indent=2))

def metrics(ranked,selected,gold):
    relevance=[float(sid in gold) for sid in ranked[:10]]
    dcg=math.fsum(g/math.log2(rank+2) for rank,g in enumerate(relevance))
    ideal=math.fsum(1/math.log2(rank+2) for rank in range(min(10,len(gold))))
    return np.array([relevance[0] if relevance else 0.,math.fsum(relevance)/len(gold),dcg/ideal,float(not(gold-set(selected)))])

def generation():
    # This stage is safe before retrieval evaluation: generator sources and outputs only.
    m=read(P/'manifest.json');freeze=read(P/'generation-freeze.json')
    def records(path):return [json.loads(line) for line in path.open()]
    original=records(P/'cache/generator-inputs.jsonl');raw=records(P/'generation-raw.jsonl');side=records(P/'enrichment.jsonl')
    for group in [original,raw,side]:
        assert [r['skill_id'] for r in group]==m['selected_skill_ids']
        assert len(group)==len(set(r['skill_id'] for r in group))==512
    hashes={'enrichment.jsonl':'enrichment_sha256','generation-raw.jsonl':'raw_sha256','cache/generator-inputs.jsonl':'inputs_sha256','run.py':'run_sha256','PROTOCOL.md':'protocol_sha256'}
    for filename,key in hashes.items():assert sha(P/filename)==freeze[key]
    normalize=lambda x:' '.join(x.lower().split())
    rejected_total=collections.Counter();counts=collections.Counter()
    for src,r,out in zip(original,raw,side):
        assert hashlib.sha256(src['source'].encode()).hexdigest()==src['source_sha256']==r['source_sha256']
        text=r['raw'].strip();expected={'intents':[],'queries':[]};rej=collections.Counter();seen=set()
        if text.startswith('```'):
            text=re.sub(r'^```(?:json)?\s*','',text);text=re.sub(r'\s*```$','',text)
        try:
            parsed=json.loads(text)
            if not isinstance(parsed,dict):raise ValueError('non-object')
        except (ValueError,TypeError):
            parsed={};rej['invalid_json']=1
        if not rej:
            for kind,bounds in [('intents',(2,10)),('queries',(5,32))]:
                items=parsed.get(kind,[])
                if not isinstance(items,list):rej['invalid_array']+=1;continue
                for item in items[:3]:
                    if not isinstance(item,dict) or not isinstance(item.get('text'),str) or not isinstance(item.get('evidence'),str):rej['invalid_item']+=1;continue
                    phrase=item['text'].strip();evidence=item['evidence'].strip();key=normalize(phrase)
                    if not(bounds[0]<=len(phrase.split())<=bounds[1] and 4<=len(evidence.split())<=35):rej['word_bounds']+=1;continue
                    if normalize(evidence) not in normalize(src['source']):rej['evidence_not_in_source']+=1;continue
                    if key in seen:rej['duplicate']+=1;continue
                    seen.add(key);expected[kind].append({'text':phrase,'evidence':evidence})
        assert {'skill_id':src['skill_id'],**expected}==out
        assert dict(rej)==r['rejections'];rejected_total.update(rej)
        counts['accepted_intents']+=len(expected['intents']);counts['accepted_queries']+=len(expected['queries'])
        counts['docs_with_intents']+=bool(expected['intents']);counts['docs_with_queries']+=bool(expected['queries'])
        counts['empty_documents']+=not(expected['intents'] or expected['queries'])
        counts['input_tokens']+=r['input_tokens'];counts['output_tokens']+=r['output_tokens'];counts['body_excerpted']+=r['body_excerpted'];counts['cap_hits']+=r['hit_generation_cap']
    for key,value in counts.items():
        if key in freeze:assert value==freeze[key]
    assert dict(rejected_total)==freeze['rejections']
    obj={'status':'passed','checked_documents':512,'all_ids_unique_ordered_and_match_manifest':True,'mechanical_filter_exactly_reproduced':True,'source_hashes_verified':True,'freeze_hashes_verified':True,'counts':dict(counts),'rejections':dict(rejected_total),'generation_freeze_sha256':sha(P/'generation-freeze.json'),'qa_script_sha256':sha(Path(__file__)),'before_retrieval_results':not(P/'results.json').exists()}
    write('generation-independent-qa.json',obj);print(json.dumps(obj,indent=2))

def verify():
    m,q,strata=cohort();qidx={qid:i for i,(qid,_) in enumerate(q)}
    source_hashes_checked=[]
    for filename,expected_hash in m['source_hashes'].items():
        assert sha(Path(filename))==expected_hash,filename
        source_hashes_checked.append(filename)
    result=read(P/'results.json');freeze=read(P/'generation-freeze.json');registered=read(P/'cluster-sensitivity-registration.json');precomponents=read(P/'gold-sharing-components.json')
    assert sha(P/'cluster-sensitivity-protocol.md')==registered['protocol_sha256']
    assert registered['root_run_sha256']==sha(P/'run.py')==freeze['run_sha256']==result['run_sha256']
    assert sha(P/'enrichment.jsonl')==freeze['enrichment_sha256']==result['enrichment_sha256']
    assert sha(P/'rankings.jsonl.gz')==result['ranking_sha256']
    assert sha(P/'generation-raw.jsonl')==freeze['raw_sha256']
    assert sha(P/'cache/generator-inputs.jsonl')==freeze['inputs_sha256']
    vals={arm:np.full((len(q),len(NAMES)),np.nan) for arm in ARMS};seen=set();count=0
    for line in gzip.open(P/'rankings.jsonl.gz','rt'):
        r=json.loads(line);arm=r['arm'];qid=r['query_id'];key=(arm,qid)
        assert arm in ARMS and qid in qidx and key not in seen;seen.add(key);i=qidx[qid]
        assert len(r['ranked'])<=10 and len(r['selected'])<=4
        assert len(set(r['ranked']))==len(r['ranked']) and len(set(r['selected']))==len(r['selected'])
        v=metrics(r['ranked'],r['selected'],q[i][1]);saved=np.array([r['metrics'][k] for k in NAMES]);np.testing.assert_allclose(v,saved,rtol=0,atol=1e-12)
        vals[arm][i]=v;count+=1
    assert count==len(ARMS)*len(q) and all(np.isfinite(v).all() for v in vals.values())
    comparisons=[(ARMS[0],ARMS[1]),(ARMS[0],ARMS[2]),(ARMS[1],ARMS[2])]
    comp=component_ids(q)
    assert [{'query_id':q[i][0],'component':comp[i]} for i in range(len(q))]==precomponents['query_components']
    output={};query_checks=0
    for label,ii in strata.items():
        expected=result['summary'][label];assert expected['n']==len(ii)
        for arm in ARMS:
            np.testing.assert_allclose(vals[arm][ii].mean(0),[expected['arms'][arm][k] for k in NAMES],rtol=0,atol=1e-12)
        groups=groups_for(ii,comp);stats=group_stats(groups);size=np.array([len(g) for g in groups]);output[label]={'component_stats':stats,'contrasts':{}}
        for a,b in comparisons:
            name=b+' minus '+a;d=vals[b]-vals[a];local=d[ii];mean=local.mean(0)
            original=result['paired_differences'][label][name]
            rng=np.random.default_rng(20260906)
            qb=np.asarray([local[rng.integers(0,len(ii),len(ii))].mean(0) for _ in range(2000)])
            query_ci=np.quantile(qb,[.025,.975],axis=0)*100
            component_sums=np.array([d[g].sum(0) for g in groups]);rng=np.random.default_rng(20260907)
            cb=[]
            for _ in range(5000):
                picked=rng.integers(0,len(groups),len(groups));cb.append(component_sums[picked].sum(0)/size[picked].sum())
            cluster_ci=np.quantile(np.asarray(cb),[.025,.975],axis=0)*100
            output[label]['contrasts'][name]={}
            for j,k in enumerate(NAMES):
                o=original[k]
                np.testing.assert_allclose([mean[j]*100,*query_ci[:,j]],[o['delta_pp'],*o['ci95_pp']],rtol=0,atol=1e-10)
                assert int((local[:,j]>0).sum())==o['increases'] and int((local[:,j]<0).sum())==o['decreases'];query_checks+=1
                output[label]['contrasts'][name][k]={'delta_pp':float(mean[j]*100),'query_ci95_pp':query_ci[:,j].tolist(),'cluster_ci95_pp':cluster_ci[:,j].tolist(),'query_ci_excludes_zero':bool(query_ci[0,j]>0 or query_ci[1,j]<0),'cluster_ci_excludes_zero':bool(cluster_ci[0,j]>0 or cluster_ci[1,j]<0),'interval_informative':not stats['unstable_regime']}
    prim=result['paired_differences']['overall']['C_metadata_queries minus A_original'];guard=result['paired_differences']['no_gold_selected']['C_metadata_queries minus A_original']
    gate=bool(prim['recall10']['delta_pp']>0 and prim['recall10']['ci95_pp'][0]>0 and prim['all_gold_selected4']['delta_pp']>=0 and guard['recall10']['delta_pp']>=-.5)
    assert gate==result['advance_to_full_coverage_gate']
    artifacts={'status':'passed','independent_metric_rows':count,'summary_strata':len(strata),'paired_metric_cells_checked':query_checks,'primary_gate_matches':True,'primary_gate_value':gate,'qa_script_sha256':sha(Path(__file__)),'rankings_sha256':sha(P/'rankings.jsonl.gz'),'clustering_preregistered':registered,'source_hashes_checked':source_hashes_checked,'model_weight_hashes_independently_recomputed':False,'model_weight_hash_note':'Original generation freeze records model weight digests; independent QA rechecks data, model config/tokenizer config, script and artifact hashes, not the large weight shards.','cluster_sensitivity':output}
    write('independent-qa.json',artifacts)
    print(json.dumps({'status':'passed','metric_rows':count,'paired_metric_cells_checked':query_checks,'gate':gate,'primary_cluster_sensitivity':output['overall']['contrasts']['C_metadata_queries minus A_original'],'overall_components':output['overall']['component_stats']},indent=2))

if __name__=='__main__':
    {'components':components,'generation':generation,'verify':verify}[sys.argv[1]]()
