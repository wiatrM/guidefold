import {defineConfig} from '@playwright/test';
export default defineConfig({
 testDir:'./e2e',testMatch:'landing-flow.spec.ts',timeout:60000,workers:1,
 use:{baseURL:'http://127.0.0.1:4332',trace:'retain-on-failure'},
 webServer:{command:'pnpm exec vite --host 127.0.0.1 --port 4332',url:'http://127.0.0.1:4332',reuseExistingServer:!process.env.CI},
 reporter:[['list'],['json',{outputFile:'qa/landing-flow-report.json'}]],
});
