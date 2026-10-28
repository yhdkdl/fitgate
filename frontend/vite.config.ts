/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    watch: {
      usePolling: true,
    },
    proxy: {
      "/api": {
        target: process.env.API_PROXY_TARGET || "http://backend:8000",
        changeOrigin: false,
        configure: (proxy) => {
          proxy.on("proxyReq", (proxyReq, req) => {
            if (req.headers.host) {
              proxyReq.setHeader("Host", req.headers.host);
              proxyReq.setHeader("X-Forwarded-Host", req.headers.host);
            }
          });
        },
      },
      "/media": {
        target: process.env.API_PROXY_TARGET || "http://backend:8000",
        changeOrigin: false,
        configure: (proxy) => {
          proxy.on("proxyReq", (proxyReq, req) => {
            if (req.headers.host) {
              proxyReq.setHeader("Host", req.headers.host);
              proxyReq.setHeader("X-Forwarded-Host", req.headers.host);
            }
          });
        },
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    testTimeout: 15000,
  },
});
