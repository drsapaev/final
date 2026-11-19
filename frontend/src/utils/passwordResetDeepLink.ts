/** Keep reset capabilities out of URLs, telemetry and browser storage. */
let pendingToken: string | null = null;
let pendingTimer: number | null = null;

export function clearPasswordResetCredential(): void {
  pendingToken = null;
  if (pendingTimer !== null && typeof window !== 'undefined') window.clearTimeout(pendingTimer);
  pendingTimer = null;
}

export function getPasswordResetCredential(): string | null {
  return pendingToken;
}

export function extractPasswordResetCredential(): boolean {
  if (typeof window === 'undefined') return false;
  let path: string;
  try {
    path = decodeURIComponent(window.location.pathname).toLowerCase().replace(/\/+$/, '');
  } catch {
    return false;
  }
  if (path !== '/reset-password') return false;

  const query = new URLSearchParams(window.location.search);
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const queryKeys = Array.from(query.keys()).filter((key) => key.toLowerCase().includes('token'));
  const fragmentKeys = Array.from(fragment.keys()).filter((key) => key.toLowerCase().includes('token'));
  if (!queryKeys.length && !fragmentKeys.length) return false;
  const candidates = [...query, ...fragment]
    .filter(([key]) => key.toLowerCase() === 'token')
    .map(([, value]) => value);
  for (const key of queryKeys) query.delete(key);
  for (const key of fragmentKeys) fragment.delete(key);
  clearPasswordResetCredential();
  const search = query.toString();
  const hash = fragment.toString();
  // Do not retain or submit the capability if the visible URL cannot be cleaned.
  window.history.replaceState(window.history.state, '', window.location.pathname
    + (search ? `?${search}` : '') + (hash ? `#${hash}` : ''));
  const token = candidates.length === 1 ? candidates[0] : '';
  if (/^[A-Za-z0-9_-]{1,256}$/.test(token)) {
    pendingToken = token;
    pendingTimer = window.setTimeout(clearPasswordResetCredential, 60 * 60 * 1000);
  }
  return true;
}
