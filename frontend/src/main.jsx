import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import PublicApp from './PublicApp.jsx';
import './styles/theme.css';
import './styles/dark-theme-visibility-fix.css';
import './styles/global-fixes.css';
import './theme/macos-tokens.css';
import './styles/macos.css';
import { bootstrapStoredColorScheme } from './theme/colorScheme.js';

// Инициализация API interceptors
import { setupInterceptors, initializeAuth } from './api/interceptors';

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
        <PublicApp />
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
        <PublicApp />
      </BrowserRouter>
    </React.StrictMode>
  );
}

