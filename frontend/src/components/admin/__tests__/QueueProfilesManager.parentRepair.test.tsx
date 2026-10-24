import '@testing-library/jest-dom';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import QueueProfilesManager from '../QueueProfilesManager';

const { apiMock, state } = vi.hoisted(() => {
  const profile = {
    key: 'synthetic-conflict',
    title: 'Synthetic conflicting direction',
    title_ru: 'Синтетическое направление с конфликтом',
    queue_tags: ['synthetic_conflict'],
    department_key: 'legacy-cardiology',
    is_active: true,
    show_on_qr_page: true,
    effective_availability: {
      state: 'conflict',
      is_available: false,
      reason_codes: ['parent_conflict'],
    },
    icon: 'Heart',
  };
  const preview = {
    success: true,
    profile_id: 42,
    profile_key: 'synthetic-conflict',
    current_department_key: 'legacy-cardiology',
    current_availability_state: 'conflict',
    current_reason_codes: ['parent_conflict'],
    parent_references: [
      {
        source: 'profile_key',
        department_key: 'synthetic-conflict',
        department_name_ru: 'Синтетическое целевое отделение',
        exists: true,
        active: true,
      },
      {
        source: 'department_key',
        department_key: 'legacy-cardiology',
        department_name_ru: 'Старое синтетическое отделение',
        exists: true,
        active: true,
      },
    ],
    target: {
      department_key: 'synthetic-conflict',
      department_name_ru: 'Синтетическое целевое отделение',
      active: true,
    },
    proposed_availability_state: 'available',
    proposed_reason_codes: [],
    links: {
      services: 2,
      department_services: 1,
      active_doctors: 1,
      active_queue_resources: 0,
      daily_queues: 1,
      entries_waiting: 1,
      entries_total: 3,
      active_public_addresses: 1,
    },
    services_removed_from_parent_scope: 1,
    services_added_to_parent_scope: 0,
    service_scope_confirmation_required: true,
    qr_catalog_would_be_bookable: true,
    permanent_address_would_be_bookable: true,
    public_access_confirmation_required: true,
    can_apply: true,
    blocker_code: null,
    preview_token: 'a'.repeat(64),
  };
  const state = { profile, preview, applyError: null as unknown };
  const apiMock = {
    get: vi.fn((url: string) => {
      if (url.includes('/parent-repair-preview')) {
        return Promise.resolve({ data: { ...state.preview } });
      }
      if (url.startsWith('/queues/profiles')) {
        return Promise.resolve({
          data: { success: true, profiles: [{ ...state.profile, queue_tags: [...state.profile.queue_tags] }] },
        });
      }
      if (url === '/admin/departments') return Promise.resolve({ data: { data: [] } });
      return Promise.resolve({ data: { data: [] } });
    }),
    post: vi.fn(async () => {
      if (state.applyError) throw state.applyError;
      return { data: { result: 'applied', department_key: null } };
    }),
    put: vi.fn(() => Promise.resolve({ data: { success: true } })),
    delete: vi.fn(() => Promise.resolve({ data: { success: true } })),
  };
  return { apiMock, state };
});

vi.mock('../../../api/client', () => ({
  default: apiMock,
  api: apiMock,
  apiClient: apiMock,
}));

const renderManager = async () => {
  render(
    <ThemeProvider>
      <QueueProfilesManager />
    </ThemeProvider>,
  );
  await waitFor(() => {
    expect(screen.getByText('Синтетическое направление с конфликтом')).toBeInTheDocument();
  });
};

const openRepairDialog = async (user: ReturnType<typeof userEvent.setup>) => {
  const row = screen.getByText('Синтетическое направление с конфликтом').closest('tr')!;
  await user.click(within(row).getByRole('button', { name: 'Исправить конфликт' }));
  return screen.findByRole('dialog', { name: 'Исправить привязку профиля' });
};

beforeEach(() => {
  state.profile.department_key = 'legacy-cardiology';
  state.preview.preview_token = 'a'.repeat(64);
  state.applyError = null;
  vi.clearAllMocks();
});

describe('QueueProfilesManager parent-conflict repair', () => {
  it('requires displayed impact confirmations and submits only the own-key target', async () => {
    const user = userEvent.setup();
    await renderManager();
    const dialog = await openRepairDialog(user);

    const targetSection = within(dialog).getByRole('region', {
      name: 'Отделение, которое будет использоваться',
    });
    expect(within(targetSection).getByText('Синтетическое целевое отделение')).toBeInTheDocument();
    expect(apiMock.get).toHaveBeenCalledWith(
      '/queues/profiles/synthetic-conflict/parent-repair-preview',
    );
    const apply = within(dialog).getByRole('button', { name: 'Исправить привязку' });
    expect(apply).toBeDisabled();

    for (const checkbox of within(dialog).getAllByRole('checkbox')) {
      await user.click(checkbox);
    }
    expect(apply).toBeEnabled();
    await user.click(apply);

    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledExactlyOnceWith(
        '/queues/profiles/synthetic-conflict/parent-repair',
        {
          target_department_key: 'synthetic-conflict',
          preview_token: 'a'.repeat(64),
          confirm_target: true,
          confirm_service_scope_change: true,
          confirm_public_access: true,
          reason_code: 'resolve_parent_conflict_to_own_key',
        },
      );
    });
    expect(await screen.findByText(
      'Привязка профиля исправлена; сведения перечитаны с сервера.',
    )).toBeInTheDocument();
  });

  it('keeps the stale-preview warning visible while refreshing the preview', async () => {
    const user = userEvent.setup();
    state.applyError = {
      response: {
        status: 409,
        data: { detail: { reason: 'parent_repair_stale', message: 'stale' } },
      },
    };
    await renderManager();
    const dialog = await openRepairDialog(user);

    for (const checkbox of within(dialog).getAllByRole('checkbox')) {
      await user.click(checkbox);
    }
    await user.click(within(dialog).getByRole('button', { name: 'Исправить привязку' }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'Состояние изменилось после предварительной проверки. Проверьте обновлённый результат и подтвердите заново.',
    );
    expect(apiMock.get).toHaveBeenCalledWith(
      '/queues/profiles/synthetic-conflict/parent-repair-preview',
    );
  });
});
