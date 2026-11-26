// Render replacement frames for patching an already-recorded demo video, using the same
// overlay and title-card code as run-demo.ts, so patches match a fresh recording.
//
//   node render-cards.ts --cards 0,22,23 --captions 1,2 [--bar-color 33,39,58] [--out out/patch]
//
// --cards     steps whose title card is replaced: full 1920x1080 PNG (card + caption bar)
// --captions  steps whose caption bar is replaced: transparent PNG with only the bar. The bar
//             is drawn in a solid colour (measured from the old video, where the 92%-opaque
//             bar sits on the light page) so it fully covers the old text.
// --fade-captions  steps whose bar fades in after a page load: also writes caption-NN-fade.png
//             with the runner's real 92%-opaque bar and shadow, to fade in over a clean
//             background (patch-video.sh), so old and new text never overlap.
//
// patch-video.sh lays these over the original MP4.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer';
import yaml from 'js-yaml';
import { OVERLAY_JS } from './overlay.ts';
import { titleCardHtml, FIT_TITLE_JS } from './title-card.ts';
import type { TitleCard } from './title-card.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const doc = yaml.load(fs.readFileSync(path.join(HERE, 'steps.yaml'), 'utf8')) as {
  steps: { part: string; caption: string; actions: Record<string, any>[] }[];
};

const args = process.argv.slice(2);
const opt = (name: string, dflt = '') => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args[i + 1] : dflt;
};
const list = (s: string) => (s ? s.split(',').map(Number) : []);
const cards = list(opt('cards'));
const captions = list(opt('captions'));
const fadeCaptions = list(opt('fade-captions'));   // also render with the runner's real styling
const barColor = opt('bar-color', '33,39,58');
const outDir = path.resolve(HERE, opt('out', 'out/patch'));
fs.mkdirSync(outDir, { recursive: true });

const chrome = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'].find((p) => fs.existsSync(p));
const browser = await puppeteer.launch({ executablePath: chrome, headless: true, defaultViewport: { width: 1920, height: 1080 } });
const page = await browser.newPage();

async function showCaption(step: { part: string; caption: string }) {
  await page.evaluate(() => { delete (window as any).__demo; });
  await page.evaluate(OVERLAY_JS);
  await page.evaluate(() => { const c = document.getElementById('__demo_cursor'); if (c) c.style.display = 'none'; });
  await page.evaluate((c) => (window as any).__demo.caption(c), { part: step.part, text: step.caption, compress: false });
  await new Promise((r) => setTimeout(r, 400));   // caption fades in over 0.25 s
}

for (const i of cards) {
  const step = doc.steps[i];
  const card = step.actions.find((a) => a.title_card)?.title_card as TitleCard | undefined;
  if (!card) throw new Error(`Step ${i} has no title_card`);
  await page.setContent(titleCardHtml(card));
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(FIT_TITLE_JS);
  await showCaption(step);
  const file = path.join(outDir, `card-${String(i).padStart(2, '0')}.png`);
  await page.screenshot({ path: file });
  console.log(file);
}

for (const i of captions) {
  const step = doc.steps[i];
  await page.setContent('<!doctype html><html><body style="margin:0;background:transparent"></body></html>');
  await showCaption(step);
  await page.addStyleTag({ content: `#__demo_cap{background:rgb(${barColor}) !important;box-shadow:none !important;transition:none !important}` });
  const box = await page.$eval('#__demo_cap', (e) => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height].map(Math.round); });
  const file = path.join(outDir, `caption-${String(i).padStart(2, '0')}.png`);
  await page.screenshot({ path: file, omitBackground: true });
  console.log(file, 'bar box', box.join(','));
}

for (const i of fadeCaptions) {
  const step = doc.steps[i];
  await page.setContent('<!doctype html><html><body style="margin:0;background:transparent"></body></html>');
  await showCaption(step);
  const file = path.join(outDir, `caption-${String(i).padStart(2, '0')}-fade.png`);
  await page.screenshot({ path: file, omitBackground: true });
  console.log(file);
}

await browser.close();
