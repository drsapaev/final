import { describe, expect, it } from 'vitest';

import {
  isCanceledApiError,
  isExpectedApiErrorStatus,
  shouldClearAuthOnUnauthorized,
  shouldSuppressApiError,
} from '../interceptors';

describe('isExpectedApiErrorStatus', () => {
  it('returns true when response status is explicitly expected', () => {
    expect(
      isExpectedApiErrorStatus({ expectedErrorStatuses: [404, 409] }, 404)
    ).toBe(true);
  });

  it('returns false when response status is not declared as expected', () => {
    expect(
      isExpectedApiErrorStatus({ expectedErrorStatuses: [409] }, 404)
    ).toBe(false);
  });

  it('returns false when request metadata is missing or invalid', () => {
    expect(isExpectedApiErrorStatus(null, 404)).toBe(false);
    expect(isExpectedApiErrorStatus({}, 404)).toBe(false);
    expect(isExpectedApiErrorStatus({ expectedErrorStatuses: '404' }, 404)).toBe(false);
  });
});

describe('shouldSuppressApiError', () => {
  it('suppresses canceled axios requests before centralized error handling', () => {
    expect(shouldSuppressApiError({ code: 'ERR_CANCELED' })).toBe(true);
    expect(isCanceledApiError({ name: 'CanceledError' })).toBe(true);
  });

  it('suppresses silent 404 empty-state requests', () => {
    expect(
      shouldSuppressApiError({
        config: { silent: true },
        response: { status: 404 },
      })
    ).toBe(true);
  });

  it('suppresses explicit expected statuses and keeps unrelated errors visible', () => {
    expect(
      shouldSuppressApiError({
        config: { expectedErrorStatuses: [404] },
        response: { status: 404 },
      })
    ).toBe(true);

    expect(
      shouldSuppressApiError({
        config: { silent: false, expectedErrorStatuses: [409] },
        response: { status: 404 },
      })
    ).toBe(false);
  });
});

describe('shouldClearAuthOnUnauthorized', () => {
  it('clears auth on 401 responses from protected endpoints when a token exists', () => {
    expect(
      shouldClearAuthOnUnauthorized({
        config: { url: '/users/me/preferences' },
        response: { status: 401 },
      }, true)
    ).toBe(true);

    expect(
      shouldClearAuthOnUnauthorized({
        config: { url: '/messages/unread' },
        response: { status: 401 },
      }, true)
    ).toBe(true);
  });

  it('does not clear auth for auth endpoints or when no token exists', () => {
    expect(
      shouldClearAuthOnUnauthorized({
        config: { url: '/authentication/refresh' },
        response: { status: 401 },
      }, true)
    ).toBe(false);

    expect(
      shouldClearAuthOnUnauthorized({
        config: { url: '/users/me/preferences' },
        response: { status: 401 },
      }, false)
    ).toBe(false);
  });
});
