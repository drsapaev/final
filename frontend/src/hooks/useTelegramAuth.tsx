/**
 * useTelegramAuth — M4-P0-2 frontend integration (P5).
 *
 * Exchanges Telegram Mini App initData for short-lived JWT.
 * After exchange, all API calls use JWT instead of sending initData
 * with every request.
 *
 * Flow:
 *   1. Read initData from Telegram.WebApp
 *   2. POST /telegram/mini-app/auth/exchange { init_data }
 *   3. Store JWT access_token + refresh_token
 *   4. Attach Authorization: Bearer <token> to all subsequent requests
 *   5. On 401: try refresh, if fails → re-exchange
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
// @ts-expect-error — module resolves at runtime via Vite alias
import { readTelegramMiniAppInitData } from '../patientUtils';

const TOKEN_STORAGE_KEY = 'patient_jwt_token';
const REFRESH_TOKEN_STORAGE_KEY = 'patient_refresh_token';
const TOKEN_EXPIRY_KEY = 'patient_token_expires_at';

interface TokenData {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

interface ExchangeErrorResponse {
  response?: {
    data?: {
      detail?: {
        reason?: string;
      };
    };
  };
}

export interface UseTelegramAuthReturn {
  token: string | null;
  isAuthenticating: boolean;
  error: string;
  exchange: () => Promise<string | null>;
  refreshToken: () => Promise<string | null>;
  clearTokens: () => void;
  isAuthenticated: boolean;
}

export function useTelegramAuth(): UseTelegramAuthReturn {
  const [token, setToken] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem(TOKEN_STORAGE_KEY);
    } catch {
      return null;
    }
  });
  const [isAuthenticating, setIsAuthenticating] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const storeTokens = useCallback((data: TokenData): void => {
    try {
      sessionStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
      sessionStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, data.refresh_token);
      const expiresAt = Date.now() + data.expires_in * 1000;
      sessionStorage.setItem(TOKEN_EXPIRY_KEY, String(expiresAt));
      setToken(data.access_token);
    } catch {
      // sessionStorage may be unavailable in some contexts
    }
  }, []);

  const clearTokens = useCallback((): void => {
    try {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY);
      sessionStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
      sessionStorage.removeItem(TOKEN_EXPIRY_KEY);
    } catch {
      // ignore
    }
    setToken(null);
  }, []);

  const exchange = useCallback(async (): Promise<string | null> => {
    const initData = readTelegramMiniAppInitData();
    if (!initData) {
      setError('init_data_required');
      return null;
    }

    setIsAuthenticating(true);
    setError('');

    try {
      const response = await api.post('/telegram/mini-app/auth/exchange', {
        init_data: initData,
      });

      const data = response.data as TokenData | undefined;
      if (data?.access_token) {
        storeTokens(data);
        return data.access_token;
      }
      return null;
    } catch (err) {
      const e = err as ExchangeErrorResponse;
      const reason = e?.response?.data?.detail?.reason || 'exchange_failed';
      setError(String(reason));
      return null;
    } finally {
      setIsAuthenticating(false);
    }
  }, [storeTokens]);

  const refreshToken = useCallback(async (): Promise<string | null> => {
    try {
      const storedRefresh = sessionStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
      if (!storedRefresh) {
        return null;
      }

      const response = await api.post('/auth/refresh', {
        refresh_token: storedRefresh,
      });

      const data = response.data as TokenData | undefined;
      if (data?.access_token) {
        storeTokens(data);
        return data.access_token;
      }
      return null;
    } catch {
      clearTokens();
      return null;
    }
  }, [storeTokens, clearTokens]);

  useEffect(() => {
    if (!token) {
      exchange();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!token) return;

    try {
      const expiresAt = parseInt(sessionStorage.getItem(TOKEN_EXPIRY_KEY) || '0', 10);
      const now = Date.now();
      const msUntilExpiry = expiresAt - now;
      const refreshAt = msUntilExpiry - 60_000;

      if (refreshAt > 0) {
        if (refreshTimerRef.current) {
          clearTimeout(refreshTimerRef.current);
        }
        refreshTimerRef.current = setTimeout(() => {
          refreshToken();
        }, refreshAt);
      }
    } catch {
      // ignore
    }

    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, [token, refreshToken]);

  return {
    token,
    isAuthenticating,
    error,
    exchange,
    refreshToken,
    clearTokens,
    isAuthenticated: Boolean(token),
  };
}

export default useTelegramAuth;
