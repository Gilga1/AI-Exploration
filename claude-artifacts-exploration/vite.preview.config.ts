import { defineConfig } from "vite";

export default defineConfig({
  root: ".",
  server: {
    port: 4178,
    open: "/preview/index.html",
  },
  preview: {
    port: 4178,
  },
});
