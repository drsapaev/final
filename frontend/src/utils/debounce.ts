// src/utils/debounce.ts
// Phase 1 — migrated from .js. Pure function + React hook; types added.

import { useCallback, useRef } from 'react';

/**
 * Debounce utility function.
 * Delays execution of a function until after a specified wait time has elapsed
 * since the last time it was invoked.
 *
 * Note: `this` is intentionally typed as `unknown` — the debounced wrapper
 * forwards whatever `this` it is called with. Callers that rely on `this`
 * binding should use arrow functions or explicit `.bind()`.
 */
export function debounce<TArgs extends unknown[]>(
  func: (...args: TArgs) => void,
  wait: number = 300,
  immediate: boolean = false,
): (...args: TArgs) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null;

  return function executedFunction(this: unknown, ...args: TArgs): void {
    const context = this;

    const later = (): void => {
      timeout = null;
      if (!immediate) func.apply(context, args);
    };

    const callNow = immediate && !timeout;

    if (timeout !== null) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(later, wait);

    if (callNow) func.apply(context, args);
  };
}

/**
 * Hook wrapper for debounce to use in React components.
 * The returned callback is stable across renders (deps: [callback, delay]).
 */
export function useDebounce<TArgs extends unknown[]>(
  callback: (...args: TArgs) => void,
  delay: number = 300,
): (...args: TArgs) => void {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  return useCallback(
    (...args: TArgs): void => {
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = setTimeout(() => {
        callback(...args);
      }, delay);
    },
    [callback, delay],
  );
}
