import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev-only proxy: forward `/api/*` to the sandbox API Gateway so the browser
// sees a same-origin request during local development. Production builds
// talk to VITE_LINA_API_BASE directly (CORS-enabled on the API).
const DEV_API_TARGET = "https://kfrbjzy4l7.execute-api.us-east-1.amazonaws.com";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: DEV_API_TARGET,
        changeOrigin: true,
        rewrite: (p: string) => p.replace(/^\/api/, ""),
        secure: true,
      },
    },
  },
  build: {
    target: "es2022",
    sourcemap: false,
  },
});
