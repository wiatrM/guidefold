import {defineConfig} from '@playwright/test';
/** Verify the built artifact; isolate traces from other ongoing QA jobs. */
export default defineConfig({
 testDir:'./e2e',testMatch:['spectrum-migration.spec.ts','spectrum-pie.spec.ts','landing-flow.spec.ts','landing-workbench.spec.ts','landing-pyramid.spec.ts','accessibility.spec.ts','owner-keyboard.spec.ts'],
 timeout:120000,expect:{timeout:15000},workers:1,
 outputDir:'test-results-spectrum',
 use:{baseURL:'http://127.0.0.1:4334',viewport:{width:1440,height:1000},reducedMotion:'reduce',trace:'retain-on-failure'},
 webServer:{command:'pnpm exec vite preview --host 127.0.0.1 --port 4334',url:'http://127.0.0.1:4334',reuseExistingServer:!process.env.CI},
 reporter:[['list'],['json',{outputFile:'qa/spectrum-browser-report.json'}]],
});
