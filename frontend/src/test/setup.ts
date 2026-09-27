import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Очищаем DOM после каждого теста
afterEach(() => {
  cleanup();
  // Safety net: ensure real timers are restored after each test.
  // Some test files call vi.useFakeTimers() but forget vi.useRealTimers()
  // in their afterEach. In singleFork mode, fake timers leak across files
  // and can cause vitest's internal shutdown to hang indefinitely.
  vi.useRealTimers();
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

  // Mock localStorage — store-backed so tests that write then read
  // (e.g. useFinance cache persistence) work without per-test spy setup.
  // `vi.fn()` wrappers preserve `.mockImplementation` override capability
  // for tests that need to control the return value explicitly.
  const _localStorageStore: Record<string, string> = {};
  const localStorageMock = {
    getItem: vi.fn((key: string) => _localStorageStore[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { _localStorageStore[key] = String(value); }),
    removeItem: vi.fn((key: string) => { delete _localStorageStore[key]; }),
    clear: vi.fn(() => { for (const k of Object.keys(_localStorageStore)) delete _localStorageStore[k]; }),
    // Round-9 (PR #3362 review P1-2): Storage-faithful enumeration — the
    // per-attempt attempt-state discovery scans keys by prefix, so the
    // mock must implement length + key(i) like a real Storage.
    get length() { return Object.keys(_localStorageStore).length; },
    key(index: number) { return Object.keys(_localStorageStore)[index] ?? null; },
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
  const _sessionStore: Record<string, string> = {};
  const sessionStorageMock = {
    getItem: vi.fn((key) => _sessionStore[key] ?? null),
    setItem: vi.fn((key, value) => { _sessionStore[key] = String(value); }),
    removeItem: vi.fn((key) => { delete _sessionStore[key]; }),
    clear: vi.fn(() => { for (const k of Object.keys(_sessionStore)) delete _sessionStore[k]; }),
    // Round-8: Storage-faithful enumeration (same reason as localStorage).
    get length() { return Object.keys(_sessionStore).length; },
    key(index: number) { return Object.keys(_sessionStore)[index] ?? null; },
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
