/**
 * Regression: the user-row "⋯" actions menu positions itself through CSS
 * custom properties consumed directly as `top`/`left` (admin.css). React
 * renders custom properties verbatim — a bare number (e.g. `420`) is INVALID
 * for top/left, so the menu silently failed to appear next to the row
 * (the operator-reported 2026-09 defect). The binding must unitize the
 * coordinates explicitly.
 */
import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import UserManagement from '../UserManagement';
import { api } from '@/api/client';

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockedGet = vi.mocked(api.get);

const oneUserPage = {
  users: [
    {
      id: 7,
      username: 'doctor.new',
      full_name: 'Новый Врач',
      email: 'doctor.new@clinic.test',
      role: 'Doctor',
      is_active: true,
    },
  ],
  total: 1,
  total_pages: 1,
};

const renderPanel = () =>
  render(
    <ThemeProvider>
      <UserManagement />
    </ThemeProvider>,
  );

describe('UserManagement actions menu positioning', () => {
  beforeEach(() => {
    mockedGet.mockReset();
    // users list + any secondary loads (roles come from useRoles hook tests
    // mock the endpoint the hook calls; unknown GETs resolve to empty data)
    mockedGet.mockImplementation(async (url: string) => {
      if (String(url).startsWith('/users/users')) {
        return { data: oneUserPage } as never;
      }
      return { data: {} } as never;
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('unitizes the position CSS variables so the menu renders next to the row', async () => {
    const user = userEvent.setup();
    renderPanel();

    const opener = await screen.findByRole(
      'button',
      { name: /Новый Врач|doctor\.new/i },
      { timeout: 5000 },
    );
    await user.click(opener);

    const menu = await screen.findByRole('menu', {}, { timeout: 5000 });
    const style = menu.getAttribute('style') ?? '';
    const readVar = (name: string): string => {
      const m = style.match(new RegExp(`${name}:\s*([^;]+)`));
      return m ? m[1].trim() : '';
    };
    // The variables MUST be valid CSS lengths: a bare number is invalid for
    // top/left, so the unit is part of the contract being pinned here.
    for (const name of ['--admin-top0', '--admin-left1']) {
      const value = readVar(name);
      expect(value).not.toBe('');
      expect(value.endsWith('px')).toBe(true);
      expect(Number.parseFloat(value)).not.toBeNaN();
    }
    void waitFor;
  });
});
