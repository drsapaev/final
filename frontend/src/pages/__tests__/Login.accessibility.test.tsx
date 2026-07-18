import React from 'react';
import { fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Login from '../Login';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { MacOSThemeProvider } from '../../theme/macosTheme';

vi.mock('../../api/client', () => ({
  api: {
    get: vi.fn(),
  },
  buildApiUrl: vi.fn((path) => path),
  setToken: vi.fn(),
}));

vi.mock('../../hooks/useSetupStatus.ts', () => ({
  useSetupStatus: () => ({
    initialized: true,
    isLoading: false,
    error: null,
  }),
}));

// UX Audit Stage 2: mock useTranslation чтобы не требовать TranslationProvider
vi.mock('../../hooks/useTranslation', () => ({
  useTranslation: () => ({
    language: 'ru',
    setLanguage: vi.fn(),
    availableLanguages: [{ code: 'ru', name: 'Русский', flag: '🇷🇺' }],
    t: (key) => key,
  }),
}));

function renderLogin() {
  return render(
    <MemoryRouter>
      <MacOSThemeProvider>
        <ThemeProvider>
          <Login />
        </ThemeProvider>
      </MacOSThemeProvider>
    </MemoryRouter>
  );
}

describe('Login canonical surface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  it('renders canonical login fields without legacy role defaults', () => {
    const { container } = renderLogin();

    const usernameField = container.querySelector('input[name="username"]');
    const passwordField = container.querySelector('input[name="password"]');
    const legacyRoleSelect = container.querySelector('select[name="role"]');

    expect(usernameField).toBeInTheDocument();
    expect(usernameField).toHaveValue('');
    expect(passwordField).toBeInTheDocument();
    expect(legacyRoleSelect).not.toBeInTheDocument();
    expect(container).not.toHaveTextContent('admin@example.com');
    expect(container).not.toHaveTextContent('registrar@example.com');
  });

  it('does not call backend auth when canonical fields are empty', () => {
    const { container } = renderLogin();
    const form = container.querySelector('form');

    fireEvent.submit(form);

    expect(global.fetch).not.toHaveBeenCalled();
  });
});
