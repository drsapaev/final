const DEFAULT_API_BASE_URL = 'http://localhost:18000';

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
  const apiOrigin = currentOrigin || trimTrailingSlash(import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL);
  const apiBaseUrl = `${apiOrigin}/api/v1`;
  const wsProtocol = new URL(apiOrigin).protocol === 'https:' ? 'wss:' : 'ws:';
  const wsOrigin = `${wsProtocol}//${new URL(apiOrigin).host}`;

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
