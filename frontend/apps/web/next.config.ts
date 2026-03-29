import type { NextConfig } from 'next';

const isTauriBuild = process.env.TAURI_BUILD === '1';

const nextConfig: NextConfig = {
  ...(isTauriBuild && { output: 'export' }),
  images: { unoptimized: true },
  transpilePackages: [
    '@gilbertus/ui',
    '@gilbertus/rbac',
    '@gilbertus/api-client',
    '@gilbertus/i18n',
  ],
  env: {
    NEXT_PUBLIC_GILBERTUS_API_URL:
      process.env.GILBERTUS_API_URL || 'http://127.0.0.1:8000',
  },
};

export default nextConfig;
