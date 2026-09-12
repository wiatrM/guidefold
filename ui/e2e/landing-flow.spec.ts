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
 // The loader overlay in index.html covers the viewport until the fonts are ready and the
 // hero has committed. axe reads colour against what is actually painted, so anything it
 // scans while the overlay is still up is measured against the overlay, not the page.
 await page.waitForFunction(()=>!document.getElementById('loader'),null,{timeout:10000}).catch(()=>undefined);
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

for(const size of viewports)test('opens on the outcome, then the nine v3 screens in order at '+size.width,async({page})=>{
 await page.setViewportSize(size);
 await page.goto('/');
 // The headline is three `Reveal` line-mask blocks (DESIGN.md 4.1 decision 4): each is its
 // own block box, so the accessible name (backed by the h1's `aria-label`) carries the
 // word-spaces between them while the raw DOM text of adjoining block children does not.
 // `toHaveAccessibleName` reads the same string a screen reader would.
 await expect(page.getByRole('heading',{level:1})).toHaveAccessibleName("Your coding agent doesn't know your team's rules. Now it does.");
 const headings=page.getByRole('heading',{level:2});
 await expect(headings.nth(0)).toHaveText('One place for every rule, wired into every agent.');
 await expect(headings.nth(1)).toHaveText("One team's fix becomes everyone's rule.");
 await expect(headings.nth(2)).toHaveText("Your organisation's brain, reviewed by owners.");
 await expect(headings.nth(3)).toHaveText('Thirty thousand rules. Four reach the agent.');
 await expect(headings.nth(4)).toHaveText('A search server for your rules, next to your Git.');
 const ids=await page.evaluate(()=>[...document.querySelectorAll('main section[id]')].map(node=>node.id));
 expect(ids).toEqual(['hero','why','extraction','portal','how-it-works','under-the-hood','proof','waitlist','questions']);
 await expect(page.locator('#demo')).toHaveCount(1);
 await expect(page.getByText('Open source today.',{exact:true})).toBeVisible();
 await expect(page.getByText('Paid hosting is planned.').first()).toBeVisible();
 expect(await noHorizontalScroll(page)).toBe(true);
 // Wait for the entrance layer to rest before axe: without it, axe catches headings, sublines
 // and bodies still mid-fade (opacity < 1), which reads as a false color-contrast positive on
 // tokens (stone-300, warning-ink, system-ink) that measure 7.98-12.84:1 at rest.
 await settled(page);
 expect(await axeViolations(page)).toEqual([]);
 await page.screenshot({path:`qa/landing-v3/page-${size.width}.png`,fullPage:true});
});

/**
 * The owner's budget for v3, measured on the built page rather than asserted in a document:
 * the whole page under 8.5 viewports at 1440, and no sideways scroll at any of the four
 * widths the spec names.
 */
test('stays under 8.5 viewports at 1440 and never scrolls sideways',async({page})=>{
 await page.setViewportSize({width:1440,height:900});
 await page.goto('/');
 await settled(page);
 const viewportsTall=await page.evaluate(()=>document.documentElement.scrollHeight/window.innerHeight);
 expect(viewportsTall).toBeLessThan(8.5);
 for(const width of [1440,1080,720,390]){
  await page.setViewportSize({width,height:900});
  await page.waitForTimeout(200);
  expect(await noHorizontalScroll(page),`no horizontal overflow at ${width}`).toBe(true);
 }
});

/**
 * The value panel is the owner's answer to "barely visible, looks vibe-coded": one shared
 * component on every block, spanning the block's own column rather than a narrow measure.
 */
