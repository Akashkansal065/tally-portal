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
  }
};

export default nextConfig;
