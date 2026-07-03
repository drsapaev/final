import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { visualizer } from "rollup-plugin-visualizer";
import { sentryVitePlugin } from "@sentry/vite-plugin";

const apiProxyTarget = process.env.VITE_PROXY_TARGET || process.env.BACKEND_URL || "http://localhost:18000";
const wsProxyTarget =
  process.env.VITE_WS_PROXY_TARGET ||
  apiProxyTarget.replace(/^http:/i, "ws:").replace(/^https:/i, "wss:");

// Sentry Vite plugin — only enabled when DSN + auth token are set.
// In dev, this is a no-op. In CI/production builds, it uploads source maps
// so Sentry can de-minify stack traces.
const sentryPlugin =
  process.env.SENTRY_AUTH_TOKEN && process.env.VITE_SENTRY_DSN
    ? [
        sentryVitePlugin({
          org: process.env.SENTRY_ORG,
          project: process.env.SENTRY_PROJECT,
          authToken: process.env.SENTRY_AUTH_TOKEN,
          release: { name: process.env.VITE_APP_VERSION || undefined },
          // Upload source maps only — do NOT inject a new SDK init here,
          // we initialize Sentry ourselves in src/services/sentry.js.
          applicationKey: 'clinic-frontend',
        }),
      ]
    : [];

function createPlugins(enableBundleVisualizer) {
  const plugins = [react(), ...sentryPlugin];

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
    // Source maps: enable for production so Sentry can de-minify traces.
    // Files are hidden behind source map upload via @sentry/vite plugin
    // (no .map files served to clients).
    sourcemap: true
  },
  // PWA настройки
  define: {
    // Переменные окружения для PWA
    'process.env.REACT_APP_VAPID_PUBLIC_KEY': JSON.stringify(process.env.REACT_APP_VAPID_PUBLIC_KEY || ''),
  }
}));
