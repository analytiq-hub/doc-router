import { start, dump, sleep, OUT, base, clickText } from './probe-lib.ts';

const { browser, page } = await start();
await page.goto(`${base}/orgs/6afe2e5ec0d7f78066bd49dd/docs/6afe30c2c0d7f78066bd4a09`, { waitUntil: 'networkidle0' });
await sleep(1500);
await clickText(page, '[role=tab],button', 'Chat');
await sleep(1500);
await page.screenshot({ path: `${OUT}/c1-chat.png` });
console.log(await dump(page));
const html = await page.evaluate(() => {
  const ta = document.querySelector('textarea');
  return ta ? ta.outerHTML + '\nPARENT:' + ta.closest('form')?.outerHTML.slice(0, 1500) : 'no textarea';
});
console.log(html);
await browser.close();
