import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import ServiceCatalog from '../ServiceCatalog';
import { api } from '@/api/client';

const websiteService = vi.hoisted(() => ({
  id: 41,
  active: true,
  name_ru: 'SYNTHETIC консультация',
  name_uz: null,
  description_ru: null,
  description_uz: null,
  slug: null,
  show_on_website: false,
  website_first_published_at: null,
  slug_locked: false,
  missing_fields: ['name_uz', 'description_ru', 'description_uz', 'slug'],
}));

vi.mock('../../../api/client', () => {
  const initialContent = { ...websiteService };
  const apiMock = {
    get: vi.fn((url: string) => {
      if (url === '/services/admin/website-content') {
        return Promise.resolve({ data: [initialContent] });
      }
      if (url === '/services' || url === '/services/categories' || url === '/services/admin/doctors') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/admin/departments') return Promise.resolve({ data: { data: [] } });
      if (url.startsWith('/queues/profiles')) return Promise.resolve({ data: { profiles: [] } });
      return Promise.resolve({ data: [] });
    }),
    post: vi.fn(),
    put: vi.fn((url: string, payload: Record<string, unknown>) => {
      const operation = payload.operation;
      const visible = operation === 'publish' || operation === 'republish' || operation === 'save_published';
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
    delete: vi.fn(),
  };

  return { default: apiMock, api: apiMock, apiClient: apiMock };
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('ServiceCatalog website publication editor', () => {
  it('loads content only when opened and sends explicit draft and publication operations', async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ServiceCatalog />
      </ThemeProvider>,
    );

    await screen.findByRole('heading', { name: 'Контент и публикация на сайте' });
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(5));
    expect(api.get).not.toHaveBeenCalledWith('/services/admin/website-content');

    await user.click(screen.getByRole('button', { name: 'Открыть редактор сайта' }));
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/services/admin/website-content'));
    await screen.findByRole('textbox', { name: /Название на узбекском/ });

    fireEvent.change(screen.getByRole('textbox', { name: /Название на узбекском/ }), {
      target: { value: 'SYNTHETIC maslahat' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: /Описание на русском/ }), {
      target: { value: 'SYNTHETIC описание услуги.' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: /Описание на узбекском/ }), {
      target: { value: 'SYNTHETIC xizmat tavsifi.' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: /Адрес страницы/ }), {
      target: { value: 'synthetic-consultation' },
    });

    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith(
      '/services/admin/website-content/41',
      expect.objectContaining({ operation: 'save_draft', slug: 'synthetic-consultation' }),
    ));

    await user.click(screen.getByRole('button', { name: 'Опубликовать' }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith(
      '/services/admin/website-content/41',
      expect.objectContaining({ operation: 'publish', slug: 'synthetic-consultation' }),
    ));
    expect(await screen.findByText('Опубликовано')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Снять с публикации' })).toBeInTheDocument();
  });
});
