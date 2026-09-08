/**
 * Component gallery pixel comparison. Run: cd ui && pnpm test:visual (dev server on :4331).
 *
 * The baseline in qa/baseline/ is a capture of this gallery accepted by the owner
 * (2026-09-08, after the sample-value gallery replaced the former fixture one); the frozen
 * hi-fi gallery in prototypes/pipeline-hifi/qa/baseline stays as the pre-extraction record and
 * is no longer the comparison target. `pnpm test:visual:update` re-captures the baseline; do
 * that only to accept a reviewed change, never to make a difference disappear.
 */
import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';import path from 'node:path';import {fileURLToPath} from 'node:url';import {createHash} from 'node:crypto';import {PNG} from 'pngjs';import pixelmatch from 'pixelmatch';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const baseline=path.join(root,'qa/baseline'),out=path.join(root,'qa/gallery');
const update=process.argv.includes('--update');
const components=['ActionButton','BrandMark','Panel','StateBadge','RouteState','Tabs','ProvenanceTrail','ScopeTree','DataTable','SkillDiff','MetricRow','Urn','SkillContent','Field','PyramidChart'];
const widths=[1280,820,390];
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
await fs.mkdir(out,{recursive:true});
const b=await chromium.launch();const captured=[];
for(const width of widths){
 const p=await b.newPage({viewport:{width,height:720},reducedMotion:'reduce'});
 await p.goto('http://127.0.0.1:4331/__components',{waitUntil:'networkidle'});
 await p.locator('[data-component=Field]').waitFor();await p.evaluate(()=>document.fonts.ready);
 for(const name of components){
  const target=p.locator('[data-component='+name+']');await target.scrollIntoViewIfNeeded();
  const file=name+'-'+width+'.png';
  const bytes=await target.screenshot({animations:'disabled'});
  captured.push({name,width,file,bytes});
 }
 await p.close();
}
await b.close();
if(update){
 await fs.rm(baseline,{recursive:true,force:true});await fs.mkdir(baseline,{recursive:true});
 for(const entry of captured)await fs.writeFile(path.join(baseline,entry.file),entry.bytes);
 const manifest={capturedAt:new Date().toISOString(),purpose:'Accepted capture of the ui component gallery (/__components, sample values from src/sample.ts). Regenerate only to accept a reviewed visual change.',records:captured.map(({name,width,file,bytes})=>({name,width,file,sha256:sha(bytes)}))};
 await fs.writeFile(path.join(baseline,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
 console.log(JSON.stringify({updated:captured.length,baseline:path.relative(root,baseline)}));
 process.exit(0);
}
const manifest=JSON.parse(await fs.readFile(path.join(baseline,'manifest.json'),'utf8'));
const records=[];
for(const entry of captured){
 const actualPath=path.join(out,entry.file);await fs.writeFile(actualPath,entry.bytes);
 const record=manifest.records.find(r=>r.file===entry.file);
 if(!record){records.push({...entry,bytes:undefined,pass:false,reason:'no baseline record'});continue;}
 const expectedBytes=await fs.readFile(path.join(baseline,entry.file));
 if(sha(expectedBytes)!==record.sha256)throw Error('Baseline image changed outside --update: '+entry.file);
 const expected=PNG.sync.read(expectedBytes),actual=PNG.sync.read(entry.bytes);
 if(expected.width!==actual.width||expected.height!==actual.height){records.push({name:entry.name,width:entry.width,file:entry.file,pass:false,reason:'dimensions differ',expected:[expected.width,expected.height],actual:[actual.width,actual.height]});continue;}
 const diff=new PNG({width:expected.width,height:expected.height});
 const changed=pixelmatch(expected.data,actual.data,diff.data,expected.width,expected.height,{threshold:0.05,includeAA:true});
 if(changed)await fs.writeFile(path.join(out,'diff-'+entry.file),PNG.sync.write(diff));
 records.push({name:entry.name,width:entry.width,file:entry.file,sha256:record.sha256,changedPixels:changed,totalPixels:expected.width*expected.height,pass:changed===0});
}
const expectedCount=components.length*widths.length;
const report={date:new Date().toISOString(),kind:'ui component gallery versus its accepted baseline (qa/baseline)',baselineCapturedAt:manifest.capturedAt,records,passed:records.length===expectedCount&&records.every(r=>r.pass)};
await fs.writeFile(path.join(root,'qa/pixel-diff.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify({cases:records.length,passed:report.passed,differences:records.filter(r=>!r.pass)},null,2));if(!report.passed)process.exitCode=1;
