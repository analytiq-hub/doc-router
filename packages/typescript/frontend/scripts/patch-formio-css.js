#!/usr/bin/env node
/**
 * Copies formio.full.css to public/ and removes the legacy *zoom: 1 rule
 * that Turbopack/LightningCSS cannot parse (invalid in modern CSS).
 */
const fs = require('fs');
const path = require('path');

const src = path.join(__dirname, '../node_modules/formiojs/dist/formio.full.css');
const dest = path.join(__dirname, '../public/formio.full.css');

if (!fs.existsSync(src)) {
  console.warn('patch-formio-css: formiojs dist not found, skipping');
  process.exit(0);
}

const FA_CDN = 'https://cdn.jsdelivr.net/npm/font-awesome@4.7.0/fonts';

let css = fs.readFileSync(src, 'utf8');
css = css.replace(/\s*\*zoom:\s*1;\s*/g, ' ');
// Scope .hidden to Formio containers only so Tailwind's .hidden / .sm:block etc. work in the rest of the app
css = css.replace(/\.hidden\s*\{\s*display:\s*none\s*!important;\s*\}/g,
  '.formio-form .hidden, .formio-builder .hidden, .formio-dialog .hidden { display: none !important; }');
// Form.io references fonts at relative path fonts/ → /fonts/ which don't exist. Point to CDN.
css = css.replace(/url\s*\(\s*['"]?fonts\/fontawesome-webfont\.(eot|woff2|woff|ttf|svg)([^'"]*)['"]?\s*\)/g, (m, ext, q) => `url('${FA_CDN}/fontawesome-webfont.${ext}${q}')`);
fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.writeFileSync(dest, css);
console.log('patch-formio-css: wrote public/formio.full.css');
