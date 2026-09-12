import {test,expect} from '@playwright/test';
import type {Page} from '@playwright/test';
import {axeViolations,noHorizontalScroll} from './stub';

/**
 * Brings the entrance layer to rest instead of sleeping for a fixed 1000 ms before axe.
 * `Reveal` writes `data-reveal-ready="true"` when it installs an element and
 * `data-reveal-entered="true"` when that element's entrance fires (Reveal.tsx); under reduced
 * motion neither attribute is written, so the wait is then vacuously satisfied.
 *
 * axe scans the whole document, not the viewport, so waiting only on what is currently on
 * screen is not enough: a section further down is still at its pre-entrance opacity and axe
 * reports it as a colour-contrast violation on tokens that measure 7.98-12.84:1 at rest. The
 * sweep to the bottom and back therefore fires every `IntersectionObserver` first; entrance
 * flags are never removed once set, so the page is at rest by the time it returns to the top.
 *
 * The last step drains the CSS transitions those flags start. Infinite animations are excluded
 * (they never settle) and both the wait and the drain are capped, so a stalled animation
 * degrades to roughly the old fixed delay instead of failing the test for the wrong reason.
 */
async function settled(page:Page){
 await page.evaluate(async()=>{
  const step=window.innerHeight*0.8;
  for(let y=0;y<document.body.scrollHeight;y+=step){
   window.scrollTo(0,y);
   await new Promise(resolve=>{window.setTimeout(resolve,120);});
  }
  window.scrollTo(0,0);
 });
 await page.waitForFunction(
  ()=>!document.querySelector('[data-reveal-ready="true"]:not([data-reveal-entered="true"])'),
  null,{timeout:15000},
 ).catch(()=>undefined);
 await page.evaluate(async()=>{
  // The entered flag is written from a callback; the transition it starts does not exist as
  // an Animation until the next style recalculation, so collecting getAnimations() in the
  // same turn can return an empty list and let axe read a still-fading element.
  await new Promise(resolve=>{requestAnimationFrame(()=>requestAnimationFrame(resolve));});
  await Promise.race([
   Promise.all(document.getAnimations()
    .filter(animation=>animation.effect?.getComputedTiming().iterations!==Infinity)
    .map(animation=>animation.finished.catch(()=>undefined))),
   new Promise(resolve=>{window.setTimeout(resolve,2000);}),
  ]);
 });
}

const viewports=[{width:1440,height:900},{width:390,height:844}];

for(const size of viewports)test('research evidence preserves context and negative results at '+size.width,async({page})=>{
 await page.setViewportSize(size);
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/');
 const evidence=page.getByRole('region',{name:'Plus 8.53 points of recall over flat.'});
 await page.getByRole('link',{name:'Read the numbers and how we got them'}).click();
 await expect(evidence.getByText(/5,400 queries across 26,262 skills/)).toBeVisible();
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

for(const size of viewports)test('opens on the outcome, then extraction, retrieval and the safety boundary in order at '+size.width,async({page})=>{
 await page.setViewportSize(size);
 await page.goto('/');
 // The headline is set as two `Reveal` line-mask blocks (DESIGN.md 4.1 decision 4): each is
 // its own block box, so the accessible name (backed by the h1's `aria-label`) carries the
 // word-space between them while the raw DOM text of two adjoining block children does not.
 // `toHaveAccessibleName` reads the same string a screen reader would, which is what this
 // assertion is protecting.
 await expect(page.getByRole('heading',{level:1})).toHaveAccessibleName('Your repos are already writing the handbook.');
 const headings=page.getByRole('heading',{level:2});
 await expect(headings.nth(0)).toHaveText("One team's fix becomes everyone's rule.");
 await expect(headings.nth(1)).toHaveText('Thirty thousand rules. Four reach the agent.');
 await expect(headings.nth(2)).toHaveText('Seventy-six harmful rules. Seventy-six refusals.');
 await expect(page.locator('#how-it-works')).toHaveCount(1);
 await expect(page.locator('#waitlist')).toHaveCount(1);
 await expect(page.locator('#demo')).toHaveCount(1);
 await expect(page.getByText('Open source today.',{exact:true})).toBeVisible();
 await expect(page.getByText('Paid hosting is planned.').first()).toBeVisible();
 expect(await noHorizontalScroll(page)).toBe(true);
 // Wait for the entrance layer to rest before axe: without it, axe catches headings, sublines
 // and bodies still mid-fade (opacity < 1), which reads as a false color-contrast positive on
 // tokens (stone-300, warning-ink, system-ink) that measure 7.98-12.84:1 at rest.
 await settled(page);
 expect(await axeViolations(page)).toEqual([]);
 await page.screenshot({path:`qa/landing-v2-${size.width}.png`,fullPage:true});
});

test('the demo dialog mounts the player only on request and restores focus',async({page})=>{
 await page.route('https://www.youtube-nocookie.com/embed/**',route=>route.fulfill({contentType:'text/html',body:'<title>Stubbed player</title><p>Player boundary test</p>'}));
 await page.goto('/');
 // Settle before the dialog opens: the page behind it is what axe scans, and sweeping the
 // scroll with a modal open would be both meaningless and hostile to the focus trap.
 await settled(page);
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
 for(const question of ['Is Guidefold available now?','What will hosting cost?','Which coding tools can I use?','How is my email used?'])
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
  const offset=await page.locator('[data-tier-route]').evaluate(node=>getComputedStyle(node).strokeDashoffset);
  expect(offset).toBe('0px');
  expect(await axeViolations(page)).toEqual([]);
 });
});

