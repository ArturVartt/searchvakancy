import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // слушать 0.0.0.0 — нужно для запуска в Docker
    port: 5173,
  },
});
