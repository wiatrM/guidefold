const {chromium}=require('../pipeline-tools/node_modules/@playwright/test');
const fs=require('fs');
(async()=>{
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({acceptDownloads:true});
const page=await context.newPage();
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const base='http://127.0.0.1:4320/';
await page.goto(base+'import.html');
await page.getByRole('button',{name:'Continue with selected provider (fixture)'}).click();
await page.getByRole('button',{name:'Create meridian (fixture)'}).click();
await page.getByRole('button',{name:'Simulate import',exact:true}).click();
await page.getByRole('link',{name:'Open Map',exact:true}).click();
if(!page.url().includes('map.html'))throw Error('Import → Map failed');
await page.goto(base+'library.html?org=meridian&repo=monorepo');
await page.getByLabel('Search name, description or path').fill('postgres-auth');
await page.getByRole('button',{name:'Apply filters'}).click();
await page.getByRole('link',{name:'postgres-auth',exact:true}).click();
await page.getByRole('link',{name:'Source & scope',exact:true}).click();
if(!await page.getByText('0f506e5c5bd354754b4ab4244c6992d2819e5266dc10717b97eef693442b214b',{exact:true}).count())throw Error('Missing source digest');
await page.getByRole('link',{name:'← Back to Library',exact:true}).click();
if(!page.url().includes('q=postgres-auth'))throw Error('Filters lost');
await page.goto(base+'proposals.html?org=meridian&repo=monorepo');
await page.getByLabel('Approve for export — prepare the candidate file').check();
await page.getByLabel('Reason for this decision').fill('Local test: exact source and scope reviewed.');
await page.getByRole('button',{name:'Record decision (local)'}).click();
const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'Export SKILL.md',exact:true}).click()]);
const text=fs.readFileSync(await download.path(),'utf8');
const fixture=JSON.parse(fs.readFileSync(__dirname+'/fixture.json','utf8'));if(text!==fixture.skills.find(s=>s.name==='postgres-auth').raw)throw Error('Export differs from exact source bytes');
await page.getByRole('link',{name:'Inspect source and scope',exact:true}).click();
await page.getByRole('link',{name:'← Back to Proposals',exact:true}).click();
await page.getByRole('button',{name:'Simulate Git sync',exact:true}).click();
if(!await page.getByText('Published (fixture)',{exact:true}).count())throw Error('Publication step failed');
for(const view of ['import','library','map','skill','proposals','usage','organization']){
for(const state of ['empty','loading','partial','error','degraded','restricted']){
await page.goto(`${base}${view}.html?org=meridian&repo=monorepo&state=${state}`);
if(state==='restricted'){
if(await page.locator('main').innerText().then(s=>s.includes('postgres-auth')))throw Error(`Leaked restricted data ${view}`);
if(await page.locator('main button:not(:disabled)').count())throw Error(`Restricted mutation ${view}`);
}
}
}
await page.goto(base+'map.html?tab=scopes');
if(!await page.getByText('_index (unmapped scope)',{exact:false}).count())throw Error('Unmapped scope absent');
for(const view of ['import','library','map','skill','proposals','usage','organization']){
await page.setViewportSize({width:390,height:844});await page.goto(base+view+'.html');
const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
if(overflow)errors.push('Mobile document overflow: '+view);
}
// IA R1 regression: edit body only while full-file digest and export remain exact.
await page.evaluate(()=>sessionStorage.clear());
await page.goto(base+'proposals.html?org=meridian&repo=monorepo');
await page.getByLabel('Edit candidate — return to a local draft').check();
await page.getByLabel('Reason for this decision').fill('Regression test: edit only body.');
await page.getByRole('button',{name:'Record decision (local)'}).click();
const source=fixture.skills.find(s=>s.name==='postgres-auth');
const prefix=source.raw.slice(0,source.raw.indexOf(source.body));
const bodyEditor=page.getByLabel('Candidate body · local operator edit');
if((await bodyEditor.inputValue()).includes('metadata:\n'))throw Error('Editor exposes frontmatter');
const firstSourceLine=source.body.split('\n')[0];
const editedBody=(await bodyEditor.inputValue()).replace(firstSourceLine,firstSourceLine+' (local review)')+'\nLocal fixture review note.\n';
await bodyEditor.fill(editedBody);
await page.getByRole('button',{name:'Save local draft'}).click();
const expectedCandidate=prefix+editedBody;
const visibleDiff=await page.getByLabel('Source to candidate line diff',{exact:true}).innerText();
if(!visibleDiff.includes('-'+firstSourceLine)||!visibleDiff.includes('+'+firstSourceLine+' (local review)'))throw Error('Edited body has no accurate added/removed line diff');
if(await page.getByLabel('Original source text',{exact:true}).isVisible()||await page.getByLabel('Candidate source text',{exact:true}).isVisible())throw Error('Full source texts are not collapsed for review');
if(await page.getByLabel('Candidate source text',{exact:true}).textContent()!==expectedCandidate)throw Error('Body edit changed frontmatter or omitted body');
const expectedDigest=require('crypto').createHash('sha256').update(expectedCandidate).digest('hex');
if(!await page.getByText(expectedDigest,{exact:true}).count())throw Error('Edited candidate digest does not cover full file');
await page.getByLabel('Approve for export — prepare the candidate file').check();
await page.getByLabel('Reason for this decision').fill('Regression test: prepare exact edited body with unchanged metadata.');
await page.getByRole('button',{name:'Record decision (local)'}).click();
await page.goto(base+'proposals.html?org=meridian&repo=monorepo&role=member');
if(!await page.getByRole('button',{name:'Export SKILL.md',exact:true}).isDisabled())throw Error('Member can export');
await page.goto(base+'proposals.html?org=meridian&repo=monorepo');
const [editedDownload]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'Export SKILL.md',exact:true}).click()]);
if(fs.readFileSync(await editedDownload.path(),'utf8')!==expectedCandidate)throw Error('Edited export is not complete exact file');

