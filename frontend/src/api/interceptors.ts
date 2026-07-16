/**
 * API Interceptors
 * Обработка запросов и ответов
 */
import { api } from './client';
import { tokenManager } from '../utils/tokenManager';
import { clearToken as clearAuthState } from '../stores/auth.js';
import logger from '../utils/logger';
import { handleError } from '../utils/errorHandler';

export function isExpectedApiErrorStatus(originalRequest, status) {
  if (!originalRequest || typeof status !== 'number') {
    return false;
  }

  const expectedStatuses = originalRequest.expectedErrorStatuses;
  return Array.isArray(expectedStatuses) && expectedStatuses.includes(status);
}

export function isCanceledApiError(error) {
  return error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError';
}

export function shouldSuppressApiError(error) {
  const originalRequest = error?.config;
  const status = error?.response?.status;

  if (isCanceledApiError(error)) {
    return true;
  }

  if (isExpectedApiErrorStatus(originalRequest, status)) {
    return true;
  }

  return originalRequest?.silent === true && status === 404;
}

export function shouldClearAuthOnUnauthorized(error, hasToken = tokenManager.hasToken()) {
  if (!hasToken || error?.response?.status !== 401) {
    return false;
  }

  const requestUrl = String(error?.config?.url || '');
  if (
    requestUrl.includes('/auth/login') ||
    requestUrl.includes('/auth/csrf-token') ||
    requestUrl.includes('/authentication/login') ||
    requestUrl.includes('/authentication/refresh')
  ) {
    return false;
  }

  return true;
}

/**
 * Настройка interceptors для API клиента
 */
export function setupInterceptors() {
  // Request interceptor - добавляем токен к каждому запросу
  api.interceptors.request.use(
    (config) => {
      // Добавляем токен если есть
      const token = tokenManager.getAccessToken();
      if (token && !config.headers.Authorization) {
        config.headers.Authorization = `Bearer ${token}`;
      }

      // Логируем запросы в development
      if (process.env.NODE_ENV === 'development') {
        logger.log(`🔄 API Request: ${config.method?.toUpperCase()} ${config.url}`, {
          params: config.params,
          data: config.data
        });
      }

      return config;
    },
    (error) => {
      logger.error('❌ Request Error:', error);
      return Promise.reject(error);
    }
  );

  // Response interceptor - обработка ответов и ошибок
  api.interceptors.response.use(
    (response) => {
      // Логируем успешные ответы в development
      if (process.env.NODE_ENV === 'development') {
        logger.log(`✅ API Response: ${response.config.method?.toUpperCase()} ${response.config.url}`, {
          status: response.status,
          data: response.data
        });
      }

      return response;
    },
    async (error) => {
      const originalRequest = error.config;
      const status = error.response?.status;

      if (shouldSuppressApiError(error)) {
        logger.info('[FIX:API] Suppressing handled API error', {
          url: originalRequest?.url,
          method: originalRequest?.method,
          status,
          canceled: isCanceledApiError(error)
        });
        return Promise.reject(error);
      }

      // Обрабатываем ошибку централизованно
      void handleError(error, {
        context: `API ${originalRequest.method?.toUpperCase()} ${originalRequest.url}`,
        showToast: !originalRequest.silent, // Поддержка silent режима
        logError: true
      });

      // Логируем ошибки
      logger.error(`❌ API Error: ${originalRequest?.method?.toUpperCase()} ${originalRequest?.url}`, {
        status,
        data: error.response?.data
      });

      // Обработка 401 ошибок (неавторизован)
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;

        try {
          // Пытаемся обновить токен
          const refreshToken = tokenManager.getRefreshToken();

          if (refreshToken) {
            const response = await api.post('/authentication/refresh', {
              refresh_token: refreshToken
            });

            if (response.data.access_token) {
              // Сохраняем новый токен
              tokenManager.setAccessToken(response.data.access_token);
              api.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;

              // Повторяем оригинальный запрос
              originalRequest.headers.Authorization = `Bearer ${response.data.access_token}`;
              return api(originalRequest);
            }
          }
        } catch (refreshError) {
          logger.error('Ошибка обновления токена:', refreshError);
        }

        const hadToken = tokenManager.hasToken();
        const requestUrl = originalRequest?.url || originalRequest?.baseURL + originalRequest?.url || '';
        const isNonCriticalEndpoint = requestUrl.includes('/clinic/stats') ||
        requestUrl.includes('/clinic/health') ||
        originalRequest?.skipAuthRedirect;

        // Логируем для отладки
        if (process.env.NODE_ENV === 'development') {
          logger.log('🔍 401 Error:', {
            url: requestUrl,
            isNonCritical: isNonCriticalEndpoint,
            hadToken,
            shouldClearAuth: shouldClearAuthOnUnauthorized(error, hadToken),
            currentPath: window.location.pathname,
            willRedirect: !isNonCriticalEndpoint && hadToken && window.location.pathname !== '/login'
          });
        }

        if (shouldClearAuthOnUnauthorized(error, hadToken)) {
          logger.warn('[FIX:AUTH] Clearing invalid session after 401', {
            url: requestUrl,
            message: error.response?.data?.message || error.response?.data?.detail || 'Unauthorized'
          });
          clearAuthState();
        }
      }

      return Promise.reject(error);
    }
  );
}

/**
 * Установка базового токена при загрузке приложения
 */
export function initializeAuth() {
  const token = tokenManager.getAccessToken();
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }
}

/**
 * Очистка авторизации
 */
export function clearAuth() {
  tokenManager.clearAll();
  delete api.defaults.headers.common['Authorization'];
}
