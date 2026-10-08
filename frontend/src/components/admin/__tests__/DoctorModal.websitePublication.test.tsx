import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import DoctorModal from '../DoctorModal';
import { api } from '@/api/client';

const doctorWebsiteContent = vi.hoisted(() => ({
  id: 54,
  active: true,
  owner_active: true,
  display_name: 'SYNTHETIC Website Doctor',
  bio_ru: null,
  bio_uz: null,
  slug: null,
  show_on_website: false,
  website_first_published_at: null,
  slug_locked: false,
  missing_fields: ['bio_ru', 'bio_uz', 'slug'],
}));

vi.mock('../../../api/client', () => {
  const initialContent = { ...doctorWebsiteContent };
  const apiMock = {
    get: vi.fn((url: string) => {
      if (url === '/admin/doctors/specialty-vocabulary') return Promise.resolve({ data: [] });
      if (url === '/admin/doctors/54/website-content') return Promise.resolve({ data: initialContent });
      return Promise.resolve({ data: [] });
    }),
    put: vi.fn((url: string, payload: Record<string, unknown>) => {
      const visible = payload.operation === 'publish' || payload.operation === 'republish' || payload.operation === 'save_published';
      return Promise.resolve({
        data: {
          ...initialContent,
          ...payload,
          show_on_website: visible,
          website_first_published_at: visible ? '2026-10-08T10:00:00Z' : null,
          slug_locked: visible,
          missing_fields: [],
        },
      });
    }),
    post: vi.fn(),
    delete: vi.fn(),
  };

  return { default: apiMock, api: apiMock, apiClient: apiMock };
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('DoctorModal website publication editor', () => {
  it('keeps website publication actions separate and locks the slug after first publish', async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <DoctorModal
          isOpen
          onClose={vi.fn()}
          doctor={{
            id: 54,
            user_id: 88,
            specialty: 'dentistry',
            active: true,
            user: {
              id: 88,
              full_name: 'SYNTHETIC Website Doctor',
              role: 'Doctor',
              is_active: true,
            },
          }}
          onSave={vi.fn()}
          availableUsers={[]}
        />
      </ThemeProvider>,
    );

    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/admin/doctors/54/website-content'));
    await screen.findByRole('textbox', { name: /Биография на русском/ });

    fireEvent.change(screen.getByRole('textbox', { name: /Биография на русском/ }), {
      target: { value: 'SYNTHETIC описание врача.' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: /Биография на узбекском/ }), {
      target: { value: 'SYNTHETIC shifokor tarjimai holi.' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: /Адрес страницы/ }), {
      target: { value: 'synthetic-doctor' },
    });

    await user.click(screen.getByRole('button', { name: 'Опубликовать' }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith(
      '/admin/doctors/54/website-content',
      expect.objectContaining({ operation: 'publish', slug: 'synthetic-doctor' }),
    ));

    expect(await screen.findByText('Опубликовано')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /Адрес страницы/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Сохранить опубликованные изменения' })).toBeInTheDocument();
  });
});
