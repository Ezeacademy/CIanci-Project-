import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async rewrites() {
    const backendUrl = (
      process.env.BACKEND_INTERNAL_URL || "http://backend:8000"
    ).replace(/\/$/, "");
    return [
      {
        source: "/admin",
        destination: `${backendUrl}/admin/`,
      },
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
      {
        source: "/admin/:path*",
        destination: `${backendUrl}/admin/:path*/`,
      },
      {
        source: "/static/:path*",
        destination: `${backendUrl}/static/:path*`,
      },
    ];
  },
};

export default nextConfig;
