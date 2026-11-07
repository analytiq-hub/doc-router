#!/usr/bin/env node
/**
 * Phase C: replace next/link, next/navigation, next/dynamic, next/image in client/shared src.
 * Skips Next.js server layouts/pages that still use real next/navigation.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const srcRoot = path.resolve(__dirname, '../src');

const SKIP_REL = new Set([
  'shims/next-link.tsx',
  'shims/next-navigation.ts',
  'shims/next-dynamic.tsx',
  'shims/next-image.tsx',
  'utils/session.ts',
  'app/feedback/page.tsx',
  'app/admin/feedback/page.tsx',
  'app/settings/layout.tsx',
  'app/settings/account/layout.tsx',
  'app/settings/account/development/layout.tsx',
  'app/orgs/layout.tsx',
]);

function walk(dir, acc = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = fs.statSync(full);
    if (st.isDirectory()) walk(full, acc);
    else if (/\.(tsx?|jsx?)$/.test(name)) acc.push(full);
  }
  return acc;
}

function transform(content) {
  let out = content;

  out = out.replace(/import Link from ['"]next\/link['"];?\n/g, "import { Link } from 'react-router-dom';\n");
  if (/import Image from ['"]next\/image['"]/.test(out)) {
    out = out.replace(/import Image from ['"]next\/image['"];?\n/g, "import AppImage from '@/components/AppImage';\n");
    out = out.replace(/<Image(\s|\/|>)/g, '<AppImage$1');
    out = out.replace(/<\/Image>/g, '</AppImage>');
  }

  out = out.replace(
    /import dynamic from ['"]next\/dynamic['"];?\n/g,
    "import dynamic from '@/utils/dynamicImport';\n",
  );

  out = out.replace(
    /from ['"]next\/navigation['"]/g,
    "from '@/utils/appRouter'",
  );

  out = out.replace(/<Link(\s[^>]*?)href=/g, '<Link$1to=');
  out = out.replace(/\s+passHref(?:=\{[^}]*\})?/g, '');
  out = out.replace(/\bscroll=\{false\}/g, 'preventScrollReset');

  if (out.includes('useServerInsertedHTML')) {
    out = out.replace(/import \{ useServerInsertedHTML \} from ['"]next\/navigation['"];?\n/, '');
    if (!out.includes('function useServerInsertedHTML')) {
      out = out.replace(
        "'use client';",
        `'use client';\n\n/** CSR-only: no SSR style injection (Vite SPA). */\nfunction useServerInsertedHTML(_fn: () => React.ReactNode) {}\n`,
      );
    }
  }

  return out;
}

function fixDocPageUrl(content) {
  return content
    .replace(
      /import type \{ ReadonlyURLSearchParams \} from 'next\/navigation';\n/,
      '',
    )
    .replace(/ReadonlyURLSearchParams \| URLSearchParams/g, 'URLSearchParams');
}

let changed = 0;
for (const file of walk(srcRoot)) {
  const rel = path.relative(srcRoot, file).replace(/\\/g, '/');
  if (SKIP_REL.has(rel)) continue;

  const raw = fs.readFileSync(file, 'utf8');
  if (!/from ['"]next\//.test(raw) && !raw.includes('<Link') && rel !== 'utils/docPageUrl.ts') continue;
  if (!/next\/(link|navigation|dynamic|image)/.test(raw) && rel !== 'utils/docPageUrl.ts') continue;

  let next = rel === 'utils/docPageUrl.ts' ? fixDocPageUrl(raw) : transform(raw);
  if (next !== raw) {
    fs.writeFileSync(file, next);
    changed += 1;
    console.log('updated', rel);
  }
}

console.log(`Phase C codemod: ${changed} file(s) updated`);
