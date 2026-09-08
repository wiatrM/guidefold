import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
const args=Object.fromEntries(process.argv.slice(2).map(x=>x.split('=')));
const origin=args.origin||'http://127.0.0.1:4320';
const out=path.resolve(args.out||'../pipeline-wireframes/qa');
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch();
const views=['import','library','map','skill','proposals','usage','organization'];
const records=[];
for(const width of [1280,820,390]){
 const context=await browser.newContext({viewport:{width,height:720},reducedMotion:'reduce'});
 const page=await context.newPage();
 for(const view of views){
  const errors=[];
  const onError=e=>errors.push(e.message); page.on('pageerror',onError);
  await page.goto(origin+'/'+view+'.html',{waitUntil:'networkidle'});
  await page.screenshot({path:path.join(out,view+'-'+width+'.png'),fullPage:true});
  const dimensions=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,viewport:innerWidth}));
  await page.addScriptTag({path:path.resolve('node_modules/axe-core/axe.min.js')});
  const audit=await page.evaluate(async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));
  records.push({view,width,errors,dimensions,violations:audit.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))});
  page.off('pageerror',onError);
 }
 await context.close();
}
await browser.close();
await fs.writeFile(path.join(out,'report.json'),JSON.stringify({fixture:'Meridian fixture',origin,records},null,2));
console.log(JSON.stringify({captures:records.length,consoleErrors:records.reduce((n,r)=>n+r.errors.length,0),overflows:records.filter(r=>r.dimensions.scroll>r.width).map(r=>({view:r.view,width:r.width,scroll:r.dimensions.scroll})),violations:records.filter(r=>r.violations.length).map(r=>({view:r.view,width:r.width,violations:r.violations}))},null,2));
