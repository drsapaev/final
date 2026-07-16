// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, useTheme } from '../ThemeContext';
import { getColorSchemeDefinition } from '../../theme/colorScheme.js';

const { apiMock } = vi.hoisted(() => {
  const apiMock = {
    get: vi.fn(),
    put: vi.fn(),
  };

  return {
    apiMock,
  };
});

vi.mock('../../api/client.js', () => ({
  default: apiMock,
  api: apiMock,
  apiClient: apiMock,
}));

function ThemeHarness() {
  const { theme, colorScheme, setColorScheme } = useTheme();

  return (
    <div>
      <div data-testid="theme">{theme}</div>
      <div data-testid="color-scheme">{colorScheme}</div>
      <button type="button" onClick={() => setColorScheme('glass')}>glass</button>
      <button type="button" onClick={() => setColorScheme('vibrant')}>vibrant</button>
      <button type="button" onClick={() => setColorScheme('light')}>light</button>
    </div>);

}

function renderWithProvider() {
  return render(
    <MemoryRouter initialEntries={['/admin']}>
      <ThemeProvider>
        <ThemeHarness />
      </ThemeProvider>
    </MemoryRouter>);

}

describe('ThemeContext', () => {
  beforeEach(() => {
    localStorage.clear();
    apiMock.get.mockReset();
    apiMock.put.mockReset();

    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
      })),
    });
  });

  it('applies custom color schemes through a single context state', async () => {
    renderWithProvider();

    fireEvent.click(screen.getByRole('button', { name: 'glass' }));

    await waitFor(() => {
      expect(screen.getByTestId('color-scheme')).toHaveTextContent('glass');
      expect(screen.getByTestId('theme')).toHaveTextContent('dark');
      expect(document.documentElement.getAttribute('data-color-scheme')).toBe('glass');
      expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
      expect(document.body.getAttribute('data-color-scheme')).toBe('glass');
      expect(document.body.classList.contains('dark-theme')).toBe(true);
      expect(document.body.classList.contains('scheme-glass')).toBe(true);
      expect(document.documentElement.classList.contains('scheme-glass')).toBe(true);
    });
  });

  it('loads and saves theme preferences for authenticated users', async () => {
    apiMock.get.mockResolvedValue({ data: { theme: 'gradient' } });
    apiMock.put.mockResolvedValue({ data: { success: true } });

    renderWithProvider();
    await act(async () => {
      localStorage.setItem('auth_token', 'jwt-token');
      window.dispatchEvent(new CustomEvent('authStateChanged', {
        detail: { token: 'jwt-token' },
      }));
    });

    await waitFor(() => {
      expect(apiMock.get).toHaveBeenCalledWith('/users/me/preferences');
      expect(screen.getByTestId('color-scheme')).toHaveTextContent('gradient');
    });
    expect(apiMock.put).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'vibrant' }));

    await waitFor(() => {
      expect(apiMock.put).toHaveBeenCalledWith('/users/me/preferences', { theme: 'vibrant' });
    }, { timeout: 2000 });
  });

  it('does not load remote preferences on public routes', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <ThemeHarness />
        </ThemeProvider>
      </MemoryRouter>);

    await waitFor(() => {
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
    });

    expect(apiMock.get).not.toHaveBeenCalledWith('/users/me/preferences');
    expect(apiMock.put).not.toHaveBeenCalled();
  });

  it('keeps vibrant and gradient as visually distinct custom schemes', () => {
    const vibrant = getColorSchemeDefinition('vibrant');
    const gradient = getColorSchemeDefinition('gradient');

    expect(vibrant.preview.background).not.toBe(gradient.preview.background);
    expect(vibrant.tokens['--mac-gradient-window']).not.toBe(gradient.tokens['--mac-gradient-window']);
    expect(vibrant.tokens['--mac-card-bg']).not.toBe(gradient.tokens['--mac-card-bg']);
    expect(vibrant.tokens['--mac-main-shell-bg']).not.toBe(gradient.tokens['--mac-main-shell-bg']);
    expect(vibrant.tokens['--mac-scheme-accent']).not.toBe(gradient.tokens['--mac-scheme-accent']);
  });
});
