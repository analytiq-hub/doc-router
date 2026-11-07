import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, loadEnv, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '../../..');

const FORMIO_CSS_MARKER = `${path.sep}@tsed${path.sep}tailwind-formio${path.sep}`;
const STRIP_CSS_SOURCEMAP = /\/\*#\s*sourceMappingURL=[^*]+\*\//g;

/** @tsed/tailwind-formio grid.css points at a .map file that is not published. */
function stripBrokenFormioCssSourcemaps(): Plugin {
  const isFormioStyleSheet = (id: string) => {
    const file = id.split('?')[0];
    return file.includes(FORMIO_CSS_MARKER) && file.endsWith('.css');
  };

  return {
    name: 'strip-broken-formio-css-sourcemaps',
    enforce: 'pre',
    load(id) {
      const file = id.split('?')[0];
      if (!isFormioStyleSheet(id)) return null;
      const code = fs.readFileSync(file, 'utf-8');
      return code.replace(STRIP_CSS_SOURCEMAP, '');
    },
  };
}

/** Inject NEXT_PUBLIC_* from the repo root .env (same as Next) for shared config modules. */
function nextPublicEnvDefine(mode: string): Record<string, string> {
  const env = loadEnv(mode, repoRoot, '');
  const define: Record<string, string> = {
    'process.env.NEXT_PUBLIC_FASTAPI_FRONTEND_URL': JSON.stringify(
      env.NEXT_PUBLIC_FASTAPI_FRONTEND_URL || '/fastapi',
    ),
  };
  for (const [key, value] of Object.entries(env)) {
    if (key.startsWith('NEXT_PUBLIC_')) {
      define[`process.env.${key}`] = JSON.stringify(value);
    }
  }
  return define;
}

export default defineConfig(({ mode }) => {
  const backend = process.env.VITE_BACKEND_URL ?? loadEnv(mode, repoRoot, '').VITE_BACKEND_URL ?? 'http://127.0.0.1:8000';

  return {
    plugins: [react(), stripBrokenFormioCssSourcemaps()],
    envDir: repoRoot,
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        '@docrouter/sdk': path.resolve(__dirname, '../sdk/src/index.ts'),
        'next/link': path.resolve(__dirname, './src/shims/next-link.tsx'),
        'next/navigation': path.resolve(__dirname, './src/shims/next-navigation.ts'),
        'next/dynamic': path.resolve(__dirname, './src/shims/next-dynamic.tsx'),
      },
    },
    define: nextPublicEnvDefine(mode),
    server: {
      host: 'localhost',
      port: 5173,
      strictPort: true,
      proxy: {
        '/fastapi': {
          target: backend,
          changeOrigin: false,
          rewrite: (p) => p.replace(/^\/fastapi/, ''),
        },
      },
    },
    build: {
      outDir: 'dist-vite',
      emptyOutDir: true,
    },
  };
});
