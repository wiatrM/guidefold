import {test,expect} from '@playwright/test';
import path from 'node:path';
const views=['import','library','map','skill','proposals','usage','organization'];
for(const width of [1280,820,390])test('seven views and gallery axe at '+width,async({page})=>{
 test.setTimeout(120000);await page.setViewportSize({width,height:720});
 for(const view of [...views,'__components']){
  await page.goto('/'+view,{waitUntil:'networkidle'});
  if(view==='__components')await page.locator('[data-component=Field]').waitFor();
  else {await page.locator('main').waitFor();await page.locator('main [aria-busy=true]').waitFor({state:'hidden'});}
  await page.evaluate(()=>document.fonts.ready);
  await page.addScriptTag({path:path.resolve('node_modules/axe-core/axe.min.js')});
  const violations=await page.evaluate(async()=>{const result=await (window as any).axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}});return result.violations.map((v:any)=>({id:v.id,nodes:v.nodes.map((n:any)=>n.target)}));});
  expect(violations,view).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),view).toBe(true);
 }
});
test('revealed proposal content and mobile menu remain accessible',async({page})=>{
 await page.setViewportSize({width:390,height:720});await page.goto('/proposals');
 await page.getByText('Read source body',{exact:true}).click();
 await page.locator('details').filter({has:page.locator('summary').filter({hasText:'Navigate ·'})}).locator('summary').click();
 await page.addScriptTag({path:path.resolve('node_modules/axe-core/axe.min.js')});
 const ids=await page.evaluate(async()=>((await (window as any).axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations).map((v:any)=>v.id));
 expect(ids).toEqual([]);
});
