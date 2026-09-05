#!/usr/bin/env node
"use strict";

// Run with an installed Playwright on NODE_PATH and, when needed,
// CHROMIUM_EXECUTABLE_PATH pointing at an existing headless Chromium.
// Every test uses a fresh, temporary browser context; no user profile is opened.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { pathToFileURL } = require("node:url");
const { chromium } = require("playwright");

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i < 0 ? fallback : path.resolve(process.argv[i + 1]);
}
const htmlPath = arg("--html", path.join(__dirname, "sciezka-nauki.html"));
const outputPath = arg("--output", path.join(__dirname, "tracker-functional-qa.json"));
const KEY = "guidefold.learning.progress.v1";
const BACKUP = KEY + ".previous";
const url = pathToFileURL(htmlPath).href;
const firstStage = "stage1";
const maliciousNote = 'Zażółć gęślą jaźń 🧠\n</textarea><img data-qa-injected src=x onerror="window.__qaInjected=1"><script>window.__qaInjected=2</script>& "dowód"';
const tests = [];
let browser;
const add = (name, fn) => tests.push({ name, fn });
const raw = page => page.evaluate(key => localStorage.getItem(key), KEY);
const saved = async page => JSON.parse(await raw(page));
const val = (page, id) => page.locator("#" + id).inputValue();
async function shown(page, id, expected = true) {
  await page.locator("#" + id).waitFor({ state: expected ? "visible" : "hidden" });
}
async function textIs(page, id, expected) {
  assert.equal(await page.locator("#" + id).textContent(), expected);
}
async function openStage(page, id) {
  if (!(await page.locator("#" + id).evaluate(el => el.open))) {
    await page.locator("#" + id + " > summary").click();
  }
}
async function downloadText(page, id = "export") {
  const pending = page.waitForEvent("download");
  await page.locator("#" + id).click();
  const download = await pending;
  assert.equal(await download.failure(), null);
  const stream = await download.createReadStream();
  assert.ok(stream, "Downloaded file must be readable");
  let text = "";
  for await (const chunk of stream) text += chunk.toString("utf8");
  return { text, filename: download.suggestedFilename() };
}
async function exported(page, id = "export") {
  return JSON.parse((await downloadText(page, id)).text);
}
async function upload(page, input) {
  const text = typeof input === "string" ? input : JSON.stringify(input);
  await page.locator("#import-file").setInputFiles({
    name: "progress.json", mimeType: "application/json", buffer: Buffer.from(text, "utf8")
  });
}
async function seed(page) {
  await page.locator("#stage1-jsonl").check();
  await page.locator("#hours-stage1").fill("1.75");
  await page.locator("#notes-stage1").fill("Oryginalny postęp żółwia 🐢");
  return saved(page);
}
async function createPage(context, configure) {
  const page = await context.newPage();
  page.setDefaultTimeout(6000);
  if (configure) await configure(page);
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.locator("#stage1-jsonl").waitFor();
  return page;
}

add("Fresh state and completion gate; removing a check reopens completed stage", async ({ page }) => {
  assert.equal(await raw(page), null);
  await textIs(page, "done-count", "0 / 10");
  await textIs(page, "checks-count", "0 / 30");
  await textIs(page, "percent", "0%");
  const done = page.locator("#status-stage1 option[value=done]");
  assert.equal(await done.isDisabled(), true);
  await page.locator("#stage1-jsonl").check();
  assert.equal(await val(page, "status-stage1"), "active");
  assert.equal(await done.isDisabled(), true);
  await page.locator("#stage1-metrics").check();
  await page.locator("#stage1-debug").check();
  assert.equal(await done.isDisabled(), false);
  // Checking every box makes completion available; it does not assert mastery.
  assert.equal(await val(page, "status-stage1"), "active");
  await page.locator("#status-stage1").selectOption("done");
  const complete = (await saved(page)).stages[firstStage];
  assert.equal(complete.status, "done");
  assert.ok(Number.isFinite(Date.parse(complete.completedAt)));
  await textIs(page, "done-count", "1 / 10");
  await page.locator("#stage1-debug").uncheck();
  const reopened = (await saved(page)).stages[firstStage];
  assert.equal(reopened.status, "active");
  assert.equal(reopened.completedAt, null);
  assert.equal(await done.isDisabled(), true);
  await textIs(page, "done-count", "0 / 10");
});

