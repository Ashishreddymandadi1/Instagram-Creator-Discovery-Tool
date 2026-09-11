/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    return [{ source: "/api/backend/:path*", destination: `${api}/api/:path*` }];
  },
};
export default nextConfig;
