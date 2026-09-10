import {test,expect} from '@playwright/test';
import {axeViolations,noHorizontalScroll} from './stub';

const viewports=[{width:1440,height:900},{width:390,height:844}];

for(const size of viewports)test('research evidence preserves context and negative results at '+size.width,async({page})=>{
 await page.setViewportSize(size);
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/');
 const evidence=page.getByRole('region',{name:'More relevant skills found'});
 await page.getByRole('link',{name:/New research:/}).click();
 await expect(evidence.getByText(/5,400 queries and 26,262 skills/)).toBeVisible();
 await expect(evidence.getByRole('cell',{name:'65.22%',exact:true})).toBeVisible();
 await expect(evidence.getByRole('cell',{name:'47.19%',exact:true})).toBeVisible();
 await expect(evidence.locator('svg.recharts-surface')).toBeVisible();
 const details=evidence.locator('summary');
 await details.focus();
 await page.keyboard.press('Enter');
 await expect(evidence.getByRole('row',{name:/CHAMP 223 -8.67 -5.83/})).toBeVisible();
 await expect(evidence.getByRole('row',{name:/TheoremQA 747 -6.29 -12.18/})).toBeVisible();
 await expect(evidence.getByText(/Neither selected skill matched/)).toBeVisible();
 await expect(evidence.getByText(/not a test of spontaneous tool adoption/)).toBeVisible();
 const response=await page.request.get('/evidence/research-2026-09-10.json');
 expect(response.ok()).toBe(true);
 const record=await response.json();
 expect(record.skills).toBe(26262);
 expect(record.pi.gold_overlap).toBe(0);
 expect(record.verification.retained_ranking_metrics_recomputed).toBe(37800);
 expect(await noHorizontalScroll(page)).toBe(true);
 expect(await axeViolations(page)).toEqual([]);
 await evidence.screenshot({path:`qa/research-update-${size.width}.png`});
});

for(const size of viewports)test('answers why, how and value in order at '+size.width,async({page})=>{
 await page.setViewportSize(size);
 await page.goto('/');
 await expect(page.getByRole('heading',{level:1})).toHaveText('Thirty thousand skills. Nobody knows which four the agent should read.');
 const headings=page.getByRole('heading',{level:2});
 await expect(headings.nth(0)).toHaveText("Let's not make every team rediscover this from scratch");
 await expect(headings.nth(1)).toHaveText('What Guidefold does about it');
 await expect(headings.nth(2)).toHaveText('What your team gets');
 await expect(page.locator('#how-it-works')).toHaveCount(1);
 await expect(page.locator('#waitlist')).toHaveCount(1);
 await expect(page.locator('#demo')).toHaveCount(1);
 await expect(page.getByText('Open source today.',{exact:true})).toBeVisible();
 await expect(page.getByText('Hosting is planned.').first()).toBeVisible();
 expect(await noHorizontalScroll(page)).toBe(true);
 expect(await axeViolations(page)).toEqual([]);
 await page.screenshot({path:`qa/landing-v2-${size.width}.png`,fullPage:true});
});

test('the demo dialog mounts the player only on request and restores focus',async({page})=>{
 await page.route('https://www.youtube-nocookie.com/embed/**',route=>route.fulfill({contentType:'text/html',body:'<title>Stubbed player</title><p>Player boundary test</p>'}));
 await page.goto('/');
 await expect(page.locator('iframe')).toHaveCount(0);
 const play=page.getByRole('button',{name:'Play demo',exact:true});
 await play.focus();
 await page.keyboard.press('Enter');
 const dialog=page.getByRole('dialog');
 await expect(dialog).toBeVisible();
 await expect(dialog.getByTitle('Guidefold product demo')).toBeVisible();
 await expect(dialog.getByRole('button',{name:'Stop video'})).toBeFocused();
 await expect(dialog.getByRole('link',{name:/Watch on YouTube/})).toHaveAttribute('href','https://www.youtube.com/watch?v=e350wBr1W8c');
 expect(await axeViolations(page)).toEqual([]);
 await page.keyboard.press('Escape');
 await expect(dialog).toHaveCount(0);
 await expect(page.locator('iframe')).toHaveCount(0);
 await expect(play).toBeFocused();
});

test('every answer ships closed, and the privacy deep link opens its panel',async({page})=>{
 await page.goto('/');
 for(const question of ['Can I use it today?','What will hosting cost?','Does it work with the tool my team already uses?','How is my email used?'])
  await expect(page.getByRole('button',{name:question})).toHaveAttribute('aria-expanded','false');
 await page.goto('/#privacy');
 await expect(page.getByRole('button',{name:'How is my email used?'})).toHaveAttribute('aria-expanded','true');
 await expect(page.getByText(/Unconfirmed signups are scheduled for deletion after 30 days/)).toBeVisible();
});

test('the instruction reader shows the fixture excerpt and its source',async({page})=>{
 await page.goto('/');
 const reader=page.locator('[data-slot="instruction-reader"]');
 await expect(reader.getByText(/Not a live run/)).toBeVisible();
 await expect(reader.getByText(/Tokens are verified with the key set/)).toBeVisible();
 await expect(reader.getByRole('link',{name:/Open the original file/})).toHaveAttribute('href',/postgres-auth\/SKILL\.md$/);
 await reader.getByRole('tab',{name:'Markdown source'}).click();
 await expect(reader.getByText(/never log the token or the resource payload/).first()).toBeVisible();
});

test.describe('reduced motion',()=>{
 test.use({reducedMotion:'reduce'});
 test('downloads no video and rests on the finished composition',async({page})=>{
  const media:string[]=[];
  page.on('request',request=>{if(/\/assets\/landing\/(hero-flight|intro)\./.test(request.url()))media.push(request.url());});
  await page.goto('/');
  await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
  await page.waitForTimeout(500);
  expect(media).toEqual([]);
  await expect(page.locator('video')).toHaveCount(0);
  const offset=await page.locator('[class*="routeLine"]').evaluate(node=>getComputedStyle(node).strokeDashoffset);
  expect(offset).toBe('0px');
  expect(await axeViolations(page)).toEqual([]);
 });
});

test('scrolling to the footer and back returns every plane to its exact transform',async({page})=>{
 await page.goto('/');
 await page.locator('[data-p-ready]').first().waitFor({state:'attached'});
 await page.waitForTimeout(200);
 const read=()=>page.evaluate(()=>[...document.querySelectorAll('[class*="plane"],[class*="topo"],[class*="survey"]')].map(node=>getComputedStyle(node).transform));
 const before=await read();
 await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
 await page.waitForTimeout(300);
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.waitForTimeout(300);
 expect(await read()).toEqual(before);
});
