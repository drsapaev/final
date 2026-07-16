// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

const NETWORK_ERROR_PATTERNS = [
  /failed to fetch/i,
  /network error/i,
  /load failed/i,
  /network request failed/i,
];

export const DEFAULT_USER_FACING_NETWORK_ERROR =
  'Не удалось выполнить запрос. Проверьте соединение и попробуйте снова.';

export function isNetworkFetchError(message = '') {
  if (typeof message !== 'string' || !message.trim()) {
    return false;
  }

  return NETWORK_ERROR_PATTERNS.some((pattern) => pattern.test(message));
}

function normalizeValidationDetail(detail) {
  if (Array.isArray(detail)) {
    return detail
      .map((item) => `${item?.loc?.join('.') || 'field'}: ${item?.msg || 'invalid value'}`)
      .join(', ');
  }

  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim();
  }

  return null;
}

export function formatNetworkErrorMessage({
  responseDetail,
  responseMessage,
  rawMessage,
  fallbackMessage = DEFAULT_USER_FACING_NETWORK_ERROR,
} = {}) {
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

export function formatApiErrorMessage(error, fallbackMessage = DEFAULT_USER_FACING_NETWORK_ERROR) {
  if (typeof error === 'string') {
    return formatNetworkErrorMessage({
      rawMessage: error,
      fallbackMessage,
    });
  }

  if (!error || typeof error !== 'object') {
    return fallbackMessage;
  }

  const responseDetail = error.response?.data?.detail ?? error.data?.detail ?? error.detail;
  const responseMessage =
    error.response?.data?.message ??
    error.data?.message ??
    error.response?.data?.error ??
    error.error;
  const rawMessage = error.normalizedMessage || error.message || '';

  if (error.response && !responseDetail && !responseMessage && !isNetworkFetchError(rawMessage)) {
    return null;
  }

  return formatNetworkErrorMessage({
    responseDetail,
    responseMessage,
    rawMessage,
    fallbackMessage,
  });
}