add("Fractional hours survive invalid input without overwriting durable value", async ({ page }) => {
  await page.locator("#hours-stage1").fill("1.75");
  const before = await raw(page);
  await textIs(page, "hours-count", "1,75 h");
  for (const bad of ["-1", "10001", ""]) {
    await page.locator("#hours-stage1").fill(bad);
    assert.equal(await page.locator("#hours-stage1").getAttribute("aria-invalid"), "true");
    assert.equal(await raw(page), before);
    assert.equal((await exported(page)).stages[firstStage].hours, 1.75);
  }
  await page.reload();
  assert.equal(await val(page, "hours-stage1"), "1.75");
  await page.locator("#hours-stage1").fill("0.125");
  assert.equal((await saved(page)).stages[firstStage].hours, 0.125);
  assert.equal(await page.locator("#hours-stage1").getAttribute("aria-invalid"), null);
});

add("Unicode and markup remain literal; checks, status, hours and notes persist after reload", async ({ page }) => {
  await page.locator("#stage1-jsonl").check();
  await page.locator("#status-stage1").selectOption("paused");
  await page.locator("#hours-stage1").fill("2.5");
  await page.locator("#notes-stage1").fill(maliciousNote);
  const before = await raw(page);
  await page.reload();
  assert.equal(await raw(page), before);
  assert.equal(await val(page, "notes-stage1"), maliciousNote);
  assert.equal(await val(page, "status-stage1"), "paused");
  assert.equal(await val(page, "hours-stage1"), "2.5");
  assert.equal(await page.locator("#stage1-jsonl").isChecked(), true);
  assert.equal(await page.locator("[data-qa-injected]").count(), 0);
  assert.equal(await page.evaluate(() => window.__qaInjected), undefined);
  assert.equal((await exported(page)).stages[firstStage].notes, maliciousNote);
});

add("Real JSON download and confirmed import round-trip retain a recoverable previous copy", async ({ page }) => {
  const original = await seed(page);
  const download = await downloadText(page);
  assert.match(download.filename, /^guidefold-postep-\d{4}-\d{2}-\d{2}\.json$/);
  const copy = JSON.parse(download.text);
  assert.equal(copy.app, "guidefold-learning");
  assert.equal(copy.version, 1);
  assert.ok(Number.isFinite(Date.parse(copy.exportedAt)));
  assert.deepEqual(copy.stages, original.stages);
  await page.locator("#notes-stage1").fill("Nowszy lokalny zapis");
  await page.locator("#hours-stage1").fill("8.25");
  const beforeImport = await raw(page);
  await upload(page, copy);
  await shown(page, "import-dialog");
  assert.equal(await raw(page), beforeImport, "Upload must wait for confirmation");
  await page.locator("#confirm-import").click();
  await shown(page, "import-dialog", false);
  assert.deepEqual((await saved(page)).stages, original.stages);
  assert.equal(await page.evaluate(key => localStorage.getItem(key), BACKUP), beforeImport);
  assert.deepEqual(JSON.parse((await downloadText(page, "previous-backup")).text).stages, JSON.parse(beforeImport).stages);
  await page.reload();
  assert.deepEqual((await saved(page)).stages, original.stages);
});

