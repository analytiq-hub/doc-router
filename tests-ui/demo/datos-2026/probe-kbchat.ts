import { start, dump, sleep, OUT, base, clickText } from './probe-lib.ts';

const ORG = '6afe2e5ec0d7f78066bd49dd';
const AUTO_FNOL = '6afe2fdac0d7f78066bd49e2';
const { browser, page } = await start();

// Part 3: tag the auto FNOL with the agent's tag through the Update sheet.
await page.goto(`${base}/orgs/${ORG}/docs`, { waitUntil: 'networkidle0' });
await page.type('input[placeholder="Search documents..."]', 'first_notice', { delay: 30 });
await sleep(1500);
const row = await page.$(`xpath///a[contains(@href, "/docs/${AUTO_FNOL}")]/ancestor::tr//button[starts-with(@aria-label, "Actions for")]`);
console.log('auto row found', !!row);
await row!.click();
await clickText(page, '[role=menuitem]', 'Update');
await sleep(800);
await clickText(page, '[role=dialog] label, [role=dialog] span', 'First Notice of Loss');
await sleep(500);
await page.screenshot({ path: `${OUT}/t2-checked.png` });
const t0 = Date.now();
await clickText(page, '[role=dialog] button', 'Save');
await page.goto(`${base}/orgs/${ORG}/docs/${AUTO_FNOL}`, { waitUntil: 'networkidle0' });
for (let i = 0; i < 40; i++) {
  const txt = await page.evaluate(() => document.body.innerText);
  if (/claim_number/.test(txt)) break;
  await sleep(3000);
  if (i % 3 === 2) await page.reload({ waitUntil: 'networkidle0' });
}
console.log('auto extraction ms', Date.now() - t0);
await page.screenshot({ path: `${OUT}/t3-auto-extraction.png` });

// Part 4: knowledge base chat.
await page.goto(`${base}/orgs/${ORG}/knowledge-bases`, { waitUntil: 'networkidle0' });
await clickText(page, 'a', 'Policy Library');
await sleep(1500);
await clickText(page, 'button', 'Chat');
await sleep(1500);
await page.screenshot({ path: `${OUT}/k2-chat.png` });
console.log('--- kb chat\n' + (await dump(page)).split('\n').filter((l) => !/\[8,|base-ui-_r_[38]_ /.test(l)).join('\n'));
const input = (await page.$('textarea')) || (await page.$('input[type=text]'));
await input!.type('Is the roof damage at 12 Maple Lane covered, and what deductible applies?', { delay: 15 });
const t1 = Date.now();
await page.keyboard.press('Enter');
await sleep(3000);
let last = '';
for (let i = 0; i < 40; i++) {
  await sleep(3000);
  const txt = await page.evaluate(() => document.body.innerText);
  if (txt === last) break;
  last = txt;
}
console.log('kb chat ms', Date.now() - t1);
await page.screenshot({ path: `${OUT}/k3-answer.png` });
await browser.close();
