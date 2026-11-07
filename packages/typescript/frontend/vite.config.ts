import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '../../..');

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
    plugins: [react()],
    envDir: repoRoot,
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        '@docrouter/sdk': path.resolve(__dirname, '../sdk/src/index.ts'),
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
