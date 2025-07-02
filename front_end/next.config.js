/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
  },
  images: {
    domains: ['localhost', 'api'],
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8000',
        pathname: '/api/v1/files/**',
      },
      {
        protocol: 'http',
        hostname: 'api',
        port: '8000',
        pathname: '/api/v1/files/**',
      },
    ],
  },
  async rewrites() {
    // Use INTERNAL_API_URL for server-side rewrites within Docker
    // Fall back to NEXT_PUBLIC_API_URL for local development
    const internalApiUrl = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    
    return [
      {
        source: '/api/:path*',
        destination: `${internalApiUrl}/api/:path*`,
      },
    ];
  },
  
  // Increase timeout for long-running operations like caption generation
  experimental: {
    proxyTimeout: 60000, // 60 seconds
  },
};

module.exports = nextConfig; 