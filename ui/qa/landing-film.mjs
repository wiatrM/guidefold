/**
 * Verifies the scroll-driven film: the playhead follows scroll, returns to where it was
 * when the visitor scrolls back, and the poster survives every failure path. Also grabs
 * one screenshot per section so the composition can be reviewed against the copy.
 */
import {chromium} from '@playwright/test';
import {mkdirSync} from 'node:fs';

const base = process.env.BASE ?? 'http://127.0.0.1:4331';
const out = 'qa/film';
mkdirSync(out, {recursive: true});
const browser = await chromium.launch();
const report = {base, marks: [], reverse: null, reducedMotion: null, blocked: null, errors: []};

const page = await browser.newPage({viewport: {width: 1440, height: 900}});
page.on('console', (m) => {if (m.type() === 'error') report.errors.push(m.text());});
page.on('pageerror', (e) => report.errors.push(e.message));
await page.goto(base, {waitUntil: 'networkidle'});
await page.waitForFunction(() => document.documentElement.dataset.film === 'on', null, {timeout: 15000})
  .catch(() => report.errors.push('film never reported ready'));

const readHead = () => page.evaluate(() => {
  const v = document.querySelector('video');
  return v ? +v.currentTime.toFixed(3) : null;
});
const scrollTo = async (fraction) => {
  await page.evaluate((f) => window.scrollTo(0, (document.documentElement.scrollHeight - innerHeight) * f), fraction);
  await page.waitForTimeout(900);
};

for (const fraction of [0, 0.25, 0.5, 0.75, 1]) {
  await scrollTo(fraction);
  report.marks.push({scroll: fraction, currentTime: await readHead()});
  await page.screenshot({path: `${out}/scroll-${String(fraction).replace('.', '')}.png`});
}
await scrollTo(0.25);
report.reverse = {scroll: 0.25, currentTime: await readHead()};
await page.close();

const reduced = await browser.newPage({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
const requested = [];
reduced.on('request', (r) => {if (/hero-flight/.test(r.url())) requested.push(r.url());});
await reduced.goto(base, {waitUntil: 'networkidle'});
await reduced.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
await reduced.waitForTimeout(600);
report.reducedMotion = {
  videoElements: await reduced.locator('video').count(),
  filmRequests: requested.length,
  posterVisible: await reduced.locator('img[src*="hero-poster"]').first().isVisible(),
};
await reduced.close();

const blocked = await browser.newPage({viewport: {width: 1440, height: 900}});
await blocked.route('**/hero-flight.*', (route) => route.abort());
await blocked.goto(base, {waitUntil: 'networkidle'});
await blocked.waitForTimeout(1200);
report.blocked = {
  filmFlag: await blocked.evaluate(() => document.documentElement.dataset.film ?? null),
  posterVisible: await blocked.locator('img[src*="hero-poster"]').first().isVisible(),
  overflow: await blocked.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth),
};
await blocked.screenshot({path: `${out}/blocked.png`});
await blocked.close();

await browser.close();
console.log(JSON.stringify(report, null, 1));
