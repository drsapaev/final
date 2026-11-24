import { extractPasswordResetCredential } from './passwordResetDeepLink';

// Evaluated before app imports and telemetry; a failed rewrite aborts startup.
extractPasswordResetCredential();

if (typeof window !== 'undefined') {
  const onNavigation = () => {
    try {
      if (extractPasswordResetCredential()) window.dispatchEvent(new Event('passwordResetLinkChanged'));
    } catch (error) {
      // A mounted page must discard any previous capability on rewrite failure.
      window.dispatchEvent(new Event('passwordResetLinkChanged'));
      throw error;
    }
  };
  window.addEventListener('hashchange', onNavigation);
  window.addEventListener('popstate', onNavigation);
}
