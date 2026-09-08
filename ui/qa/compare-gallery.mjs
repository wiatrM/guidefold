import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';import path from 'node:path';import {fileURLToPath} from 'node:url';import {createHash} from 'node:crypto';import {PNG} from 'pngjs';import pixelmatch from 'pixelmatch';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const baseline=path.resolve(root,'../prototypes/pipeline-hifi/qa/baseline'),hifi=path.resolve(root,'../prototypes/pipeline-hifi');
const manifest=JSON.parse(await fs.readFile(path.join(baseline,'manifest.json'),'utf8'));
for(const [name,expected] of Object.entries(manifest.sourceHashes)){
 const actual=createHash('sha256').update(await fs.readFile(path.join(hifi,name))).digest('hex');
 if(actual!==expected)throw Error('Frozen hifi source changed: '+name);
}
const out=path.join(root,'qa/gallery');await fs.mkdir(out,{recursive:true});
const b=await chromium.launch();const records=[];
for(const width of [1280,820,390]){
 const p=await b.newPage({viewport:{width,height:720},reducedMotion:'reduce'});
 await p.goto('http://127.0.0.1:4331/__components',{waitUntil:'networkidle'});
 await p.locator('[data-component=Field]').waitFor();await p.evaluate(()=>document.fonts.ready);
 for(const entry of manifest.records.filter(r=>r.width===width)){
  const target=p.locator('[data-component='+entry.name+']');await target.scrollIntoViewIfNeeded();
  const actualPath=path.join(out,entry.file);await target.screenshot({path:actualPath,animations:'disabled'});
  const expectedBytes=await fs.readFile(path.join(baseline,entry.file));
  if(createHash('sha256').update(expectedBytes).digest('hex')!==entry.sha256)throw Error('Baseline image changed: '+entry.file);
  const expected=PNG.sync.read(expectedBytes),actual=PNG.sync.read(await fs.readFile(actualPath));
  if(expected.width!==actual.width||expected.height!==actual.height){records.push({...entry,pass:false,reason:'dimensions differ',expected:[expected.width,expected.height],actual:[actual.width,actual.height]});continue;}
  const diff=new PNG({width:expected.width,height:expected.height});
  const changed=pixelmatch(expected.data,actual.data,diff.data,expected.width,expected.height,{threshold:0.05,includeAA:true});
  if(changed)await fs.writeFile(path.join(out,'diff-'+entry.file),PNG.sync.write(diff));
  records.push({...entry,changedPixels:changed,totalPixels:expected.width*expected.height,pass:changed===0});
 }
 await p.close();
}
await b.close();
const report={date:new Date().toISOString(),kind:'Independent pre-extraction hifi versus UI component render',baselineCapturedAt:manifest.capturedAt,sourceHashesVerified:true,records,passed:records.length===42&&records.every(r=>r.pass)};
await fs.writeFile(path.join(root,'qa/pixel-diff.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify({cases:records.length,passed:report.passed,differences:records.filter(r=>!r.pass)},null,2));if(!report.passed)process.exitCode=1;