add("Import cancellation, Escape and exporting before import do not replace the current state", async ({ page }) => {
  const candidate = await exported(page);
  const original = await seed(page);
  const before = await raw(page);
  await upload(page, candidate);
  await shown(page, "import-dialog");
  assert.deepEqual((await exported(page, "export-before-import")).stages, original.stages);
  await page.locator("#cancel-import").click();
  assert.equal(await raw(page), before);
  await upload(page, candidate);
  await shown(page, "import-dialog");
  await page.keyboard.press("Escape");
  await shown(page, "import-dialog", false);
  assert.equal(await raw(page), before);
});

add("Malformed, incompatible and oversized imports preserve current state and previous backup", async ({ page }) => {
  const original = await seed(page);
  const before = await raw(page);
  await page.evaluate(key => localStorage.setItem(key, "existing backup"), BACKUP);
  const mutate = fn => { const x = structuredClone(original); fn(x); return JSON.stringify(x); };
  const invalid = [
    "{bad JSON",
    mutate(x => { x.version = 2; }),
    mutate(x => { x.stages.stage1.status = ["done"]; }),
    mutate(x => { delete x.stages.stage1; }),
    mutate(x => { x.stages.stage1.hours = -1; }),
    mutate(x => { x.stages.stage1.hours = "1.75"; }),
    mutate(x => { x.stages.stage1.status = "done"; x.stages.stage1.completedAt = new Date().toISOString(); }),
    mutate(x => { x.stages.stage1.notes = "n".repeat(10001); }),
    mutate(x => { x.stages.stage1.checks.jsonl = "false"; }),
    mutate(x => { x.extra = "unexpected"; }),
    " ".repeat(2 * 1024 * 1024 + 1)
  ];
  for (const input of invalid) {
    await page.locator("#toast").evaluate(el => { el.hidden = true; });
    await upload(page, input);
    await shown(page, "toast");
    assert.match(await page.locator("#toast").textContent(), /Nie wczytano pliku/);
    assert.equal(await page.locator("#import-dialog").isVisible(), false);
    assert.equal(await raw(page), before);
    assert.equal(await page.evaluate(key => localStorage.getItem(key), BACKUP), "existing backup");
    assert.equal(await val(page, "notes-stage1"), original.stages.stage1.notes);
  }
});

add("Blocked localStorage still allows editing and export with an explicit warning", async ({ context }) => {
  await context.addInitScript(() => {
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() { throw new DOMException("QA blocked storage", "SecurityError"); }
    });
  });
  const page = await createPage(context);
  assert.match(await page.locator("#save-status").textContent(), /blokuje zapis/);
  await page.locator("#stage1-jsonl").check();
  await page.locator("#hours-stage1").fill("3.5");
  await page.locator("#notes-stage1").fill(maliciousNote);
  const copy = await exported(page);
  assert.equal(copy.stages.stage1.hours, 3.5);
  assert.equal(copy.stages.stage1.notes, maliciousNote);
  assert.equal(copy.stages.stage1.checks.jsonl, true);
  assert.match(await page.locator("#save-status").textContent(), /niedostępny/);
  assert.equal(await page.locator("[data-qa-injected]").count(), 0);
},);

add("Storage write failure preserves previous durable data and exports unsaved changes", async ({ page }) => {
  await seed(page);
  const before = await raw(page);
  await page.evaluate(() => {
    Storage.prototype.setItem = function () { throw new DOMException("QA quota exceeded", "QuotaExceededError"); };
  });
  await page.locator("#notes-stage1").fill("Zmiana tylko w pamięci 📝");
  await page.locator("#hours-stage1").fill("7.125");
  assert.equal(await raw(page), before);
  assert.equal((await exported(page)).stages.stage1.notes, "Zmiana tylko w pamięci 📝");
  assert.equal((await exported(page)).stages.stage1.hours, 7.125);
  assert.match(await page.locator("#save-status").textContent(), /niedostępny/);
});

