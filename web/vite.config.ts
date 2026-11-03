import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Em desenvolvimento, o Vite repassa as chamadas para a API local: a página e a API
// parecem estar no mesmo endereço, então a API continua sem CORS.
const API = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/chat": API, "/handoff": API, "/health": API },
  },
  build: { outDir: "dist", sourcemap: false },
});
