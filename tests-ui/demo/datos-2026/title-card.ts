// Title cards in the series design (same background, fonts and layout as the video poster,
// docrouter.github.io/_brand/demo-poster). Shared by run-demo.ts and render-cards.ts.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import yaml from 'js-yaml';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const cfg = (yaml.load(fs.readFileSync(path.join(HERE, 'steps.yaml'), 'utf8')) as { config: any }).config;

export type TitleCard = { label?: string; heading: string; sub?: string; qr?: boolean };

const BRAND = path.resolve(HERE, cfg.brand_dir);
const dataUri = (file: string, mime: string) => {
  const p = path.isAbsolute(file) ? file : path.join(BRAND, file);
  if (!fs.existsSync(p)) throw new Error(`Missing brand asset ${p}`);
  return `data:${mime};base64,${fs.readFileSync(p).toString('base64')}`;
};

/** HTML for a full-screen 1920x1080 title card. */
export function titleCardHtml(arg: TitleCard): string {
  const font = (w: string) => dataUri(`../fonts/Inter-${w}.ttf`, 'font/ttf');
  const sub = (arg.sub ?? '').replace('{cta_url}', cfg.cta.url_text);
  const qr = arg.qr ? dataUri(cfg.cta.qr_image, 'image/png') : '';
  return `<!doctype html><html><head><style>
    @font-face{font-family:Inter;font-weight:500;src:url(${font('Medium')})}
    @font-face{font-family:Inter;font-weight:600;src:url(${font('SemiBold')})}
    @font-face{font-family:Inter;font-weight:700;src:url(${font('Bold')})}
    html,body{margin:0;width:1920px;height:1080px;overflow:hidden;font-family:Inter,sans-serif;color:#fff;
      background:#1a2b4c url(${dataUri(cfg.card_background, 'image/png')}) center/cover no-repeat}
    .text{position:absolute;left:140px;top:200px}
    .logo{width:560px;display:block;margin-bottom:70px}
    .label{font-weight:600;font-size:34px;letter-spacing:.14em;color:#f89c54;margin-bottom:34px;line-height:1}
    h1{font-weight:700;font-size:108px;line-height:1.1;margin:0 0 22px;white-space:nowrap}
    .sub{font-weight:500;font-size:48px;color:#cbd5e1;line-height:1.2}
    .qr{position:absolute;right:170px;top:330px;width:250px;background:#fff;padding:18px;border-radius:20px}
  </style></head><body>
    <div class="text" data-max-width="${qr ? 1120 : 1640}">
      <img class="logo" src="${dataUri('docrouter-logo-horizontal-white.svg', 'image/svg+xml')}">
      ${arg.label ? `<div class="label">${arg.label}</div>` : ''}
      <h1>${arg.heading}</h1>
      ${sub ? `<div class="sub">${sub}</div>` : ''}
    </div>
    ${qr ? `<img class="qr" src="${qr}">` : ''}
  </body></html>`;
}

/** Shrink the title until it fits, like the poster builder does. */
export const FIT_TITLE_JS = `(() => {
  const box = document.querySelector('.text'); const h = document.querySelector('h1');
  if (!box || !h) return;
  const max = Number(box.dataset.maxWidth); let size = 108;
  while (h.scrollWidth > max && size > 40) { size -= 2; h.style.fontSize = size + 'px'; }
})();`;
