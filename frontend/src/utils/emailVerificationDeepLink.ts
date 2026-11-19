/** Capture email verification capabilities before telemetry or requests. */
let pendingToken: string | null = null;
let pendingTimer: number | null = null;

function clearPending(): void {
  pendingToken = null;
  if (pendingTimer !== null && typeof window !== 'undefined') window.clearTimeout(pendingTimer);
  pendingTimer = null;
}

export function extractEmailVerificationCredential(): boolean {
  if (typeof window === 'undefined') return false;
  let pathname: string;
  try {
    pathname = decodeURIComponent(window.location.pathname).toLowerCase().replace(/\/+$/, '');
  } catch {
    return false;
  }
  if (pathname !== '/verify-email') return false;

  const { search, hash } = window.location;
  const query = new URLSearchParams(search);
  const secretKeys = Array.from(query.keys()).filter((key) => key.toLowerCase().includes('token'));
  for (const key of secretKeys) query.delete(key);
  if (!hash && secretKeys.length === 0) return false;
  const params = new URLSearchParams(hash.startsWith('#') ? hash.slice(1) : hash);
  const candidates = params.getAll('token');
  const token = candidates.length === 1 ? candidates[0] : '';
  const nextSearch = query.toString();
  clearPending();
  // If history replacement fails, fail closed: do not start telemetry or
  // submit a credential that is still exposed in the address bar.
  window.history.replaceState(window.history.state, '', window.location.pathname + (nextSearch ? `?${nextSearch}` : ''));
  if (/^v1\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{22}$/.test(token)) {
    pendingToken = token;
    pendingTimer = window.setTimeout(clearPending, 5 * 60 * 1000);
  }
  return true;
}

export function takeEmailVerificationCredential(): string | null {
  const token = pendingToken;
  clearPending();
  return token;
}
