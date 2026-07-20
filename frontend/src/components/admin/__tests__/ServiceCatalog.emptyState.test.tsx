import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '../../../contexts/ThemeContext';
import ServiceCatalog from '../ServiceCatalog';
import { api } from '../../../api/client';

vi.mock('../../../api/client', () => {
  const apiMock = {
    get: vi.fn((url) => {
      if (url === '/departments') {
        return Promise.resolve({ data: { data: [] } });
      }

      if (url.startsWith('/queues/profiles')) {
        return Promise.resolve({ data: { profiles: [] } });
      }

      return Promise.resolve({ data: [] });
    }),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  };

  return {
    default: apiMock,
    api: apiMock,
    apiClient: apiMock
  };
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('ServiceCatalog empty state', () => {
  it('does not emit nested table row warnings when no services are returned', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ThemeProvider>
        <ServiceCatalog />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledTimes(5);
    });

    await waitFor(() => {
      expect(screen.getAllByRole('status').length).toBeGreaterThan(0);
    });

    const nestingWarnings = consoleError.mock.calls.filter((call) =>
      call.join(' ').includes('validateDOMNesting')
    );
    expect(nestingWarnings).toEqual([]);

    consoleError.mockRestore();
  });
});
