import { createRequire } from "node:module"; const require = createRequire(import.meta.url);
const { chromium } = require('@playwright/test');
const fs = require('node:fs');
const readline = require('node:readline');
(async () => {
  const browser = await chromium.launch({headless:true});
  const context = await browser.newContext({ viewport: {width:1440,height:1000}, acceptDownloads:true });
  const page = await context.newPage();
  const report = {type:'syntetyczne',n:1,participant:'P3 operator dostarczania',run:'s05-operator-r1',events:[]};
  const out = '/home/mike/projects/guidefold/prototypes/pipeline-wireframes/qa/s05-operator-r1.json';
  const save=()=>fs.writeFileSync(out,JSON.stringify(report,null,2));
  await page.goto('http://127.0.0.1:4320/import.html');
  console.log(JSON.stringify({ready:true,url:page.url(),text:await page.locator('body').innerText()}));
  const rl = readline.createInterface({input:process.stdin,output:process.stdout,terminal:false});
  for await (const line of rl) {
    try {
      const cmd=JSON.parse(line); let result;
      if(cmd.op==='read') result={url:page.url(),text:await page.locator('body').innerText()};
      if(cmd.op==='controls') result=await page.locator('a,button,input,select,textarea').evaluateAll(es=>es.map(e=>({tag:e.tagName,text:e.innerText,value:e.value,type:e.type,name:e.name,id:e.id,href:e.getAttribute('href'),placeholder:e.getAttribute('placeholder'),aria:e.getAttribute('aria-label'),disabled:e.disabled})));
      if(cmd.op==='click') { const locator=cmd.role?page.getByRole(cmd.role,{name:cmd.name,exact:cmd.exact!==false}):page.getByText(cmd.text,{exact:cmd.exact!==false}); await locator.click(); await page.waitForTimeout(200); result={url:page.url(),text:await page.locator('body').innerText()}; report.events.push({op:'click',...cmd,url:page.url()}); }
      if(cmd.op==='fill') { const locator=cmd.label?page.getByLabel(cmd.label,{exact:true}):page.getByPlaceholder(cmd.placeholder,{exact:true}); await locator.fill(cmd.value); result={filled:true};report.events.push({...cmd,url:page.url()}); }
      if(cmd.op==='select') { await page.getByLabel(cmd.label,{exact:true}).selectOption(cmd.value); result={selected:true};report.events.push({...cmd,url:page.url()}); }
      if(cmd.op==='screenshot') { const path='/home/mike/projects/guidefold/prototypes/pipeline-wireframes/qa/s05-operator-r1.png'; await page.screenshot({path,fullPage:true});result={path}; }
      if(cmd.op==='download') { const event=page.waitForEvent('download');await page.getByRole(cmd.role||'link',{name:cmd.name,exact:true}).click();const dl=await event;const stream=await dl.createReadStream();let chunks=[];for await (const c of stream) chunks.push(c);const body=Buffer.concat(chunks).toString('utf8');result={filename:dl.suggestedFilename(),bytes:Buffer.byteLength(body),body};report.events.push({op:'download',name:cmd.name,...result,url:page.url()}); }
      if(cmd.op==='record') {Object.assign(report,cmd.data);result={recorded:true};}
      if(cmd.op==='exit') {save();await browser.close();process.exit(0);}
      save();console.log(JSON.stringify({ok:true,result}));
    } catch(error) {console.log(JSON.stringify({ok:false,error:String(error)}));}
  }
})();



