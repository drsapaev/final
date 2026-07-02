/**
 * Debounce utility function
 * Delays execution of a function until after a specified wait time has elapsed
 * since the last time it was invoked
 * 
 * @param {Function} func - The function to debounce
 * @param {number} wait - The delay in milliseconds
 * @param {boolean} immediate - If true, trigger function on leading edge instead of trailing
 * @returns {Function} Debounced function
 */
export function debounce(func, wait = 300, immediate = false) {
  let timeout;

  return function executedFunction(...args) {
    const context = this;

    const later = () => {
      timeout = null;
      if (!immediate) func.apply(context, args);
    };

    const callNow = immediate && !timeout;

    clearTimeout(timeout);
    timeout = setTimeout(later, wait);

    if (callNow) func.apply(context, args);
  };
}

/**
 * Hook wrapper for debounce to use in React components
 */
import { useCallback, useRef } from 'react';

export function useDebounce(callback, delay = 300) {
  const timeoutRef = useRef(null);

  return useCallback(
    (...args) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = setTimeout(() => {
        callback(...args);
      }, delay);
    },
    [callback, delay]
  );
}