add("Corrupt storage is preserved byte-for-byte and can be downloaded before an explicit reset", async ({ page }) => {
  const broken = '{"old":"Żółć 🐢", definitely not JSON';
  await page.evaluate(({ key, value }) => localStorage.setItem(key, value), { key: KEY, value: broken });
  await page.reload();
  await shown(page, "corrupt");
  await page.locator("#stage1-jsonl").check();
  await page.locator("#notes-stage1").fill("Odzyskana praca");
  assert.equal(await raw(page), broken);
  assert.equal((await downloadText(page, "export-raw")).text, broken);
  assert.equal((await exported(page)).stages.stage1.notes, "Odzyskana praca");
  page.once("dialog", dialog => dialog.dismiss());
  await page.locator("#new-storage").click();
  assert.equal(await raw(page), broken);
  await shown(page, "corrupt");
  page.once("dialog", dialog => dialog.accept());
  await page.locator("#new-storage").click();
  await shown(page, "corrupt", false);
  assert.equal((await saved(page)).stages.stage1.notes, "Odzyskana praca");
  assert.equal(await page.evaluate(key => localStorage.getItem(key), BACKUP), broken);
  await page.reload();
  assert.equal(await val(page, "notes-stage1"), "Odzyskana praca");
});

add("Real second-tab storage events prevent overwrite and support both conflict resolutions", async ({ page, context }) => {
  await seed(page);
  const second = await createPage(context);
  await second.locator("#notes-stage1").fill("Wersja z drugiej karty");
  await shown(page, "conflict");
  const secondRaw = await raw(second);
  await page.locator("#notes-stage1").fill("Moja niezapisana wersja");
  assert.equal(await raw(page), secondRaw);
  assert.equal((await exported(page, "export-current")).stages.stage1.notes, "Moja niezapisana wersja");
  await page.locator("#load-latest").click();
  await shown(page, "conflict", false);
  assert.equal(await val(page, "notes-stage1"), "Wersja z drugiej karty");
  await second.locator("#notes-stage1").fill("Jeszcze nowsza druga karta");
  await shown(page, "conflict");
  const latestRaw = await raw(page);
  page.once("dialog", dialog => dialog.dismiss());
  await page.locator("#keep-current").click();
  assert.equal(await raw(page), latestRaw);
  page.once("dialog", dialog => dialog.accept());
  await page.locator("#keep-current").click();
  await shown(page, "conflict", false);
  assert.equal((await saved(page)).stages.stage1.notes, "Wersja z drugiej karty");
  assert.equal(await page.evaluate(key => localStorage.getItem(key), BACKUP), latestRaw);
  await shown(second, "conflict");
});

add("Import confirmation refuses to overwrite a newer second-tab update", async ({ page, context }) => {
  const oldCopy = await exported(page);
  await seed(page);
  const second = await createPage(context);
  await upload(page, oldCopy);
  await shown(page, "import-dialog");
  await second.locator("#notes-stage1").fill("Nowsza wersja po otwarciu importu");
  const before = await raw(second);
  await page.locator("#confirm-import").click();
  await shown(page, "import-dialog", false);
  await shown(page, "conflict");
  assert.equal(await raw(page), before);
  await page.locator("#load-latest").click();
  assert.equal(await val(page, "notes-stage1"), "Nowsza wersja po otwarciu importu");
});

add("Completing all stages updates aggregate progress, next action and durable state", async ({ page }) => {
  const ids = await page.locator("#stages > details.stage").evaluateAll(elements => elements.map(el => el.id));
  assert.equal(ids.length, 10);
  for (const id of ids) {
    await openStage(page, id);
    const checkboxes = page.locator("#" + id + " input[type=checkbox]");
    for (let i = 0; i < await checkboxes.count(); i++) await checkboxes.nth(i).check();
    await page.locator("#hours-" + id).fill("0.5");
    await page.locator("#status-" + id).selectOption("done");
  }
  await textIs(page, "done-count", "10 / 10");
  await textIs(page, "checks-count", "30 / 30");
  await textIs(page, "hours-count", "5 h");
  await textIs(page, "percent", "100%");
  assert.equal(await page.locator("#overall-progress").evaluate(el => el.value / el.max), 1);
  assert.equal(await page.locator("#continue").isDisabled(), true);
  await textIs(page, "next-title", "Wszystkie etapy zaliczone");
  const completed = await saved(page);
  assert.equal(Object.values(completed.stages).filter(s => s.status === "done" && Number.isFinite(Date.parse(s.completedAt))).length, 10);
  await page.reload();
  await textIs(page, "done-count", "10 / 10");
  await textIs(page, "percent", "100%");
  assert.deepEqual((await saved(page)).stages, completed.stages);
});


