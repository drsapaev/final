/**
 * Сервис аутентификации
 * Централизованная работа с авторизацией
 */
import { api } from '../api/client';

export const authService = {
  /**
   * Авторизация пользователя
   */
  async login(credentials) {
    try {
      const response = await api.post('/authentication/login', credentials);
      
      if (response.data.access_token) {
        // Сохраняем токен
        localStorage.setItem('token', response.data.access_token);
        localStorage.setItem('refresh_token', response.data.refresh_token);
        localStorage.setItem('user', JSON.stringify(response.data.user));
        
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
      await api.post('/authentication/logout');
    } catch (error) {
      console.warn('Ошибка выхода:', error);
    } finally {
      // Очищаем локальные данные
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
      delete api.defaults.headers.common['Authorization'];
    }
  },

  /**
   * Обновление токена
   */
  async refreshToken() {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) return false;

      const response = await api.post('/authentication/refresh', {
        refresh_token: refreshToken
      });

      if (response.data.access_token) {
        localStorage.setItem('token', response.data.access_token);
        api.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Ошибка обновления токена:', error);
      this.logout();
      return false;
    }
  },

  /**
   * Получение профиля пользователя
   */
  async getProfile() {
    try {
      const response = await api.get('/authentication/profile');
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
    const token = localStorage.getItem('token');
    return !!token;
  },

  /**
   * Получение текущего пользователя
   */
  getCurrentUser() {
    try {
      const userStr = localStorage.getItem('user');
      return userStr ? JSON.parse(userStr) : null;
    } catch (error) {
      return null;
    }
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
