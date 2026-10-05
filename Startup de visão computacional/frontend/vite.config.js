import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ command }) => ({
  plugins: [vue()],
  base: command === "build" ? "/static/" : "/",
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
}));
