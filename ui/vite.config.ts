import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The host provides these through its import map (design D6); keep them out of the bundle.
export const externals = [
  "react",
  "react-dom",
  "react/jsx-runtime",
  "@kirocrew/app-sdk",
  "@kirocrew/app-sdk/ui",
];

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    lib: {
      entry: "src/index.tsx",
      formats: ["es"],
      fileName: () => "index.mjs",
    },
    rollupOptions: {
      external: externals,
    },
  },
});
