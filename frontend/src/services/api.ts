// src/services/api.ts
// Phase 1 — migrated from .js. Axios-like API wrapper; types added.
//
// Note: This is a separate legacy API client (not to be confused with
// src/api/client.ts which is the main axios-based client). It exists for
// backward compatibility with components that import from '@/services/api'.

import logger from '../utils/logger';
import { buildApiUrl } from '../api/runtime';
import { tokenManager } from '../utils/tokenManager';

interface ApiRequestOptions {
  headers?: Record<string, string>;
  params?: Record<string, unknown>;
  body?: unknown;
  data?: unknown;
}

interface ApiResponse<T = unknown> {
  data: T | null;
  status: number;
}

function getAuthToken(): string {
  return tokenManager.getAccessToken() || '';
}

async function request<T = unknown>(
  method: string,
  path: string,
  options: ApiRequestOptions = {},
): Promise<ApiResponse<T>> {
  const token = getAuthToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  // Build URL with params
  let url = buildApiUrl(path);
  if (options.params) {
    const searchParams = new URLSearchParams();
    Object.entries(options.params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  logger.log(`[api] ${method} ${path}`, { hasToken: !!token });

  const fetchOptions: RequestInit & { body?: string } = {
    method,
    headers,
  };

  if (options.body || (options.data && method !== 'GET')) {
    fetchOptions.body = JSON.stringify(options.body || options.data);
  }

  const res = await fetch(url, fetchOptions);

  if (!res.ok) {
    let detail = 'Request failed';
    try {
      const errorData = await res.json();
      detail = (errorData as { detail?: string; message?: string }).detail
        || (errorData as { message?: string }).message
        || detail;
    } catch {
      detail = `HTTP ${res.status}: ${res.statusText}`;
    }

    logger.error(`[api] Request failed: ${path}`, { status: res.status, detail });
    throw new Error(detail);
  }

  try {
    const data = await res.json();
    return { data, status: res.status };
  } catch {
    return { data: null, status: res.status };
  }
}

const api = {
  get: <T = unknown>(path: string, options?: ApiRequestOptions) => request<T>('GET', path, options),
  post: <T = unknown>(path: string, data: unknown, options?: ApiRequestOptions) =>
    request<T>('POST', path, { ...options, body: data }),
  put: <T = unknown>(path: string, data: unknown, options?: ApiRequestOptions) =>
    request<T>('PUT', path, { ...options, body: data }),
  delete: <T = unknown>(path: string, options?: ApiRequestOptions) => request<T>('DELETE', path, options),
  patch: <T = unknown>(path: string, data: unknown, options?: ApiRequestOptions) =>
    request<T>('PATCH', path, { ...options, body: data }),
};

export default api;
