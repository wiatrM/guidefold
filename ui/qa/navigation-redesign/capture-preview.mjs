import {chromium} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
const out = new URL('./previews/', import.meta.url).pathname;
await mkdir(out, {recursive:true});
const browser=await chromium.launch({headless:true});
for (const width of [1440,390]) {
 for (const [name,url] of [['landing','http://127.0.0.1:4332/'],['gallery','http://127.0.0.1:4331/__components']]) {
  const page=await browser.newPage({viewport:{width,height:1000}});
  page.on('pageerror',e=>console.error(name,e.message));
  await page.goto(url,{waitUntil:'networkidle',timeout:30000});
  await page.locator('[data-slot="database-schema-node"]').first().waitFor({timeout:45000});
  await page.waitForTimeout(1200);
  await page.screenshot({path:`${out}${name}-${width}.png`,fullPage:true});
  await page.screenshot({path:`${out}${name}-viewport-${width}.png`});
  console.log(name,width,await page.title(),await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,view:innerWidth})),await page.locator('[data-slot="database-schema-node"]').count());
  await page.close();
 }
}
await browser.close();
