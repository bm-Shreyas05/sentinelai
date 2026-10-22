import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// `npm run dev` proxies API calls to a local `python -m sentinelai serve --demo`.
const api = process.env.SENTINEL_API ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/v1": api, "/health": api, "/docs": api, "/openapi.json": api } },
  build: { chunkSizeWarningLimit: 900 },
});