add("Import backup quota failure preserves current progress and existing backup", async ({ page }) => {
  const candidate = await exported(page);
  await seed(page);
  const before = await raw(page);
  await page.evaluate(key => {
    localStorage.setItem(key, "existing previous copy");
    const realSet = Storage.prototype.setItem;
    Storage.prototype.setItem = function (name, value) {
      if (name.endsWith(".previous")) throw new DOMException("QA backup quota", "QuotaExceededError");
      return realSet.call(this, name, value);
    };
  }, BACKUP);
  await upload(page, candidate);
  await shown(page, "import-dialog");
  await page.locator("#confirm-import").click();
  assert.equal(await raw(page), before);
  assert.equal(await page.evaluate(key => localStorage.getItem(key), BACKUP), "existing previous copy");
  assert.equal(await val(page, "notes-stage1"), JSON.parse(before).stages.stage1.notes);
  assert.deepEqual((await exported(page, await page.locator("#import-dialog").isVisible() ? "export-before-import" : "export")).stages, JSON.parse(before).stages);
});

async function main() {
  const report = {
    schemaVersion: 1,
    checkedAt: new Date().toISOString(),
    target: path.basename(htmlPath),
    mode: "Headless Chromium; file://; fresh non-persistent context per test; external HTTP(S) requests blocked",
    runtime: { node: process.version, playwright: require("playwright/package.json").version },
    inputs: {},
    tests: []
  };
  for (const file of [htmlPath, path.join(__dirname, "tracker.js"), path.join(__dirname, "tracker-data.json"), __filename]) {
    const bytes = fs.readFileSync(file);
    report.inputs[path.basename(file)] = {
      bytes: bytes.length, sha256: crypto.createHash("sha256").update(bytes).digest("hex")
    };
  }
  browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE_PATH ? { executablePath: process.env.CHROMIUM_EXECUTABLE_PATH } : {})
  });
  report.runtime.chromium = browser.version();
  try {
    for (const test of tests) {
      const started = Date.now();
      const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1280, height: 900 } });
      const errors = [];
      await context.route(/https?:\/\//, route => route.abort());
      context.on("page", page => page.on("pageerror", error => errors.push(error.message)));
      try {
        // The blocked-storage case installs its fault before opening the page.
        const page = test.name.startsWith("Blocked localStorage") ? null : await createPage(context);
        await test.fn({ page, context });
        assert.deepEqual(errors, [], "No unhandled page errors");
        report.tests.push({ name: test.name, status: "passed", durationMs: Date.now() - started, pageErrors: errors });
        console.log("PASS " + test.name);
      } catch (error) {
        report.tests.push({ name: test.name, status: "failed", durationMs: Date.now() - started, error: error.stack, pageErrors: errors });
        console.error("FAIL " + test.name + "\n" + error.stack);
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
  report.summary = {
    total: report.tests.length,
    passed: report.tests.filter(t => t.status === "passed").length,
    failed: report.tests.filter(t => t.status === "failed").length
  };
  fs.writeFileSync(outputPath, JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify(report.summary));
  if (report.summary.failed) process.exitCode = 1;
}

main().catch(async error => {
  console.error(error.stack);
  if (browser) await browser.close().catch(() => {});
  process.exitCode = 1;
});
