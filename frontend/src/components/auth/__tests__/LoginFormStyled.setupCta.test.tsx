import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LoginFormStyled from '../LoginFormStyled';

const { useSetupStatusMock } = vi.hoisted(() => ({
  useSetupStatusMock: vi.fn(),
}));

vi.mock('../../../hooks/useSetupStatus.ts', () => ({
  useSetupStatus: useSetupStatusMock,
}));

vi.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({}),
}));

// UX Audit Stage 2: mock useTranslation чтобы не требовать TranslationProvider
vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({ language: 'ru', setLanguage: vi.fn(), availableLanguages: [], t: (k) => k }),
  TranslationProvider: ({ children }) => children,
}));

const setupCtaName = /\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u043a\u043b\u0438\u043d\u0438\u043a\u0443/i;
const registrationName = /\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u044f/i;

const renderLoginForm = () => {
  render(
    <MemoryRouter>
      <LoginFormStyled />
    </MemoryRouter>
  );
};

describe('LoginFormStyled setup CTA', () => {
  beforeEach(() => {
    useSetupStatusMock.mockReset();
  });

  it('shows primary setup CTA when the system is not initialized', () => {
    useSetupStatusMock.mockReturnValue({
      initialized: false,
      isLoading: false,
      error: null,
    });

    renderLoginForm();

    expect(screen.getByRole('button', { name: setupCtaName })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: registrationName })).not.toBeInTheDocument();
  });

  it('hides primary setup CTA after initialization', () => {
    useSetupStatusMock.mockReturnValue({
      initialized: true,
      isLoading: false,
      error: null,
    });

    renderLoginForm();

    expect(screen.queryByRole('button', { name: setupCtaName })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: registrationName })).not.toBeInTheDocument();
  });
});
