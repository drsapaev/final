// vitest.config.ts — Phase 0 migration from vitest.config.js
// Added: `@/*` path alias (plan 0.2)
// Retained: jsdom, one fork worker, root and contract-test path resolution.
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}'],
    exclude: [
      'e2e/**',
      'node_modules/**',
      'dist/**',
      '**/playwright.config.*',
    ],
    css: true,
    // Fix: ensure process.cwd() resolves to the frontend directory,
    // not the project root. This fixes contract tests that use
    // path.resolve(process.cwd(), 'src') to read source files.
    root: __dirname,
    // Use one fork worker and reset modules/mocks between files, as Vitest 3 did.
    pool: 'forks',
    maxWorkers: 1,
    isolate: true,
    // Vitest 5 clears mocks by default; preserve the previous history behavior.
    clearMocks: false,
  }
});
