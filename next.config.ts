import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // `server.py` hosts the generated files directly on the Raspberry Pi.
  output: "export",
  experimental: {
    agentFeedback: true,
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
