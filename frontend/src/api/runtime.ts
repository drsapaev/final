// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

const DEFAULT_API_BASE_URL = 'http://localhost:18000';
const LOCAL_ORIGIN_PATTERN = /^https?:\/\/(?:localhost|127\.0\.0\.1|\[::1\]|0\.0\.0\.0)(?::\d+)?(?:\/|$)/i;

function trimTrailingSlash(value = '') {
  return value.replace(/\/+$/, '');
}

function trimLeadingSlash(value = '') {
  return value.replace(/^\/+/, '');
}

function isAbsoluteHttpUrl(value = '') {
  return /^https?:\/\//i.test(value);
}

function isAbsoluteWsUrl(value = '') {
  return /^wss?:\/\//i.test(value);
}

function isLocalOrigin(value = '') {
  return LOCAL_ORIGIN_PATTERN.test(value);
}

function isViteDevProxyOrigin(value = '') {
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

function parseOriginParts(value = '') {
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

function getBrowserOrigin() {
  if (typeof window === 'undefined' || !window.location?.origin) {
    return '';
  }

  if (!isAbsoluteHttpUrl(window.location.origin)) {
    return '';
  }

  return trimTrailingSlash(window.location.origin);
}

function buildRuntimeSnapshot() {
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

function syncRuntimeProbeState(snapshot) {
  if (typeof window === 'undefined') {
    return snapshot;
  }

  window.__CLINIC_RUNTIME__ = {
    currentOrigin: snapshot.currentOrigin,
    apiOrigin: snapshot.apiOrigin,
    apiBaseUrl: snapshot.apiBaseUrl,
    wsOrigin: snapshot.wsOrigin,
  };
  return snapshot;
}

export function getRuntimeResolution() {
  return syncRuntimeProbeState(buildRuntimeSnapshot());
}

export function getApiOrigin() {
  return getRuntimeResolution().apiOrigin;
}

export function getApiBaseUrl() {
  return getRuntimeResolution().apiBaseUrl;
}

export function buildApiUrl(path = '') {
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

export function getWsBaseUrl() {
  return getRuntimeResolution().wsOrigin;
}

export function buildWsUrl(path = '') {
  if (!path) {
    return getWsBaseUrl();
  }

  if (isAbsoluteWsUrl(path)) {
    return path;
  }

  return `${getWsBaseUrl()}/${trimLeadingSlash(path)}`;
}
