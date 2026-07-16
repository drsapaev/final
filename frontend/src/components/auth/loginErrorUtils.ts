// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { formatNetworkErrorMessage, isNetworkFetchError } from '../../utils/networkErrorMessages';

const NETWORK_LOGIN_ERROR_MESSAGE =
  'Не удалось подключиться к серверу входа. Проверьте, что backend запущен на 18000, и попробуйте снова.';

const DEFAULT_LOGIN_ERROR_MESSAGE =
  'Не удалось войти в систему. Проверьте логин, пароль и доступность backend.';

export function formatLoginErrorMessage({
  responseStatus,
  responseDetail,
  responseMessage,
  rawMessage,
  fallbackMessage = DEFAULT_LOGIN_ERROR_MESSAGE,
} = {}) {
  if (responseStatus === 401) {
    return 'Неверный логин или пароль';
  }

  if (responseStatus === 403) {
    return 'У вас нет доступа к системе';
  }

  if (responseStatus && responseStatus >= 500) {
    return 'Сервер входа временно недоступен. Попробуйте ещё раз позже.';
  }

  const loginFallbackMessage = isNetworkFetchError(rawMessage) ?
  NETWORK_LOGIN_ERROR_MESSAGE :
  fallbackMessage;

  return formatNetworkErrorMessage({
    responseDetail,
    responseMessage,
    rawMessage,
    fallbackMessage: loginFallbackMessage || NETWORK_LOGIN_ERROR_MESSAGE,
  });
}

export const LOGIN_ERROR_MESSAGES = {
  DEFAULT: DEFAULT_LOGIN_ERROR_MESSAGE,
  NETWORK: NETWORK_LOGIN_ERROR_MESSAGE,
};
