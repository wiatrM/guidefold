import {test,expect} from '@playwright/test';
import {stubApi,query,chosen,axeViolations,noHorizontalScroll} from './stub';

for(const width of [1440,390])test('Spectrum migration visual packet at '+width,async({page})=>{
 test.setTimeout(180000);
 await page.setViewportSize({width,height:1000});
 await stubApi(page);
 for(const [view,extra] of [['import','&step=result'],['library',''],['map','&tab=repository'],['skill','&skill='+encodeURIComponent(chosen.id)+'&revision='+chosen.revision],['proposals','&proposal=p-1'],['usage',''],['organization','']]){
  await page.goto('/'+view+query(extra));
  await expect(page.locator('#main')).toBeVisible();
  await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
  await expect(page.locator('main h1')).toBeVisible();
  if(view==='usage'){
   const charts=page.locator('.spectrum-charts .recharts-surface');
   await expect(charts.first()).toBeVisible();
   for(const chart of await charts.all()){
    const box=await chart.boundingBox();
    expect(box?.width).toBeGreaterThan(150);
    expect(box?.height).toBeGreaterThan(100);
   }
  }
  await page.screenshot({path:'qa/spectrum-'+view+'-'+width+'.png',fullPage:true});
  if(!await noHorizontalScroll(page))console.log(view,await page.locator('body').evaluate(body=>Array.from(body.querySelectorAll('*')).filter(el=>el.getBoundingClientRect().right>innerWidth+1).slice(0,12).map(el=>({tag:el.tagName,class:el.className,width:el.getBoundingClientRect().width}))));
  expect(await noHorizontalScroll(page),view).toBe(true);
 }
 if(width===1440){
  const collapse=page.getByRole('button',{name:'Collapse sidebar'});
  await collapse.click();
  await expect(page.getByRole('link',{name:'Usage & quality',exact:true})).toBeVisible();
  await page.screenshot({path:'qa/spectrum-folded-navigation.png'});
  expect(await axeViolations(page)).toEqual([]);
 }
});

test('Spectrum search filters only the labelled landing fixture',async({page})=>{
 await page.goto('/');
 const search=page.getByRole('searchbox',{name:'Search example instructions'});
 await search.fill('rbac');
 const demo=page.locator('[data-slot="scope-mini-demo"]');
 await expect(demo.getByText('rbac-policies',{exact:true})).toBeVisible();
 await expect(demo.getByText('postgres-auth',{exact:true})).toHaveCount(0);
 await search.fill('no-such-instruction');
 await expect(demo.getByRole('status')).toContainText('No example instructions match');
 await demo.getByRole('button',{name:'Clear'}).click();
 await expect(demo.getByText('postgres-auth',{exact:true})).toBeVisible();
});
