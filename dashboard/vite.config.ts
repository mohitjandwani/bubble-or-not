import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Pass 1 dashboard: dev server proxies API calls straight through to the
// in-memory backend so the SPA can be developed against fixtures or a live
// server interchangeably.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/state": "http://localhost:8000",
      "/events": "http://localhost:8000",
      "/evidence": "http://localhost:8000",
      "/rescore": "http://localhost:8000",
    },
  },
});
