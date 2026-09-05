const {chromium}=require("playwright");
const fs=require("node:fs");
const path=require("node:path");
const {pathToFileURL}=require("node:url");
(async()=>{
 const root=__dirname;
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE_PATH});
 const context=await browser.newContext({viewport:{width:1440,height:1100}});
 const page=await context.newPage();const errors=[];const requests=[];
 page.on("pageerror",e=>errors.push(e.message));page.on("request",r=>{if(/^https?:/.test(r.url()))requests.push(r.url())});
 await page.goto(pathToFileURL(path.join(root,"sciezka-nauki.html")).href);
 await page.getByText("Gotowe. Postęp zapisuje się lokalnie po każdej zmianie.").waitFor();
 await page.screenshot({path:path.join(root,"tracker-desktop.png"),fullPage:false});
 const widths=[];
 for(const width of [1440,768,390,320]){
   await page.setViewportSize({width,height:1000});
   for(const view of ["tracker","starter","library"]){
     await page.locator('[data-view="'+view+'"]').click();
     if(view==="library") await page.locator("#reading-budget summary").click();
     const overflow=await page.evaluate(()=>({doc:document.documentElement.scrollWidth,viewport:window.innerWidth}));
     if(overflow.doc>overflow.viewport+1)throw new Error("Overflow "+JSON.stringify({width,view,overflow}));
     widths.push({width,view,overflow:false});
     if(view==="library") await page.locator("#reading-budget summary").click();
   }
 }
 await page.setViewportSize({width:390,height:844});
 await page.locator('[data-view="tracker"]').click();
 await page.screenshot({path:path.join(root,"tracker-mobile.png"),fullPage:false});
 await page.locator('[data-view="starter"]').click();
 await page.screenshot({path:path.join(root,"tracker-starter-mobile.png"),fullPage:false});
 await page.setViewportSize({width:1440,height:1100});
 await page.locator('[data-view="tracker"]').click();
 const summary=page.locator("#stage1 > summary");
 await summary.focus();const before=await page.locator("#stage1").getAttribute("open");
 await page.keyboard.press("Enter");
 if(await page.locator("#stage1").getAttribute("open")===before)throw new Error("Keyboard summary does not toggle");
 await page.keyboard.press("Enter");
 await page.locator("#stage1-jsonl").focus();await page.keyboard.press("Space");
 if(!await page.locator("#stage1-jsonl").isChecked())throw new Error("Keyboard checkbox failed");
 const unlabelled=await page.locator("#stages input,#stages select,#stages textarea").evaluateAll(nodes=>nodes.filter(n=>!n.labels?.length).map(n=>n.id));
 if(unlabelled.length)throw new Error("Unlabelled "+unlabelled);
 if(errors.length||requests.length)throw new Error(JSON.stringify({errors,requests}));
 const receipt={passed:true,viewports:widths,keyboard_summary:true,keyboard_checkbox:true,all_fields_labelled:true,page_errors:errors,external_requests:requests};
 fs.writeFileSync(path.join(root,"tracker-layout-qa.json"),JSON.stringify(receipt,null,2)+"\n");
 console.log(JSON.stringify(receipt));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
