/**
 * Activation deep-link credential handling (Phase 0 follow-up, Codex P1 +
 * owner review round 12).
 *
 * The canonical handout link carries the 72h activation credential in the
 * URL fragment (/patient/activate#token=...) so it is never transmitted to
 * the server. Legacy links already handed out within the TTL still use the
 * query form (/patient/activate?token=...) — the query component reaches
 * the server on the first HTTP navigation and stays in window.location
 * until the PatientActivatePage effect strips it. Telemetry (Sentry)
 * initializes in main.tsx BEFORE React mounts, and the Sentry scrubber
 * redacts object keys containing "token"; URL-valued telemetry fields
 * (request.url, breadcrumb from/to, pageload transaction URLs) carry the
 * credential as a plain string, so a pageload trace or a startup error
 * could otherwise leak EITHER handout form to Sentry.
 *
 * extractPatientActivationCredential() must therefore run BEFORE
 * initSentry(): it copies the token into an in-memory one-shot slot (never
 * storage) and rewrites the address bar without the credential — for BOTH
 * forms (the canonical fragment wins when a URL carries both). The query
 * strip preserves unrelated query params. PatientActivatePage consumes the
 * slot on mount and falls back to the router location (fragment/query) for
 * environments where the bootstrap extraction did not run (tests,
 * MemoryRouter). Defense-in-depth: services/sentry.ts additionally redacts
 * credential query params inside URL-valued telemetry strings.
 */

let pendingActivationFragmentToken: string | null = null;

function isActivateRoutePathname(pathname: string): boolean {
  // Codex P1 (rounds 3+6+11): mirror React Router's matching semantics —
  // RR DECODES the pathname before matching, matches case-insensitively
  // (no caseSensitive flag in App.tsx) and accepts trailing slashes, so
  // /patient/%61ctivate#token=..., /Patient/Activate/ and friends all
  // reach the activation page. The credential must be stripped BEFORE
  // initSentry() for every one of those forms.
  let normalized: string;
  try {
    normalized = decodeURIComponent(pathname);
  } catch {
    // Malformed percent-encoding cannot match the activation route in the
    // router either — treat as a foreign path (no extraction, no strip).
    return false;
  }
  normalized = normalized.toLowerCase().replace(/\/+$/, '');
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
      console.warn('[patientActivateDeepLink] fragment extraction failed:', e);
    }
  }
}

/**
 * Legacy backward-compatibility path (owner round-12 P1): links already
 * handed out within the 72h TTL use /patient/activate?token=... The query
 * component is present in window.location from the very first HTTP request
 * and survives until the PatientActivatePage effect — i.e. past Sentry
 * init. Strip it BEFORE initSentry(): stash the token (the canonical
 * fragment form wins when both are present) and rewrite the address bar
 * with unrelated query params preserved (a legacy URL may carry lang/utm
 * companions that are not credentials).
 */
function extractPatientActivationQueryToken(): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    const { pathname, search, hash } = window.location;
    if (!search || !isActivateRoutePathname(pathname)) {
      return;
    }
    const params = new URLSearchParams(search);
    // URLSearchParams percent-decodes names, so this also catches a
    // hand-obfuscated %74oken= key that the page fallback would still
    // resolve to the credential.
    const token = (params.get('token') || '').trim();
    if (!token) {
      return;
    }
    if (pendingActivationFragmentToken === null) {
      pendingActivationFragmentToken = token;
    }
    // Drop every token param (all occurrences), keep the rest verbatim,
    // preserve an unrelated hash. replace: the history entry must not keep
    // the secret either.
    params.delete('token');
    const nextSearch = params.toString();
    window.history.replaceState(
      window.history.state,
      '',
      pathname + (nextSearch ? `?${nextSearch}` : '') + hash
    );
  } catch (e) {
    // Never break bootstrap over deep-link hygiene.
    if (import.meta.env.MODE === 'development') {
      // eslint-disable-next-line no-console
      console.warn('[patientActivateDeepLink] legacy query extraction failed:', e);
    }
  }
}

/**
 * Bootstrap entry point (main.tsx, BEFORE initSentry()): extract the
 * activation credential from BOTH handout forms — the canonical #token=
 * fragment and the legacy ?token= query — and strip both from the address
 * bar/history. See the module docs for the telemetry rationale.
 */
export function extractPatientActivationCredential(): void {
  extractPatientActivationFragment();
  extractPatientActivationQueryToken();
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
