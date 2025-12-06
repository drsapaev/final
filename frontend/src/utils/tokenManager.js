/**
 * Централизованное управление токенами аутентификации
 *
 * ВАЖНО: Использовать ТОЛЬКО этот модуль для работы с токенами!
 * Единственный источник истины для ключей токенов.
 */

const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_KEY = 'user';

/**
 * Менеджер токенов
 */
export const tokenManager = {
  /**
   * Получить access token
   * @returns {string|null} Access token или null
   */
  getAccessToken() {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch (error) {
      console.error('Error reading access token:', error);
      return null;
    }
  },

  /**
   * Установить access token
   * @param {string} token - Access token
   */
  setAccessToken(token) {
    try {
      if (token) {
        localStorage.setItem(TOKEN_KEY, token);
      } else {
        localStorage.removeItem(TOKEN_KEY);
      }
    } catch (error) {
      console.error('Error setting access token:', error);
    }
  },

  /**
   * Получить refresh token
   * @returns {string|null} Refresh token или null
   */
  getRefreshToken() {
    try {
      return localStorage.getItem(REFRESH_TOKEN_KEY);
    } catch (error) {
      console.error('Error reading refresh token:', error);
      return null;
    }
  },

  /**
   * Установить refresh token
   * @param {string} token - Refresh token
   */
  setRefreshToken(token) {
    try {
      if (token) {
        localStorage.setItem(REFRESH_TOKEN_KEY, token);
      } else {
        localStorage.removeItem(REFRESH_TOKEN_KEY);
      }
    } catch (error) {
      console.error('Error setting refresh token:', error);
    }
  },

  /**
   * Получить данные пользователя
   * @returns {object|null} User data или null
   */
  getUserData() {
    try {
      const data = localStorage.getItem(USER_KEY);
      return data ? JSON.parse(data) : null;
    } catch (error) {
      console.error('Error reading user data:', error);
      return null;
    }
  },

  /**
   * Установить данные пользователя
   * @param {object} userData - User data object
   */
  setUserData(userData) {
    try {
      if (userData) {
        localStorage.setItem(USER_KEY, JSON.stringify(userData));
      } else {
        localStorage.removeItem(USER_KEY);
      }
    } catch (error) {
      console.error('Error setting user data:', error);
    }
  },

  /**
   * Очистить все токены и данные пользователя
   */
  clearAll() {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    } catch (error) {
      console.error('Error clearing tokens:', error);
    }
  },

  /**
   * Проверить наличие access token
   * @returns {boolean} true если токен существует
   */
  hasToken() {
    return !!this.getAccessToken();
  },

  /**
   * Проверить валидность токена (базовая проверка)
   * @returns {boolean} true если токен выглядит валидным
   */
  isTokenValid() {
    const token = this.getAccessToken();
    if (!token) return false;

    // Базовая проверка формата JWT (xxx.yyy.zzz)
    const parts = token.split('.');
    if (parts.length !== 3) return false;

    try {
      // Проверка срока действия (если это JWT)
      const payload = JSON.parse(atob(parts[1]));
      if (payload.exp) {
        const expirationTime = payload.exp * 1000; // Convert to milliseconds
        return Date.now() < expirationTime;
      }
      return true; // Если нет exp, считаем валидным
    } catch (error) {
      // Не JWT или ошибка парсинга - считаем валидным
      return true;
    }
  }
};

// Экспорт констант для использования в тестах
export const TOKEN_KEYS = {
  TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  USER_KEY
};

export default tokenManager;
