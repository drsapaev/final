import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { visualizer } from "rollup-plugin-visualizer";

const apiProxyTarget = process.env.VITE_PROXY_TARGET || process.env.BACKEND_URL || "http://localhost:18000";
const wsProxyTarget =
  process.env.VITE_WS_PROXY_TARGET ||
  apiProxyTarget.replace(/^http:/i, "ws:").replace(/^https:/i, "wss:");

function createPlugins(enableBundleVisualizer) {
  const plugins = [react()];

  if (enableBundleVisualizer) {
    plugins.push(
      visualizer({
        filename: "dist/bundle-visualizer.html",
        template: "treemap",
        gzipSize: true,
        brotliSize: true,
        open: false,
      }),
    );
  }

  return plugins;
}

export default defineConfig(({ mode }) => ({
  plugins: createPlugins(
    mode === "analyze" ||
      process.env.ANALYZE_BUNDLE === "true" ||
      process.env.VITE_BUNDLE_ANALYZE === "true",
  ),
  server: {
    port: 5173,
    host: '0.0.0.0',
    strictPort: false,
    hmr: false,
    watch: {
      usePolling: true,
      interval: 1000
    },
    allowedHosts: true,
    proxy: {
      // HTTP API -> target backend (overridable for isolated restore rehearsal)
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
        secure: false,
      },
      // WebSocket -> target backend (overridable for isolated restore rehearsal)
      "/ws": {
        target: wsProxyTarget,
        ws: true,
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    // Увеличиваем лимит для больших файлов (vendor чанк может быть большим)
    chunkSizeWarningLimit: 1500,
    // Минификация
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true
      }
    },
    // Source maps только для development
    sourcemap: process.env.NODE_ENV === 'development'
  },
  // PWA настройки
  define: {
    // Переменные окружения для PWA
    'process.env.REACT_APP_VAPID_PUBLIC_KEY': JSON.stringify(process.env.REACT_APP_VAPID_PUBLIC_KEY || ''),
  }
}));
