from pathlib import Path
p=Path('audit-hifi.mjs');s=p.read_text()
s=s.replace("await page.goto(origin+'/'+view,{waitUntil:'networkidle'});","await page.goto(origin+'/'+view,{waitUntil:'networkidle'});\n  await page.locator('main').waitFor();\n  await page.locator('main [aria-busy=true]').waitFor({state:'hidden'});")
s=s.replace("const body=await page.locator('body').innerText();","if(['partial','degraded'].includes(state))await page.locator('main [aria-busy=true]').waitFor({state:'hidden'});\n const body=await page.locator('body').innerText();")
s=s.replace("await page.goto(origin+'/proposals',{waitUntil:'networkidle'});","await page.goto(origin+'/proposals',{waitUntil:'networkidle'});\nawait page.locator('main [aria-busy=true]').waitFor({state:'hidden'});")
p.write_text(s)
p=Path('../pipeline-hifi/src/routes/OnboardingRoutes.tsx');s=p.read_text().replace('No real tokens are available or issued. This exercise stores one boolean scenario value.','No real tokens are available or issued. Use this local exercise to preview token creation and revocation.');p.write_text(s)
