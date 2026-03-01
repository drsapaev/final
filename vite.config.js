import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react({
    jsxImportSource: '@emotion/react',
    babel: {
      plugins: [
        ['@emotion/babel-plugin', { sourceMap: true }]
      ]
    }
  })],
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
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes('node_modules')) {
            if (id.includes('react') || id.includes('react-dom')) {
              return 'react-vendor';
            }
            if (id.includes('@mui')) {
              return 'mui';
            }
            return 'vendor';
          }
        }
      }
    },
    chunkSizeWarningLimit: 1500,
    minify: 'terser',
    sourcemap: process.env.NODE_ENV === 'development'
  },
  optimizeDeps: {
    include: ['@mui/material', '@mui/icons-material', '@emotion/react', '@emotion/styled']
  }
});
