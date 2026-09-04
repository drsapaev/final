import React from 'react';
import { fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LoginFormStyled from '../../components/auth/LoginFormStyled';
import { ThemeProvider } from '../../contexts/ThemeContext';

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
    t: (key: string) => key,
  }),
}));

function renderLogin() {
  return render(
    <MemoryRouter>
              <ThemeProvider>
          <LoginFormStyled />
        </ThemeProvider>
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

    // Non-null assertion: Login always renders a <form>; preserves runtime
    // behavior (would still throw if form were unexpectedly absent).
    fireEvent.submit(form!);

    expect(global.fetch).not.toHaveBeenCalled();
  });
});
