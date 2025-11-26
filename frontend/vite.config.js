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
          // Vendor chunks - более детальное разделение
          if (id.includes('node_modules')) {
            // React ecosystem
            if (id.includes('react') || id.includes('react-dom') || id.includes('react-router')) {
              return 'react-vendor';
            }
            
            // Material-UI отдельно (очень большой)
            if (id.includes('@mui')) {
              return 'mui';
            }
            
            // Иконки отдельно
            if (id.includes('lucide-react') || id.includes('@mui/icons-material')) {
              return 'icons';
            }
            
            // HTTP клиенты
            if (id.includes('axios') || id.includes('fetch') || id.includes('http')) {
              return 'http';
            }
            
            // Утилиты и библиотеки
            if (id.includes('lodash') || id.includes('moment') || id.includes('date-fns')) {
              return 'utils';
            }
            
            // Остальные vendor библиотеки
            return 'vendor';
          }
          
          // App chunks по функциональности - более детальное разделение
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
            // macOS UI компоненты отдельно
            if (id.includes('/ui/macos/')) {
              return 'macos-ui';
            }
            
            // Медицинские компоненты
            if (id.includes('medical') || id.includes('laboratory')) {
              return 'medical-components';
            }
            
            // Админ компоненты
            if (id.includes('admin') || id.includes('auth')) {
              return 'admin-components';
            }
            
            // PWA компоненты
            if (id.includes('pwa') || id.includes('mobile')) {
              return 'pwa-components';
            }
            
            // AI компоненты
            if (id.includes('ai')) {
              return 'ai-components';
            }
            
            // Таблицы отдельно (могут быть большими)
            if (id.includes('table') || id.includes('Table')) {
              return 'table-components';
            }
            
            // Формы отдельно
            if (id.includes('form') || id.includes('Form') || id.includes('input') || id.includes('Input')) {
              return 'form-components';
            }
            
            return 'common-components';
          }
          
          // Хуки и утилиты отдельно
          if (id.includes('/hooks/') || id.includes('/utils/') || id.includes('/contexts/')) {
            return 'utils';
          }
          
          // Стили отдельно
          if (id.includes('.css') || id.includes('.scss')) {
            return 'styles';
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
