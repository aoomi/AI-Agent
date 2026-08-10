import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      vue: fileURLToPath(new URL("./node_modules/vue", import.meta.url)),
    },
    dedupe: ["vue"],
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api/v1": { target: "http://127.0.0.1:8080", changeOrigin: true },
      "/api": { target: "http://127.0.0.1:8787", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8080", changeOrigin: true },
    },
  },
});
