import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 開發時把 API 轉給本機的 yomitoki serve（預設 127.0.0.1:8765）
const backend = process.env.YOMITOKI_BACKEND ?? "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: true },
      "/fonts": { target: backend, changeOrigin: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
