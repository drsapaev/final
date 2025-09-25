/**
 * API Interceptors
 * Обработка запросов и ответов
 */
import { api } from './client';

/**
 * Настройка interceptors для API клиента
 */
export function setupInterceptors() {
  // Request interceptor - добавляем токен к каждому запросу
  api.interceptors.request.use(
    (config) => {
      // Добавляем токен если есть
      const token = localStorage.getItem('auth_token');
      if (token && !config.headers.Authorization) {
        config.headers.Authorization = `Bearer ${token}`;
      }

      // Логируем запросы в development
      if (process.env.NODE_ENV === 'development') {
        console.log(`🔄 API Request: ${config.method?.toUpperCase()} ${config.url}`, {
          params: config.params,
          data: config.data
        });
      }

      return config;
    },
    (error) => {
      console.error('❌ Request Error:', error);
      return Promise.reject(error);
    }
  );

  // Response interceptor - обработка ответов и ошибок
  api.interceptors.response.use(
    (response) => {
      // Логируем успешные ответы в development
      if (process.env.NODE_ENV === 'development') {
        console.log(`✅ API Response: ${response.config.method?.toUpperCase()} ${response.config.url}`, {
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
      console.error(`❌ API Error: ${originalRequest?.method?.toUpperCase()} ${originalRequest?.url}`, {
        status: error.response?.status,
        data: error.response?.data
      });

      // Обработка 401 ошибок (неавторизован)
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;

        try {
          // Пытаемся обновить токен
          const refreshToken = localStorage.getItem('refresh_token');
          
          if (refreshToken) {
            const response = await api.post('/authentication/refresh', {
              refresh_token: refreshToken
            });

            if (response.data.access_token) {
              // Сохраняем новый токен
              localStorage.setItem('auth_token', response.data.access_token);
              api.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
              
              // Повторяем оригинальный запрос
              originalRequest.headers.Authorization = `Bearer ${response.data.access_token}`;
              return api(originalRequest);
            }
          }
        } catch (refreshError) {
          console.error('Ошибка обновления токена:', refreshError);
        }

        // Если обновление токена не удалось, выходим
        localStorage.removeItem('auth_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        delete api.defaults.headers.common['Authorization'];
        
        // Перенаправляем на страницу входа
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }

      // Обработка 403 ошибок (недостаточно прав)
      if (error.response?.status === 403) {
        console.warn('Недостаточно прав доступа');
        
        // Можно показать уведомление пользователю
        if (window.showToast) {
          window.showToast('Недостаточно прав для выполнения операции', 'error');
        }
      }

      // Обработка 500 ошибок (серверные ошибки)
      if (error.response?.status >= 500) {
        console.error('Серверная ошибка');
        
        if (window.showToast) {
          window.showToast('Серверная ошибка. Попробуйте позже.', 'error');
        }
      }

      // Обработка сетевых ошибок
      if (!error.response) {
        console.error('Сетевая ошибка');
        
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
  const token = localStorage.getItem('auth_token');
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }
}

/**
 * Очистка авторизации
 */
export function clearAuth() {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
  delete api.defaults.headers.common['Authorization'];
}
