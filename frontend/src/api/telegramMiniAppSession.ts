import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios';
import { getApiBaseUrl } from './runtime';
import { miniAppTokenManager, type TelegramMiniAppStoredSession } from '../utils/tokenManager';
import type {
  TelegramMiniAppTokenResponseDto, TelegramMiniAppSessionItemDto,
  TelegramMiniAppSessionListResponseDto,
} from '../types/api';

type TokenPair = TelegramMiniAppTokenResponseDto;
export type MiniAppSession = TelegramMiniAppSessionItemDto;
type SessionList = TelegramMiniAppSessionListResponseDto;

// This client never reads staff tokens or runs staff refresh/logout interceptors.
const transport = axios.create({ baseURL: getApiBaseUrl(), withCredentials: true, timeout: 20000 });
let csrfToken = '';
let csrfFlight: Promise<string> | null = null;
let authFlight: { context: string; promise: Promise<TelegramMiniAppStoredSession> } | null = null;
let refreshFlight: { token: string; promise: Promise<TelegramMiniAppStoredSession> } | null = null;
const terminatedContexts = new Set<string>();

function sessionError() {
  return Object.assign(new Error('Mini App session expired'), {
    response: { status: 401, data: { detail: { reason: 'session_invalid' } } },
  });
}

async function contextFor(initData: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(initData));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

async function csrf(): Promise<string> {
  if (csrfToken) return csrfToken;
  if (!csrfFlight) {
    csrfFlight = transport.get<{ csrf_token: string }>('/auth/csrf-token')
      .then(({ data }) => {
        if (!data.csrf_token) throw new Error('CSRF bootstrap failed');
        csrfToken = data.csrf_token;
        return csrfToken;
      })
      .finally(() => { csrfFlight = null; });
  }
  return csrfFlight;
}

async function post<T>(
  url: string, body: unknown, config: AxiosRequestConfig = {}, csrfRetry = true,
): Promise<AxiosResponse<T>> {
  try {
    return await transport.post<T>(url, body, {
      ...config, headers: { ...config.headers, 'X-CSRF-Token': await csrf() },
    });
  } catch (error) {
    // Cookie rotation/expiry has one bounded recovery. No auth retry here.
    if (csrfRetry && axios.isAxiosError(error)
      && error.response?.headers?.['x-csrf-status'] === 'rejected') {
      csrfToken = '';
      return post<T>(url, body, config, false);
    }
    throw error;
  }
}

function install(pair: TokenPair, context: string): TelegramMiniAppStoredSession {
  const session = { ...pair, context, expires_at: Date.now() + pair.expires_in * 1000 };
  miniAppTokenManager.set(session);
  return session;
}

async function refresh(session: TelegramMiniAppStoredSession): Promise<TelegramMiniAppStoredSession> {
  if (refreshFlight?.token === session.refresh_token) return refreshFlight.promise;
  const promise = post<TokenPair>('/telegram/mini-app/auth/refresh', {
    refresh_token: session.refresh_token,
  }).then(({ data }) => {
    const current = miniAppTokenManager.get();
    if (current?.refresh_token !== session.refresh_token || terminatedContexts.has(session.context)) {
      throw sessionError();
    }
    return install(data, session.context);
  }).catch((error: unknown) => {
    // A late response from an older principal cannot clear a replacement.
    if (miniAppTokenManager.get()?.refresh_token === session.refresh_token
      && axios.isAxiosError(error) && [401, 403].includes(error.response?.status || 0)) {
      miniAppTokenManager.clear();
      terminatedContexts.add(session.context);
    }
    throw error;
  }).finally(() => {
    if (refreshFlight?.token === session.refresh_token) refreshFlight = null;
  });
  refreshFlight = { token: session.refresh_token, promise };
  return promise;
}

async function ensureSession(initData: string): Promise<TelegramMiniAppStoredSession> {
  if (!initData) throw sessionError();
  const context = await contextFor(initData);
  if (terminatedContexts.has(context)) throw sessionError();
  const existing = miniAppTokenManager.get();
  if (existing?.context === context) {
    return existing.expires_at > Date.now() + 30000 ? existing : refresh(existing);
  }
  if (authFlight?.context === context) return authFlight.promise;
  // A changed Telegram launch must not inherit the previous patient's session.
  miniAppTokenManager.clear();
  const promise = post<TokenPair>('/telegram/mini-app/auth/exchange', { init_data: initData })
    .then(({ data }) => {
      if (authFlight?.context !== context || terminatedContexts.has(context)) throw sessionError();
      return install(data, context);
    })
    .finally(() => { if (authFlight?.context === context) authFlight = null; });
  authFlight = { context, promise };
  return promise;
}

async function authorizedPost<T>(
  url: string, body: unknown, initData: string, config: AxiosRequestConfig = {},
): Promise<AxiosResponse<T>> {
  const session = await ensureSession(initData);
  const send = (token: string) => post<T>(url, body, {
    ...config, headers: { ...config.headers, Authorization: `Bearer ${token}` },
  });
  try {
    return await send(session.access_token);
  } catch (error) {
    if (!axios.isAxiosError(error) || error.response?.status !== 401) throw error;
    const live = miniAppTokenManager.get();
    if (live?.context !== session.context) throw sessionError();
    const next = live.access_token === session.access_token ? await refresh(live) : live;
    return send(next.access_token);
  }
}

export const telegramMiniAppApi = {
  async post(
    url: string, body: Record<string, unknown>, config?: AxiosRequestConfig,
  ): Promise<AxiosResponse> {
    const initData = typeof body.initData === 'string' ? body.initData : '';
    if (!initData || url.includes('/onboarding/')) return post(url, body, config);
    const payload = Object.fromEntries(
      Object.entries(body).filter(([key]) => key !== 'initData' && key !== 'entryToken'),
    );
    try {
      return await authorizedPost(url, payload, initData, config);
    } catch (error) {
      // Unknown/unlinked users retain their restricted onboarding manifest.
      // Invalid/revoked JWTs and replay/expiry never fall back to initData.
      const reason = axios.isAxiosError(error) ? error.response?.data?.detail?.reason : '';
      if (url === '/telegram/mini-app/patient/manifest'
        && ['patient_scope_required', 'telegram_link_required'].includes(reason)) {
        return post(url, body, config);
      }
      throw error;
    }
  },
};

export const telegramMiniAppSessions = {
  async list(initData: string): Promise<SessionList> {
    return (await authorizedPost<SessionList>('/telegram/mini-app/sessions/list', {}, initData)).data;
  },
  async revokeOthers(initData: string): Promise<void> {
    await authorizedPost('/telegram/mini-app/sessions/revoke-all', {}, initData);
  },
  async revoke(id: string, initData: string): Promise<void> {
    await authorizedPost(`/telegram/mini-app/sessions/${encodeURIComponent(id)}/revoke`, {}, initData);
  },
  async logout(initData: string): Promise<void> {
    const context = await contextFor(initData);
    await authorizedPost('/telegram/mini-app/auth/logout', {}, initData);
    terminatedContexts.add(context);
    if (miniAppTokenManager.get()?.context === context) miniAppTokenManager.clear();
  },
};
