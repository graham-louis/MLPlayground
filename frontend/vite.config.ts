import { TanStackRouterVite } from "@tanstack/router-plugin/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [
    TanStackRouterVite(),
    react(),
  ],
  server: {
    proxy: {
      "/api": {
        // Inside Docker the backend is reachable via its service name.
        // Set BACKEND_URL=http://backend:8000 in the compose override.
        // Falls back to localhost for running Vite directly on the host.
        target: process.env.BACKEND_URL ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
})
