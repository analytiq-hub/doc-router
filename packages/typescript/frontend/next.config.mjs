/** @type {import('next').NextConfig} */
//import { withPlugins } from 'next-compose-plugins';
import path from 'path';
import { fileURLToPath } from 'url';
import TerserPlugin from 'terser-webpack-plugin';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const nextConfig = {
  output: 'standalone',
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
