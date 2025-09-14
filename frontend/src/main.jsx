import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.jsx';

// Инициализация API interceptors
import { setupInterceptors, initializeAuth } from './api/interceptors';

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
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.StrictMode>
  );
} else {
  createRoot(rootEl).render(
    <React.StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.StrictMode>
  );
}

