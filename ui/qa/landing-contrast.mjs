/**
 * Measures the composited background behind landing body copy, which the generated
 * cream-paper planes put at risk. Text is hidden so the sampled pixels are background
 * only; contrast is then computed against the copy colour the section actually uses.
 */
import {chromium} from '@playwright/test';
import {PNG} from 'pngjs';
import {mkdirSync, writeFileSync} from 'node:fs';

const base = process.env.BASE ?? 'http://127.0.0.1:4331';
const out = 'qa/verify';
mkdirSync(out, {recursive: true});

const srgb = (c) => {const s = c / 255; return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;};
const lum = (r, g, b) => 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
const ratio = (a, b) => (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);

const browser = await chromium.launch();
const context = await browser.newContext({viewport: {width: 1440, height: 900}, deviceScaleFactor: 1});
let page = await context.newPage();
await page.goto(base, {waitUntil: 'networkidle'});

const sections = await page.evaluate(() => [...document.querySelectorAll('main section')].map((s, i) => s.id || `section-${i}`));
const results = [];

for (const id of sections) {
  await page.close();
  page = await context.newPage();
  await page.goto(base, {waitUntil: 'networkidle'});
  const found = await page.evaluate((sel) => {
    const el = document.getElementById(sel) ?? [...document.querySelectorAll('main section')][Number(sel.split('-')[1])];
    if (!el) return null;
    el.scrollIntoView({block: 'center'});
    return true;
  }, id);
  if (!found) continue;
  await page.waitForTimeout(700);
  // Record where the copy actually sits, then hide it so the sampled pixels behind
  // those exact rectangles are background only.
  const {copy, boxes, where} = await page.evaluate((sel) => {
    const list = [...document.querySelectorAll('main section')];
    const scope = document.getElementById(sel) ?? list[Number(sel.split('-')[1])] ?? document.body;
    const nodes = [...scope.querySelectorAll('p,li,h1,h2,h3,strong,label')]
      .filter((n) => n.textContent.trim() && getComputedStyle(n).visibility !== 'hidden');
    // Only boxes fully inside the viewport and clear of the sticky header, so a clamped
    // rectangle can never sample header pixels and report them as section background.
    const top = document.querySelector('header')?.getBoundingClientRect().bottom ?? 0;
    const vis = nodes.map((n) => n.getBoundingClientRect())
      .filter((r) => r.width > 8 && r.height > 8 && r.top > top + 4 && r.bottom < innerHeight - 4)
      .map((r) => ({x: r.x, y: r.y, w: Math.min(r.width, innerWidth - r.x), h: r.height}));
    const p = nodes.find((n) => n.tagName === 'P' || n.tagName === 'LI') ?? nodes[0];
    return {copy: p ? getComputedStyle(p).color : null, boxes: vis, where: scope.className + ' ' + (scope.getAttribute('aria-label') || scope.getAttribute('aria-labelledby') || '')};
  }, id);
  await page.addStyleTag({content: 'main p,main li,main h1,main h2,main h3,main span,main strong,main a,main button,main img,main video,main svg,main input,main label,main code,main dt,main dd,main summary,main figcaption,main time,main em{visibility:hidden !important}'});
  await page.waitForTimeout(200);
  const buf = await page.screenshot({clip: {x: 0, y: 0, width: 1440, height: 900}});
  const png = PNG.sync.read(buf);
  let max = 0, sum = 0, n = 0;
  for (const b of boxes) {
    for (let y = Math.floor(b.y); y < Math.min(899, b.y + b.h); y += 2) {
      for (let x = Math.floor(b.x); x < Math.min(1439, b.x + b.w); x += 2) {
        const i = (png.width * y + x) << 2;
        const l = lum(png.data[i], png.data[i + 1], png.data[i + 2]);
        max = Math.max(max, l); sum += l; n++;
      }
    }
  }
  if (!n) continue;
  const m = copy?.match(/(\d+),\s*(\d+),\s*(\d+)/);
  const textLum = m ? lum(+m[1], +m[2], +m[3]) : lum(238, 241, 243);
  results.push({
    section: id,
    where,
    sampledTextBoxes: boxes.length,
    copyColor: copy,
    maxBackgroundLuminance: +(max * 100).toFixed(1),
    meanBackgroundLuminance: +((sum / n) * 100).toFixed(1),
    worstCaseContrast: +ratio(textLum, max).toFixed(2),
    meanContrast: +ratio(textLum, sum / n).toFixed(2),
  });
}

await browser.close();
writeFileSync(`${out}/contrast.json`, JSON.stringify(results, null, 1));
console.log(JSON.stringify(results, null, 1));
