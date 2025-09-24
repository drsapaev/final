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
        manualChunks: (id) => {
          // Vendor chunks
          if (id.includes('node_modules')) {
            if (id.includes('react') || id.includes('react-dom')) {
              return 'react-vendor';
            }
            if (id.includes('react-router')) {
              return 'router';
            }
            if (id.includes('@mui')) {
              return 'mui';
            }
            if (id.includes('lucide-react')) {
              return 'icons';
            }
            if (id.includes('axios') || id.includes('fetch')) {
              return 'http';
            }
            return 'vendor';
          }
          
          // App chunks по функциональности
          if (id.includes('/pages/')) {
            if (id.includes('Admin') || id.includes('Settings') || id.includes('Audit')) {
              return 'admin-pages';
            }
            if (id.includes('Doctor') || id.includes('Cardiologist') || id.includes('Dermatologist') || id.includes('Dentist')) {
              return 'doctor-pages';
            }
            if (id.includes('Patient') || id.includes('Mobile')) {
              return 'patient-pages';
            }
            if (id.includes('Payment') || id.includes('Cashier')) {
              return 'payment-pages';
            }
            if (id.includes('Queue') || id.includes('Display')) {
              return 'queue-pages';
            }
            return 'other-pages';
          }
          
          if (id.includes('/components/')) {
            if (id.includes('medical') || id.includes('laboratory')) {
              return 'medical-components';
            }
            if (id.includes('admin') || id.includes('auth')) {
              return 'admin-components';
            }
            if (id.includes('pwa') || id.includes('mobile')) {
              return 'pwa-components';
            }
            if (id.includes('ai')) {
              return 'ai-components';
            }
            return 'common-components';
          }
        }
      }
    },
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
    // Принудительно предварительно собираем Material-UI
    include: ['@mui/material', '@mui/icons-material', '@emotion/react', '@emotion/styled']
  },
  // PWA настройки
  define: {
    // Переменные окружения для PWA
    'process.env.REACT_APP_VAPID_PUBLIC_KEY': JSON.stringify(process.env.REACT_APP_VAPID_PUBLIC_KEY || ''),
  }
});
