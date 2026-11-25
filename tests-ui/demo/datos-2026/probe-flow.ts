import { start, dump, sleep, OUT, base, clickText } from './probe-lib.ts';

const { browser, page } = await start();
await page.goto(`${base}/orgs/6795345439604beca2b2808d/flows/6a386e942647557e5dab4082`, { waitUntil: 'networkidle0' });
await sleep(1500);
const t0 = Date.now();
await page.click('xpath///button[not(@aria-label)][normalize-space(.)="Execute flow"]');
await sleep(1500);
await page.screenshot({ path: `${OUT}/f1-running.png` });
await sleep(12000);
console.log('waited ms', Date.now() - t0);
await page.screenshot({ path: `${OUT}/f2-done.png` });
await page.click('.react-flow__node[data-id="5a9cd57d-6b46-4b6f-9b81-7d6134590479"]', { count: 2 });
await sleep(2000);
await page.screenshot({ path: `${OUT}/f3-code.png` });
console.log(await dump(page));
await browser.close();
