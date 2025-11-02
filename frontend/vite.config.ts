import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  const env = loadEnv(mode, process.cwd(), "");

  // Read API base from env; allow either absolute URL (recommended for dev)
  // or relative path (used at runtime in production behind the same domain).
  const rawApiBase = env.VITE_API_BASE_URL || "";
  const apiBaseUrl = rawApiBase || "http://localhost:8000";

  // Ensure proxy target is always an absolute URL to avoid `base.invalid`
  // when someone accidentally sets VITE_API_BASE_URL to a relative path like "/api".
  const proxyTarget = /^https?:\/\//.test(apiBaseUrl)
    ? apiBaseUrl
    : "http://localhost:8000";

  const wsBaseUrl = env.VITE_WS_BASE_URL ||
                    proxyTarget.replace(/^http/, "ws") ||
                    "ws://localhost:8000";

  return {
    server: {
      host: "::",
      port: 8080,
      fs: {
        // Allow access to frontend directory and subdirectories
        allow: [
          path.resolve(__dirname, "."),  // Frontend root (for index.html)
          path.resolve(__dirname, "./client"),
          path.resolve(__dirname, "./shared"),
          path.resolve(__dirname, "./public"),
        ],
        deny: [".env", ".env.*", "*.{crt,pem}", "**/.git/**"],
      },
      // Proxy API requests to external backend (FastAPI)
      // Configure VITE_API_BASE_URL in .env file to point to your backend
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => path, // Keep /api prefix
        },
        "/upload": {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => path, // Keep /upload
        },
        "/ws": {
          target: wsBaseUrl,
          ws: true,
          changeOrigin: true,
          rewrite: (path) => path, // Keep /ws prefix
        },
      },
    },
    build: {
      outDir: "dist/spa",
    },
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./client"),
        "@shared": path.resolve(__dirname, "./shared"),
      },
    },
  };
});
