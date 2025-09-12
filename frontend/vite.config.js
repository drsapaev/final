import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react({
    // Исправляем проблемы с Material-UI
    jsxImportSource: '@emotion/react',
    babel: {
      plugins: [
        ['@emotion/babel-plugin', { sourceMap: true }]
      ]
    }
  })],
  server: {
    port: 5173,
    host: '0.0.0.0',
    strictPort: true,
    hmr: {
      port: 5173,
      host: 'localhost',
      clientPort: 5173
    },
    watch: {
      usePolling: true,
      interval: 1000
    },
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
    // PWA оптимизации
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          router: ['react-router-dom'],
          ui: ['lucide-react'],
          mui: ['@mui/material', '@mui/icons-material']
        }
      }
    },
    // Увеличиваем лимит для больших файлов
    chunkSizeWarningLimit: 1000
  },
  optimizeDeps: {
    // Принудительно предварительно собираем Material-UI
    include: ['@mui/material', '@mui/icons-material', '@emotion/react', '@emotion/styled']
  },
  // PWA настройки
  define: {
    // Переменные окружения для PWA
    'process.env.REACT_APP_VAPID_PUBLIC_KEY': JSON.stringify(process.env.REACT_APP_VAPID_PUBLIC_KEY || ''),
  }
});
