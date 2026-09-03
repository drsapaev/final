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

  it('renders the shared theme catalog copy with 3 standard schemes', async () => {
    renderSelector();

    expect(screen.getByText('Что именно меняет настройка')).toBeInTheDocument();
    // PR-UI-02: custom schemes (vibrant/glass/gradient) deleted.
    // Only 3 standard schemes remain: light, dark, auto.
    expect(screen.getAllByText('Светлая').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Темная').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Авто').length).toBeGreaterThan(0);
  });
});
