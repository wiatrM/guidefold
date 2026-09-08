import {test,expect,type Page,type Locator} from '@playwright/test';
import fs from 'node:fs/promises';
import fixture from '../src/data/fixture.json' with {type:'json'};
async function tabTo(page:Page,target:Locator){
 await expect(target).toBeVisible();
 for(let n=0;n<180;n++){if(await target.evaluate(e=>e===document.activeElement))return;await page.keyboard.press('Tab');}
 throw Error('Target is not reachable through Tab: '+await target.getAttribute('id'));
}
async function enter(page:Page,target:Locator){await tabTo(page,target);await page.keyboard.press('Enter');}
test('owner completes login, import, library and review with keyboard only',async({page})=>{
 await page.goto('/import');
 await enter(page,page.getByRole('button',{name:'Continue with selected provider (fixture)',exact:true}));
 await enter(page,page.getByRole('button',{name:'Create meridian (fixture)',exact:true}));
 await enter(page,page.getByRole('button',{name:'Simulate import',exact:true}));
 await enter(page,page.getByRole('link',{name:'Open Map',exact:true}));
 await enter(page,page.getByRole('navigation',{name:'Main navigation'}).getByRole('link',{name:'Library',exact:true}));
 await tabTo(page,page.getByLabel('Search name, description or path',{exact:true}));await page.keyboard.type('postgres-auth');
 await enter(page,page.getByRole('button',{name:'Apply filters',exact:true}));
 await enter(page,page.getByRole('link',{name:'postgres-auth',exact:true}));
 const source=fixture.skills.find(s=>s.name==='postgres-auth')!;
 const href=await page.getByRole('link',{name:'Open exact source revision',exact:false}).getAttribute('href');
 expect(href).toBe('https://github.com/wiatrM/guidefold/blob/'+fixture.commit+'/examples/monorepo/'+source.path);
 await enter(page,page.getByRole('navigation',{name:'Main navigation'}).getByRole('link',{name:'Proposals',exact:true}));
 await enter(page,page.getByRole('link',{name:'Review decision: approve, edit or reject',exact:true}));
 await tabTo(page,page.locator('input[name=decision][value=approve]'));await page.keyboard.press('Space');
 await tabTo(page,page.getByLabel('Reason for this decision',{exact:true}));await page.keyboard.type('Reviewed exact source, scope and revision in this local keyboard scenario.');
 await enter(page,page.getByRole('button',{name:'Record decision (local)',exact:true}));
 const pending=page.waitForEvent('download');await enter(page,page.getByRole('button',{name:'Export SKILL.md',exact:true}));const download=await pending;
 const file=await download.path();expect(await fs.readFile(file!,'utf8')).toBe(source.raw);
 await expect(page.getByRole('link',{name:'Check usage evidence',exact:true})).toHaveCount(0);
 await enter(page,page.getByRole('button',{name:'Simulate Git sync',exact:true}));
 await enter(page,page.getByRole('link',{name:'Check usage evidence',exact:true}));
 await expect(page.getByLabel('Revision',{exact:true})).toHaveValue(source.revision);
 expect(new URL(page.url()).searchParams.get('scope')).toBe(source.scope);
});
