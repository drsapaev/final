/**
 * Type guards and error utilities — backward-compat shim.
 * Per ADR-0016 + Sprint C1. Canonical implementations in:
 *   - types/errors.ts  (HttpApiError, BaseApiError, WorkflowError, etc.)
 *   - utils/error-utils.ts  (getErrorMessage, isHttpApiError, etc.)
 */
export type { HttpApiError, AxiosLikeError, BaseApiError, WorkflowError } from '../types/errors';
export {
  isHttpApiError,
  isAxiosLikeError,
  isAxiosError,
  getErrorMessage,
  getErrorStatus,
  extractApiPayload,
  extractApiMessage,
  extractNetworkInfo,
} from './error-utils';
