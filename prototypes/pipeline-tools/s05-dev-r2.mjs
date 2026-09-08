import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import readline from 'node:readline';
const out='../pipeline-wireframes/qa/s05-dev-r2.json';
const png='../pipeline-wireframes/qa/s05-dev-r2.png';
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1050},acceptDownloads:true});
const page=await context.newPage();
const report={persona:'P2 developer',method:'Niezależna syntetyczna symulacja przy zadaniu, n=1. Wyłącznie renderowany interfejs.',tasks:[],findings:[],thinkaloud:[],counts:{clicks:0,disclosures:0,selects:0,typing:0},completed:false,steps:[]};
let task='A';
await page.goto('http://127.0.0.1:4320/import.html');
async function state(){console.log(JSON.stringify({url:page.url(),text:await page.locator('body').innerText(),controls:await page.locator('a,button,input,select,summary').evaluateAll(es=>es.filter(e=>e.checkVisibility()).map(e=>({tag:e.tagName,text:(e.innerText||e.getAttribute('aria-label')||'').trim(),type:e.type||'',placeholder:e.getAttribute('placeholder')||'',value:e.value||'',href:e.getAttribute('href')||'',options:e.tagName==='SELECT'?[...e.options].map(o=>({label:o.text,value:o.value})):undefined})))},null,2));await page.screenshot({path:png,fullPage:true});}
await state();
// Default replay follows only the actual actions recorded in this simulation's own QA output.
// Use --interactive for a new manual DOM-led session. No application files are read.
const baseline=JSON.parse((await fs.readFile(out,'utf8')).replace(/^\uFEFF/,''));
const recorded=[...baseline.steps,...baseline.thinkaloud.map(n=>({action:'note',...n})),...baseline.tasks.map(result=>({action:'result',result})),...baseline.findings.map(finding=>({action:'finding',finding})),{action:'end'}].map(c=>JSON.stringify(c));
for(const k of ['findingsSummary','countMethod','limitations'])report[k]=baseline[k];
const rl=process.argv.includes('--interactive')?readline.createInterface({input:process.stdin,output:process.stdout,terminal:false}):recorded;
for await (const line of rl){if(!line.trim())continue;try{const c=JSON.parse(line);if(c.task)task=c.task;if(c.action==='note'){report.thinkaloud.push({task,text:c.text});console.log('noted');continue;}if(c.action==='result'){report.tasks.push(c.result);console.log('recorded');continue;}if(c.action==='finding'){report.findings.push(c.finding);console.log('recorded');continue;}if(c.action==='end'){report.counts.ordinaryClicks=report.counts.clicks-report.counts.disclosures;report.counts.disclosureClicks=report.counts.disclosures;report.counts.radioSelections=report.steps.filter(s=>s.role==='radio').length;report.completed=report.tasks.length===3&&report.tasks.every(t=>t.completed);await fs.writeFile(out,JSON.stringify(report,null,2));await page.screenshot({path:png,fullPage:true});console.log('SAVED '+out);await browser.close();break;}if(c.action==='click'){const l=c.role?page.getByRole(c.role,{name:c.name,exact:true}):page.getByText(c.name,{exact:true});await l.nth(c.index||0).click();report.counts.clicks++;if(c.disclosure)report.counts.disclosures++;}if(c.action==='fill'){const l=c.label?page.getByLabel(c.label,{exact:true}):page.getByPlaceholder(c.placeholder,{exact:true});await l.fill(c.value);report.counts.typing++;}if(c.action==='select'){const l=c.label?page.getByLabel(c.label,{exact:true}):page.locator('select').nth(c.index||0);await l.selectOption({label:c.value});report.counts.selects++;}if(c.action==='download'){const pending=page.waitForEvent('download');await page.getByRole(c.role||'button',{name:c.name,exact:true}).click();const d=await pending;report.counts.clicks++;report.download={suggestedFilename:d.suggestedFilename(),downloadCompleted:(await d.failure())===null};}if(c.action==='goto'){await page.goto(c.url);}if(c.action!=='inspect')report.steps.push({task,...c});await state();}catch(e){console.log(JSON.stringify({error:String(e)}));}}

