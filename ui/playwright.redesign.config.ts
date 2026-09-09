import {defineConfig} from '@playwright/test';
import base from './playwright.config';
/** Combined release candidate; separate port from the shared checkout. */
export default defineConfig({...base,
 use:{...base.use,baseURL:'http://127.0.0.1:4332'},
 webServer:{command:'pnpm exec vite --host 127.0.0.1 --port 4332',url:'http://127.0.0.1:4332',reuseExistingServer:!process.env.CI},
 reporter:[['list'],['json',{outputFile:'qa/redesign-report.json'}]],
});