test('scrolling to the footer and back returns the film and parallax layers to their exact transform',async({page})=>{
 await page.goto('/');
 await page.locator('[data-p-ready]').first().waitFor({state:'attached'});
 await page.waitForTimeout(200);
 // Rounded to 3 decimals: the matrix serializes with float noise in its least-significant
 // digit between two reads of the same resting value (0.985003 vs 0.985), which is not a
 // reversibility regression. Rounding keeps the assertion meaningful (same transform, not
 // byte-identical serialization) without loosening what "returns to its exact transform" checks.
 const read=()=>page.evaluate(()=>[...document.querySelectorAll('[class*="film"],[data-beat],[class*="proofRail"]')].map(node=>{
  const t=getComputedStyle(node).transform;
  return t==='none'?t:t.replace(/-?\d+\.?\d*/g,n=>Number(n).toFixed(3));
 }));
 const before=await read();
 await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
 await page.waitForTimeout(300);
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.waitForTimeout(300);
 expect(await read()).toEqual(before);
});

test('the extraction chapter pins at 1440 and stacks at 390',async({page})=>{
 await page.setViewportSize({width:1440,height:900});
 await page.goto('/');
 const stage=page.locator('#extraction [class*="stage"]');
 await expect(stage).toHaveCSS('position','sticky');
 for(const beat of ['1','2','3'])await expect(page.locator(`#extraction [data-beat="${beat}"]`)).toBeAttached();
 await page.setViewportSize({width:390,height:844});
 await expect(stage).not.toHaveCSS('position','sticky');
 for(const beat of ['1','2','3'])await expect(page.locator(`#extraction [data-beat="${beat}"]`)).toBeVisible();
 expect(await noHorizontalScroll(page)).toBe(true);
});

test('every control meets 44px at 390',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await page.goto('/');
 const controls=page.locator('main a[href], main button:not([disabled]), main input[type="checkbox"]');
 const count=await controls.count();
 for(let i=0;i<count;i++){
  const box=await controls.nth(i).boundingBox();
  if(!box)continue;
  expect(box.height,`control ${i} height`).toBeGreaterThanOrEqual(44);
 }
});

for(const size of viewports)test('axe is clean with the FAQ open and the dialog open at '+size.width,async({page})=>{
 await page.route('https://www.youtube-nocookie.com/embed/**',route=>route.fulfill({contentType:'text/html',body:'<title>Stubbed player</title><p>Player boundary test</p>'}));
 await page.setViewportSize(size);
 await page.goto('/');
 // Axe must read resting colour and opacity rather than a still-fading element, which would
 // report a transient false positive.
 await settled(page);
 expect(await axeViolations(page)).toEqual([]);
 await page.getByRole('button',{name:'How is my email used?'}).click();
 expect(await axeViolations(page)).toEqual([]);
 await page.getByRole('button',{name:'Play demo',exact:true}).click();
 expect(await axeViolations(page)).toEqual([]);
});
