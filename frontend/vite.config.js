import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '127.0.0.1',
    strictPort: false,
    hmr: false,
    watch: {
      usePolling: true,
      interval: 1000
    },
    allowedHosts: ['localhost', '127.0.0.1'],
    proxy: {
      // HTTP API -> http://localhost:8000
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
      },
      // WebSocket -> ws://localhost:8000
      "/ws": {
        target: "ws://localhost:8000",
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
  optimizeDeps: {
    // Only include packages that are in frontend/package.json dependencies
    include: ['@mui/material']
  },
  // PWA настройки
  define: {
    // Переменные окружения для PWA
    'process.env.REACT_APP_VAPID_PUBLIC_KEY': JSON.stringify(process.env.REACT_APP_VAPID_PUBLIC_KEY || ''),
  }
});
