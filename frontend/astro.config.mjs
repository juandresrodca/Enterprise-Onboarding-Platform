// @ts-check
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

// The dev server proxies /api to the FastAPI backend so cookies stay
// same-origin. In production, nginx (see docker/) does the same.
export default defineConfig({
  // For GitHub Pages project sites set PUBLIC_BASE_PATH=/<repo-name> at build
  // time (see .github/workflows/deploy-pages.yml). Defaults to "/".
  base: process.env.PUBLIC_BASE_PATH || "/",
  server: { port: 4321 },
  vite: {
    plugins: [tailwindcss()],
    server: {
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: false,
        },
      },
    },
  },
});
