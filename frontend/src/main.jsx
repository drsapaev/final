import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
// Unified i18n: initializes react-i18next with ru/uz-Latn/uz-Cyrl/en/kk locales.
// See frontend/src/i18n/index.js for supported languages and configuration.
import './i18n';
import App from './App.jsx';
import './styles/theme.css';
import './styles/dark-theme-visibility-fix.css';
import './styles/global-fixes.css';
import './theme/macos-tokens.css';
import './styles/macos.css';
import './components/admin/admin.css';
import { bootstrapStoredColorScheme } from './theme/colorScheme.js';

// Инициализация API interceptors
import { setupInterceptors, initializeAuth } from './api/interceptors';

// Sentry — no-op if VITE_SENTRY_DSN is unset
import { initSentry } from './services/sentry';

initSentry();
bootstrapStoredColorScheme();

// Настраиваем interceptors
setupInterceptors();
initializeAuth();

const rootEl = document.getElementById('root');
if (!rootEl) {
  const el = document.createElement('div');
  el.id = 'root';
  document.body.appendChild(el);
  createRoot(el).render(
    <React.StrictMode>
      <BrowserRouter
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true
        }}
      >
        <App />
      </BrowserRouter>
    </React.StrictMode>
  );
} else {
  createRoot(rootEl).render(
    <React.StrictMode>
      <BrowserRouter
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true
        }}
      >
        <App />
      </BrowserRouter>
    </React.StrictMode>
  );
}

