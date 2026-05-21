import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  outputFileTracingIncludes: {
    '/api/**': ['./messages.db'],
    '/': ['./messages.db'],
    '/post/**': ['./messages.db'],
  },
};

export default nextConfig;
