/**
 * Type guards and error utilities — replaces inline `as { response?: ... }` casts.
 *
 * Usage:
 *   import { getErrorMessage, isAxiosError } from '../utils/type-guards';
 *   catch (err) {
 *     toast.error(getErrorMessage(err));
 *   }
 */

export interface AxiosLikeError {
  isAxiosError?: boolean;
  response?: {
    status?: number;
    data?: { detail?: string; message?: string; [key: string]: unknown };
  };
  message?: string;
}

/**
 * Type guard: checks if an unknown error is an Axios error.
 */
export function isAxiosError(
  err: unknown
): err is AxiosLikeError {
  return (
    typeof err === 'object' &&
    err !== null &&
    'isAxiosError' in err &&
    (err as { isAxiosError?: unknown }).isAxiosError === true
  );
}

/**
 * Extracts a human-readable error message from any caught error.
 *
 * Priority:
 * 1. Axios error: response.data.detail || response.data.message || err.message
 * 2. Error instance: err.message
 * 3. Fallback: String(err)
 */
export function getErrorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (detail) return String(detail);
    const message = err.response?.data?.message;
    if (message) return String(message);
    if (err.message) return err.message;
  }

  if (err instanceof Error) {
    return err.message;
  }

  if (typeof err === 'string') {
    return err;
  }

  return String(err);
}

/**
 * Extracts the HTTP status code from an error, if available.
 * Returns null for non-HTTP errors.
 */
export function getErrorStatus(err: unknown): number | null {
  if (isAxiosError(err)) {
    return err.response?.status ?? null;
  }
  return null;
}
