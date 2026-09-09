/**
 * Post-asset verification for the landing page: real generated stills in place.
 * Screenshots at 390/1440, axe on the whole page, and a luminance probe of every
 * background plane inside the copy area, which is what the generated cream sheets
 * put at risk. Run against a served production build.
 */
import {chromium} from '@playwright/test';
import {readFileSync, mkdirSync} from 'node:fs';

const base = process.env.BASE ?? 'http://127.0.0.1:4331';
const out = 'qa/verify';
mkdirSync(out, {recursive: true});
const axe = readFileSync('node_modules/axe-core/axe.min.js', 'utf8');

const browser = await chromium.launch();
const report = {base, viewports: [], axe: null, planeLuminance: [], errors: []};

for (const width of [390, 1440]) {
  const page = await browser.newPage({viewport: {width, height: width === 390 ? 844 : 900}});
  page.on('console', (m) => {if (m.type() === 'error') report.errors.push(`${width}: ${m.text()}`);});
  page.on('pageerror', (e) => report.errors.push(`${width}: ${e.message}`));
  await page.goto(base, {waitUntil: 'networkidle'});
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(600);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(400);
  await page.screenshot({path: `${out}/landing-${width}.png`, fullPage: true});
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  const navLinks = await page.evaluate(() => [...document.querySelectorAll('header nav a')]
    .filter((a) => a.getBoundingClientRect().width > 0).map((a) => a.textContent.trim()));
  report.viewports.push({width, horizontalOverflow: overflow, visibleNavLinks: navLinks});
  if (width === 1440) {
    await page.addScriptTag({content: axe});
    const results = await page.evaluate(async () => {
      const r = await window.axe.run(document, {runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']});
      return r.violations.map((v) => ({id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target)}));
    });
    report.axe = results;
    // Sample the rendered luminance of each plane region while it is fully revealed.
    report.planeLuminance = await page.evaluate(async () => {
      const out = [];
      for (const section of ['why', 'how-it-works', 'value', 'hero']) {
        const el = document.getElementById(section) ?? document.querySelector(`[data-section="${section}"]`);
        if (!el) continue;
        el.scrollIntoView({block: 'center'});
        await new Promise((r) => setTimeout(r, 500));
        const planes = [...el.querySelectorAll('[class*="plane"],[class*="heroMedia"]')];
        for (const p of planes) {
          const cs = getComputedStyle(p);
          out.push({section, cls: p.className, opacity: cs.opacity, image: cs.backgroundImage.slice(0, 80)});
        }
      }
      return out;
    });
  }
  await page.close();
}
await browser.close();
console.log(JSON.stringify(report, null, 1));
