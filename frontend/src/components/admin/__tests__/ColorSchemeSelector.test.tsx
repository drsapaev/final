import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ColorSchemeSelector from '../ColorSchemeSelector';
import { ThemeProvider } from '@/contexts/ThemeContext';

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock('../../../api/client.ts', () => ({
  api: apiMock,
}));

function renderSelector() {
  return render(
          <ThemeProvider>
        <ColorSchemeSelector />
      </ThemeProvider>
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
    // PR-UI-01: accent picker removed (multi-accent system deleted).
    // Test no longer asserts on the obsolete 'Accent сейчас:' status block.

    fireEvent.click(screen.getByRole('button', { name: /Полупрозрачная стеклянная/i }));

    await waitFor(() => {
      expect(document.documentElement.getAttribute('data-color-scheme')).toBe('glass');
      expect(screen.getByText('Премиальная')).toBeInTheDocument();
      expect(screen.getAllByText('Стекло').length).toBeGreaterThan(0);
    });
  });
});
