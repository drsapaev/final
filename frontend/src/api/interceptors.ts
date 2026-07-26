/**
 * API Interceptors
 * Обработка запросов и ответов
 */
import { api } from './client';
import { tokenManager } from '../utils/tokenManager';
import { clearToken as clearAuthState } from '../stores/auth';
import logger from '../utils/logger';
import { handleError } from '../utils/errorHandler';
// Phase 1 — typed accessor for axios-like errors in interceptors.
interface AxiosLikeError {
  config?: { url?: string; expectedErrorStatuses?: number[]; silent?: boolean };
  response?: { status?: number };
  code?: string;
  name?: string;
}


export function isExpectedApiErrorStatus(originalRequest: { expectedErrorStatuses?: number[] } | undefined, status: unknown): boolean {
  if (!originalRequest || typeof status !== 'number') {
    return false;
  }

  const expectedStatuses = originalRequest.expectedErrorStatuses;
  return Array.isArray(expectedStatuses) && expectedStatuses.includes(status);
}

export function isCanceledApiError(error: unknown): boolean {
  return (error as AxiosLikeError)?.code === 'ERR_CANCELED' || (error as AxiosLikeError)?.name === 'CanceledError';
}

export function shouldSuppressApiError(error: unknown): boolean {
  const originalRequest = (error as AxiosLikeError)?.config;
  const status = (error as AxiosLikeError)?.response?.status;

  if (isCanceledApiError(error)) {
    return true;
  }

  if (isExpectedApiErrorStatus(originalRequest, status)) {
    return true;
  }

  return originalRequest?.silent === true && status === 404;
}

export function shouldClearAuthOnUnauthorized(error: unknown, hasToken: boolean = tokenManager.hasToken()): boolean {
  if (!hasToken || (error as AxiosLikeError)?.response?.status !== 401) {
    return false;
  }

  const requestUrl = String((error as AxiosLikeError)?.config?.url || '');
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
export function setupInterceptors(): void {
  // audit/phase-final, BS-26 + BS-27: no-op. Interceptors registered in api/client.ts.
  // Previously registered a SECOND pair on the same instance (double registration).
}

/**
 * Установка базового токена при загрузке приложения
 */
export function initializeAuth(): void {
  const token = tokenManager.getAccessToken();
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }
}

/**
 * Очистка авторизации
 */
export function clearAuth(): void {
  tokenManager.clearAll();
  delete api.defaults.headers.common['Authorization'];
}
