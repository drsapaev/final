/**
 * Canonical error types for the frontend.
 *
 * Per ADR-0016 (Error Taxonomy), this file consolidates the 17 duplicate
 * Axios-like error interface declarations that existed across the codebase
 * before the P0 error-model consolidation sprint.
 *
 * The three types here form a small hierarchy:
 *
 *   HttpApiError        — the full error shape (what catch blocks cast to)
 *     └── response?: ApiErrorResponse   — the HTTP response (if the error reached the server)
 *           └── data?: ApiErrorPayload  — the response body (detail / message / error)
 *
 * NetworkErrorInfo is a derived view — extracted from an error via
 * `extractNetworkInfo()` in `utils/error-utils.ts`. It is NOT stored on
 * the error itself.
 *
 * These types are deliberately PERMISSIVE (every field optional). They
 * model the shape of arbitrary thrown values, not a strict contract.
 * Use `isHttpApiError()` (in `utils/error-utils.ts`) to narrow before
 * accessing fields.
 *
 * See ADR-0016 for the full rationale and the "do NOT unify into AppError"
 * decision.
 */

// ===========================================================================
// ApiErrorPayload — the response.data shape
// ===========================================================================

/**
 * Canonical shape of an API error response body (response.data).
 *
 * Backend FastAPI conventions:
 * - `detail` is the primary error field. It can be:
 *   - a string (simple error: "Patient not found")
 *   - an object with { message, error, reason } (structured error)
 *   - an array of validation errors (handled by formatApiErrorMessage)
 * - `message` is an alternative to `detail` (some endpoints use one, some the other)
 * - `error` is rare but exists in some legacy endpoints
 *
 * The index signature is permissive — the backend may add fields we don't
 * model here (e.g. `cooldownMs` on 429 responses).
 */
export interface ApiErrorPayload {
  /**
   * Primary error field. Can be:
   * - a string (simple error)
   * - an object with { message, error, reason } (structured error)
   * - an array of validation errors (handled by formatApiErrorMessage)
   * The index signature below covers any other backend-specific shape.
   */
  detail?: string | { message?: string; error?: string; reason?: string };
  message?: string;
  error?: unknown;
  [key: string]: unknown;
}

// ===========================================================================
// ApiErrorResponse — the response shape
// ===========================================================================

/**
 * Canonical shape of the `response` field of an HttpApiError.
 */
export interface ApiErrorResponse {
  status?: number;
  statusText?: string;
  data?: ApiErrorPayload;
  config?: unknown;
  headers?: Record<string, string>;
}

// ===========================================================================
// HttpApiError — the canonical catch-block type
// ===========================================================================

/**
 * Canonical shape of an Axios-like error.
 *
 * This is a SUPERSET of all the local error interfaces that existed in the
 * codebase before ADR-0016 consolidation:
 *
 *   WrappedApiError (api/patients.ts, api/payments.ts)
 *   ApiErrorResponse (components/admin/WebhookManager.tsx, components/security/TwoFactorManager.tsx)
 *   HttpApiError (api/interceptors.ts, utils/type-guards.ts, utils/networkErrorMessages.ts)
 *   ErrorWithExtras (components/TelegramManager.tsx, pages/RegistrarPanel.tsx)
 *   ErrorWithResponse (utils/errorHandler.ts)
 *   EMRApiError (types/domain/emr.ts)
 *   CatchError (hooks/useApi.ts, hooks/useDoctorQueue.ts, hooks/usePatients.ts)
 *   WebAuthnErrorResponse (hooks/useWebAuthn.tsx)
 *
 * All of those are replaced by this single type.
 *
 * Every field is optional because callers may pass arbitrary thrown values.
 * Use `isHttpApiError()` to narrow before accessing fields.
 */
// Sprint C1: BaseApiError — root of the error type hierarchy.
export interface BaseApiError {
  message?: string;
  code?: string;
}

export interface HttpApiError extends BaseApiError {
  // Axios markers
  isAxiosError?: boolean;
  name?: string;
  code?: string;
  message?: string;

  // HTTP response (if the error reached the server)
  response?: ApiErrorResponse;

  // Network-level info (for errors that didn't reach the server)
  request?: unknown;

  // Config (for retry / suppression logic — used by api/interceptors.ts)
  config?: {
    url?: string;
    expectedErrorStatuses?: number[];
    silent?: boolean;
    [key: string]: unknown;
  };

  // Flat aliases — some code paths flatten response.status / response.data.detail
  // onto the error itself (e.g. WrappedApiError in api/patients.ts, the
  // permissive HttpApiError in utils/networkErrorMessages.ts).
  // Kept for compatibility with existing cast-and-access patterns.
  status?: number;
  detail?: string | { message?: string; error?: string; reason?: string };
  error?: unknown;
  data?: ApiErrorPayload;

  // Normalized message (set by interceptors after formatting)
  normalizedMessage?: string;
}

// ===========================================================================
// NetworkErrorInfo — derived view (not stored on the error)
// ===========================================================================

/**
 * Network-level info extracted from an error.
 *
 * Produced by `extractNetworkInfo()` in `utils/error-utils.ts`. Useful for
 * logging and for deciding retry / cooldown / re-auth behavior.
 */
export interface NetworkErrorInfo {
  status: number | null;
  statusText: string | null;
  code: string | null;
  /** True if the request never reached the server (no response, but has request). */
  isNetworkError: boolean;
  /** True if the request was cancelled by the user (ERR_CANCELED / CanceledError). */
  isCancelled: boolean;
  /** True if status === 429. */
  isRateLimited: boolean;
  /** True if status === 401 or 403. */
  isAuthError: boolean;
}

// ===========================================================================
// Backward-compat alias + WorkflowError
// ===========================================================================

/** @deprecated Use HttpApiError. Kept for backward compat during Sprint C1. */
export type AxiosLikeError = HttpApiError;

/** Error for workflow state machines (EMR draft→dirty→saving→conflict). */
export interface WorkflowError extends BaseApiError {
  step?: string;
}
