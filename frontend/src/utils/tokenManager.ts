/**
 * Централизованное управление токенами аутентификации
 *
 * ВАЖНО: Использовать ТОЛЬКО этот модуль для работы с токенами!
 * Единственный источник истины для ключей токенов.
 *
 * PR-39 / P0-2: Tokens migrated from localStorage to sessionStorage.
 * localStorage persists across browser sessions (until manually cleared) —
 * a stolen device or shared computer exposes tokens indefinitely.
 * sessionStorage is cleared when the tab closes, limiting the exposure window.
 *
 * Full httpOnly cookie migration requires backend coordination (Set-Cookie
 * with SameSite=Strict + credentials: 'include' on axios). This is a
 * partial mitigation until that work is done.
 */
import logger from './logger';

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
      // PR-39 / P0-2: sessionStorage instead of localStorage
      const t = sessionStorage.getItem(TOKEN_KEY);
      return t ? t.trim() : null;
    } catch (error) {
      logger.error('Error reading access token:', error);
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
        const trimmed = typeof token === 'string' ? token.trim() : token;
        if (trimmed) sessionStorage.setItem(TOKEN_KEY, trimmed);else
        sessionStorage.removeItem(TOKEN_KEY);
      } else {
        sessionStorage.removeItem(TOKEN_KEY);
      }
    } catch (error) {
      logger.error('Error setting access token:', error);
    }
  },

  /**
   * Получить refresh token
   * @returns {string|null} Refresh token или null
   */
  getRefreshToken() {
    try {
      // PR-39 / P0-2: sessionStorage instead of localStorage
      return sessionStorage.getItem(REFRESH_TOKEN_KEY);
    } catch (error) {
      logger.error('Error reading refresh token:', error);
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
        // PR-39 / P0-2: sessionStorage instead of localStorage
        sessionStorage.setItem(REFRESH_TOKEN_KEY, token);
      } else {
        sessionStorage.removeItem(REFRESH_TOKEN_KEY);
      }
    } catch (error) {
      logger.error('Error setting refresh token:', error);
    }
  },

  /**
   * Получить данные пользователя
   * @returns {object|null} User data или null
   */
  getUserData() {
    try {
      // PR-39 / P0-2: sessionStorage instead of localStorage (user data may contain role/permissions)
      const data = sessionStorage.getItem(USER_KEY);
      return data ? JSON.parse(data) : null;
    } catch (error) {
      logger.error('Error reading user data:', error);
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
        // PR-39 / P0-2: sessionStorage instead of localStorage
        sessionStorage.setItem(USER_KEY, JSON.stringify(userData));
      } else {
        sessionStorage.removeItem(USER_KEY);
      }
    } catch (error) {
      logger.error('Error setting user data:', error);
    }
  },

  /**
   * Очистить все токены и данные пользователя
   */
  clearAll() {
    try {
      // PR-39 / P0-2: sessionStorage instead of localStorage
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(REFRESH_TOKEN_KEY);
      sessionStorage.removeItem(USER_KEY);
    } catch (error) {
      logger.error('Error clearing tokens:', error);
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
    } catch {
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
