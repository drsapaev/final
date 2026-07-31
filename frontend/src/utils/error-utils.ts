/**
 * Canonical error utility functions.
 *
 * Per ADR-0016 (Error Taxonomy), this file consolidates the two prior
 * `getErrorMessage` exports:
 *   - utils/type-guards.ts:getErrorMessage(err)         → 1-arg
 *   - utils/errorHandler.ts:getErrorMessage(err, fb)    → 2-arg (rich)
 *
 * The canonical `getErrorMessage` uses the RICHER behavior (2-arg with
 * fallback) as its base, because it is a strict superset of the 1-arg
 * version. The 1-arg call sites get BETTER behavior: a user-facing
 * fallback message instead of `String(err)` (which could produce
 * `"[object Object]"` for weird values).
 *
 * The old files (type-guards.ts, errorHandler.ts) are kept as backward-compat
 * re-export shims. New code should import from `utils/error-utils.ts`
 * directly.
 *
 * See ADR-0016 for the full rationale.
 */

import type {
  HttpApiError,
  ApiErrorPayload,
  NetworkErrorInfo,
} from '../types/errors';
import {
  DEFAULT_USER_FACING_NETWORK_ERROR,
  formatApiErrorMessage,
} from './networkErrorMessages';

// ===========================================================================
// Type guards
// ===========================================================================

/**
 * Type guard: checks if an unknown error is an Axios-like error.
 *
 * More permissive than the prior `isAxiosError` (which required
 * `isAxiosError === true`). This version also accepts errors that have a
 * `response` or `request` field — which covers WrappedApiError, CatchError,
 * and other local shapes that don't set the Axios marker.
 *
 * This is a behavioral improvement: errors that have `response.data.detail`
 * but no `isAxiosError: true` are now correctly recognized, so
 * `getErrorMessage` can extract the server-provided message instead of
 * falling through to `err.message` or `String(err)`.
 */
export function isHttpApiError(err: unknown): err is HttpApiError {
  if (typeof err !== 'object' || err === null) return false;
  return (
    'isAxiosError' in err ||
    'response' in err ||
    'request' in err
  );
}

/**
 * Backward-compat alias for `isHttpApiError`.
 *
 * The old name `isAxiosError` is kept because 30+ files import it from
 * `utils/type-guards.ts`. New code should use `isHttpApiError` for clarity
 * (the canonical type is `HttpApiError`, not `AxiosError`).
 */
export const isAxiosLikeError = isHttpApiError;
export const isAxiosError = isHttpApiError;

// ===========================================================================
// Extractors
// ===========================================================================

/**
 * Extract the API error payload (response.data) from an error, if present.
 *
 * Checks both `err.response.data` (standard Axios) and `err.data` (flat
 * alias used by some code paths).
 */
export function extractApiPayload(err: unknown): ApiErrorPayload | null {
  if (!isHttpApiError(err)) return null;
  return err.response?.data ?? err.data ?? null;
}

/**
 * Extract a human-readable message from the API payload.
 *
 * Priority:
 * 1. `detail` as string
 * 2. `detail.message` (structured error object)
 * 3. `detail.error` (structured error object)
 * 4. `detail.reason` (structured error object, used by WebAuthn)
 * 5. `message` (top-level payload field)
 * 6. `error` as string (top-level payload field)
 *
 * Returns null if no message can be extracted.
 */
export function extractApiMessage(err: unknown): string | null {
  const payload = extractApiPayload(err);
  if (!payload) return null;

  if (typeof payload.detail === 'string' && payload.detail.trim()) {
    return payload.detail;
  }

  if (payload.detail && typeof payload.detail === 'object') {
    const d = payload.detail as { message?: string; error?: string; reason?: string };
    if (typeof d.message === 'string' && d.message.trim()) return d.message;
    if (typeof d.error === 'string' && d.error.trim()) return d.error;
    if (typeof d.reason === 'string' && d.reason.trim()) return d.reason;
  }

  if (typeof payload.message === 'string' && payload.message.trim()) {
    return payload.message;
  }

  if (typeof payload.error === 'string' && payload.error.trim()) {
    return payload.error;
  }

  return null;
}

/**
 * Extract network-level info from an error.
 *
 * Useful for logging and for deciding retry / cooldown / re-auth behavior.
 */
