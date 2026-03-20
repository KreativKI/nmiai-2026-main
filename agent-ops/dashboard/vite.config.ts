import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    proxy: {
      "/api/nlp-health": {
        target: "https://tripletex-agent-795548831221.europe-west4.run.app",
        changeOrigin: true,
        rewrite: (path) => path.replace("/api/nlp-health", "/solve"),
      },
    },
  },
});
