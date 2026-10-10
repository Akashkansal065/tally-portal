import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  /* config options here */
  turbopack: {
    root: path.resolve(__dirname),
  },
  allowedDevOrigins: ['127.0.0.1', 'localhost', '[IP_ADDRESS]'],
  typescript: {
    ignoreBuildErrors: true,
  },
  experimental: {
    optimizePackageImports: ['lucide-react', 'date-fns'],
  },
  async redirects() {
    return [
      {
        source: '/orders',
        destination: '/temporders',
        permanent: true,
      },
      {
        source: '/orders/new',
        destination: '/temporders/new',
        permanent: true,
      },
      {
        source: '/orders/edit/:id',
        destination: '/temporders/edit/:id',
        permanent: true,
      },
    ];
  },
  async headers() {
    return [
      {
        source: '/sw.js',
        headers: [
          {
            key: 'Content-Type',
            value: 'application/javascript; charset=utf-8',
          },
          {
            key: 'Cache-Control',
            value: 'no-cache, no-store, must-revalidate',
          },
          {
            key: 'Service-Worker-Allowed',
            value: '/',
          },
        ],
      },
    ];
  },
};

export default nextConfig;
