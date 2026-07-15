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
 *
 * Usage:
 *   const { token, isAuthenticating, error, exchange } = useTelegramAuth();
 *
 *   // In API calls:
 *   api.post('/telegram/mini-app/cabinet/summary', {
 *     ...body,
 *     // No more init_data needed — JWT is in Authorization header
 *   });
 */
import { useState, useCallback, useEffect, useRef } from 'react';
import { api } from '../../api/client';
import { readTelegramMiniAppInitData } from '../patientUtils';

const TOKEN_STORAGE_KEY = 'patient_jwt_token';
const REFRESH_TOKEN_STORAGE_KEY = 'patient_refresh_token';
const TOKEN_EXPIRY_KEY = 'patient_token_expires_at';

export function useTelegramAuth() {
  const [token, setToken] = useState(() => {
    try {
      return sessionStorage.getItem(TOKEN_STORAGE_KEY);
    } catch {
      return null;
    }
  });
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [error, setError] = useState('');
  const refreshTimerRef = useRef(null);

  const storeTokens = useCallback((data) => {
    try {
      sessionStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
      sessionStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, data.refresh_token);
      const expiresAt = Date.now() + (data.expires_in * 1000);
      sessionStorage.setItem(TOKEN_EXPIRY_KEY, String(expiresAt));
      setToken(data.access_token);
    } catch {
      // sessionStorage may be unavailable in some contexts
    }
  }, []);

  const clearTokens = useCallback(() => {
    try {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY);
      sessionStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
      sessionStorage.removeItem(TOKEN_EXPIRY_KEY);
    } catch {
      // ignore
    }
    setToken(null);
  }, []);

  const exchange = useCallback(async () => {
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

      if (response.data?.access_token) {
        storeTokens(response.data);
        return response.data.access_token;
      }
      return null;
    } catch (err) {
      const reason = err?.response?.data?.detail?.reason || 'exchange_failed';
      setError(reason);
      return null;
    } finally {
      setIsAuthenticating(false);
    }
  }, [storeTokens]);

  const refreshToken = useCallback(async () => {
    try {
      const storedRefresh = sessionStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
      if (!storedRefresh) {
        return null;
      }

      const response = await api.post('/auth/refresh', {
        refresh_token: storedRefresh,
      });

      if (response.data?.access_token) {
        storeTokens(response.data);
        return response.data.access_token;
      }
      return null;
    } catch {
      clearTokens();
      return null;
    }
  }, [storeTokens, clearTokens]);

  // Auto-exchange on mount if no token
  useEffect(() => {
    if (!token) {
      exchange();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-refresh before expiry
  useEffect(() => {
    if (!token) return;

    try {
      const expiresAt = parseInt(sessionStorage.getItem(TOKEN_EXPIRY_KEY) || '0', 10);
      const now = Date.now();
      const msUntilExpiry = expiresAt - now;
      const refreshAt = msUntilExpiry - 60_000; // Refresh 1 min before expiry

      if (refreshAt > 0) {
        if (refreshTimerRef.current) {
          clearTimeout(refreshTimerRef.current);
        }
        refreshTimerRef.current = window.setTimeout(() => {
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
