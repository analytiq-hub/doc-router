// Dev helpers for probing the live UI while building the demo. Not used by run-demo.ts.
import fs from 'node:fs';
import puppeteer from 'puppeteer';
import type { Page } from 'puppeteer';

export const env: Record<string, string> = Object.fromEntries(
  fs.readFileSync(new URL('.env', import.meta.url), 'utf8').split('\n').filter(Boolean).map((l) => l.split(/=(.*)/s).slice(0, 2)),
);
export const OUT = process.env.PROBE_OUT || '/tmp';
export const base = 'http://localhost:5173';
export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function start() {
  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    defaultViewport: { width: 1920, height: 1080 },
  });
  const page = await browser.newPage();
  await page.goto(`${base}/auth/signin`, { waitUntil: 'networkidle0' });
  await page.type('#email', env.DEMO_EMAIL);
  await page.type('#password', env.DEMO_PASSWORD);
  await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0' }), page.click('button[type=submit]')]);
  return { browser, page };
}

export async function dump(page: Page, filter = ''): Promise<string> {
  return page.evaluate((f: string) =>
    [...document.querySelectorAll('button,input,textarea,select,[role=tab],[role=button],[role=dialog],[contenteditable=true]')]
      .filter((e) => (e as HTMLElement).offsetParent !== null)
      .map((e) => {
        const h = e as HTMLElement;
        const r = h.getBoundingClientRect();
        const label = (h.getAttribute('aria-label') || h.getAttribute('placeholder') || h.getAttribute('title') || h.innerText || '').replace(/\s+/g, ' ').slice(0, 80);
        return `${e.tagName.toLowerCase()}${h.id ? '#' + h.id : ''}${h.getAttribute('role') ? '[' + h.getAttribute('role') + ']' : ''} [${Math.round(r.x)},${Math.round(r.y)}] ${label}`;
      })
      .filter((s) => s.includes(f))
      .join('\n'), filter);
}

export async function clickText(page: Page, selector: string, text: string) {
  const handle = await page.waitForFunction(
    (sel: string, t: string) => [...document.querySelectorAll(sel)].find((e) => (e as HTMLElement).offsetParent !== null && (e as HTMLElement).innerText.trim().includes(t)),
    { timeout: 15000 }, selector, text,
  );
  await (handle as any).asElement().click();
}
