/**
 * Activation deep-link credential handling (Phase 0 follow-up, Codex P1).
 *
 * The canonical handout link carries the 72h activation credential in the
 * URL fragment (/patient/activate#token=...) so it is never transmitted to
 * the server. But the fragment still lives in window.location until the
 * PatientActivatePage effect strips it — and telemetry (Sentry) initializes
 * in main.tsx BEFORE React mounts. The Sentry scrubber redacts object keys
 * containing "token"; URL-valued telemetry fields (request.url, breadcrumb
 * from/to) are NOT scrubbed, so a pageload trace or a startup error could
 * otherwise carry the credential to Sentry.
 *
 * extractPatientActivationFragment() must therefore run BEFORE initSentry():
 * it copies the token into an in-memory one-shot slot (never storage) and
 * rewrites the address bar without the fragment. PatientActivatePage consumes
 * the slot on mount and falls back to the router location (fragment/query)
 * for environments where the bootstrap extraction did not run (tests,
 * MemoryRouter).
 */

let pendingActivationFragmentToken: string | null = null;

function isActivateRoutePathname(pathname: string): boolean {
  // Codex P1 (round 3): normalize a trailing slash — /patient/activate/ is
  // served by the catch-all rewrite and accepted by React Router, and the
  // credential must be stripped BEFORE initSentry() for that form too.
  const normalized =
    pathname.length > 1 && pathname.endsWith('/') ? pathname.slice(0, -1) : pathname;
  // Tolerate an optional deployment base prefix; the route itself is flat.
  return normalized === '/patient/activate' || normalized.endsWith('/patient/activate');
}

/**
 * Pull the activation credential out of the URL fragment (if present) and
 * strip the fragment from the address bar/history. Safe to run on every
 * route: it is a no-op unless the current path is the activation route and
 * the fragment parses to a `token=` value.
 */
export function extractPatientActivationFragment(): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    const { pathname, search, hash } = window.location;
    if (!hash || !isActivateRoutePathname(pathname)) {
      return;
    }
    const params = new URLSearchParams(hash.replace(/^#/, ''));
    const token = (params.get('token') || '').trim();
    if (!token) {
      return;
    }
    pendingActivationFragmentToken = token;
    // The fragment carried the credential — drop it wholesale (replace:
    // the history entry must not keep the secret either).
    window.history.replaceState(window.history.state, '', pathname + search);
  } catch (e) {
    // Never break bootstrap over deep-link hygiene.
    if (import.meta.env.MODE === 'development') {
      // eslint-disable-next-line no-console
      console.warn('[patientActivateDeepLink] extraction failed:', e);
    }
  }
}

/**
 * One-shot consume of the stashed activation token (null when absent).
 * One-shot by design: the credential must not sit in a readable slot
 * longer than the prefill needs.
 */
export function takePatientActivationFragmentToken(): string | null {
  const token = pendingActivationFragmentToken;
  pendingActivationFragmentToken = null;
  return token;
}
