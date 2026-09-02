import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        timeout: 0,
        proxyTimeout: 0,
        configure(proxy) {
          proxy.on("error", () => undefined);
        },
      },
    },
  },
  test: {
    exclude: ["**/node_modules/**", "**/dist/**", "**/tests/e2e/**"],
  },
});
