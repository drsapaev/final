// src/utils/networkErrorMessages.ts
// Phase 1 — migrated from .js. Pure functions; types added.
// No behavioral changes.

const NETWORK_ERROR_PATTERNS: readonly RegExp[] = [
  /failed to fetch/i,
  /network error/i,
  /load failed/i,
  /network request failed/i,
];

export const DEFAULT_USER_FACING_NETWORK_ERROR =
  'Не удалось выполнить запрос. Проверьте соединение и попробуйте снова.';

export function isNetworkFetchError(message: unknown = ''): boolean {
  if (typeof message !== 'string' || !message.trim()) {
    return false;
  }

  return NETWORK_ERROR_PATTERNS.some((pattern) => pattern.test(message));
}

interface ValidationDetailItem {
  loc?: unknown[];
  msg?: string;
}

function normalizeValidationDetail(detail: unknown): string | null {
  if (Array.isArray(detail)) {
    return detail
      .map((item: unknown) => {
        const obj = item as ValidationDetailItem | undefined;
        const loc = Array.isArray(obj?.loc) ? obj.loc.join('.') : 'field';
        const msg = obj?.msg ?? 'invalid value';
        return `${loc}: ${msg}`;
      })
      .join(', ');
  }

  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim();
  }

  return null;
}

interface FormatNetworkErrorMessageArgs {
  responseDetail?: unknown;
  responseMessage?: unknown;
  rawMessage?: unknown;
  fallbackMessage?: string;
}

export function formatNetworkErrorMessage({
  responseDetail,
  responseMessage,
  rawMessage,
  fallbackMessage = DEFAULT_USER_FACING_NETWORK_ERROR,
}: FormatNetworkErrorMessageArgs = {}): string {
  const normalizedDetail = normalizeValidationDetail(responseDetail);
  if (normalizedDetail) {
    return normalizedDetail;
  }

  if (typeof responseMessage === 'string' && responseMessage.trim()) {
    return responseMessage.trim();
  }

  const message = typeof rawMessage === 'string' ? rawMessage.trim() : '';
  if (isNetworkFetchError(message)) {
    return fallbackMessage;
  }

  return message || fallbackMessage;
}

// Shape of axios-like errors we inspect. Kept permissive because callers
// may pass arbitrary thrown values.
interface AxiosLikeError {
  response?: {
    data?: {
      detail?: unknown;
      message?: unknown;
      error?: unknown;
    };
  };
  data?: {
    detail?: unknown;
    message?: unknown;
  };
  detail?: unknown;
  error?: unknown;
  normalizedMessage?: string;
  message?: string;
}

export function formatApiErrorMessage(
  error: unknown,
  fallbackMessage: string = DEFAULT_USER_FACING_NETWORK_ERROR,
): string | null {
  if (typeof error === 'string') {
    return formatNetworkErrorMessage({
      rawMessage: error,
      fallbackMessage,
    });
  }

  if (!error || typeof error !== 'object') {
    return fallbackMessage;
  }

  const err = error as AxiosLikeError;
  const responseDetail = err.response?.data?.detail ?? err.data?.detail ?? err.detail;
  const responseMessage =
    err.response?.data?.message ??
    err.data?.message ??
    err.response?.data?.error ??
    err.error;
  const rawMessage = err.normalizedMessage || err.message || '';

  if (err.response && !responseDetail && !responseMessage && !isNetworkFetchError(rawMessage)) {
    return null;
  }

  return formatNetworkErrorMessage({
    responseDetail,
    responseMessage,
    rawMessage,
    fallbackMessage,
  });
}
