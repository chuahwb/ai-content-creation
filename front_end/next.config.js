/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  
  // Enable strict checks for production builds
  eslint: {
    // Enable ESLint during builds
    ignoreDuringBuilds: false,
    dirs: ['src'],
  },
  typescript: {
    // Enable TypeScript strict checking during builds
    ignoreBuildErrors: false,
  },

  // Optimize builds
  swcMinify: true,
  compiler: {
    // Remove console.log in production
    removeConsole: process.env.NODE_ENV === 'production',
  },

  // Environment variables
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
  },

  // Security headers
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block',
          },
        ],
      },
    ];
  },

  // Image optimization
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
    formats: ['image/webp', 'image/avif'],
    minimumCacheTTL: 60,
  },

  // API rewrites for backend communication
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
  
  // Performance optimizations
  experimental: {
    // Increase timeout for long-running operations like caption generation
    proxyTimeout: 60000, // 60 seconds
    
    // Enable modern JavaScript features
    esmExternals: true,
    
    // Optimize bundle splitting
    optimizeCss: true,
  },

  // Webpack optimizations
  webpack: (config, { buildId, dev, isServer, defaultLoaders, webpack }) => {
    // Production optimizations
    if (!dev) {
      config.optimization.splitChunks = {
        chunks: 'all',
        cacheGroups: {
          vendor: {
            test: /[\\/]node_modules[\\/]/,
            name: 'vendors',
            chunks: 'all',
          },
        },
      };
    }

    return config;
  },

  // Output file tracing for standalone builds
  outputFileTracing: true,

  // Power optimizations
  poweredByHeader: false,
};

module.exports = nextConfig; 