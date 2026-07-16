/**
 * Централизованная система обработки ошибок
 */

import { toast } from 'react-toastify';

import logger from '../utils/logger';
import {
  DEFAULT_USER_FACING_NETWORK_ERROR,
  formatApiErrorMessage,
} from './networkErrorMessages';

// Phase 1 — typed accessor for error objects with axios-like shape.
interface ErrorWithResponse {
  response?: {
    status?: number;
    data?: { detail?: unknown; message?: string };
    statusText?: string;
  };
  message?: string;
  code?: string;
  name?: string;
}
/**
 * Типы ошибок
 */
export const ERROR_TYPES = {
  NETWORK: 'network',
  AUTHENTICATION: 'authentication',
  AUTHORIZATION: 'authorization',
  VALIDATION: 'validation',
  SERVER: 'server',
  UNKNOWN: 'unknown'
};

/**
 * Коды ошибок HTTP
 */
export const HTTP_STATUS = {
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  UNPROCESSABLE_ENTITY: 422,
  INTERNAL_SERVER_ERROR: 500,
  BAD_GATEWAY: 502,
  SERVICE_UNAVAILABLE: 503
};

/**
 * Определяет тип ошибки по HTTP статусу и содержимому
 */
export function getErrorType(error: unknown): string {
  if (!(error as ErrorWithResponse).response) {
    return ERROR_TYPES.NETWORK;
  }

  const status = (error as ErrorWithResponse).response.status;
  
  switch (status) {
    case HTTP_STATUS.UNAUTHORIZED:
      return ERROR_TYPES.AUTHENTICATION;
    case HTTP_STATUS.FORBIDDEN:
      return ERROR_TYPES.AUTHORIZATION;
    case HTTP_STATUS.BAD_REQUEST:
    case HTTP_STATUS.UNPROCESSABLE_ENTITY:
      return ERROR_TYPES.VALIDATION;
    case HTTP_STATUS.INTERNAL_SERVER_ERROR:
    case HTTP_STATUS.BAD_GATEWAY:
    case HTTP_STATUS.SERVICE_UNAVAILABLE:
      return ERROR_TYPES.SERVER;
    default:
      return ERROR_TYPES.UNKNOWN;
  }
}

/**
 * Извлекает сообщение об ошибке из ответа сервера
 */
export function getErrorMessage(error: unknown, fallbackMessage: string = DEFAULT_USER_FACING_NETWORK_ERROR): string {
  const formatted = formatApiErrorMessage(error, fallbackMessage);
  if (formatted) {
    return formatted;
  }

  if (!(error as ErrorWithResponse)?.response) {
    return fallbackMessage;
  }

  const { status, data } = (error as ErrorWithResponse).response;

  // Сообщение от сервера
  if (data?.detail) {
    if (typeof data.detail === 'string') {
      return data.detail;
    }
    
    // Обработка массива ошибок валидации
    if (Array.isArray(data.detail)) {
      return (data.detail as Array<{ msg?: string; loc?: unknown[] }>).map(err => {
        if (err.msg && err.loc) {
          const field = err.loc[err.loc.length - 1];
          return `${field}: ${err.msg}`;
        }
        return err.msg || 'Ошибка валидации';
      }).join(', ');
    }
  }

  if (data?.message) {
    return data.message;
  }

  if ((data as { error?: string })?.error) {
    return (data as { error?: string }).error as string;
  }

  // Стандартные сообщения по HTTP статусам
  switch (status) {
    case HTTP_STATUS.BAD_REQUEST:
      return 'Некорректный запрос';
    case HTTP_STATUS.UNAUTHORIZED:
      return 'Необходима авторизация';
    case HTTP_STATUS.FORBIDDEN:
      return 'Недостаточно прав для выполнения операции';
    case HTTP_STATUS.NOT_FOUND:
      return 'Запрашиваемый ресурс не найден';
    case HTTP_STATUS.UNPROCESSABLE_ENTITY:
      return 'Ошибка валидации данных';
    case HTTP_STATUS.INTERNAL_SERVER_ERROR:
      return 'Внутренняя ошибка сервера';
    case HTTP_STATUS.BAD_GATEWAY:
      return 'Ошибка шлюза';
    case HTTP_STATUS.SERVICE_UNAVAILABLE:
      return 'Сервис временно недоступен';
    default:
      return `Ошибка сервера (${status})`;
  }
}

/**
 * Определяет, нужно ли показывать уведомление пользователю
 */
export function shouldShowNotification(errorType: string, options: { silentErrors?: string[]; silent?: boolean; showNetworkErrors?: boolean } = {}): boolean {
  const { silent = false, showNetworkErrors = true } = options;

  if (silent) return false;
  
  switch (errorType) {
    case ERROR_TYPES.NETWORK:
      return showNetworkErrors;
    case ERROR_TYPES.AUTHENTICATION:
      return false; // Обрабатывается interceptor'ом
    case ERROR_TYPES.AUTHORIZATION:
    case ERROR_TYPES.VALIDATION:
    case ERROR_TYPES.SERVER:
    case ERROR_TYPES.UNKNOWN:
      return true;
    default:
      return true;
  }
}

/**
 * Основная функция обработки ошибок
 */