export function extractNetworkInfo(err: unknown): NetworkErrorInfo {
  if (!isHttpApiError(err)) {
    return {
      status: null,
      statusText: null,
      code: null,
      isNetworkError: false,
      isCancelled: false,
      isRateLimited: false,
      isAuthError: false,
    };
  }

  const status = err.response?.status ?? err.status ?? null;
  const statusText = err.response?.statusText ?? null;
  const code = err.code ?? null;

  return {
    status,
    statusText,
    code,
    isNetworkError: !err.response && !!err.request,
    isCancelled: code === 'ERR_CANCELED' || err.name === 'CanceledError',
    isRateLimited: status === 429,
    isAuthError: status === 401 || status === 403,
  };
}

/**
 * Extract the HTTP status code from an error. Returns null for non-HTTP errors.
 *
 * (Migrated from utils/type-guards.ts:getErrorStatus)
 */
export function getErrorStatus(err: unknown): number | null {
  if (!isHttpApiError(err)) return null;
  return err.response?.status ?? err.status ?? null;
}

// ===========================================================================
// getErrorMessage — the canonical unified implementation
// ===========================================================================

/**
 * HTTP-status-specific user-facing messages.
 *
 * Used when the error has a response with a known status code but no
 * extractable detail/message in response.data. Preserves the behavior of
 * the old `utils/errorHandler.ts:getErrorMessage` (lines 119-138).
 */
const HTTP_STATUS_MESSAGES: Record<number, string> = {
  400: 'Некорректный запрос',
  401: 'Необходима авторизация',
  403: 'Недостаточно прав для выполнения операции',
  404: 'Запрашиваемый ресурс не найден',
  422: 'Ошибка валидации данных',
  500: 'Внутренняя ошибка сервера',
  502: 'Ошибка шлюза',
  503: 'Сервис временно недоступен',
};

/**
 * Extracts a human-readable error message from any caught error.
 *
 * This is the canonical implementation, consolidating the two prior exports:
 *   - utils/type-guards.ts:getErrorMessage(err)         → 1-arg
 *   - utils/errorHandler.ts:getErrorMessage(err, fb)    → 2-arg (rich)
 *
 * Priority:
 * 1. `formatApiErrorMessage(err, fallback)` — the rich formatter from
 *    `utils/networkErrorMessages.ts`. Handles validation arrays, network
 *    error patterns (e.g. "Failed to fetch" → localized message), and
 *    uses the fallback for network blips.
 * 2. `extractApiMessage(err)` — direct extraction from response.data
 *    (detail / message / error / reason).
 * 3. HTTP-status-specific message (if response exists with a known status
 *    but no extractable detail/message).
 * 4. `err.message` (if err is an Error instance)
 * 5. `err` itself (if it's a string)
 * 6. `fallbackMessage` (default: localized network error message)
 *
 * The `fallbackMessage` default is `DEFAULT_USER_FACING_NETWORK_ERROR`
 * (a localized Russian message). Callers that need a different fallback
 * can pass it explicitly.
 */
export function getErrorMessage(
  err: unknown,
  fallbackMessage: string = DEFAULT_USER_FACING_NETWORK_ERROR,
): string {
  // 1. Rich formatter (handles validation arrays + network patterns)
  const formatted = formatApiErrorMessage(err, fallbackMessage);
  if (formatted) return formatted;

  // 2. Direct extraction from response.data
  const apiMessage = extractApiMessage(err);
  if (apiMessage) return apiMessage;

  // 3. HTTP-status-specific message (preserves old errorHandler.ts behavior)
  const status = getErrorStatus(err);
  if (status !== null) {
    const statusMessage = HTTP_STATUS_MESSAGES[status];
    if (statusMessage) return statusMessage;
    return `Ошибка сервера (${status})`;
  }

  // 4. Error instance
  if (err instanceof Error) return err.message;

  // 5. String
  if (typeof err === 'string') return err;

  // 6. Fallback
  return fallbackMessage;
}

// ===========================================================================
// Detail reason extractor — for patterns like err.response.data.detail.reason
// ===========================================================================

/**
 * Extract the `reason` field from an error's response.data.detail.
 *
 * `detail` can be a string or an object with { message, error, reason }.
 * This helper narrows to the object form and returns `reason`, or undefined.
 */
export function extractDetailReason(err: unknown): string | undefined {
  if (!isHttpApiError(err)) return undefined;
  const detail = err.response?.data?.detail ?? err.detail;
  if (typeof detail === 'object' && detail !== null) {
    return detail.reason;
  }
  return undefined;
}
