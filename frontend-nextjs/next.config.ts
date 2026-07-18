import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  allowedDevOrigins: ['127.0.0.1', 'localhost', '[IP_ADDRESS]'],
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
