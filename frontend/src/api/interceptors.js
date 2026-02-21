/**
 * API Interceptors
 * Обработка запросов и ответов
 */
import { api } from './client';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';

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
      
      // Импортируем обработчик ошибок
      const { handleError } = await import('../utils/errorHandler');
      
      // Обрабатываем ошибку централизованно
      const errorInfo = handleError(error, {
        context: `API ${originalRequest.method?.toUpperCase()} ${originalRequest.url}`,
        showToast: !originalRequest.silent, // Поддержка silent режима
        logError: true
      });

      // Логируем ошибки
      logger.error(`❌ API Error: ${originalRequest?.method?.toUpperCase()} ${originalRequest?.url}`, {
        status: error.response?.status,
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

        // Проверяем, есть ли токен ДО удаления
        const hadToken = tokenManager.hasToken();
        
        // Перенаправляем на страницу входа только если запрос не помечен как некритичный
        // или если это не некритичный эндпоинт (например, /clinic/stats, /clinic/health)
        const requestUrl = originalRequest?.url || originalRequest?.baseURL + originalRequest?.url || '';
        const isNonCriticalEndpoint = requestUrl.includes('/clinic/stats') || 
                                      requestUrl.includes('/clinic/health') ||
                                      originalRequest?.skipAuthRedirect;
        
        // Проверяем, не происходит ли это при начальной загрузке страницы
        // Если мы на защищенной странице и токен есть, не редиректим сразу
        const isProtectedRoute = !['/login', '/', '/health'].includes(window.location.pathname);
        // Проверяем, является ли это начальной загрузкой (нет referrer или referrer совпадает с текущим URL)
        const isInitialLoad = !document.referrer || document.referrer === window.location.href || 
                             (performance.navigation && performance.navigation.type === 0);
        
        // Логируем для отладки
        if (process.env.NODE_ENV === 'development') {
          logger.log('🔍 401 Error:', { 
            url: requestUrl, 
            isNonCritical: isNonCriticalEndpoint,
            hadToken,
            isProtectedRoute,
            isInitialLoad,
            currentPath: window.location.pathname,
            willRedirect: !isNonCriticalEndpoint && hadToken && !isInitialLoad && window.location.pathname !== '/login'
          });
        }
        
        // Не очищаем токен при начальной загрузке (после логина), чтобы не терять только что выданный токен
        if (!isInitialLoad) {
          tokenManager.clearAll();
          delete api.defaults.headers.common['Authorization'];
        }
        
        // Перенаправляем только если:
        // 1. Это не некритичный эндпоинт
        // 2. Был токен (значит пользователь был авторизован, но токен истек)
        // 3. Мы не на странице логина
        // 4. Это не начальная загрузка страницы (чтобы дать RequireAuth время проверить токен)
        // НЕ перенаправляем для некритичных эндпоинтов или если токена не было (значит пользователь не был авторизован)
        if (!isNonCriticalEndpoint && hadToken && window.location.pathname !== '/login' && !isInitialLoad) {
          // Используем небольшую задержку, чтобы дать RequireAuth время проверить токен
          setTimeout(() => {
            // Проверяем еще раз, не был ли токен восстановлен
            if (!tokenManager.hasToken()) {
              window.location.href = '/login';
            }
          }, 100);
        }
      }

      // Обработка 403 ошибок (недостаточно прав)
      if (error.response?.status === 403) {
        const errorMessage = error.response?.data?.detail || error.response?.data?.message || 'Недостаточно прав для выполнения операции';
        logger.warn(`❌ 403 Forbidden: ${errorMessage}`, {
          url: originalRequest?.url,
          method: originalRequest?.method,
          role: error.response?.data?.role
        });
        
        // Показываем понятное сообщение пользователю
        if (window.showToast) {
          window.showToast(errorMessage, 'error');
        } else {
          logger.error(`403 Forbidden: ${errorMessage}`);
        }
      }

      // Обработка 404 ошибок (ресурс не найден)
      if (error.response?.status === 404) {
        const errorMessage = error.response?.data?.detail || error.response?.data?.message || 'Запрашиваемый ресурс не найден';
        logger.warn(`❌ 404 Not Found: ${errorMessage}`, {
          url: originalRequest?.url,
          method: originalRequest?.method
        });
        
        if (window.showToast) {
          window.showToast(errorMessage, 'warning');
        } else {
          logger.error(`404 Not Found: ${errorMessage}`);
        }
      }

      // Обработка 500 ошибок (серверные ошибки)
      if (error.response?.status >= 500) {
        logger.error('Серверная ошибка');
        
        if (window.showToast) {
          window.showToast('Серверная ошибка. Попробуйте позже.', 'error');
        }
      }

      // Обработка сетевых ошибок
      if (!error.response) {
        logger.error('Сетевая ошибка');
        
        if (window.showToast) {
          window.showToast('Проблемы с подключением к серверу', 'error');
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
