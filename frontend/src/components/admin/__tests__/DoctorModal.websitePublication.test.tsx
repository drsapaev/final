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
      if (url === '/admin/doctors/55/website-content') {
        return Promise.resolve({
          data: {
            ...initialContent,
            id: 55,
            display_name: 'SYNTHETIC Other Website Doctor',
            bio_ru: 'SYNTHETIC biography B',
            bio_uz: 'SYNTHETIC biography B UZ',
            slug: 'synthetic-other-doctor',
            missing_fields: [],
          },
        });
      }
      return Promise.resolve({ data: [] });
    }),
    put: vi.fn((url: string, payload: Record<string, unknown>) => {
      const visible = payload.operation === 'publish' || payload.operation === 'republish' || payload.operation === 'save_published';
      const doctorId = Number(url.match(/\/admin\/doctors\/(\d+)\/website-content$/)?.[1] ?? initialContent.id);
      return Promise.resolve({
        data: {
          ...initialContent,
          id: doctorId,
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

  it('ignores a pending save after the modal switches to another doctor', async () => {
    const user = userEvent.setup();
    let resolveDoctorASave: ((response: Awaited<ReturnType<typeof api.put>>) => void) | undefined;
    vi.mocked(api.put).mockImplementationOnce(
      () => new Promise((resolve) => { resolveDoctorASave = resolve; }),
    );

    const renderDoctor = (id: number | string, name: string) => (
      <ThemeProvider>
        <DoctorModal
          isOpen
          onClose={vi.fn()}
          doctor={{
            id,
            user_id: 88,
            specialty: 'dentistry',
            active: true,
            user: {
              id: 88,
              full_name: name,
              role: 'Doctor',
              is_active: true,
            },
          }}
          onSave={vi.fn()}
          availableUsers={[]}
        />
      </ThemeProvider>
    );

    const { rerender } = render(renderDoctor(54, 'SYNTHETIC Website Doctor'));
    const bioRu = () => screen.getByRole('textbox', { name: /Биография на русском/ });
    const bioUz = () => screen.getByRole('textbox', { name: /Биография на узбекском/ });
    const slug = () => screen.getByRole('textbox', { name: /Адрес страницы/ });

    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/admin/doctors/54/website-content'));
    await waitFor(() => expect(bioRu()).toHaveValue(''));
    fireEvent.change(bioRu(), { target: { value: 'SYNTHETIC doctor A biography' } });
    fireEvent.change(bioUz(), { target: { value: 'SYNTHETIC doctor A biography UZ' } });
    fireEvent.change(slug(), { target: { value: 'synthetic-doctor-a' } });
    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));

    await waitFor(() => expect(api.put).toHaveBeenCalledWith(
      '/admin/doctors/54/website-content',
      expect.objectContaining({
        operation: 'save_draft',
        bio_ru: 'SYNTHETIC doctor A biography',
      }),
    ));

    rerender(renderDoctor('55', 'SYNTHETIC Other Website Doctor'));
    await waitFor(() => expect(bioRu()).toHaveValue('SYNTHETIC biography B'));
    expect(screen.getByRole('button', { name: 'Сохранить черновик' })).toBeEnabled();

    fireEvent.change(bioRu(), { target: { value: 'SYNTHETIC doctor B updated biography' } });
    fireEvent.change(bioUz(), { target: { value: 'SYNTHETIC doctor B updated biography UZ' } });
    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith(
      '/admin/doctors/55/website-content',
      expect.objectContaining({
        operation: 'save_draft',
        bio_ru: 'SYNTHETIC doctor B updated biography',
      }),
    ));
    expect(await screen.findByText('Профиль сайта сохранён.')).toBeInTheDocument();

    resolveDoctorASave?.({
      data: {
        ...doctorWebsiteContent,
        bio_ru: 'SYNTHETIC doctor A biography',
        bio_uz: 'SYNTHETIC doctor A biography UZ',
        slug: 'synthetic-doctor-a',
        operation: 'save_draft',
      },
    } as Awaited<ReturnType<typeof api.put>>);

    await waitFor(() => expect(bioRu()).toHaveValue('SYNTHETIC doctor B updated biography'));
    expect(bioUz()).toHaveValue('SYNTHETIC doctor B updated biography UZ');
    expect(api.put).toHaveBeenCalledTimes(2);
  });
});
