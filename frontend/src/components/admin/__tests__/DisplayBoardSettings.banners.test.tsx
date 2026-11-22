import '@testing-library/jest-dom';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMock = vi.hoisted(() => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('@/api/client', () => apiMock);
vi.mock('../../utils/logger', () => ({
  default: { log: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

import DisplayBoardSettings from '@/components/admin/DisplayBoardSettings';

// DISPLAYBANNER-FE-001 (audit PR #3961): the admin banner panel must load
// REAL banner rows from the #4016 backend CRUD, the Add button must open a
// working form whose Save POSTs a real banner, and the inert Edit/Delete
// buttons (no handlers, no backend routes) must not exist.
describe('DisplayBoardSettings banner panel (DISPLAYBANNER-FE-001)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.api.get.mockImplementation((url: string) => {
      if (url === '/admin/display/boards') {
        return Promise.resolve({
          status: 200,
          data: [
            { id: 7, display_name: 'Главное табло', theme: 'light' },
          ],
        });
      }
      if (url === '/admin/display/themes') {
        return Promise.resolve({ status: 200, data: [] });
      }
      if (url === '/admin/display/stats') {
        return Promise.resolve({ status: 200, data: {} });
      }
      if (url === '/admin/display/boards/7/banners') {
        return Promise.resolve({
          status: 200,
          data: {
            banners: [
              { id: 1, title: 'Синтетический баннер', description: 'Плановое сообщение' },
            ],
            total: 1,
          },
        });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
  });

  it('renders a real seeded banner from the backend CRUD', async () => {
    render(
      <ThemeProvider>
        <DisplayBoardSettings />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Синтетический баннер')).toBeInTheDocument();
    });
    expect(screen.getByText(/Плановое сообщение/)).toBeInTheDocument();
  });

  it('Add opens a form and Save POSTs a real banner', async () => {
    apiMock.api.post.mockResolvedValueOnce({
      status: 201,
      data: { success: true, banner_id: 42, banner: { id: 42, title: 'Новый баннер' } },
    });

    render(
      <ThemeProvider>
        <DisplayBoardSettings />
      </ThemeProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('Синтетический баннер')).toBeInTheDocument();
    });

    // No form until Add is clicked.
    expect(screen.queryByTestId('banner-form')).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: /добавить|add/i })[0]);
    expect(screen.getByTestId('banner-form')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Banner title'), {
      target: { value: 'Новый баннер' },
    });
    fireEvent.click(screen.getByTestId('banner-save'));

    await waitFor(() => {
      expect(apiMock.api.post).toHaveBeenCalledWith(
        '/admin/display/boards/7/banners',
        expect.objectContaining({ title: 'Новый баннер' })
      );
    });
    // The new banner appears in the list from the real POST result.
    await waitFor(() => {
      expect(screen.getByText('Новый баннер')).toBeInTheDocument();
    });
  });

  it('does not render inert Edit/Delete banner buttons', async () => {
    render(
      <ThemeProvider>
        <DisplayBoardSettings />
      </ThemeProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('Синтетический баннер')).toBeInTheDocument();
    });
    // Honest UI: no dead buttons without handlers/backend routes.
    expect(screen.queryByRole('button', { name: /edit banner/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /delete banner/i })).not.toBeInTheDocument();
  });
});
