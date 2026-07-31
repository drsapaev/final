/**
 * Type guards and error utilities — backward-compat shim.
 *
 * Per ADR-0016 (Error Taxonomy), the canonical implementations now live in:
 *   - types/errors.ts           (AxiosLikeError, ApiErrorPayload, etc.)
 *   - utils/error-utils.ts      (getErrorMessage, isAxiosLikeError, etc.)
 *
 * This file re-exports the canonical symbols so existing imports
 * (`from '../utils/type-guards'`) continue to work. New code should import
 * from `utils/error-utils.ts` directly.
 *
 * The deprecated `AxiosLikeError` interface that used to live here is
 * replaced by the canonical one in `types/errors.ts`. It is re-exported
 * below for backward compatibility.
 */

export type { AxiosLikeError } from '../types/errors';
export {
  isAxiosLikeError,
  isAxiosError,
  getErrorMessage,
  getErrorStatus,
  extractApiPayload,
  extractApiMessage,
  extractNetworkInfo,
} from './error-utils';
