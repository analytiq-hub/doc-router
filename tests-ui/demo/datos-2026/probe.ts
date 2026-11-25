// Dev helper: log in, visit a URL, dump interactive elements and a screenshot.
// node probe.ts <path> [outName]
import fs from 'node:fs';
import puppeteer from 'puppeteer';
const env = Object.fromEntries(fs.readFileSync(new URL('.env', import.meta.url), 'utf8').split('\n').filter(Boolean).map((l) => l.split(/=(.*)/s).slice(0, 2)));
const OUT = process.env.PROBE_OUT || '.';
const base = 'http://localhost:5173';
const browser = await puppeteer.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, defaultViewport: { width: 1920, height: 1080 } });
const page = await browser.newPage();
await page.goto(`${base}/auth/signin`, { waitUntil: 'networkidle0' });
await page.type('#email', env.DEMO_EMAIL); await page.type('#password', env.DEMO_PASSWORD);
await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0' }), page.click('button[type=submit]')]);
for (const [i, p] of process.argv.slice(2).entries()) {
  await page.goto(base + p, { waitUntil: 'networkidle0' });
  await new Promise((r) => setTimeout(r, 2500));
  const els = await page.evaluate(() => [...document.querySelectorAll('button,a,input,textarea,[role=tab],[role=button],[contenteditable=true],.react-flow__node')].filter((e) => (e as HTMLElement).offsetParent !== null).map((e) => {
    const h = e as HTMLElement; const r = h.getBoundingClientRect();
    return `${e.tagName.toLowerCase()}${h.id ? '#' + h.id : ''} [${Math.round(r.x)},${Math.round(r.y)}] ${(h.getAttribute('aria-label') || h.getAttribute('placeholder') || h.getAttribute('title') || h.innerText || '').replace(/\s+/g, ' ').slice(0, 70)} ${e.tagName === 'A' ? h.getAttribute('href') : ''} ${h.dataset.id ? 'data-id=' + h.dataset.id : ''}`;
  }));
  console.log(`\n=== ${p} -> ${page.url()}\n` + els.join('\n'));
  await page.screenshot({ path: `${OUT}/${i}.png` });
}
await browser.close();
