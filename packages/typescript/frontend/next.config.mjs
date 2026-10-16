/** @type {import('next').NextConfig} */
//import { withPlugins } from 'next-compose-plugins';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import TerserPlugin from 'terser-webpack-plugin';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const DEFAULT_APP_NAME = 'Smart Document Router';

const appNameFromEnv = () =>
  (process.env.APP_NAME && process.env.APP_NAME.trim()) || DEFAULT_APP_NAME;

const appFaviconFromEnv = () => {
  const branded = path.join(__dirname, 'public/branded-favicon.ico');
  if (fs.existsSync(branded)) {
    return '/branded-favicon.ico';
  }
  return '/favicon.ico';
};

// Hostnames (no scheme/port) that may load the dev server, taken from the top-level .env
// so remote dev access doesn't need a hardcoded IP.
const devOriginHosts = (urls) => {
  const hosts = new Set(['127.0.0.1']);
  for (const url of urls) {
    try {
      hosts.add(new URL(url).hostname);
    } catch {
      // Unset or relative (e.g. '/fastapi') — nothing to add
    }
  }
  return [...hosts];
};

const nextConfig = {
  env: {
    NEXT_PUBLIC_FASTAPI_FRONTEND_URL: process.env.PUBLIC_API_URL || '/fastapi',
    NEXT_PUBLIC_APP_NAME: appNameFromEnv(),
    NEXT_PUBLIC_APP_FAVICON: appFaviconFromEnv(),
  },
  output: 'standalone',
  allowedDevOrigins: devOriginHosts([process.env.NEXTAUTH_URL, process.env.PUBLIC_API_URL]),
  transpilePackages: ['@tsed/react-formio', '@tsed/tailwind-formio', '@docrouter/sdk'],
  // Include files from monorepo parent for file: dependencies (production build)
  outputFileTracingRoot: path.join(__dirname, '..'),
  // Proxy /fastapi/* to the backend — only active in local dev (npm run dev).
  // Strip the /fastapi prefix when forwarding, matching deploy/compose/nginx.conf
  // (location /fastapi/ { proxy_pass http://backend:8000/; }).
  // Routes are registered at /v0/... on FastAPI, not /fastapi/v0/...
  // In Docker Compose and Kubernetes, nginx/ingress intercepts /fastapi/ before
  // Next.js sees it, so this rewrite never fires in deployed environments.
  async rewrites() {
    return [{
      source: '/fastapi/:path*',
      destination: 'http://localhost:8000/:path*',
    }];
  },
  // Cache for hashed static assets (chunks, CSS); 8h max so post-midnight release is picked up next day
  async headers() {
    return [
      {
        source: '/_next/static/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=28800',
          },
        ],
      },
    ];
  },
  // Webpack config for compatibility (Turbopack will use this as fallback)
  webpack: (config) => {
    // Use SDK TypeScript source so new APIs (e.g. OCR export) are always current; `file:../sdk`
    // otherwise resolves to package `exports` → stale `dist/` until `npm run build` in sdk/.
    config.resolve.alias = {
      ...config.resolve.alias,
      '@docrouter/sdk': path.resolve(__dirname, '../sdk/src/index.ts'),
    };

    if (config.optimization) {
      config.optimization.minimizer = [
        new TerserPlugin({
          terserOptions: {
            // Your Terser options here
          },
          exclude: /pdf.worker.min.mjs/,
        }),
      ];
    }

    // Handle ESM modules - exclude PDF.js worker
    config.module.rules.push({
      test: /\.m?js$/,
      exclude: /pdf\.worker\.min\.mjs$/,
      type: 'javascript/auto',
      resolve: {
        fullySpecified: false,
      },
    });

    // Handle @tsed/tailwind-formio ESM/CommonJS mismatch
    config.resolve.extensionAlias = {
      '.js': ['.js', '.ts', '.tsx'],
      '.mjs': ['.mjs'],
    };

    // Configure webpack to handle ESM in @tsed packages
    config.module.rules.push({
      test: /node_modules\/@tsed\/.*\.modern\.js$/,
      type: 'javascript/auto',
      parser: {
        sourceType: 'module',
      },
    });

    return config;
  },
};

export default nextConfig;
