import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
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
