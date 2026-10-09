import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  optimizeDeps: { entries: ["index.html"] },
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
    watch: {
      ignored: [
        "**/criminial--network--analysis-/**",
        "**/.runtime/**",
        "**/venv/**",
        "**/backend/**",
        "**/tmp/**",
        "**/test_data/**",
      ],
    },
  },
});
