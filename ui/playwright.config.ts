import {defineConfig} from '@playwright/test';
export default defineConfig({
 testDir:'./e2e',testIgnore:'**/live/**',timeout:60000,fullyParallel:false,retries:0,
 use:{baseURL:'http://127.0.0.1:4331',viewport:{width:1280,height:720},reducedMotion:'reduce',trace:'retain-on-failure'},
 webServer:{command:'pnpm dev',url:'http://127.0.0.1:4331',reuseExistingServer:!process.env.CI,timeout:30000},
 reporter:[['list'],['json',{outputFile:'qa/playwright-report.json'}]]
});
