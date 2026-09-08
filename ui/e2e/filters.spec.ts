import {test,expect} from '@playwright/test';
import path from 'node:path';
test('unknown URL filter stays visible until the user explicitly replaces or clears it',async({page})=>{
 for(const [key,label] of [['scope','Scope'],['owner','Owner from source'],['layer','Source layer'],['status','Source status']]){
  await page.goto('/library?'+key+'=missing-value');
  const field=page.getByLabel(label,{exact:true});
  await expect(field).toHaveValue('missing-value');
  await expect(field).toHaveAttribute('aria-invalid','true');
  await expect(field.locator('option:checked')).toHaveText('Unavailable: missing-value');
  await expect(page.getByText('Resolve unavailable filters before reading the result count.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Apply filters',exact:true}).click();
  expect(new URL(page.url()).searchParams.get(key)).toBe('missing-value');
  await expect(field).toHaveValue('missing-value');
  await page.addScriptTag({path:path.resolve('node_modules/axe-core/axe.min.js')});
  const violations=await page.evaluate(async()=>((await (window as any).axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations).map((v:any)=>v.id));
  expect(violations).toEqual([]);
  await field.selectOption('');
  await page.getByRole('button',{name:'Apply filters',exact:true}).click();
  expect(new URL(page.url()).searchParams.has(key)).toBe(false);
  await expect(field).not.toHaveAttribute('aria-invalid','true');
  // The unfiltered library now groups by scope, collapsed beyond the first five (IA §4);
  // postgres-auth's scope (atlas.identity.turnstile) sorts past that threshold.
  await page.locator('details').filter({has:page.locator('> summary').filter({hasText:'atlas.identity.turnstile'})}).first().locator('> summary').click();
  await expect(page.getByRole('link',{name:'postgres-auth',exact:true})).toBeVisible();
 }
});
