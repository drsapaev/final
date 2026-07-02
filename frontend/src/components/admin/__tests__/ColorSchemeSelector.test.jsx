import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ColorSchemeSelector from '../ColorSchemeSelector.jsx';
import { ThemeProvider } from '../../../contexts/ThemeContext.jsx';
import { MacOSThemeProvider } from '../../../theme/macosTheme.jsx';

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock('../../../api/client.js', () => ({
  api: apiMock,
}));

function renderSelector() {
  return render(
    <MacOSThemeProvider>
      <ThemeProvider>
        <ColorSchemeSelector />
      </ThemeProvider>
    </MacOSThemeProvider>
  );
}

describe('ColorSchemeSelector', () => {
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

  it('renders the shared theme catalog copy and applies a selected custom scheme', async () => {
    renderSelector();

    expect(screen.getByText('Что именно меняет настройка')).toBeInTheDocument();
    expect(screen.getByText(/Accent сейчас:/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Полупрозрачная стеклянная/i }));

    await waitFor(() => {
      expect(document.documentElement.getAttribute('data-color-scheme')).toBe('glass');
      expect(screen.getByText('Премиальная')).toBeInTheDocument();
      expect(screen.getAllByText('Стекло').length).toBeGreaterThan(0);
    });
  });
});
