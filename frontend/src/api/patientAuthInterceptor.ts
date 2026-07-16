/**
 * API interceptor — attaches patient JWT to all API requests (P5).
 *
 * Phase 1 — migrated from .js. Types added via Axios's built-in generics.
 *
 * Automatically adds Authorization: Bearer <token> header to all
 * api-client requests when a patient JWT is available.
 * On 401 response: clears token and triggers re-exchange.
 */
import type { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import { api } from './client';

const TOKEN_STORAGE_KEY = 'patient_jwt_token';

// Request interceptor: attach JWT if available
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    try {
      const token = sessionStorage.getItem(TOKEN_STORAGE_KEY);
      if (token) {
        config.headers.set('Authorization', `Bearer ${token}`);
      }
    } catch {
      // sessionStorage may be unavailable
    }
    return config;
  },
  (error: unknown) => Promise.reject(error),
);

// Response interceptor: on 401, clear token (will trigger re-exchange)
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    if (error?.response?.status === 401) {
      try {
        sessionStorage.removeItem(TOKEN_STORAGE_KEY);
        sessionStorage.removeItem('patient_refresh_token');
        sessionStorage.removeItem('patient_token_expires_at');
      } catch {
        // ignore
      }
    }
    return Promise.reject(error);
  },
);

export { api };
