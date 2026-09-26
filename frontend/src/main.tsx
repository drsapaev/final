import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
// Russian initializes immediately; the saved locale loads after URL credential extraction.
import { loadPersistedLanguage } from './i18n';
import App from './App';
import './styles/theme.css';
import './styles/dark-theme-visibility-fix.css';
import './styles/global-fixes.css';
import './design-system/tokens.css';
import './styles/macos.css';
import './components/admin/admin.css';
import { bootstrapStoredColorScheme } from './theme/colorScheme';

// Инициализация API interceptors
import { setupInterceptors, initializeAuth } from './api/interceptors';

// Phase 0 follow-up (Codex P1 + owner round-12 P1): pull the activation
// credential out of the URL BEFORE telemetry initializes — for BOTH handout
// forms: the canonical #token= fragment and the legacy ?token= query kept
// for links handed out within the 72h TTL. The Sentry scrubber redacts
// token-keyed fields but not URL-valued telemetry fields (request.url,
// breadcrumb from/to, pageload transaction request.url), so a pageload
// trace or startup error would otherwise carry the credential to Sentry
// before React strips the URL. PatientActivatePage reads the stashed value
// (see utils/patientActivateDeepLink.ts).
import { extractPatientActivationCredential } from './utils/patientActivateDeepLink';

// Sentry — no-op if VITE_SENTRY_DSN is unset
import { initSentry } from './services/sentry';

extractPatientActivationCredential();
initSentry();
bootstrapStoredColorScheme();

// Настраиваем interceptors
setupInterceptors();
initializeAuth();

function mountApp() {
  const rootEl = document.getElementById('root') ?? document.createElement('div');
  if (!rootEl.isConnected) {
    rootEl.id = 'root';
    document.body.appendChild(rootEl);
  }
  createRoot(rootEl).render(
    <React.StrictMode>
      {/* react-router-dom v7: флаги v7_startTransition/v7_relativeSplatPath
          стали поведением по умолчанию, проп future удалён */}
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.StrictMode>
  );
}

// Wait for the selected catalog (or Russian fallback) before the first paint.
void loadPersistedLanguage().then(mountApp, mountApp);
