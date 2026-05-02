/**
 * Сервис аутентификации
 * Централизованная работа с авторизацией
 */
import { api } from '../api/client';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';

export const authService = {
  /**
   * Авторизация пользователя
   */
  async login(credentials) {
    try {
      const response = await api.post('/auth/login', credentials);
      
      if (response.data.access_token) {
        // Сохраняем токен через tokenManager
        tokenManager.setAccessToken(response.data.access_token);
        tokenManager.setRefreshToken(response.data.refresh_token);
        tokenManager.setUserData(response.data.user);

        // Устанавливаем токен в заголовки
        api.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
      }
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка авторизации'
      };
    }
  },

  /**
   * Выход из системы
   */
  async logout() {
    try {
      await api.post('/auth/logout');
    } catch (error) {
      logger.warn('Ошибка выхода:', error);
    } finally {
      // Очищаем локальные данные через tokenManager
      tokenManager.clearAll();
      delete api.defaults.headers.common['Authorization'];
    }
  },

  /**
   * Обновление токена
   */
  async refreshToken() {
    try {
      const refreshToken = tokenManager.getRefreshToken();
      if (!refreshToken) return false;

      const response = await api.post('/auth/refresh', {
        refresh_token: refreshToken
      });

      if (response.data.access_token) {
        tokenManager.setAccessToken(response.data.access_token);
        api.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
        return true;
      }

      return false;
    } catch (error) {
      logger.error('Ошибка обновления токена:', error);
      this.logout();
      return false;
    }
  },

  /**
   * Получение профиля пользователя
   */
  async getProfile() {
    try {
      const response = await api.get('/auth/me');
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка получения профиля'
      };
    }
  },

  /**
   * Проверка авторизации
   */
  isAuthenticated() {
    return tokenManager.hasToken();
  },

  /**
   * Получение текущего пользователя
   */
  getCurrentUser() {
    return tokenManager.getUserData();
  },

  /**
   * Проверка роли пользователя
   */
  hasRole(requiredRoles) {
    const user = this.getCurrentUser();
    if (!user || !user.role) return false;
    
    if (Array.isArray(requiredRoles)) {
      return requiredRoles.includes(user.role);
    }
    
    return user.role === requiredRoles;
  }
};

/**
 * Получение токена авторизации
 */
export const getAuthToken = () => {
  return tokenManager.getAccessToken();
};
