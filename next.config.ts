import type { NextConfig } from "next";

// Node.js 22+ exposes a broken localStorage global that crashes libraries
// like 'debug' (used by recharts/reactflow dependencies) during SSR.
if (typeof globalThis.localStorage !== 'undefined' && typeof globalThis.localStorage.getItem !== 'function') {
  (globalThis as any).localStorage = {
    getItem: () => null,
    setItem: () => {},
    removeItem: () => {},
    clear: () => {},
    key: () => null,
    length: 0,
  };
}

const nextConfig: NextConfig = {
  webpack: (config) => {
    // MediaPipe WASM bundle uses dynamic requires that bundlers can't resolve.
    // Tell webpack to not parse it — it's a pre-built self-contained bundle.
    config.resolve.alias = {
      ...config.resolve.alias,
    };
    return config;
  },
};

export default nextConfig;
