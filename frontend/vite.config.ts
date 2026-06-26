import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// Dev: Vite serves the SPA on :5173 and proxies /api to the FastAPI backend
// on :8000. In production FastAPI serves the built bundle from frontend/dist.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
