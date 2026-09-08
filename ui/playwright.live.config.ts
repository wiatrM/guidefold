/**
 * Live E2E: the same app as the fixture suite, driven against a running hosted API.
 *
 * The specs open the app with `?mode=api`, so `/api` and `/v1` are proxied same-origin by
 * `pnpm dev` (ui/vite.config.ts) to 127.0.0.1:8765 and no CORS is involved. It needs a stack
 * that is already up and seeded — see ui/README.md — and it proves wiring against the real
 * service, not pilot behaviour.
 */
import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir: './e2e/live',
  timeout: 90000,
  fullyParallel: false,
  // One worker on purpose: these specs share one organisation's real rows, and a
  // decision or a membership removal in one file would otherwise race another.
  workers: 1,
  retries: 0,
  projects: [{name: 'live'}],
  use: {
    baseURL: 'http://127.0.0.1:4331',
    viewport: {width: 1280, height: 720},
    reducedMotion: 'reduce',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'pnpm dev',
    url: 'http://127.0.0.1:4331',
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
  reporter: [['list'], ['json', {outputFile: 'qa/playwright-live-report.json'}]],
});
