import '@testing-library/jest-dom';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import QueueProfilesManager from '../QueueProfilesManager';

const { apiMock } = vi.hoisted(() => {
  const syntheticProfiles = [
    {
      key: 'synthetic-active',
      title: 'Active Queue',
      title_ru: 'Синтетическая активная очередь',
      queue_tags: ['synthetic_active'],
      is_active: true,
      show_on_qr_page: true,
      effective_availability: { state: 'available', is_available: true, reason_codes: [] },
      icon: 'Heart',
      color: '#E53E3E',
    },
    {
      key: 'synthetic-hidden',
      title: 'Hidden Queue',
      title_ru: 'Синтетическая скрытая очередь',
      queue_tags: ['synthetic_hidden'],
      is_active: false,
      show_on_qr_page: false,
      icon: 'Package',
      color: '#718096',
    },
    {
      key: 'synthetic-archived-published',
      title: 'Archived QR-configured Queue',
      title_ru: 'Синтетическая архивная очередь с настройкой QR',
      queue_tags: ['synthetic_archived_published'],
      is_active: false,
      show_on_qr_page: true,
      effective_availability: {
        state: 'unavailable',
        is_available: false,
        reason_codes: ['manual_archived'],
        parent_department_key: null,
        parent_active: null,
      },
      icon: 'Package',
      color: '#718096',
    },
    {
      key: 'synthetic-unpublished',
      title: 'Unpublished Queue',
      title_ru: 'Синтетическое неопубликованное направление',
      queue_tags: ['synthetic_unpublished'],
      is_active: true,
      show_on_qr_page: false,
      icon: 'Package',
      color: '#718096',
    },
  ];

  const apiMock = {
    get: vi.fn((url: string) => {
      if (url.startsWith('/queues/profiles')) {
        return Promise.resolve({ data: { profiles: syntheticProfiles } });
      }
      if (url === '/admin/departments') {
        return Promise.resolve({ data: { data: [] } });
      }
      return Promise.resolve({ data: { data: [] } });
    }),
    post: vi.fn(() => Promise.resolve({ data: { success: true } })),
    put: vi.fn(() => Promise.resolve({ data: { success: true } })),
    delete: vi.fn(() => Promise.resolve({ data: { success: true } })),
  };

  return { apiMock };
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
    expect(screen.getByText('Синтетическая активная очередь')).toBeInTheDocument();
    expect(screen.getByText('Синтетическая скрытая очередь')).toBeInTheDocument();
  });
};

