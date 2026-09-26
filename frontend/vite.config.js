import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Local dev: `npm run dev` proxies /api/* to the FastAPI backend on :8000, so the app
// works with relative fetch("/api/...") calls exactly like the production build does
// (where VITE_API_BASE points at the deployed backend instead — see src/api.js).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
