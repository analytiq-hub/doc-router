import { start, sleep, OUT, base, clickText } from './probe-lib.ts';

const ORG = '6afe2e5ec0d7f78066bd49dd';
const DOC = '6afe30c2c0d7f78066bd4a09';
const { browser, page } = await start();

// Pre-approve every read-write agent tool for this document.
const tools = await page.evaluate(async (o: string, d: string) => {
  const r = await fetch(`http://localhost:8000/v0/orgs/${o}/documents/${d}/chat/tools`, { credentials: 'include' });
  return r.ok ? (await r.json()).read_write : `ERR ${r.status}`;
}, ORG, DOC);
console.log('tools', tools);
await page.evaluate((o: string, d: string, t: string[]) => localStorage.setItem(`agent-auto-approved-tools-${o}-${d}`, JSON.stringify(t)), ORG, DOC, tools);

await page.goto(`${base}/orgs/${ORG}/docs/${DOC}`, { waitUntil: 'networkidle0' });
await sleep(1000);
await clickText(page, '[role=tab]', 'Chat');
await page.waitForSelector('textarea[placeholder="Message the agent…"]');
await page.type('textarea[placeholder="Message the agent…"]', "Create a tag, schema and prompt to process this kind of document, then run it on this document. The LLM should be the newest Gemini Flash.", { delay: 15 });
const t0 = Date.now();
await page.keyboard.press('Enter');
await page.waitForSelector('button[title="Stop"]', { timeout: 10000 }).catch(() => console.log('no stop button seen'));
let n = 0;
while (await page.$('button[title="Stop"]')) {
  await sleep(5000);
  await page.screenshot({ path: `${OUT}/a-${String(++n).padStart(2, '0')}.png` });
  if (Date.now() - t0 > 240000) { console.log('TIMEOUT'); break; }
}
console.log('agent ms', Date.now() - t0);
await sleep(1500);
await page.screenshot({ path: `${OUT}/a-done.png` });
await clickText(page, '[role=tab]', 'Extraction');
await sleep(3000);
await page.screenshot({ path: `${OUT}/a-extraction.png` });
await browser.close();