const openCreateDialog = async (user: ReturnType<typeof userEvent.setup>) => {
  const addButton = screen.getByRole('button', { name: 'Добавить' });
  await user.click(addButton);
  return addButton;
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('QueueProfilesManager interactions', () => {
  it('uses the selected status value instead of stringifying the Select event object', async () => {
    const user = userEvent.setup();
    await renderManager();

    await user.click(screen.getByRole('button', { name: 'Все' }));
    await user.click(screen.getByRole('option', { name: 'Профили в архиве' }));

    expect(screen.getByText('Синтетическая скрытая очередь')).toBeInTheDocument();
    expect(screen.queryByText('Синтетическая активная очередь')).not.toBeInTheDocument();
  });

  it('keeps the create form open while a title containing spaces is typed', async () => {
    const user = userEvent.setup();
    await renderManager();
    await openCreateDialog(user);

    const titleInput = screen.getByLabelText('Название вкладки очереди на русском');
    await user.type(titleInput, 'Новое направление');

    expect(titleInput).toHaveValue('Новое направление');
    expect(screen.getByRole('dialog', { name: 'Новая вкладка' })).toBeInTheDocument();
  });

  it('creates new profiles hidden and keeps QR publication for the edit action', async () => {
    const user = userEvent.setup();
    await renderManager();
    await openCreateDialog(user);

    const dialog = screen.getByRole('dialog', { name: 'Новая вкладка' });
    const qrCheckbox = screen.getByRole('checkbox', {
      name: 'Показывать профиль на QR-странице',
    });
    expect(qrCheckbox).not.toBeChecked();
    expect(qrCheckbox).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByText('Новые профили создаются без публикации на QR. После создания откройте «Редактировать», включите показ на QR и сохраните профиль.')).toBeInTheDocument();

    await user.type(screen.getByLabelText('Уникальный ключ вкладки очереди'), 'synthetic_new');
    await user.type(screen.getByLabelText('Название вкладки очереди на английском'), 'Synthetic new direction');
    await user.type(screen.getByLabelText('Название вкладки очереди на русском'), 'Синтетическое новое направление');
    await user.click(within(dialog).getByRole('button', { name: 'Создать вкладку очереди' }));

    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        '/queues/profiles',
        expect.objectContaining({
          key: 'synthetic_new',
          show_on_qr_page: false,
        }),
      );
    });
  });

  it('shows archive and QR publication as separate states and archives without changing QR publication', async () => {
    const user = userEvent.setup();
    await renderManager();

    const profileName = screen.getByText('Синтетическое неопубликованное направление');
    const row = profileName.closest('tr')!;

    expect(within(row).getByText('Активен в регистратуре')).toBeInTheDocument();
    expect(within(row).getByText('Не опубликован на QR')).toBeInTheDocument();

    await user.click(within(row).getByRole('button', {
      name: 'Архивировать профиль Синтетическое неопубликованное направление',
    }));

    expect(apiMock.put).toHaveBeenCalledExactlyOnceWith(
      '/queues/profiles/synthetic-unpublished',
      { is_active: false },
    );
  });

  it('shows the saved QR setting separately from effective availability for an archived profile', async () => {
    await renderManager();

    const row = screen
      .getByText('Синтетическая архивная очередь с настройкой QR')
      .closest('tr')!;

    expect(within(row).getByText('В архиве регистратуры')).toBeInTheDocument();
    expect(within(row).getByText('Настроен для QR')).toBeInTheDocument();
    expect(within(row).getByText('Доступность профиля: недоступна')).toBeInTheDocument();
    expect(within(row).queryByText('Опубликован на QR')).not.toBeInTheDocument();
  });

  it('opens edit from an unpublished profile and publishes only after the QR option is saved', async () => {
    const user = userEvent.setup();
    await renderManager();

    const row = screen.getByText('Синтетическое неопубликованное направление').closest('tr')!;
    const editButton = within(row).getByRole('button', {
      name: 'Редактировать профиль Синтетическое неопубликованное направление для настройки QR-публикации',
    });
    expect(editButton).toHaveAttribute('title', 'Редактировать для настройки QR');

    await user.click(editButton);
    const qrCheckbox = screen.getByRole('checkbox', {
      name: 'Показывать профиль на QR-странице',
    });
    expect(qrCheckbox).not.toBeChecked();
    expect(qrCheckbox).toBeEnabled();

    await user.click(qrCheckbox);
    await user.click(screen.getByRole('button', { name: 'Сохранить вкладку очереди' }));

    await waitFor(() => {
      expect(apiMock.put).toHaveBeenCalledWith(
        '/queues/profiles/synthetic-unpublished',
        expect.objectContaining({ show_on_qr_page: true }),
      );
    });
  });

  it('shows the typed binding conflict message and blocked fields', async () => {
    const user = userEvent.setup();
    apiMock.put.mockRejectedValueOnce({
      response: {
        data: {
          detail: {
            reason: 'profile_binding_change_blocked',
            message: 'Связи используемого профиля менять нельзя.',
            blocked_fields: ['queue_tags', 'department_key'],
          },
        },
      },
    });
    await renderManager();

    await user.click(screen.getAllByTitle('Редактировать')[0]);
    await user.click(screen.getByRole('button', { name: 'Сохранить вкладку очереди' }));

    expect(
      await screen.findByText(
        'Связи используемого профиля менять нельзя. Заблокированные поля: queue_tags, department_key',
      ),
    ).toBeInTheDocument();
  });

  it.each([
    {
      reason: 'profile_has_significant_links',
      message: 'Профиль используется: архивируйте его (is_active=false) вместо удаления.',
      links: { services: 1, daily_queues: 2 },
    },
    {
      reason: 'profile_binding_changed',
      message: 'Привязка направления изменилась во время удаления. Обновите страницу и повторите действие.',
      stale_fields: ['department_key'],
    },
  ])('shows the structured delete refusal $reason and preserves the profile', async (detail) => {
    const user = userEvent.setup();
    apiMock.get.mockResolvedValueOnce({
      data: {
        profiles: [{
          key: 'specialists',
          title: 'SYNTHETIC profile deletion',
          title_ru: 'Синтетический профиль для проверки удаления',
          queue_tags: ['synthetic_specialists'],
          is_active: true,
          show_on_qr_page: true,
          icon: 'Heart',
          color: '#E53E3E',
        }],
      },
    });
    apiMock.delete.mockRejectedValueOnce({
      response: { status: 409, data: { detail } },
    });
    render(<ThemeProvider><QueueProfilesManager /></ThemeProvider>);

    const profile = await screen.findByText('Синтетический профиль для проверки удаления');
    const row = profile.closest('tr')!;
    expect(apiMock.get).toHaveBeenCalledWith('/queues/profiles?active_only=false');
    expect(apiMock.delete).not.toHaveBeenCalled();
    await user.click(within(row).getByTitle('Удалить'));
    const confirmation = screen.getByRole('dialog', { name: 'Удаление вкладки очереди' });
    await user.click(within(confirmation).getByRole('button', { name: 'Удалить' }));

    expect(await screen.findByText(detail.message)).toBeInTheDocument();
    expect(screen.queryByText('[object Object]')).not.toBeInTheDocument();
    expect(apiMock.delete).toHaveBeenCalledExactlyOnceWith('/queues/profiles/specialists');
    expect(apiMock.put).not.toHaveBeenCalled();
    expect(screen.getByText('Синтетический профиль для проверки удаления')).toBeInTheDocument();
    expect(within(row).getByTitle('Архивировать профиль')).toBeEnabled();
    expect(apiMock.get.mock.calls.filter(([url]) => url.startsWith('/queues/profiles'))).toHaveLength(1);
  });

  it('traps keyboard focus, closes on Escape, and restores focus to the opener', async () => {
    const user = userEvent.setup();
    await renderManager();
    const addButton = await openCreateDialog(user);

    const dialog = screen.getByRole('dialog', { name: 'Новая вкладка' });
    const keyInput = screen.getByLabelText('Уникальный ключ вкладки очереди');
    const closeButton = screen.getByRole('button', { name: 'Закрыть форму вкладки очереди' });
    const createButton = screen.getByRole('button', { name: 'Создать вкладку очереди' });

    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(keyInput).toHaveFocus();

    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(closeButton).toHaveFocus();
    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(createButton).toHaveFocus();
    await user.keyboard('{Tab}');
    expect(closeButton).toHaveFocus();

    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(addButton).toHaveFocus();
  });

  it('allows clicks and Enter on color presets, and keeps every preset valid for the API and color input', async () => {
    const user = userEvent.setup();
    await renderManager();
    await openCreateDialog(user);

    const dialog = screen.getByRole('dialog', { name: 'Новая вкладка' });
    const presetButtons = within(dialog).getAllByRole('button', { name: /^Выбрать цвет / });
    const presetColors = presetButtons.map((button) => (button as HTMLButtonElement).title);

    expect(presetColors).toHaveLength(8);
    presetColors.forEach((color) => {
      expect(color).toMatch(/^#[0-9a-f]{6}$/i);
      expect(color.length).toBeLessThanOrEqual(20);
    });

    const colorInput = screen.getByLabelText('Пользовательский цвет вкладки очереди');
    const firstPreset = presetButtons[0];
    await user.click(firstPreset);
    expect(colorInput).toHaveValue(firstPreset.getAttribute('title')?.toLowerCase());
    expect(screen.getByRole('dialog', { name: 'Новая вкладка' })).toBeInTheDocument();

    presetButtons[1].focus();
    await user.keyboard('{Enter}');
    expect(colorInput).toHaveValue(presetButtons[1].getAttribute('title')?.toLowerCase());
    expect(screen.getByRole('dialog', { name: 'Новая вкладка' })).toBeInTheDocument();
  });

  it('associates visible form labels with their controls', async () => {
    const user = userEvent.setup();
    await renderManager();
    await openCreateDialog(user);

    const englishTitle = screen.getByLabelText('Название вкладки очереди на английском');
    const englishLabel = screen.getByText('Название (EN) *');

    expect(englishTitle).toHaveAttribute('id', 'queue-profile-title-en');
    expect(englishLabel).toHaveAttribute('for', 'queue-profile-title-en');
  });
});
