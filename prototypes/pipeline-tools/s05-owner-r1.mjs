import { chromium } from '@playwright/test';
import readline from 'node:readline';
const browser = await chromium.launch({headless: true});
const context = await browser.newContext({viewport:{width:1440,height:1100},acceptDownloads:true});
const page = await context.newPage();
const screenshotPath='/home/mike/projects/guidefold/prototypes/pipeline-wireframes/qa/s05-owner-r1.png';
let clickCount=0,typedCount=0;
async function snapshot(){
 await page.screenshot({path:screenshotPath,fullPage:true});
 console.log(JSON.stringify({url:page.url(),clickCount,typedCount,text:await page.locator('body').innerText(),controls:await page.locator('a,button,input,select,textarea').evaluateAll(nodes=>nodes.map(n=>({tag:n.tagName,text:n.innerText||n.getAttribute('aria-label')||'',href:n.getAttribute('href'),type:n.getAttribute('type'),name:n.getAttribute('name'),placeholder:n.getAttribute('placeholder')})))},null,2));
}
await page.goto('http://127.0.0.1:4320/import.html');
await snapshot();
const rl=readline.createInterface({input:process.stdin});
for await(const line of rl){
 try{
 const cmd=JSON.parse(line);
 if(cmd.action==='click'){await page.getByRole(cmd.role||'button',{name:cmd.name,exact:true}).click();clickCount++;}
 else if(cmd.action==='textclick'){await page.getByText(cmd.name,{exact:true}).click();clickCount++;}
 else if(cmd.action==='fill'){await page.getByPlaceholder(cmd.placeholder,{exact:true}).fill(cmd.value);typedCount++;}
 else if(cmd.action==='labelFill'){await page.getByLabel(cmd.label,{exact:true}).fill(cmd.value);typedCount++;}
 else if(cmd.action==='download'){
  const d=page.waitForEvent('download');
  await page.getByRole(cmd.role||'button',{name:cmd.name,exact:true}).click();clickCount++;
  const download=await d;
  console.log(JSON.stringify({download:download.suggestedFilename(),failure:await download.failure()}));
 }else if(cmd.action==='quit'){break;}
 await page.waitForTimeout(150);await snapshot();
 }catch(error){console.log(JSON.stringify({error:String(error)}));}
}
await context.close();await browser.close();
