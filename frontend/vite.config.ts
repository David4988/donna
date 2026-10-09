import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // The backend only accepts browser connections from this exact address,
  // so fail loudly instead of silently moving to another port.
  server: { port: 5173, strictPort: true },
});
