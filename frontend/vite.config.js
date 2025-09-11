import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    strictPort: true,
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
          ui: ['lucide-react']
        }
      }
    },
    // Увеличиваем лимит для больших файлов
    chunkSizeWarningLimit: 1000
  },
  // PWA настройки
  define: {
    // Переменные окружения для PWA
    'process.env.REACT_APP_VAPID_PUBLIC_KEY': JSON.stringify(process.env.REACT_APP_VAPID_PUBLIC_KEY || ''),
  }
});
