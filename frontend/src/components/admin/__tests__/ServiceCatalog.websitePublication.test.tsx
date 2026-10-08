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
  name_uz: null as string | null,
  description_ru: null as string | null,
  description_uz: null as string | null,
  slug: null as string | null,
  show_on_website: false,
  website_first_published_at: null as string | null,
  slug_locked: false,
  missing_fields: ['name_uz', 'description_ru', 'description_uz', 'slug'],
}));

const catalogService = vi.hoisted(() => ({
  id: 41,
  name: 'SYNTHETIC консультация',
  active: true,
  price: 15000,
  duration_minutes: 30,
}));

vi.mock('../../../api/client', () => {
  const apiMock = {
    get: vi.fn((url: string) => {
      if (url === '/services/admin/website-content') {
        return Promise.resolve({ data: [{ ...websiteService }] });
      }
      if (url === '/services') return Promise.resolve({ data: [{ ...catalogService }] });
      if (url === '/services/categories' || url === '/services/admin/doctors') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/admin/departments') return Promise.resolve({ data: { data: [] } });
      if (url.startsWith('/queues/profiles')) return Promise.resolve({ data: { profiles: [] } });
      return Promise.resolve({ data: [] });
    }),
    post: vi.fn(),
    put: vi.fn((url: string, payload: Record<string, unknown>) => {
      if (url.startsWith('/services/admin/website-content/')) {
        const operation = payload.operation;
        const visible = operation === 'publish' || operation === 'republish' || operation === 'save_published';
        const firstPublishedAt = websiteService.website_first_published_at
          ?? (visible ? '2026-10-08T10:00:00Z' : null);
        Object.assign(websiteService, payload, {
          show_on_website: visible,
          website_first_published_at: firstPublishedAt,
          slug_locked: Boolean(firstPublishedAt),
          missing_fields: [],
        });
        return Promise.resolve({ data: { ...websiteService } });
      }
      return Promise.resolve({ data: { ...catalogService, ...payload } });
    }),
    delete: vi.fn(() => {
      Object.assign(websiteService, {
        active: false,
        show_on_website: false,
        missing_fields: ['active'],
      });
      return Promise.resolve({ data: { active: false, message: 'Service deactivated' } });
    }),
  };

  return { default: apiMock, api: apiMock, apiClient: apiMock };
});
afterEach(() => {
  vi.clearAllMocks();
  Object.assign(websiteService, {
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
  });
  Object.assign(catalogService, {
    id: 41,
    name: 'SYNTHETIC консультация',
    active: true,
    price: 15000,
    duration_minutes: 30,
  });
});

describe('ServiceCatalog website publication editor', () => {
  it('syncs the main service catalog after editing website content', async () => {
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
    await screen.findByRole('textbox', { name: /Название на узбекском/ });
    fireEvent.change(screen.getByRole('textbox', { name: /Название на русском/ }), {
      target: { value: 'SYNTHETIC новое название' },
    });
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
      expect.objectContaining({
        operation: 'save_draft',
        name_ru: 'SYNTHETIC новое название',
        slug: 'synthetic-consultation',
      }),
    ));
    expect(await screen.findByRole('cell', { name: 'SYNTHETIC новое название' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Опубликовать' }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith(
      '/services/admin/website-content/41',
      expect.objectContaining({ operation: 'publish', slug: 'synthetic-consultation' }),
    ));
    expect(await screen.findByText('Опубликовано')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Снять с публикации' })).toBeInTheDocument();
  });

  it('reloads website publication state after a service is deactivated', async () => {
    Object.assign(websiteService, {
      name_uz: 'SYNTHETIC maslahat',
      description_ru: 'SYNTHETIC описание.',
      description_uz: 'SYNTHETIC tavsif.',
      slug: 'synthetic-consultation',
      show_on_website: true,
      website_first_published_at: '2026-10-08T10:00:00Z',
      slug_locked: true,
      missing_fields: [],
    });
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ServiceCatalog />
      </ThemeProvider>,
    );

    await screen.findByRole('heading', { name: 'Контент и публикация на сайте' });
    await user.click(screen.getByRole('button', { name: 'Открыть редактор сайта' }));
    await screen.findByRole('button', { name: 'Снять с публикации' });

    await user.click(screen.getByRole('button', { name: 'Delete service SYNTHETIC консультация' }));
    await user.click(await screen.findByRole('button', { name: 'Удалить' }));
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/services/41'));

    await waitFor(() => {
      const websiteLoads = vi.mocked(api.get).mock.calls.filter(
        ([url]) => url === '/services/admin/website-content',
      );
      expect(websiteLoads).toHaveLength(2);
    });
    expect(await screen.findByText('Перед публикацией активируйте услугу.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Опубликовать повторно' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Снять с публикации' })).not.toBeInTheDocument();
  });
});
