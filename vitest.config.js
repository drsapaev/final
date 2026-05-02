import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ['react', 'react-dom'],
    alias: {
      react: path.resolve(__dirname, 'node_modules/react'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
      'react-dom/client': path.resolve(__dirname, 'node_modules/react-dom/client'),
      '@testing-library/react': path.resolve(
        __dirname,
        'node_modules/@testing-library/react'
      ),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['frontend/src/**/*.test.{js,jsx}'],
    setupFiles: ['vitest.setup.js'],
  },
});
