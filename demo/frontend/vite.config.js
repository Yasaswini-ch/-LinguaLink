import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  // Streamlit serves a custom component's static files under its own
  // nested path (e.g. /component/lingualink_ui.<hash>/), not at the site
  // root — absolute asset paths ("/assets/...") 404 there, so that build
  // needs relative paths instead. The standalone HTTP build (served at a
  // real domain root, e.g. Vercel) keeps the default absolute base.
  base: mode === "streamlit" ? "./" : "/",
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
}));
