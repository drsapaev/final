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
    await user.click(screen.getByRole('option', { name: 'Скрытые' }));

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
