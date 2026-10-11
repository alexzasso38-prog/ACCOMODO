import { defineConfig } from '../frontend/node_modules/@playwright/test'
const baseURL=process.env.TAVOLO_UI_URL||'http://127.0.0.1:5174'
if(!['localhost','127.0.0.1'].includes(new URL(baseURL).hostname))throw new Error('I test E2E possono usare soltanto demo locali.')
export default defineConfig({testDir:'.',testMatch:'*.spec.ts',workers:1,reporter:'list',outputDir:'../work/e2e-results',use:{baseURL,timezoneId:'Europe/Rome',viewport:{width:1440,height:1000},headless:true,launchOptions:{executablePath:process.env.TAVOLO_BROWSER_PATH||undefined,args:['--no-sandbox']},trace:'retain-on-failure'}})
