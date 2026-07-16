interface RuntimeSnapshot {
  currentOrigin: string;
  apiOrigin: string;
  apiBaseUrl: string;
  wsOrigin: string;
}

// src/api/runtime.ts
// Phase 1 — migrated from .js. URL resolution helpers; types added.

const DEFAULT_API_BASE_URL = 'http://localhost:18000';
const LOCAL_ORIGIN_PATTERN = /^https?:\/\/(?:localhost|127\.0\.0\.1|\[::1\]|0\.0\.0\.0)(?::\d+)?(?:\/|$)/i;

function trimTrailingSlash(value: string = ''): string {
  return value.replace(/\/+$/, '');
}

function trimLeadingSlash(value: string = ''): string {
  return value.replace(/^\/+/, '');
}

function isAbsoluteHttpUrl(value: string = ''): boolean {
  return /^https?:\/\//i.test(value);
}

function isAbsoluteWsUrl(value: string = ''): boolean {
  return /^wss?:\/\//i.test(value);
}

function isLocalOrigin(value: string = ''): boolean {
  return LOCAL_ORIGIN_PATTERN.test(value);
}

function isViteDevProxyOrigin(value: string = ''): boolean {
  if (!isLocalOrigin(value)) {
    return false;
  }

  try {
    const parsed = new URL(value);
    return parsed.port === '5173';
  } catch {
    return false;
  }
}

function parseOriginParts(value: string = ''): { protocol: string; host: string } | null {
  if (!value) {
    return null;
  }

  const urlCtor = typeof globalThis.URL === 'function' ? globalThis.URL : null;
  if (urlCtor) {
    try {
      const parsed = new urlCtor(value);
      return {
        protocol: parsed.protocol,
        host: parsed.host,
      };
    } catch {
      // Fall through to the safer parser below.
    }
  }

  if (typeof document !== 'undefined' && typeof document.createElement === 'function') {
    const anchor = document.createElement('a');
    anchor.href = value;
    if (anchor.protocol && anchor.host) {
      return {
        protocol: anchor.protocol,
        host: anchor.host,
      };
    }
  }

  const match = String(value).trim().match(/^(https?:)\/\/([^/]+)(?:\/.*)?$/i);
  if (!match) {
    return null;
  }

  return {
    protocol: match[1].toLowerCase(),
    host: match[2],
  };
}

function getBrowserOrigin(): string {
  if (typeof window === 'undefined' || !window.location?.origin) {
    return '';
  }

  if (!isAbsoluteHttpUrl(window.location.origin)) {
    return '';
  }

  return trimTrailingSlash(window.location.origin);
}

function buildRuntimeSnapshot(): RuntimeSnapshot {
  const currentOrigin = getBrowserOrigin();
  const configuredOrigin = trimTrailingSlash(import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL);
  const preferBrowserOrigin =
    currentOrigin && (!isLocalOrigin(currentOrigin) || isViteDevProxyOrigin(currentOrigin));
  const apiOrigin = preferBrowserOrigin ? currentOrigin : configuredOrigin;
  const apiBaseUrl = `${apiOrigin}/api/v1`;
  const parsedOrigin = parseOriginParts(apiOrigin) || parseOriginParts(configuredOrigin);
  const wsProtocol = parsedOrigin?.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsHost = parsedOrigin?.host || 'localhost:18000';
  const wsOrigin = `${wsProtocol}//${wsHost}`;

  return {
    currentOrigin,
    apiOrigin,
    apiBaseUrl,
    wsOrigin,
  };
}

function syncRuntimeProbeState(snapshot: RuntimeSnapshot): RuntimeSnapshot {
  if (typeof window === 'undefined') {
    return snapshot;
  }

  (window as unknown as { __CLINIC_RUNTIME__?: unknown }).__CLINIC_RUNTIME__ = {
    currentOrigin: snapshot.currentOrigin,
    apiOrigin: snapshot.apiOrigin,
    apiBaseUrl: snapshot.apiBaseUrl,
    wsOrigin: snapshot.wsOrigin,
  };
  return snapshot;
}

export function getRuntimeResolution(): RuntimeSnapshot {
  return syncRuntimeProbeState(buildRuntimeSnapshot());
}

export function getApiOrigin(): string {
  return getRuntimeResolution().apiOrigin;
}

export function getApiBaseUrl(): string {
  return getRuntimeResolution().apiBaseUrl;
}

export function buildApiUrl(path: string = ''): string {
  if (!path) {
    return getApiBaseUrl();
  }

  if (isAbsoluteHttpUrl(path)) {
    return path;
  }

  const normalizedPath = trimLeadingSlash(path);
  if (normalizedPath.startsWith('api/v1/')) {
    return `${getApiOrigin()}/${normalizedPath}`;
  }

  return `${getApiBaseUrl()}/${normalizedPath}`;
}

export function getWsBaseUrl(): string {
  return getRuntimeResolution().wsOrigin;
}

export function buildWsUrl(path: string = ''): string {
  if (!path) {
    return getWsBaseUrl();
  }

  if (isAbsoluteWsUrl(path)) {
    return path;
  }

  return `${getWsBaseUrl()}/${trimLeadingSlash(path)}`;
}
