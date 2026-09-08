import { chromium } from '@playwright/test';
import readline from 'node:readline';
import fs from 'node:fs/promises';
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
const page = await context.newPage();
const report = { methodology: 'Niezależna syntetyczna symulacja P1 owner, n=1. Wyłączne wejście: renderowany interfejs. To nie jest badanie z udziałem prawdziwej osoby.', tasks: [], findings: [], thinkaloud: [], counts: { clicks: 0, disclosures: 0, fields: 0, selects: 0 }, completed: false };
let task;
let seq = 0;
const downloads = [];
page.on('download', d => downloads.push(d));
async function snapshot() {
  await page.screenshot({ path: '../pipeline-wireframes/qa/s05-owner-r2.png', fullPage: true });
  console.log(JSON.stringify({ url: page.url(), snapshot: await page.locator('body').ariaSnapshot() }));
}
await page.goto('http://127.0.0.1:4320/import.html');
await snapshot();
const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  try {
    const c = JSON.parse(line);
    if (c.op === 'task') { task = { id: c.id, goal: c.goal, steps: [], completed: false }; report.tasks.push(task); }
    else if (c.op === 'note') { report.thinkaloud.push({ task: task?.id, text: c.text, synthetic: true }); }
    else if (c.op === 'finding') { report.findings.push(c.finding); }
    else if (c.op === 'complete') { task.completed = c.completed; task.outcome = c.outcome; task.confusion = c.confusion || []; }
    else if (c.op === 'snapshot') { await snapshot(); }
    else if (c.op === 'end') {
      report.completed = report.tasks.length === 3 && report.tasks.every(t => t.completed);
      report.downloads = await Promise.all(downloads.map(async d => ({ filename: d.suggestedFilename(), failure: await d.failure() })));
      await fs.writeFile('../pipeline-wireframes/qa/s05-owner-r2.json', JSON.stringify(report, null, 2));
      await snapshot();
      await browser.close();
      break;
    } else {
      const locator = c.role ? page.getByRole(c.role, { name: c.name, exact: c.exact ?? true }) : page.getByText(c.text, { exact: true });
      if (c.op === 'fill') { await locator.fill(c.value); report.counts.fields++; }
      else if (c.op === 'select') { await locator.selectOption({ label: c.value }); report.counts.selects++; }
      else if (c.op === 'click') { await locator.click(); report.counts.clicks++; if (c.disclosure) report.counts.disclosures++; }
      else throw new Error('Nieznana operacja');
      task?.steps.push({ sequence: ++seq, action: c.op, role: c.role, label: c.name || c.text, value: c.value, disclosure: Boolean(c.disclosure), url: page.url() });
      await snapshot();
    }
    console.log(JSON.stringify({ ready: true }));
  } catch (e) { console.log(JSON.stringify({ error: String(e) })); }
}

