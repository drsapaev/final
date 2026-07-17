/**
 * useDebouncedCallback - Хук для дебаунсинга функций
 *
 * Использует централизованную политику из debouncePolicy.ts
 *
 * @module hooks/useDebouncedCallback
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { DEBOUNCE, type DebounceKey } from '../core/debouncePolicy';

/** Задержка: число (мс) или ключ из DEBOUNCE policy */
export type DebounceDelay = number | DebounceKey;

/**
 * Дебаунсированная функция с дополнительными методами управления.
 */
export interface DebouncedFunction<A extends unknown[]> {
  (...args: A): void;
  /** Немедленно вызвать callback (отменяя pending вызов) */
  flush: (...args: A) => void;
  /** Отменить pending вызов */
  cancel: () => void;
}

/**
 * Создаёт дебаунсированную версию callback-функции
 *
 * @param callback - Функция для дебаунсинга
 * @param delay - Задержка в мс или ключ из DEBOUNCE policy
 * @param deps - Зависимости для useCallback
 *
 * @example
 * // С числовой задержкой
 * const debouncedSearch = useDebouncedCallback(search, 500, [query]);
 *
 * // С ключом из policy
 * const debouncedAI = useDebouncedCallback(requestAI, 'ai', [complaints]);
 */
export function useDebouncedCallback<A extends unknown[]>(
  callback: (...args: A) => void,
  delay: DebounceDelay,
  deps: ReadonlyArray<unknown> = [],
): DebouncedFunction<A> {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const callbackRef = useRef(callback);

  // Обновляем callback ref при изменении
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  // Вычисляем реальную задержку
  const resolvedDelay: number =
    typeof delay === 'string' ? (DEBOUNCE[delay] ?? DEBOUNCE.search) : delay;

  // Очистка при размонтировании
  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const debouncedCallback = useCallback(
    (...args: A): void => {
      void deps;
      // Отменяем предыдущий таймаут
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current);
      }

      // Устанавливаем новый
      timeoutRef.current = setTimeout(() => {
        callbackRef.current(...args);
      }, resolvedDelay);
    },
    [resolvedDelay, deps],
  );

  // Метод для немедленного вызова (flush)
  // Привязываем через Object.assign вместо мутации функции — type-safe способ.
  const flush = useCallback(
    (...args: A): void => {
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      callbackRef.current(...args);
    },
    [],
  );

  // Метод для отмены pending вызова
  const cancel = useCallback((): void => {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  // Композируем функцию + методы в один объект.
  // Это type-safe: интерфейс DebouncedFunction требует и call-сигнатуру, и .flush/.cancel.
  return Object.assign(debouncedCallback, { flush, cancel });
}

/**
 * Хук для дебаунсированного значения
 *
 * @param value - Значение для дебаунсинга
 * @param delay - Задержка
 */
export function useDebouncedValue<T>(value: T, delay: DebounceDelay): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const resolvedDelay: number =
      typeof delay === 'string' ? (DEBOUNCE[delay] ?? DEBOUNCE.search) : delay;

    const timeout = setTimeout(() => {
      setDebouncedValue(value);
    }, resolvedDelay);

    return () => clearTimeout(timeout);
  }, [value, delay]);

  return debouncedValue;
}

export default useDebouncedCallback;
