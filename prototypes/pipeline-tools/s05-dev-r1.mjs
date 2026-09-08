import { chromium } from '@playwright/test';
import readline from 'node:readline';
const browser = await chromium.launch({headless:true});
const context = await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
const page = await context.newPage();
const out='/home/mike/projects/guidefold/prototypes/pipeline-wireframes/qa/s05-dev-r1';
const log=[];
page.on('download',async d=>{const entry={event:'download',suggestedFilename:d.suggestedFilename()}; log.push(entry); console.log(JSON.stringify(entry)); await d.path();});
async function snapshot(){
  await page.screenshot({path:out+'.png',fullPage:true});
  const view=await page.locator('body').innerText();
  const controls=await page.locator('a,button,input,select,textarea,[role="button"],[role="radio"]').evaluateAll(es=>es.filter(e=>e.getClientRects().length).map(e=>({tag:e.tagName,role:e.getAttribute('role'),text:e.innerText||e.getAttribute('aria-label')||'',type:e.getAttribute('type'),name:e.getAttribute('name'),value:e.value,placeholder:e.getAttribute('placeholder'),checked:e.checked,disabled:e.disabled,href:e.tagName==='A'?e.getAttribute('href'):undefined})));
  console.log(JSON.stringify({url:page.url(),view,controls}));
}
await page.goto('http://127.0.0.1:4320/import.html');
await snapshot();
const rl=readline.createInterface({input:process.stdin,crlfDelay:Infinity});
for await(const line of rl){
  try{
    const c=JSON.parse(line); log.push(c);
    if(c.action==='click') await page.getByRole(c.role,{name:c.name,exact:c.exact??true}).nth(c.nth??0).click();
    if(c.action==='fill') await page.getByRole(c.role||'textbox',{name:c.name,exact:c.exact??true}).nth(c.nth??0).fill(c.value);
    if(c.action==='check') await page.getByRole(c.role||'radio',{name:c.name,exact:c.exact??true}).nth(c.nth??0).check();
    if(c.action==='select') await page.getByRole('combobox',{name:c.name,exact:c.exact??true}).selectOption({label:c.value});
    if(c.action==='back') await page.goBack();
    if(c.action==='inspect') console.log(await page.locator('body').ariaSnapshot());
    if(c.action==='finish') {await import('node:fs/promises').then(fs=>fs.writeFile(out+'.json',JSON.stringify({actions:log,report:c.report},null,2))); await browser.close(); process.exit(0);}
    await snapshot();
  }catch(e){console.log(JSON.stringify({error:e.message}));}
}
