import {test,expect} from '@playwright/test';
import {stubApi,usageReport,query,axeViolations} from './stub';
test('Spectrum pie renders measured geometry and all reported verdicts',async({page})=>{
 const state=await stubApi(page);
 const data=usageReport('ready',state);
 await page.route(/\/api\/v1\/orgs\/[^/]+\/repos\/[^/]+\/usage(?:\?|$)/,route=>route.fulfill({json:{...data,totals:{...data.totals,feedback:{helped:12,hindered:4,mixed:2,not_applicable:0,unknown:1,n:19}}}}));
 await page.goto('/usage'+query());
 const chart=page.getByRole('img',{name:/Feedback verdicts out of 19 assessments/});
 await expect(chart).toBeVisible();
 await expect(chart.locator('.recharts-pie-sector')).toHaveCount(4);
 await expect(page.getByText('19 assessments; no rate is reported below 20.')).toBeVisible();
 const svg=chart.locator('.recharts-surface');
 expect((await svg.boundingBox())!.height).toBeGreaterThan(200);
 await chart.scrollIntoViewIfNeeded();
 expect(await axeViolations(page)).toEqual([]);
 await page.screenshot({path:'qa/spectrum-feedback-pie.png'});
});
