/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://ai-docs-app_backend_1:8000/api/:path*', // docker container name
      },
    ];
  },
};

module.exports = nextConfig;
