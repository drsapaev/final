import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, useTheme } from '../ThemeContext';
import { getColorSchemeDefinition } from '../../theme/colorScheme';

const { apiMock } = vi.hoisted(() => {
  const apiMock = {
    get: vi.fn(),
    put: vi.fn(),
  };

  return {
    apiMock,
  };
});

vi.mock('../../api/client', () => ({
  default: apiMock,
  api: apiMock,
  apiClient: apiMock,
}));

// Cast apiMock through unknown to expose vitest mock methods cleanly.
const apiMockTyped = apiMock as unknown as {
  get: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
};

function ThemeHarness() {
  const { theme, colorScheme, setColorScheme } = useTheme();

  return (
    <div>
      <div data-testid="theme">{theme}</div>
      <div data-testid="color-scheme">{colorScheme}</div>
      <button type="button" onClick={() => setColorScheme('dark')}>dark</button>
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
    apiMockTyped.get.mockReset();
    apiMockTyped.put.mockReset();

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

  it('applies standard color schemes through a single context state', async () => {
    // PR-UI-02: custom schemes (vibrant/glass/gradient) deleted.
    // Test now verifies standard schemes (light/dark/auto) work via context.
    renderWithProvider();

    fireEvent.click(screen.getByRole('button', { name: 'dark' }));

    await waitFor(() => {
      expect(screen.getByTestId('color-scheme')).toHaveTextContent('dark');
      expect(screen.getByTestId('theme')).toHaveTextContent('dark');
    });
  });

  it('loads and saves theme preferences for authenticated users', async () => {
    apiMockTyped.get.mockResolvedValue({ data: { theme: 'auto' } });
    apiMockTyped.put.mockResolvedValue({ data: { success: true } });

    renderWithProvider();
    await act(async () => {
      localStorage.setItem('auth_token', 'jwt-token');
      window.dispatchEvent(new CustomEvent('authStateChanged', {
        detail: { token: 'jwt-token' },
      }));
    });

    await waitFor(() => {
      expect(apiMockTyped.get).toHaveBeenCalledWith('/users/me/preferences');
      expect(screen.getByTestId('color-scheme')).toHaveTextContent('auto');
    });
    expect(apiMockTyped.put).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'light' }));

    await waitFor(() => {
      expect(apiMockTyped.put).toHaveBeenCalledWith('/users/me/preferences', { theme: 'light' });
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

    expect(apiMockTyped.get).not.toHaveBeenCalledWith('/users/me/preferences');
    expect(apiMockTyped.put).not.toHaveBeenCalled();
  });
  // PR-UI-02: 'keeps vibrant and gradient as visually distinct custom schemes' test removed
  // because vibrant/glass/gradient custom schemes were deleted.
});