test('gives every block one value panel at the block column width',async({page})=>{
 await page.setViewportSize({width:1440,height:900});
 await page.goto('/');
 await settled(page);
 const panels=page.locator('[data-value-panel]');
 await expect(panels).toHaveCount(6);
 const edges=await page.evaluate(()=>[...document.querySelectorAll('main section[id]')]
  .map(section=>{
   // The section is full-bleed; the container inside it is the page's one content box,
   // and that is what every block's copy, panel and screen must share edges with.
   const container=section.querySelector(':scope > div');
   const panel=section.querySelector('[data-value-panel]');
   const heading=section.querySelector('h2');
   return panel&&heading&&container
    ?{id:section.id,
      panel:Math.round(panel.getBoundingClientRect().right),
      heading:Math.round(heading.getBoundingClientRect().right),
      container:Math.round(container.getBoundingClientRect().right)}
    :null;
  }).filter(Boolean));
 for(const edge of edges as {id:string;panel:number;heading:number;container:number}[]){
  expect(edge.panel,`${edge.id} value panel ends at the heading's edge`).toBe(edge.heading);
  // The container's own padding box is wider than its content box by the page gutter.
  expect(edge.container-edge.panel,`${edge.id} value panel sits inside the page gutter`).toBe(72);
 }
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

test('the instruction reader opens from its details and shows the excerpt and its source',async({page})=>{
 await page.goto('/');
 const summary=page.getByText('Read the full rule the agent loaded');
 const reader=page.locator('[data-slot="instruction-reader"]');
 await expect(reader).toBeHidden();
 await summary.click();
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
  // Final review I4: this used to read `stroke-dashoffset` and assert '0px'. The markup
  // pins that attribute at 0 and no rule anywhere moves it (the draw moves
  // `stroke-dasharray`), so the assertion returned '0px' whether or not the scroll sampler
  // had been installed — it could not fail. What must hold under reduced motion is that no
  // sampler ran at all: the track never gets `data-p-ready`, and without it none of the
  // pinned rules apply, so the tier route keeps the full run `2000` from its presentation
  // attribute rather than the `calc(2000 * p) 2000` the pinned rule computes.
  const pReady=await page.locator('#extraction [class*="track"]').evaluate(node=>node.hasAttribute('data-p-ready'));
  expect(pReady,'the reduced-motion path must install no scroll sampler').toBe(false);
  const dasharray=await page.locator('[data-tier-route]').evaluate(node=>getComputedStyle(node).strokeDasharray);
  expect(dasharray,'the tier route must rest at its full run, undrawn').toBe('2000px');
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
 const read=()=>page.evaluate(()=>[...document.querySelectorAll('[class*="film"],[data-beat],[class*="deviceFrame"]')].map(node=>{
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

// Final review I6: the old version selected inside `main` only (so the header, where the
// brand link measured 128x28, was never measured), asserted height alone, and skipped any
// control whose box was missing. It is now the whole document, both dimensions, and a
// missing box on a visible control is a failure.
//
// Two deliberate exclusions, both written out rather than filtered by accident:
//   - inline text links inside a running sentence (`p a`, and the consent sentence's
//     Privacy link) take the line-height of their own text; enlarging them would break the
//     paragraph. WCAG 2.5.8 exempts a target inline in a block of text.
//   - `input[type=checkbox]`: the consent box is 18px, but the whole `label.consent`
//     wrapping it is the tap target (a label toggles its control) and that label carries
//     min-height 44. The label is measured below as part of no selector, so the check is
//     stated here instead.
const inlineTextLinks='p a, [class*="consent"] a';
test('every link and button meets 44px at 390',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await page.goto('/');
 const consent=await page.locator('label[class*="consent"]').boundingBox();
 expect(consent?.height,'the consent label is the checkbox tap target').toBeGreaterThanOrEqual(44);
 const controls=page.locator(`a[href]:not(${inlineTextLinks}), button:not([disabled])`);
 const count=await controls.count();
 expect(count).toBeGreaterThan(10);
 for(let i=0;i<count;i++){
  const control=controls.nth(i);
  if(!await control.isVisible())continue;
  const label=(await control.getAttribute('aria-label'))??(await control.textContent())??'';
  const box=await control.boundingBox();
  expect(box,`visible control ${i} (${label.trim().slice(0,40)}) has no box`).not.toBeNull();
  expect(box!.width,`control ${i} (${label.trim().slice(0,40)}) width`).toBeGreaterThanOrEqual(44);
  expect(box!.height,`control ${i} (${label.trim().slice(0,40)}) height`).toBeGreaterThanOrEqual(44);
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