// IA R1 regression: Map axis survives relationship links and a second Skill.
const oncall=fixture.skills.find(s=>s.name==='turnstile-oncall-runbook');
await page.goto(base+'map.html?org=meridian&repo=monorepo&tab=scopes&skill='+encodeURIComponent(oncall.id));
await page.locator('aside').getByRole('link',{name:'postgres-auth',exact:true}).click();
await page.getByRole('link',{name:'Dependencies',exact:true}).click();
await page.getByRole('link',{name:'rbac-policies',exact:true}).click();
await page.getByRole('link',{name:'← Back to Map',exact:true}).click();
if(new URL(page.url()).searchParams.get('tab')!=='scopes')throw Error('Dependency navigation lost Map scope axis');

// IA R1 regression: member can read and leave feedback, but cannot mutate owner flows.
await page.evaluate(()=>sessionStorage.clear());
await page.goto(base+'library.html?org=meridian&repo=monorepo&role=member&q=postgres-auth');
await page.getByRole('link',{name:'postgres-auth',exact:true}).click();
if(new URL(page.url()).searchParams.get('role')!=='member')throw Error('Member scenario lost in navigation');
if(!await page.locator('.context').first().innerText().then(t=>t.includes('Fixture operator: member')))throw Error('Wrong role displayed');
await page.getByRole('link',{name:'Feedback',exact:true}).click();
await page.getByLabel('Review note and reason').fill('Member fixture feedback with a stated reason.');
await page.getByRole('button',{name:'Save local note',exact:true}).click();
await page.reload();
if(await page.getByLabel('Review note and reason').inputValue()!=='Member fixture feedback with a stated reason.')throw Error('Member feedback was not saved');
for(const [view,query,button] of [['import','step=preview','Simulate import'],['proposals','','Record decision (local)'],['organization','tab=members','Simulate member invitation'],['organization','tab=integrations','Simulate connection check']]){
await page.goto(base+view+'.html?org=meridian&repo=monorepo&role=member&'+query);
if(!await page.getByRole('button',{name:button,exact:true}).isDisabled())throw Error('Member can mutate '+view);
}
await page.getByText('Local token lifecycle exercise',{exact:true}).click();
if(!await page.getByRole('button',{name:'Simulate token creation',exact:true}).isDisabled())throw Error('Member can create token scenario');

// IA R1 regression: all partial views expose the same real QA subset and omissions.
let deliveryPaths;
for(const partialView of ['import','library','map']){
await page.goto(base+partialView+'.html?org=meridian&repo=monorepo&state=partial&step=result');
if(!await page.getByText('Identical subset across Import, Library and Map: 8/27 skills.',{exact:false}).count())throw Error('Partial subset inconsistent in '+partialView);
const delivered=await page.getByText('Delivered source paths (8)',{exact:true}).locator('..').locator('li code').allTextContents();
const omitted=await page.getByText('Omitted source paths (19)',{exact:true}).locator('..').locator('li code').allTextContents();
if(delivered.length!==8||omitted.length!==19||new Set([...delivered,...omitted]).size!==27)throw Error('Invalid partial manifest in '+partialView);
if(deliveryPaths&&deliveryPaths!==delivered.join('\n'))throw Error('Different delivered paths in '+partialView);
deliveryPaths=delivered.join('\n');
if(partialView==='import'&&await page.getByText('Parsed · ready to browse',{exact:true}).count())throw Error('Partial import falsely reports ready');
}
await page.goto(base+'organization.html?org=meridian&repo=monorepo&tab=integrations');
if(!await page.getByText('Unknown · no adapter configuration',{exact:true}).count())throw Error('Installation scope is not explicitly Unknown');

if(errors.length)throw Error(errors.join('\n'));
console.log('PASS: import, source/filter return, proposal/export/Git simulation, 42 scenario views, unmapped scope, mobile width, body-only edits, Map axis continuity, member permissions, line diff, consistent partial manifests and Unknown installation scope.');
await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});




