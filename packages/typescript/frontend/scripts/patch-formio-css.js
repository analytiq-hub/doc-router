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

let css = fs.readFileSync(src, 'utf8');
css = css.replace(/\s*\*zoom:\s*1;\s*/g, ' ');
fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.writeFileSync(dest, css);
console.log('patch-formio-css: wrote public/formio.full.css');
