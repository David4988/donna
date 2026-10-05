import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Port 1420 is what Tauri's devUrl and the core's Origin allowlist expect.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 1420, strictPort: true, host: "localhost" },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
