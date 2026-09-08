from pathlib import Path
import yaml, json, hashlib, subprocess
root=Path(__file__).resolve().parents[2]
base=root/'examples/monorepo'
config=yaml.safe_load((base/'guidefold.yaml').read_text())
skills=[]
for path in sorted(base.rglob('SKILL.md')):
    raw=path.read_text()
    parts=raw.split('---',2)
    if len(parts)<3: continue
    front=yaml.safe_load(parts[1]) or {}
    meta=front.get('metadata',{})
    scope=meta.get('scope','_root')
    name=front['name']
    def values(k): return [v.strip() for v in str(meta.get(k,'')).split(',') if v.strip()]
    skills.append(dict(id=f"urn:skill:meridian:{scope}:{name}",name=name,scope=scope,owner=meta.get('owner',config['nodes'].get(scope,{}).get('owner','Unassigned')),sourceLayer=meta.get('layer','Unclassified'),knowledgeLayer='Unclassified',sourceStatus=meta.get('status','Unspecified'),description=front.get('description',''),body=parts[2].strip(),raw=raw,path=path.relative_to(base).as_posix(),revision=hashlib.sha256(raw.encode()).hexdigest(),bytes=len(raw.encode()),requires=values('requires'),refines=values('refines'),references=values('references')))
data=dict(fixture=True,label='Meridian fixture',repo='monorepo',org='meridian',commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),sources='examples/monorepo',nodes=[dict(id=k,**v) for k,v in config['nodes'].items()],skills=skills)
out=root/'prototypes/pipeline-wireframes/fixture.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'skills':len(skills),'nodes':len(config['nodes']),'bytes':sum(s['bytes'] for s in skills),'commit':data['commit']}))
