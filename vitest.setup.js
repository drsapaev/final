import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

const storageMock = () => {
  const store = new Map();
  return {
    getItem: vi.fn((key) => (store.has(key) ? store.get(key) : null)),
    setItem: vi.fn((key, value) => {
      store.set(key, String(value));
    }),
    removeItem: vi.fn((key) => {
      store.delete(key);
    }),
    clear: vi.fn(() => {
      store.clear();
    }),
  };
};

Object.defineProperty(globalThis, 'localStorage', {
  value: storageMock(),
  configurable: true,
});

Object.defineProperty(globalThis, 'sessionStorage', {
  value: storageMock(),
  configurable: true,
});

// Jest compatibility shim for existing tests
globalThis.jest = vi;
