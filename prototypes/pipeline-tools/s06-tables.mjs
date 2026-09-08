import {chromium,expect} from '@playwright/test';import fs from 'node:fs/promises';
const b=await chromium.launch(),results=[];
for(const width of [390,820,1280]){
 const p=await b.newPage({viewport:{width,height:720}});
 for(const view of ['library','organization','usage']){
  await p.goto('http://127.0.0.1:4330/'+view,{waitUntil:'networkidle'});
  await p.locator('main [aria-busy=true]').waitFor({state:'hidden'});
  const table=p.locator('div[role="region"][tabindex="0"]').filter({has:p.locator('table')}).first();
  await expect(table.locator('tbody tr').first()).toBeVisible();await expect(table.locator('table')).toHaveCSS('min-width','640px');
  await table.scrollIntoViewIfNeeded();await table.focus();
  const before=await table.evaluate(e=>({scroll:e.scrollLeft,client:e.clientWidth,width:e.scrollWidth}));
  if(width<=820&&before.width<=before.client)throw Error('Expected narrow table overflow is missing');
  if(before.width>before.client){await p.keyboard.press('ArrowRight');await expect.poll(()=>table.evaluate(e=>e.scrollLeft)).toBeGreaterThan(before.scroll);}
  if(view==='library'){const summary=p.locator('summary').filter({hasText:'Source details'}).first();const box=await summary.boundingBox();if(!box||box.width<100)throw Error('Unreadable source disclosure');}
  const overflow=await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth);if(overflow)throw Error('Page overflow');
  await p.screenshot({path:'../pipeline-hifi/qa/table-'+view+'-'+width+'.png'});
  results.push({view,width,table:before,scrollAfter:await table.evaluate(e=>e.scrollLeft),keyboardScroll:before.width>before.client?'verified':'not needed',pageOverflow:overflow});
 }
 await p.close();
}
await b.close();await fs.writeFile('../pipeline-hifi/qa/s06-tables.json',JSON.stringify({date:new Date().toISOString(),results},null,2));console.log(JSON.stringify({tables:results.length,passed:true}));
