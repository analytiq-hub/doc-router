import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, loadEnv, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

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

function pick(env: Record<string, string>, ...keys: string[]): string {
  for (const key of keys) {
    const v = env[key];
    if (typeof v === 'string' && v.trim()) return v.trim();
  }
  return '';
}

/** Inject `VITE_*` from repo root `.env` (operator aliases: `PUBLIC_API_URL`, `APP_NAME`, `APP_FAVICON`). */
function publicEnvDefine(mode: string): Record<string, string> {
  const env = loadEnv(mode, repoRoot, '');
  const fastApi = pick(env, 'VITE_FASTAPI_FRONTEND_URL', 'PUBLIC_API_URL') || '/fastapi';
  const appName = pick(env, 'VITE_APP_NAME', 'APP_NAME');
  const appFavicon = pick(env, 'VITE_APP_FAVICON', 'APP_FAVICON');

  const pairs: Record<string, string> = {
    VITE_FASTAPI_FRONTEND_URL: fastApi,
    VITE_APP_NAME: appName,
    VITE_APP_FAVICON: appFavicon,
  };

  const define: Record<string, string> = {};
  for (const [key, value] of Object.entries(pairs)) {
    define[`import.meta.env.${key}`] = JSON.stringify(value);
    define[`process.env.${key}`] = JSON.stringify(value);
  }
  for (const [key, value] of Object.entries(env)) {
    if (key.startsWith('VITE_') && !(key in pairs)) {
      define[`import.meta.env.${key}`] = JSON.stringify(value);
      define[`process.env.${key}`] = JSON.stringify(value);
    }
  }
  return define;
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, repoRoot, '');
  const backend =
    process.env.VITE_BACKEND_URL ?? env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000';

  return {
    plugins: [react(), tailwindcss(), stripBrokenFormioCssSourcemaps()],
    envDir: repoRoot,
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        '@docrouter/sdk': path.resolve(__dirname, '../sdk/src/index.ts'),
      },
    },
    define: publicEnvDefine(mode),
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
