/**
 * useLocalStorage — R-16 / P-016 (UX audit).
 *
 * A tiny localStorage-backed useState replacement. Used by the cardiologist
 * panel's floating settings popover (ldlThreshold, showEcgEchoTogether)
 * so that the doctor's preferences persist across page reloads and browser
 * restarts.
 *
 * Why not use the existing useSettings hook? That hook is for clinic-wide
 * admin settings (mock-backed, server-side). The cardiologist's LDL
 * threshold is a per-user preference — localStorage is the right home.
 *
 * Usage:
 *   const [value, setValue] = useLocalStorage('cardio.ldlThreshold', 100);
 *
 * The key is namespaced ('cardio.*') to avoid collisions with other
 * features. Values are JSON-serialised. If localStorage is unavailable
 * (private browsing, quota exceeded), the hook falls back to in-memory
 * state and logs a warning — the UI still works, just without persistence.
 */

import { useCallback, useState } from 'react';
import logger from '../utils/logger';

/** Updater function shape — same as React's setState updater. */
type SetValueAction<T> = T | ((prev: T) => T);

const safeGet = <T,>(key: string, fallback: T): T => {
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null) {
      return fallback;
    }
    // JSON.parse возвращает unknown — приводим к T. Это безопасно на уровне
    // вызова: caller контролирует тип T и fallback.
    return JSON.parse(raw) as T;
  } catch (err) {
    logger.warn(`useLocalStorage: failed to read key "${key}"`, err);
    return fallback;
  }
};

const safeSet = <T,>(key: string, value: T): void => {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch (err) {
    // Quota exceeded, private browsing, etc. — non-fatal.
    logger.warn(`useLocalStorage: failed to write key "${key}"`, err);
  }
};

export function useLocalStorage<T>(
  key: string,
  initialValue: T,
): [T, (value: SetValueAction<T>) => void] {
  const [storedValue, setStoredValue] = useState<T>(() => safeGet(key, initialValue));

  const setValue = useCallback(
    (value: SetValueAction<T>): void => {
      setStoredValue((prev) => {
        const next = value instanceof Function ? (value as (prev: T) => T)(prev) : value;
        safeSet(key, next);
        return next;
      });
    },
    [key],
  );

  return [storedValue, setValue];
}

export default useLocalStorage;
