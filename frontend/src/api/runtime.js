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

export function getApiOrigin() {
  return trimTrailingSlash(import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL);
}

export function getApiBaseUrl() {
  return `${getApiOrigin()}/api/v1`;
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
  const apiOrigin = new URL(getApiOrigin());
  const wsProtocol = apiOrigin.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${wsProtocol}//${apiOrigin.host}`;
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
