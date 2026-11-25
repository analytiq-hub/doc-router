import { start, dump, sleep, OUT, base, clickText } from './probe-lib.ts';

const ORG = '6afe2e5ec0d7f78066bd49dd';
const { browser, page } = await start();

// Tag editing from the document list.
await page.goto(`${base}/orgs/${ORG}/docs`, { waitUntil: 'networkidle0' });
await sleep(1000);
await page.type('input[placeholder="Search documents..."]', 'first_notice', { delay: 30 });
await sleep(1500);
await page.screenshot({ path: `${OUT}/t0-search.png` });
const rowBtns = await page.$$('button[aria-label="Actions for 01_first_notice_of_loss.pdf"]');
console.log('fnol rows', rowBtns.length);
await rowBtns[rowBtns.length - 1].click();
await sleep(800);
console.log('--- row menu\n' + (await page.evaluate(() => [...document.querySelectorAll('[role=menuitem]')].map((e) => (e as HTMLElement).innerText).join(' | '))));
await clickText(page, '[role=menuitem]', 'Update');
await sleep(1200);
await page.screenshot({ path: `${OUT}/t1-tags.png` });
console.log('--- tag dialog\n' + (await dump(page)).split('\n').filter((l) => !/Column menu|Actions for|\[8,|base-ui-_r_[38]_ /.test(l)).join('\n'));
await page.keyboard.press('Escape');

// Knowledge base page.
await page.goto(`${base}/orgs/${ORG}/knowledge-bases`, { waitUntil: 'networkidle0' });
await clickText(page, 'a', 'Policy Library');
await sleep(2000);
await page.screenshot({ path: `${OUT}/k1-kb.png` });
console.log('--- kb\n' + (await dump(page)).split('\n').filter((l) => !/\[8,|base-ui-_r_[38]_ /.test(l)).join('\n'));
await browser.close();
