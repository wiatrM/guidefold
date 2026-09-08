import {test,expect} from '@playwright/test';
import path from 'node:path';
const views=['import','library','map','skill','proposals','usage','organization'];
for(const state of ['empty','loading','partial','error','degraded','restricted'])test('seven routes: '+state,async({page})=>{
 test.setTimeout(90000);
 for(const view of views){
  await page.goto('/'+view+'?state='+state,{waitUntil:'networkidle'});
  await page.locator('main').waitFor();
  if(state!=='loading')await page.locator('main [aria-busy=true]').waitFor({state:'hidden'});
  await page.addScriptTag({path:path.resolve('node_modules/axe-core/axe.min.js')});
  const violations=await page.evaluate(async()=>((await (window as any).axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations).map((v:any)=>({id:v.id,targets:v.nodes.map((n:any)=>n.target)})));
  expect(violations,view+'/'+state).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),view+'/'+state).toBe(true);
  if(state==='restricted'){
   const text=await page.locator('main').innerText();
   expect(text).not.toMatch(/postgres-auth|urn:|88e404561a9f|27 source files/);
   await expect(page.locator('main input,main textarea')).toHaveCount(0);
   expect(await page.title()).not.toContain('Meridian');
  }
  if(state==='loading')await expect(page.locator('main [aria-busy=true]')).toBeVisible();
  if(state==='partial'||state==='degraded'){
   const mutation=page.getByRole('button',{name:/^(Record decision|Export SKILL.md|Simulate Git sync|Simulate import|Save feedback)/});
   for(const button of await mutation.all())await expect(button).toBeDisabled();
  }
 }
});
