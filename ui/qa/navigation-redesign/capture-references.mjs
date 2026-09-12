import {chromium} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
const out = new URL('./references/', import.meta.url).pathname;
await mkdir(out, {recursive: true});
const browser = await chromium.launch({headless: true});
for (const [name, url] of [['mintlify','https://www.mintlify.com/'],['airuncode','https://airuncode.com/'],['schema-node','https://ui.reactflow.dev/components/database-schema-node']].filter(([name])=>!process.argv[2]||process.argv[2]===name)) {
 const page = await browser.newPage({viewport:{width:1440,height:1000}, deviceScaleFactor:1});
 try {
  await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});
  await page.waitForTimeout(2500);
  await page.screenshot({path:out+name+'.png'});
  console.log(name, await page.title(), await page.locator('body').innerText().then(t=>t.slice(0,1000)));
 } catch(e) { console.log(name,String(e)); }
 await page.close();
}
await browser.close();
