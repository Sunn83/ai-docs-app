module.exports = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://144.91.115.48:8000/api/:path*',
      },
    ];
  },
};
