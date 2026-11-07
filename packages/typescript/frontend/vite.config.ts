import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Doc Router browser calls FastAPI under /fastapi (same as Next dev rewrites).
const backend = process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@docrouter/sdk': path.resolve(__dirname, '../sdk/src/index.ts'),
    },
  },
  define: {
    'process.env.NEXT_PUBLIC_FASTAPI_FRONTEND_URL': JSON.stringify('/fastapi'),
  },
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
});
