import '@testing-library/jest-dom';
import { render, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { api } from '@/api/client';
import UserManagement from '../UserManagement';

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
  setSessionInvalidationListener: vi.fn(),
}));

const mockedGet = vi.mocked(api.get);

beforeEach(() => {
  mockedGet.mockReset();
  mockedGet.mockImplementation(async (url: string) => {
    if (url === '/users/users') {
      return {
        data: {
          users: [{ id: 7, username: 'SYNTHETIC-7', role: 'Admin', is_active: true }],
          total: 1,
          total_pages: 1,
        },
      } as never;
    }
    return { data: {} } as never;
  });
});

it('requests the first users page only once on initial render', async () => {
  render(
    <ThemeProvider>
      <UserManagement />
    </ThemeProvider>,
  );

  await waitFor(() => {
    const listRequests = mockedGet.mock.calls.filter(([url]) => url === '/users/users');
    expect(listRequests).toHaveLength(1);
  });
});
