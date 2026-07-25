// vite.config.ts — Phase 0 migration from vite.config.js
// Added: `@/*` path alias (plan 0.2)
// Preserved: all original behavior (proxy, sentry, visualizer, build options)
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { visualizer } from "rollup-plugin-visualizer";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const apiProxyTarget = process.env.VITE_PROXY_TARGET || process.env.BACKEND_URL || "http://localhost:18000";
const wsProxyTarget =
  process.env.VITE_WS_PROXY_TARGET ||
  apiProxyTarget.replace(/^http:/i, "ws:").replace(/^https:/i, "wss:");

// Sentry Vite plugin — optional. Only enabled when:
// 1. @sentry/vite-plugin is installed (run: npm install --save-dev @sentry/vite-plugin)
// 2. SENTRY_AUTH_TOKEN env var is set (CI only)
// 3. VITE_SENTRY_DSN env var is set
// In dev without these, sentryPlugin is an empty array — Vite proceeds normally.
let sentryPlugin: unknown[] = [];
if (process.env.SENTRY_AUTH_TOKEN && process.env.VITE_SENTRY_DSN) {
  try {
    const { sentryVitePlugin } = await import("@sentry/vite-plugin");
    sentryPlugin = [
      sentryVitePlugin({
        org: process.env.SENTRY_ORG,
        project: process.env.SENTRY_PROJECT,
        authToken: process.env.SENTRY_AUTH_TOKEN,
        release: { name: process.env.VITE_APP_VERSION || undefined },
        // Upload source maps only — do NOT inject a new SDK init here,
        // we initialize Sentry ourselves in src/services/sentry.js.
        applicationKey: 'clinic-frontend',
      }),
    ];
  } catch {
    console.warn("[vite.config] @sentry/vite-plugin not installed — skipping source map upload. Install with: npm install --save-dev @sentry/vite-plugin");
  }
}

function createPlugins(enableBundleVisualizer: boolean) {
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
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
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
    // audit/phase-7, BS-46: gate source maps on Sentry env vars.
    // Previously `sourcemap: true` was always on, but the inline comment
    // claimed ".map files are hidden behind source map upload via
    // @sentry/vite plugin (no .map files served to clients)" — that was
    // only true when BOTH SENTRY_AUTH_TOKEN and VITE_SENTRY_DSN were set.
    // Local builds, staging without Sentry, or any build without those
    // env vars emitted .map files into dist/ and nginx served them as
    // static assets (per docker/nginx.conf), leaking original source code.
    // 'hidden' emits .map files but does not reference them in the bundle
    // output, so they are never served to clients. The Sentry plugin
    // (when enabled) still uploads them for de-minification.
    sourcemap: (process.env.SENTRY_AUTH_TOKEN && process.env.VITE_SENTRY_DSN)
      ? 'hidden'
      : false
  },
  // PWA настройки
  define: {
    // audit/phase-7, BS-47: VAPID public key for web push notifications.
    // Previously used Create-React-App convention `REACT_APP_VAPID_PUBLIC_KEY`
    // via `define` polyfill — Vite uses `VITE_` prefix and exposes via
    // `import.meta.env.VITE_*`. The `define` polyfill worked but was
    // undocumented; engineers setting up the project didn't know to set
    // `REACT_APP_VAPID_PUBLIC_KEY` (it wasn't in .env.example).
    // Now uses VITE_VAPID_PUBLIC_KEY with fallback to legacy var for
    // backward compat during migration. Consumers (pwa.ts, MobileNotifications)
    // migrated to import.meta.env.VITE_VAPID_PUBLIC_KEY in the same commit.
    'process.env.REACT_APP_VAPID_PUBLIC_KEY': JSON.stringify(
      process.env.VITE_VAPID_PUBLIC_KEY || process.env.REACT_APP_VAPID_PUBLIC_KEY || ''
    ),
  }
}));
