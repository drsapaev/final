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
type IntentKind = 'telegram' | 'entry' | 'anonymous';
type RequestIntent = { matches: (kind: IntentKind, credential: string) => boolean };
type SessionLease = {
  session: TelegramMiniAppStoredSession;
  generation: number;
  intent: RequestIntent;
};
const PATIENT_MANIFEST_URL = '/telegram/mini-app/patient/manifest';

// This client never reads staff tokens or runs staff refresh/logout interceptors.
const transport = axios.create({ baseURL: getApiBaseUrl(), withCredentials: true, timeout: 20000 });
let csrfToken = '';
let csrfFlight: Promise<string> | null = null;
let activeSessionContext: string | null = null;
let sessionGeneration = 0;
// Launch credentials remain in memory only; the stored session uses a digest.
let activeIntent: RequestIntent | null = null;
let authFlight: {
  context: string;
  generation: number;
  intent: RequestIntent;
  promise: Promise<TelegramMiniAppStoredSession>;
} | null = null;
let refreshFlight: {
  token: string;
  generation: number;
  intent: RequestIntent;
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

function claimIntent(kind: IntentKind, credential: string): RequestIntent {
  if (activeIntent?.matches(kind, credential)) return activeIntent;
  if (activeIntent || kind !== 'telegram') {
    miniAppTokenManager.clear();
    activeSessionContext = null;
    sessionGeneration += 1;
  }
  // Keep the credential in a closure, not in an enumerable object or storage.
  activeIntent = { matches: (nextKind, nextCredential) => kind === nextKind && credential === nextCredential };
  return activeIntent;
}

function assertIntentCurrent(intent: RequestIntent): void {
  if (activeIntent !== intent) throw canceledSessionRequest();
}

function currentIntent(kind: IntentKind, credential: string): RequestIntent {
  if (activeIntent && !activeIntent.matches(kind, credential)) throw canceledSessionRequest();
  return activeIntent || claimIntent(kind, credential);
}

function currentTelegramIntent(initData: string): RequestIntent {
  if (!initData) throw sessionError();
  return currentIntent('telegram', initData);
}

async function whileIntentCurrent<T>(promise: Promise<T>, intent: RequestIntent): Promise<T> {
  try {
    const value = await promise;
    assertIntentCurrent(intent);
    return value;
  } catch (error) {
    assertIntentCurrent(intent);
    throw error;
  }
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
  return activeIntent === lease.intent
    && sessionGeneration === lease.generation
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
  guard?: () => void,
): Promise<AxiosResponse<T>> {
  try {
    const csrfValue = await csrf();
    guard?.();
    return await transport.post<T>(url, body, {
      ...config, headers: { ...config.headers, 'X-CSRF-Token': csrfValue },
    });
  } catch (error) {
    guard?.();
    // Cookie rotation/expiry has one bounded recovery. No auth retry here.
    if (csrfRetry && axios.isAxiosError(error)
      && error.response?.headers?.['x-csrf-status'] === 'rejected') {
      csrfToken = '';
      return post<T>(url, body, config, false, guard);
    }
    throw error;
  }
}

async function guardedPost<T>(
  url: string, body: unknown, config: AxiosRequestConfig, guard: () => void,
): Promise<AxiosResponse<T>> {
  try {
    const response = await post<T>(url, body, config, true, guard);
    guard();
    return response;
  } catch (error) {
    guard();
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
  intent: RequestIntent,
): Promise<TelegramMiniAppStoredSession> {
  if (refreshFlight?.token === session.refresh_token
    && refreshFlight.generation === generation
    && refreshFlight.intent === intent) return refreshFlight.promise;
  const guard = () => {
    assertIntentCurrent(intent);
    const current = miniAppTokenManager.get();
    if (current?.refresh_token !== session.refresh_token
      || terminatedContexts.has(session.context)
      || sessionGeneration !== generation
      || activeSessionContext !== session.context) throw canceledSessionRequest();
  };
  const promise = post<TokenPair>('/telegram/mini-app/auth/refresh', {
    refresh_token: session.refresh_token,
  }, {}, true, guard).then(({ data }) => {
    guard();
    if (refreshFlight?.promise !== promise) throw canceledSessionRequest();
    return install(data, session.context);
  }).catch((error: unknown) => {
    // A late response from an older principal cannot clear a replacement.
    const current = miniAppTokenManager.get();
    const generationIsCurrent = activeIntent === intent && sessionGeneration === generation
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
    if (refreshFlight?.promise === promise) refreshFlight = null;
  });
  refreshFlight = { token: session.refresh_token, generation, intent, promise };
  return promise;
}

async function ensureSession(initData: string, intent: RequestIntent): Promise<SessionLease> {
  if (!initData) throw sessionError();
  const context = await whileIntentCurrent(contextFor(initData), intent);
  if (terminatedContexts.has(context)) throw sessionError();
  const existing = miniAppTokenManager.get();
  if (existing?.context === context) {
    const generation = activateSessionContext(context);
    const session = existing.expires_at > Date.now() + 30000
      ? existing
      : await whileIntentCurrent(refresh(existing, generation, intent), intent);
    const lease = { session, generation, intent };
    assertSessionLeaseCurrent(lease);
    return lease;
  }
  const flight = authFlight;
  if (flight?.context === context
    && flight.generation === sessionGeneration
    && flight.intent === intent
    && activeSessionContext === context) {
    const session = await whileIntentCurrent(flight.promise, intent);
    const lease = { session, generation: flight.generation, intent };
    assertSessionLeaseCurrent(lease);
    return lease;
  }
  // A changed Telegram launch must not inherit the previous patient's session.
  miniAppTokenManager.clear();
  const generation = beginSessionContext(context);
  const guard = () => {
    assertIntentCurrent(intent);
    if (activeSessionContext !== context || sessionGeneration !== generation
      || terminatedContexts.has(context)) throw canceledSessionRequest();
  };
  const promise = post<TokenPair>('/telegram/mini-app/auth/exchange', { init_data: initData }, {}, true, guard)
    .then(({ data }) => {
      guard();
      if (authFlight?.promise !== promise) throw canceledSessionRequest();
      return install(data, context);
    })
    .catch((error: unknown) => {
      guard();
      throw error;
    })
    .finally(() => {
      if (authFlight?.promise === promise) authFlight = null;
    });
  authFlight = { context, generation, intent, promise };
  const lease = { session: await whileIntentCurrent(promise, intent), generation, intent };
  assertSessionLeaseCurrent(lease);
  return lease;
}

async function authorizedPost<T>(
  url: string, body: unknown, initData: string, config: AxiosRequestConfig,
  intent: RequestIntent,
): Promise<AxiosResponse<T>> {
  const lease = await whileIntentCurrent(ensureSession(initData, intent), intent);
  const { session } = lease;
  assertSessionLeaseCurrent(lease);
  const send = (token: string) => guardedPost<T>(url, body, {
    ...config, headers: { ...config.headers, Authorization: `Bearer ${token}` },
  }, () => assertSessionLeaseCurrent(lease));
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
      ? await whileIntentCurrent(refresh(live, lease.generation, intent), intent)
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
    const entryToken = typeof body.entryToken === 'string' ? body.entryToken : '';
    const kind = initData ? 'telegram' : entryToken ? 'entry' : 'anonymous';
    // The shell starts a launch with the manifest. Follow-on work may use that
    // launch, but an old callback cannot replace a newer launch's principal.
    const intent = url === PATIENT_MANIFEST_URL
      ? claimIntent(kind, initData || entryToken)
      : currentIntent(kind, initData || entryToken);
    const guard = () => assertIntentCurrent(intent);
    if (!initData || url.includes('/onboarding/')) return guardedPost(url, body, config || {}, guard);
    const payload = Object.fromEntries(
      Object.entries(body).filter(([key]) => key !== 'initData' && key !== 'entryToken'),
    );
    try {
      return await authorizedPost(url, payload, initData, config || {}, intent);
    } catch (error) {
      guard();
      // Unknown/unlinked users retain their restricted onboarding manifest.
      // Invalid/revoked JWTs and replay/expiry never fall back to initData.
      const reason = axios.isAxiosError(error) ? error.response?.data?.detail?.reason : '';
      if (url === PATIENT_MANIFEST_URL
        && ['patient_scope_required', 'telegram_link_required'].includes(reason)) {
        return guardedPost(url, body, config || {}, guard);
      }
      throw error;
    }
  },
};

export const telegramMiniAppSessions = {
  async list(initData: string): Promise<SessionList> {
    const intent = currentTelegramIntent(initData);
    return (await authorizedPost<SessionList>('/telegram/mini-app/sessions/list', {}, initData, {}, intent)).data;
  },
  async revokeOthers(initData: string): Promise<void> {
    const intent = currentTelegramIntent(initData);
    await authorizedPost('/telegram/mini-app/sessions/revoke-all', {}, initData, {}, intent);
  },
  async revoke(id: string, initData: string): Promise<void> {
    const intent = currentTelegramIntent(initData);
    await authorizedPost(`/telegram/mini-app/sessions/${encodeURIComponent(id)}/revoke`, {}, initData, {}, intent);
  },
  async logout(initData: string): Promise<void> {
    const intent = currentTelegramIntent(initData);
    const context = await whileIntentCurrent(contextFor(initData), intent);
    await authorizedPost('/telegram/mini-app/auth/logout', {}, initData, {}, intent);
    assertIntentCurrent(intent);
    terminateSessionContext(context);
    if (miniAppTokenManager.get()?.context === context) miniAppTokenManager.clear();
    activeIntent = null;
  },
};
