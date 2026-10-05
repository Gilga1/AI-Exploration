import { defineConfig } from "vite";

export default defineConfig({
  root: ".",
  server: {
    port: 4177,
    host: true,
  },
  build: {
    outDir: "preview-dist",
    emptyOutDir: true,
    rollupOptions: {
      input: "preview/index.html",
    },
  },
});
