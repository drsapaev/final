import { extractEmailVerificationCredential } from './emailVerificationDeepLink';

// Imported first by main.tsx: evaluation precedes the other app modules and
// Sentry initialization. A failed history rewrite stops startup safely.
extractEmailVerificationCredential();

// Hash-only navigations can occur while the confirmation page is mounted.
// This listener is registered before telemetry and removes the new fragment
// before notifying the UI; no credential is carried in the event.
if (typeof window !== 'undefined') {
  window.addEventListener('hashchange', () => {
    if (extractEmailVerificationCredential()) window.dispatchEvent(new Event('emailVerificationLinkChanged'));
  });
}
