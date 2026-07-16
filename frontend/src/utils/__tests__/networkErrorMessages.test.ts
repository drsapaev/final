// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { describe, expect, it } from 'vitest';

import {
  formatApiErrorMessage,
  formatNetworkErrorMessage,
  isNetworkFetchError,
} from '../networkErrorMessages';

describe('networkErrorMessages', () => {
  it('detects failed-to-fetch style network errors', () => {
    expect(isNetworkFetchError('TypeError: Failed to fetch')).toBe(true);
    expect(isNetworkFetchError('Network request failed')).toBe(true);
    expect(isNetworkFetchError('Permission denied')).toBe(false);
  });

  it('normalizes network errors to a friendly fallback message', () => {
    const message = formatNetworkErrorMessage({
      rawMessage: 'TypeError: Failed to fetch',
      fallbackMessage: 'Не удалось выполнить запрос.',
    });

    expect(message).toBe('Не удалось выполнить запрос.');
  });

  it('preserves backend validation detail when present', () => {
    const message = formatNetworkErrorMessage({
      responseDetail: 'Неверный формат',
      rawMessage: 'TypeError: Failed to fetch',
    });

    expect(message).toBe('Неверный формат');
  });

  it('formats api errors from response payloads and raw error objects', () => {
    expect(
      formatApiErrorMessage({
        response: {
          data: {
            detail: 'Нет доступа',
          },
        },
      })
    ).toBe('Нет доступа');

    expect(
      formatApiErrorMessage(new Error('TypeError: Failed to fetch'))
    ).toBe('Не удалось выполнить запрос. Проверьте соединение и попробуйте снова.');
  });
});
