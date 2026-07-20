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
 */
import logger from './logger';

const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_KEY = 'user';

interface JwtPayload {
  exp?: number;
  [key: string]: unknown;
}

/**
 * Менеджер токенов
 */
export const tokenManager = {
  /** Получить access token */
  getAccessToken(): string | null {
    try {
      // PR-39 / P0-2: sessionStorage instead of localStorage
      const t = sessionStorage.getItem(TOKEN_KEY);
      return t ? t.trim() : null;
    } catch (error) {
      logger.error('Error reading access token:', error);
      return null;
    }
  },

  /** Установить access token */
  setAccessToken(token: string | null | undefined): void {
    try {
      if (token) {
        const trimmed = typeof token === 'string' ? token.trim() : token;
        if (trimmed) {
          sessionStorage.setItem(TOKEN_KEY, String(trimmed));
        } else {
          sessionStorage.removeItem(TOKEN_KEY);
        }
      } else {
        sessionStorage.removeItem(TOKEN_KEY);
      }
    } catch (error) {
      logger.error('Error setting access token:', error);
    }
  },

  /** Получить refresh token */
  getRefreshToken(): string | null {
    try {
      return sessionStorage.getItem(REFRESH_TOKEN_KEY);
    } catch (error) {
      logger.error('Error reading refresh token:', error);
      return null;
    }
  },

  /** Установить refresh token */
  setRefreshToken(token: string | null | undefined): void {
    try {
      if (token) {
        sessionStorage.setItem(REFRESH_TOKEN_KEY, token);
      } else {
        sessionStorage.removeItem(REFRESH_TOKEN_KEY);
      }
    } catch (error) {
      logger.error('Error setting refresh token:', error);
    }
  },

  /** Получить данные пользователя */
  getUserData(): Record<string, unknown> | null {
    try {
      const data = sessionStorage.getItem(USER_KEY);
      if (!data) return null;
      // JSON.parse result is unknown — narrow to object or null.
      const parsed: unknown = JSON.parse(data);
      return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : null;
    } catch (error) {
      logger.error('Error reading user data:', error);
      return null;
    }
  },

  /** Установить данные пользователя */
  setUserData(userData: Record<string, unknown> | null | undefined): void {
    try {
      if (userData) {
        sessionStorage.setItem(USER_KEY, JSON.stringify(userData));
      } else {
        sessionStorage.removeItem(USER_KEY);
      }
    } catch (error) {
      logger.error('Error setting user data:', error);
    }
  },

  /** Очистить все токены и данные пользователя */
  clearAll(): void {
    try {
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(REFRESH_TOKEN_KEY);
      sessionStorage.removeItem(USER_KEY);
    } catch (error) {
      logger.error('Error clearing tokens:', error);
    }
  },

  /** Проверить наличие access token */
  hasToken(): boolean {
    return !!this.getAccessToken();
  },

  /**
   * Проверить валидность токена (базовая проверка).
   * JWT format check + exp claim check. Non-JWT tokens are treated as valid
   * (the backend will reject them on the next /me call).
   */
  isTokenValid(): boolean {
    const token = this.getAccessToken();
    if (!token) return false;

    // Базовая проверка формата JWT (xxx.yyy.zzz)
    const parts = token.split('.');
    if (parts.length !== 3) return false;

    try {
      // Проверка срока действия (если это JWT)
      // atob returns string; JSON.parse returns unknown.
      const payload: JwtPayload = JSON.parse(atob(parts[1])) as JwtPayload;
      if (payload.exp) {
        const expirationTime = payload.exp * 1000;
        return Date.now() < expirationTime;
      }
      return true;
    } catch {
      // Не JWT или ошибка парсинга — считаем валидным
      return true;
    }
  },
};

export const TOKEN_KEYS = {
  TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  USER_KEY,
} as const;

export default tokenManager;
