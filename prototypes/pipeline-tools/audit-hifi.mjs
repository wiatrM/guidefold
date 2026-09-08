import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
const origin=process.env.ORIGIN||'http://127.0.0.1:4330';
const out=path.resolve(process.env.OUT||'../pipeline-hifi/qa');
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch();
const allViews=['import','library','map','skill','proposals','usage','organization'];
const views=process.env.VIEWS?process.env.VIEWS.split(','):allViews;
if(views.some(v=>!allViews.includes(v)))throw Error('Unknown view');
let previous={records:[],states:[]};if(process.env.VIEWS)previous=JSON.parse(await fs.readFile(path.join(out,'report.json'),'utf8'));
const records=[],strings=new Set();
for(const width of [1280,820,390]){
 const context=await browser.newContext({viewport:{width,height:720},reducedMotion:'reduce'});
 const page=await context.newPage();
 for(const view of views){
  const errors=[];const onError=e=>errors.push(e.message);page.on('pageerror',onError);
  await page.goto(origin+'/'+view,{waitUntil:'networkidle'});
  await page.locator('main').waitFor();
  await page.locator('main [aria-busy=true]').waitFor({state:'hidden'});
  await page.evaluate(()=>document.fonts.ready);
  await page.screenshot({path:path.join(out,view+'-'+width+'.png')});
  await page.screenshot({path:path.join(out,view+'-'+width+'-full.png'),fullPage:true});
  const dimensions=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,viewport:innerWidth}));
  for(const s of await page.locator('button,a,label,summary,h1,h2,h3,[role="status"],[role="alert"]').allTextContents())if(s.trim())strings.add(s.trim());
  await page.addScriptTag({path:path.resolve('node_modules/axe-core/axe.min.js')});
  const audit=await page.evaluate(async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));
  records.push({view,width,errors,dimensions,violations:audit.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))});
  page.off('pageerror',onError);
 }
 await context.close();
}
const page=await browser.newPage({viewport:{width:1280,height:720}});
const states=[];
for(const view of views)for(const state of ['empty','loading','partial','error','degraded','restricted']){
 await page.goto(origin+'/'+view+'?state='+state,{waitUntil:'networkidle'});
 if(['partial','degraded'].includes(state))await page.locator('main [aria-busy=true]').waitFor({state:'hidden'});
 const body=await page.locator('body').innerText();
 states.push({view,state,heading:await page.locator('h1').innerText(),bodyLength:body.length,privateData:state==='restricted'&&/postgres-auth|88e404|urn:meridian/.test(body),mutationsEnabled:await page.locator('button').evaluateAll(bs=>bs.filter(b=>!b.disabled).map(b=>b.textContent))});
 for(const s of await page.locator('button,a,label,summary,h1,h2,h3,[role="status"],[role="alert"]').allTextContents())if(s.trim())strings.add(s.trim());
}
await page.goto(origin+'/proposals',{waitUntil:'networkidle'});
await page.locator('main [aria-busy=true]').waitFor({state:'hidden'});
await page.locator('[data-brand]').count().then(async n=>{if(n)await page.locator('[data-brand]').evaluateAll(ns=>ns.forEach(n=>n.style.visibility='hidden'))});
await page.addStyleTag({content:'[class*="brand"], [class*="Brand"] { visibility: hidden !important; }'});
await page.screenshot({path:path.join(out,'owner-unbranded.png')});
await browser.close();
const mergedRecords=[...previous.records.filter(r=>!views.includes(r.view)),...records];
const mergedStates=[...previous.states.filter(r=>!views.includes(r.view)),...states];
for(const r of mergedRecords)r.screenshotCapturedAt=(await fs.stat(path.join(out,r.view+'-'+r.width+'.png'))).mtime.toISOString();
await fs.writeFile(path.join(out,'report.json'),JSON.stringify({generatedAt:new Date().toISOString(),fixture:'Meridian fixture',origin,records:mergedRecords,states:mergedStates},null,2));
await fs.writeFile(path.join(out,'ui-strings.json'),JSON.stringify([...strings].sort(),null,2));
console.log(JSON.stringify({captures:records.length,states:states.length,consoleErrors:records.reduce((n,r)=>n+r.errors.length,0),overflows:records.filter(r=>r.dimensions.scroll>r.width).map(r=>({view:r.view,width:r.width,scroll:r.dimensions.scroll})),violations:records.filter(r=>r.violations.length).map(r=>({view:r.view,width:r.width,violations:r.violations})),privacyLeaks:states.filter(x=>x.privateData)},null,2));
