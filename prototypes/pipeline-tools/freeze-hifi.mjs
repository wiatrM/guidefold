import {chromium} from '@playwright/test';import fs from 'node:fs/promises';import path from 'node:path';import {createHash} from 'node:crypto';
const root=path.resolve('../pipeline-hifi'),out=path.join(root,'qa/baseline');await fs.mkdir(out,{recursive:true});
try { await fs.access(path.join(out,'manifest.json')); throw Error('Baseline already frozen; refusing to overwrite independent evidence.'); } catch(error) { if(error.code!=='ENOENT') throw error; }
const names=['ActionButton','BrandMark','Panel','StateBadge','RouteState','Tabs','ProvenanceTrail','ScopeTree','DataTable','SkillDiff','MetricRow','Urn','SkillContent','Field'];
const b=await chromium.launch(),records=[];
for(const width of [1280,820,390]){
 const p=await b.newPage({viewport:{width,height:720},reducedMotion:'reduce'});await p.goto('http://127.0.0.1:4330/__components',{waitUntil:'networkidle'});await p.locator('[data-component=Field]').waitFor();await p.evaluate(()=>document.fonts.ready);
 for(const name of names){const target=p.locator('[data-component='+name+']');await target.scrollIntoViewIfNeeded();const file=name+'-'+width+'.png';await target.screenshot({path:path.join(out,file),animations:'disabled'});records.push({name,width,file,sha256:createHash('sha256').update(await fs.readFile(path.join(out,file))).digest('hex')});}
 await p.close();
}
await b.close();
const sources={};async function walk(dir){for(const e of await fs.readdir(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())await walk(p);else sources[path.relative(root,p)]=createHash('sha256').update(await fs.readFile(p)).digest('hex');}}
await walk(path.join(root,'src'));await walk(path.join(root,'public'));
await fs.writeFile(path.join(out,'manifest.json'),JSON.stringify({capturedAt:new Date().toISOString(),fixture:'Meridian fixture',purpose:'Independent hifi gallery before component extraction. Do not overwrite this baseline to accept UI changes.',sourceHashes:sources,records},null,2));console.log(JSON.stringify({baselineCaptures:records.length,sourceFiles:Object.keys(sources).length}));
