/**
 * Contrast for the two pinned sections, sampled at pin start, mid and release —
 * not once — because the panel holds across a range of film frames and the
 * worst-case background luminance can differ across that dwell. Reuses the
 * measurement approach in landing-contrast.mjs (hide text, screenshot, sample
 * the exact rectangles it stood in).
 */
import {chromium} from '@playwright/test';
import {PNG} from 'pngjs';

const base = process.env.BASE ?? 'http://127.0.0.1:4331';
const srgb = (c) => {const s = c / 255; return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;};
const lum = (r, g, b) => 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
const ratio = (a, b) => (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);

const browser = await chromium.launch();
const context = await browser.newContext({viewport: {width: 1440, height: 900}, deviceScaleFactor: 1});
const results = [];

for (const id of ['why', 'value']) {
  const page = await context.newPage();
  await page.goto(base, {waitUntil: 'networkidle'});
  await page.waitForFunction(() => document.documentElement.dataset.film === 'on', null, {timeout: 15000}).catch(() => {});
  const track = await page.evaluate((sel) => {
    const el = document.getElementById(sel).parentElement;
    const r = el.getBoundingClientRect();
    return {top: r.top + window.scrollY, height: r.height};
  }, id);
  for (const [tag, frac] of [['start', 0.05], ['mid', 0.5], ['late', 0.9]]) {
    const y = track.top + (track.height - 900) * frac;
    await page.evaluate((v) => window.scrollTo(0, v), Math.max(0, y));
    await page.waitForTimeout(500);
    const {copy, boxes} = await page.evaluate((sel) => {
      const scope = document.getElementById(sel);
      const nodes = [...scope.querySelectorAll('p,li,h1,h2,h3,strong,label,dt,dd')]
        .filter((n) => n.textContent.trim() && getComputedStyle(n).visibility !== 'hidden' && +getComputedStyle(n).opacity > 0.05);
      const top = document.querySelector('header')?.getBoundingClientRect().bottom ?? 0;
      const vis = nodes.map((n) => n.getBoundingClientRect())
        .filter((r) => r.width > 8 && r.height > 8 && r.top > top + 4 && r.bottom < innerHeight - 4)
        .map((r) => ({x: r.x, y: r.y, w: Math.min(r.width, innerWidth - r.x), h: r.height}));
      const p = nodes.find((n) => n.tagName === 'P' || n.tagName === 'LI' || n.tagName === 'DD') ?? nodes[0];
      return {copy: p ? getComputedStyle(p).color : null, boxes: vis};
    }, id);
    await page.addStyleTag({content: 'main p,main li,main h1,main h2,main h3,main span,main strong,main a,main button,main img,main video,main svg,main input,main label,main code,main dt,main dd,main summary,main figcaption,main time,main em{visibility:hidden !important}'});
    await page.waitForTimeout(150);
    const buf = await page.screenshot({clip: {x: 0, y: 0, width: 1440, height: 900}});
    const png = PNG.sync.read(buf);
    let max = 0, sum = 0, n = 0;
    for (const b of boxes) {
      for (let py = Math.floor(b.y); py < Math.min(899, b.y + b.h); py += 2) {
        for (let px = Math.floor(b.x); px < Math.min(1439, b.x + b.w); px += 2) {
          const i = (png.width * py + px) << 2;
          const l = lum(png.data[i], png.data[i + 1], png.data[i + 2]);
          max = Math.max(max, l); sum += l; n++;
        }
      }
    }
    const m = copy?.match(/(\d+),\s*(\d+),\s*(\d+)/);
    const textLum = m ? lum(+m[1], +m[2], +m[3]) : lum(238, 241, 243);
    results.push({
      section: id, dwell: tag, sampledTextBoxes: boxes.length, copyColor: copy,
      maxBackgroundLuminance: n ? +(max * 100).toFixed(1) : null,
      worstCaseContrast: n ? +ratio(textLum, max).toFixed(2) : null,
    });
    // Re-navigate for a clean DOM (the hidden-text style tag would otherwise persist).
    await page.goto(base, {waitUntil: 'networkidle'});
    await page.waitForFunction(() => document.documentElement.dataset.film === 'on', null, {timeout: 15000}).catch(() => {});
  }
  await page.close();
}

await browser.close();
console.log(JSON.stringify(results, null, 1));
