import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}'],
    exclude: [
      'e2e/**',
      'node_modules/**',
      'dist/**',
      '**/playwright.config.*',
    ],
    css: true,
    // Отключаем worker процессы для Windows
    pool: 'forks',
    poolOptions: {
      forks: {
        singleFork: true
      }
    },
    // Уменьшаем количество worker'ов до 1
    minThreads: 1,
    maxThreads: 1
  }
});
