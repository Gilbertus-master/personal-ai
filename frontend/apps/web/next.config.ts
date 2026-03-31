import type { NextConfig } from 'next';

const isTauriBuild = process.env.TAURI_BUILD === '1';

const nextConfig: NextConfig = {
  output: isTauriBuild ? 'export' : 'standalone',
  images: { unoptimized: true },
  allowedDevOrigins: ['172.17.44.2'],
  transpilePackages: [
    '@gilbertus/ui',
    '@gilbertus/rbac',
    '@gilbertus/api-client',
    '@gilbertus/i18n',
  ],
};

export default nextConfig;
