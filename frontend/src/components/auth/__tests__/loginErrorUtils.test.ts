// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { describe, expect, it } from 'vitest';

import { formatLoginErrorMessage, LOGIN_ERROR_MESSAGES } from '../loginErrorUtils';

describe('formatLoginErrorMessage', () => {
  it('normalizes failed-to-fetch into a friendly connection error', () => {
    const message = formatLoginErrorMessage({
      rawMessage: 'TypeError: Failed to fetch',
      fallbackMessage: 'Ошибка входа',
    });

    expect(message).toBe(LOGIN_ERROR_MESSAGES.NETWORK);
  });

  it('maps 401 to a clear credential error', () => {
    const message = formatLoginErrorMessage({
      responseStatus: 401,
      fallbackMessage: 'Ошибка входа',
    });

    expect(message).toBe('Неверный логин или пароль');
  });

  it('preserves backend detail text when present', () => {
    const message = formatLoginErrorMessage({
      responseStatus: 400,
      responseDetail: 'Неверный формат логина',
      fallbackMessage: 'Ошибка входа',
    });

    expect(message).toBe('Неверный формат логина');
  });
});
