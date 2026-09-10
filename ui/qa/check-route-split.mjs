import assert from 'node:assert/strict';
import {chromium} from '@playwright/test';
const origin=process.argv[2]??'http://127.0.0.1:4334';
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage();
 const requests=[];
 page.on('request',request=>requests.push(new URL(request.url()).pathname));
 // No production session is needed or exercised by this bundle boundary check.
 await page.route('**/api/**',route=>route.fulfill({status:503,contentType:'application/json',body:'{}'}));
 await page.goto(origin,{waitUntil:'networkidle'});
 await page.getByRole('heading',{name:'Thirty thousand skills. Nobody knows which four the agent should read.'}).waitFor();
 assert(!requests.some(path=>/^\/assets\/app-.*\.js$/.test(path)),'public route loaded the management app');
 assert(!requests.some(path=>path.startsWith('/api/')),'public route requested a management session');
 const publicAssets=requests.filter(path=>path.endsWith('.js'));
 await page.goto(origin+'/import',{waitUntil:'networkidle'});
 await page.getByRole('heading',{name:'Import repository skills',exact:true}).waitFor();
 assert(requests.some(path=>/^\/assets\/app-.*\.js$/.test(path)),'management route did not load its app');
 console.log(JSON.stringify({result:'passed',publicAssets,managementAppLoadedOnImport:true},null,2));
}finally{await browser.close();}