export function handleError(
  error: unknown,
  options: Record<string, unknown> = {},
): { type: string; message: string; status?: number; originalError: unknown } {
  const {
    showToast = true,
    logError = true,
    customMessage = null,
    onError = null,
    context = 'Unknown'
  } = options;

  const errorType = getErrorType(error);
  const errorMessage: string = (typeof customMessage === 'string' && customMessage)
    ? customMessage
    : getErrorMessage(error);

  // Логирование
  if (logError) {
    logger.error(`[${context}] ${errorType.toUpperCase()} Error:`, {
      message: errorMessage,
      status: (error as { response?: { status?: number } })?.response?.status,
      data: (error as ErrorWithResponse).response?.data,
      originalError: error
    });
  }

  // Уведомление пользователя
  if (showToast && shouldShowNotification(errorType, options)) {
    switch (errorType) {
      case ERROR_TYPES.VALIDATION:
        toast.error(errorMessage);
        break;
      case ERROR_TYPES.SERVER:
        toast.error('Ошибка сервера. Попробуйте позже.');
        break;
      case ERROR_TYPES.NETWORK:
        toast.error(errorMessage);
        break;
      default:
        toast.error(errorMessage);
    }
  }

  // Кастомный обработчик
  if (onError && typeof onError === 'function') {
    onError(error, errorType, errorMessage);
  }

  return {
    type: errorType,
    message: errorMessage,
    status: (error as ErrorWithResponse).response?.status,
    originalError: error
  };
}

/**
 * Хук для обработки ошибок в компонентах
 */
export function useErrorHandler(context: string = 'Component'): (error: unknown, options?: Record<string, unknown>) => ReturnType<typeof handleError> {
  return (error, options = {}) => {
    return handleError(error, { ...options, context });
  };
}

/**
 * Обработчик ошибок для async/await
 */
export function withErrorHandling<TArgs extends unknown[]>(asyncFn: (...args: TArgs) => Promise<unknown>, options: Record<string, unknown> = {}): (...args: TArgs) => Promise<unknown> {
  return async (...args) => {
    try {
      return await asyncFn(...args);
    } catch (error) {
      handleError(error, options);
      throw error;
    }
  };
}

/**
 * Retry логика для сетевых запросов
 */
export async function retryRequest<T>(
  requestFn: () => Promise<T>,
  options: {
    maxRetries?: number;
    delay?: number;
    backoff?: number;
    shouldRetry?: (error: unknown) => boolean;
  } = {},
): Promise<T> {
  const {
    maxRetries = 3,
    delay = 1000,
    backoff = 2,
    shouldRetry = (error: unknown) => getErrorType(error) === ERROR_TYPES.NETWORK,
  } = options;

  let lastError;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await requestFn();
    } catch (error) {
      lastError = error;
      
      if (attempt === maxRetries || !shouldRetry(error)) {
        throw error;
      }
      
      // Ждем перед повтором
      await new Promise(resolve => 
        setTimeout(resolve, delay * Math.pow(backoff, attempt))
      );
    }
  }
  
  throw lastError;
}

/**
 * Валидаторы форм
 */
export const validators = {
  required: (value, fieldName = 'Поле') => {
    if (!value || (typeof value === 'string' && !value.trim())) {
      return `${fieldName} обязательно для заполнения`;
    }
    return null;
  },

  email: (value) => {
    if (!value) return null;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(value)) {
      return 'Некорректный email адрес';
    }
    return null;
  },

  phone: (value) => {
    if (!value) return null;
    const phoneRegex = /^\+?[\d\s-()]{10,}$/;
    if (!phoneRegex.test(value)) {
      return 'Некорректный номер телефона';
    }
    return null;
  },

  minLength: (min) => (value, fieldName = 'Поле') => {
    if (!value) return null;
    if (value.length < min) {
      return `${fieldName} должно содержать минимум ${min} символов`;
    }
    return null;
  },

  maxLength: (max) => (value, fieldName = 'Поле') => {
    if (!value) return null;
    if (value.length > max) {
      return `${fieldName} должно содержать максимум ${max} символов`;
    }
    return null;
  },

  number: (value, fieldName = 'Поле') => {
    if (!value) return null;
    if (isNaN(Number(value))) {
      return `${fieldName} должно быть числом`;
    }
    return null;
  },

  positive: (value, fieldName = 'Поле') => {
    if (!value) return null;
    if (Number(value) <= 0) {
      return `${fieldName} должно быть положительным числом`;
    }
    return null;
  }
};

/**
 * Функция валидации формы.
 *
 * `rules` is a record of field → validator. Each validator is either:
 *   - a direct function: (value, fieldName?) => string | null
 *   - a curried function (e.g. validators.minLength(5)): (value, fieldName?) => string | null
 *   - an array of either of the above
 *
 * The function collects the first error per field and returns
 * `{ isValid, errors }`.
 */
export function validateForm(
  data: Record<string, unknown>,
  rules: Record<string, unknown>,
): { isValid: boolean; errors: Record<string, string> } {
  const errors: Record<string, string> = {};

  Object.entries(rules).forEach(([field, fieldRules]) => {
    const value = data[field];
    const rulesArray: unknown[] = Array.isArray(fieldRules) ? fieldRules : [fieldRules];
    for (const rule of rulesArray) {
      if (typeof rule !== 'function') continue;
      const error = (rule as (...args: unknown[]) => unknown)(value, field);
      if (typeof error === 'string' && error) {
        errors[field] = error;
        break; // Первая ошибка для поля
      }
    }
  });

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}
