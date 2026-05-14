import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Minimal server output for production Docker (Railway).
  // Produces .next/standalone with server.js + traced node_modules.
  output: "standalone",
};

export default nextConfig;
