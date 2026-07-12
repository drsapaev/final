import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Очищаем DOM после каждого теста
afterEach(() => {
  cleanup();
});

if (typeof window !== 'undefined') {
  // Mock window.matchMedia
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(query => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(), // deprecated
      removeListener: vi.fn(), // deprecated
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  // Mock localStorage
  const localStorageMock = {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  };
  Object.defineProperty(window, 'localStorage', {
    value: localStorageMock,
    writable: true,
    configurable: true,
  });
  Object.defineProperty(globalThis, 'localStorage', {
    value: localStorageMock,
    writable: true,
    configurable: true,
  });

  // PR-39 / P0-2: Mock sessionStorage (tokens migrated from localStorage)
  // Use a store-backed mock so tests that call setItem then getItem work
  // (the tokenManager tests use vi.fn() expectations, but NotificationPrompt
  // and other UI tests rely on actual storage behavior).
  const _sessionStore = {};
  const sessionStorageMock = {
    getItem: vi.fn((key) => _sessionStore[key] ?? null),
    setItem: vi.fn((key, value) => { _sessionStore[key] = String(value); }),
    removeItem: vi.fn((key) => { delete _sessionStore[key]; }),
    clear: vi.fn(() => { for (const k of Object.keys(_sessionStore)) delete _sessionStore[k]; }),
  };
  Object.defineProperty(window, 'sessionStorage', {
    value: sessionStorageMock,
    writable: true,
    configurable: true,
  });
  Object.defineProperty(globalThis, 'sessionStorage', {
    value: sessionStorageMock,
    writable: true,
    configurable: true,
  });
}

// Mock IntersectionObserver
global.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));
