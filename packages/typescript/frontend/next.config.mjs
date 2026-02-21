/** @type {import('next').NextConfig} */
//import { withPlugins } from 'next-compose-plugins';
import path from 'path';
import { fileURLToPath } from 'url';
import TerserPlugin from 'terser-webpack-plugin';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const nextConfig = {
  transpilePackages: ['@tsed/react-formio', '@tsed/tailwind-formio', '@docrouter/sdk'],
  // Include files from monorepo parent for file: dependencies (production build)
  outputFileTracingRoot: path.join(__dirname, '..'),
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
