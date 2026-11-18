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
type SessionLease = {
  session: TelegramMiniAppStoredSession;
  generation: number;
};

// This client never reads staff tokens or runs staff refresh/logout interceptors.
const transport = axios.create({ baseURL: getApiBaseUrl(), withCredentials: true, timeout: 20000 });
let csrfToken = '';
let csrfFlight: Promise<string> | null = null;
let activeSessionContext: string | null = null;
let sessionGeneration = 0;
let authFlight: {
  context: string;
  generation: number;
  promise: Promise<TelegramMiniAppStoredSession>;
} | null = null;
let refreshFlight: {
  token: string;
  generation: number;
  promise: Promise<TelegramMiniAppStoredSession>;
} | null = null;
const terminatedContexts = new Set<string>();

function sessionError() {
  return Object.assign(new Error('Mini App session expired'), {
    response: { status: 401, data: { detail: { reason: 'session_invalid' } } },
  });
}

function canceledSessionRequest() {
  return new axios.CanceledError('Mini App request canceled because its session changed');
}

function activateSessionContext(context: string): number {
  if (activeSessionContext !== context) {
    activeSessionContext = context;
    sessionGeneration += 1;
  }
  return sessionGeneration;
}

function beginSessionContext(context: string): number {
  activeSessionContext = context;
  sessionGeneration += 1;
  return sessionGeneration;
}

function terminateSessionContext(context: string): void {
  terminatedContexts.add(context);
  if (activeSessionContext === context) {
    activeSessionContext = null;
    sessionGeneration += 1;
  }
}

function isSessionLeaseCurrent(lease: SessionLease): boolean {
  const context = lease.session.context;
  return sessionGeneration === lease.generation
    && activeSessionContext === context
    && !terminatedContexts.has(context)
    && miniAppTokenManager.get()?.context === context;
}

function assertSessionLeaseCurrent(lease: SessionLease): void {
  if (!isSessionLeaseCurrent(lease)) throw canceledSessionRequest();
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

async function refresh(
  session: TelegramMiniAppStoredSession,
  generation: number,
): Promise<TelegramMiniAppStoredSession> {
  if (refreshFlight?.token === session.refresh_token
    && refreshFlight.generation === generation) return refreshFlight.promise;
  const promise = post<TokenPair>('/telegram/mini-app/auth/refresh', {
    refresh_token: session.refresh_token,
  }).then(({ data }) => {
    const current = miniAppTokenManager.get();
    if (current?.refresh_token !== session.refresh_token
      || terminatedContexts.has(session.context)
      || sessionGeneration !== generation
      || activeSessionContext !== session.context) {
      throw canceledSessionRequest();
    }
    return install(data, session.context);
  }).catch((error: unknown) => {
    // A late response from an older principal cannot clear a replacement.
    const current = miniAppTokenManager.get();
    const generationIsCurrent = sessionGeneration === generation
      && activeSessionContext === session.context;
    if (generationIsCurrent && current?.refresh_token === session.refresh_token
      && axios.isAxiosError(error) && [401, 403].includes(error.response?.status || 0)) {
      miniAppTokenManager.clear();
      terminateSessionContext(session.context);
    } else if (!generationIsCurrent || current?.context !== session.context) {
      throw canceledSessionRequest();
    }
    throw error;
  }).finally(() => {
    if (refreshFlight?.token === session.refresh_token
      && refreshFlight.generation === generation) refreshFlight = null;
  });
  refreshFlight = { token: session.refresh_token, generation, promise };
  return promise;
}

async function ensureSession(initData: string): Promise<SessionLease> {
  if (!initData) throw sessionError();
  const context = await contextFor(initData);
  if (terminatedContexts.has(context)) throw sessionError();
  const existing = miniAppTokenManager.get();
  if (existing?.context === context) {
    const generation = activateSessionContext(context);
    const session = existing.expires_at > Date.now() + 30000
      ? existing
      : await refresh(existing, generation);
    const lease = { session, generation };
    assertSessionLeaseCurrent(lease);
    return lease;
  }
  if (authFlight?.context === context
    && authFlight.generation === sessionGeneration
    && activeSessionContext === context) {
    const lease = { session: await authFlight.promise, generation: authFlight.generation };
    assertSessionLeaseCurrent(lease);
    return lease;
  }
  // A changed Telegram launch must not inherit the previous patient's session.
  miniAppTokenManager.clear();
  const generation = beginSessionContext(context);
  const promise = post<TokenPair>('/telegram/mini-app/auth/exchange', { init_data: initData })
    .then(({ data }) => {
      if (authFlight?.context !== context
        || authFlight.generation !== generation
        || activeSessionContext !== context
        || sessionGeneration !== generation
        || terminatedContexts.has(context)) throw canceledSessionRequest();
      return install(data, context);
    })
    .finally(() => {
      if (authFlight?.context === context && authFlight.generation === generation) authFlight = null;
    });
  authFlight = { context, generation, promise };
  const lease = { session: await promise, generation };
  assertSessionLeaseCurrent(lease);
  return lease;
}

async function authorizedPost<T>(
  url: string, body: unknown, initData: string, config: AxiosRequestConfig = {},
): Promise<AxiosResponse<T>> {
  const lease = await ensureSession(initData);
  const { session } = lease;
  assertSessionLeaseCurrent(lease);
  const send = (token: string) => post<T>(url, body, {
    ...config, headers: { ...config.headers, Authorization: `Bearer ${token}` },
  });
  try {
    const response = await send(session.access_token);
    assertSessionLeaseCurrent(lease);
    return response;
  } catch (error) {
    // A response from the previous patient/session is discarded regardless of
    // status. This also keeps stale 403/500 errors from reaching old callers.
    assertSessionLeaseCurrent(lease);
    if (!axios.isAxiosError(error) || error.response?.status !== 401) throw error;
    const live = miniAppTokenManager.get();
    if (live?.context !== session.context) throw sessionError();
    const next = live.access_token === session.access_token
      ? await refresh(live, lease.generation)
      : live;
    assertSessionLeaseCurrent(lease);
    try {
      const response = await send(next.access_token);
      assertSessionLeaseCurrent(lease);
      return response;
    } catch (retryError) {
      assertSessionLeaseCurrent(lease);
      throw retryError;
    }
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
    terminateSessionContext(context);
    if (miniAppTokenManager.get()?.context === context) miniAppTokenManager.clear();
  },
};
