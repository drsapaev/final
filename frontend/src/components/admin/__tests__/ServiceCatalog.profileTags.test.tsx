import '@testing-library/jest-dom';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import ServiceCatalog, { buildQueueTagOptions } from '../ServiceCatalog';
import { api } from '@/api/client';

// RQ-06 (F-05) — SYNTHETIC/DEV-DEMO fixtures only: profile keys and queue tags
// are domain identifiers, no PHI/PII values are used anywhere in this file.
const syntheticProfiles = [
  {
    key: 'synthetic-diagnostics',
    title_ru: 'Синтетическая диагностика',
    is_active: true,
    department_key: 'cardiology',
    queue_tags: ['ecg', 'echokg']
  },
  {
    key: 'synthetic-massage',
    title_ru: 'Синтетический массаж',
    is_active: true,
    department_key: null,
    queue_tags: ['massage']
  },
  {
    key: 'legacy-procedures',
    title_ru: 'Легаси-процедуры',
    is_active: true,
    department_key: 'procedures',
    queue_tags: []
  },
  {
    key: 'hidden-profile',
    title_ru: 'Скрытый профиль',
    is_active: false,
    department_key: 'dental',
    queue_tags: ['hidden-tag']
  }
];

vi.mock('../../../api/client', () => {
  const apiMock = {
    get: vi.fn((url: string) => {
      if (url === '/departments') {
        return Promise.resolve({ data: { data: [] } });
      }

      if (url === '/admin/departments') {
        return Promise.resolve({ data: { data: [] } });
      }

      if (url.startsWith('/queues/profiles')) {
        return Promise.resolve({ data: { profiles: syntheticProfiles } });
      }

      return Promise.resolve({ data: [] });
    }),
    post: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    put: vi.fn(),
    delete: vi.fn()
  };

  return {
    default: apiMock,
    api: apiMock,
    apiClient: apiMock
  };
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('buildQueueTagOptions (RQ-06 / F-05)', () => {
  it('offers every queue_tag of an active multi-tag profile with its real department_key', () => {
    const options = buildQueueTagOptions(syntheticProfiles);

    const diagnosticsOptions = options.filter((option) => option.departmentKey === 'cardiology');
    expect(diagnosticsOptions.map((option) => option.value)).toEqual(['ecg', 'echokg']);
    expect(diagnosticsOptions.every((option) => option.label.includes('Синтетическая диагностика'))).toBe(true);
    // The profile key must never become a selectable value when real tags exist.
    expect(options.some((option) => option.value === 'synthetic-diagnostics')).toBe(false);
  });

  it('keeps explicit absence of department_key (null, not a guessed department)', () => {
    const options = buildQueueTagOptions(syntheticProfiles);

    const massageOption = options.find((option) => option.value === 'massage');
    expect(massageOption).toBeDefined();
    expect(massageOption?.departmentKey).toBeNull();
  });

  it('falls back to the legacy profile.key value for tagless active profiles', () => {
    const options = buildQueueTagOptions(syntheticProfiles);

    const legacyOption = options.find((option) => option.value === 'legacy-procedures');
    expect(legacyOption).toBeDefined();
    expect(legacyOption?.label).toBe('Легаси-процедуры');
    expect(legacyOption?.departmentKey).toBe('procedures');
  });

  it('skips inactive profiles entirely', () => {
    const options = buildQueueTagOptions(syntheticProfiles);

    expect(options.some((option) => option.value === 'hidden-tag')).toBe(false);
  });

  it('deduplicates a shared tag keeping the first active profile', () => {
    const options = buildQueueTagOptions([
      { key: 'profile-a', title_ru: 'Профиль А', is_active: true, department_key: 'cardiology', queue_tags: ['shared-tag'] },
      { key: 'profile-b', title_ru: 'Профиль Б', is_active: true, department_key: 'dental', queue_tags: ['shared-tag'] }
    ]);

    expect(options.filter((option) => option.value === 'shared-tag')).toHaveLength(1);
    expect(options.find((option) => option.value === 'shared-tag')?.departmentKey).toBe('cardiology');
  });
});

describe('ServiceCatalog service form queue_tag → department_key sync (RQ-06 / F-05)', () => {
  const openServiceForm = async (user: ReturnType<typeof userEvent.setup>) => {
    render(
      <ThemeProvider>
        <ServiceCatalog />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledTimes(5);
    });

    // The header and the empty state both render an add button — click the first one.
    const addButtons = screen.getAllByRole('button', { name: 'Добавить услугу' });
    await user.click(addButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Добавление услуги')).toBeInTheDocument();
    });
  };

  const fillName = async (user: ReturnType<typeof userEvent.setup>, name: string) => {
    const label = screen.getByText('Название услуги *');
    const fieldContainer = label.closest('div');
    expect(fieldContainer).not.toBeNull();
    const nameInput = within(fieldContainer as HTMLElement).getByRole('textbox');
    await user.type(nameInput, name);
  };

  const openQueueTagSelect = async (user: ReturnType<typeof userEvent.setup>) => {
    await user.click(screen.getByRole('button', { name: 'Очередь' }));

    const queueTabPanel = screen.getByText('Вкладка регистратуры').closest('div');
    expect(queueTabPanel).not.toBeNull();
    const trigger = within(queueTabPanel as HTMLElement).getByRole('button', { name: /Без очереди/ });
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByRole('listbox')).toBeInTheDocument();
    });
  };

  it('saves the profile department_key (not profile.key) when a second tag is selected', async () => {
    const user = userEvent.setup();
    await openServiceForm(user);
    await fillName(user, 'Синтетическая услуга');

    await openQueueTagSelect(user);

    // All allowed tags of the multi-tag profile are offered, not only the first.
    // '· ecg' is not a substring of '· echokg', so the two name filters are unambiguous.
    expect(screen.getByRole('option', { name: /· ecg/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /echokg/ })).toBeInTheDocument();

    await user.click(screen.getByRole('option', { name: /echokg/ }));
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/services',
        expect.objectContaining({ queue_tag: 'echokg', department_key: 'cardiology' })
      );
    });

    const payload = (api.post as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    expect(payload.department_key).not.toBe('synthetic-diagnostics');
  });

  it('stores no invented department for a profile without department_key', async () => {
    const user = userEvent.setup();
    await openServiceForm(user);
    await fillName(user, 'Синтетическая услуга');

    await openQueueTagSelect(user);
    // Single-tag profile: the option label is the profile title (value is 'massage').
    await user.click(screen.getByRole('option', { name: 'Синтетический массаж' }));
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/services',
        expect.objectContaining({ queue_tag: 'massage', department_key: null })
      );
    });
  });

  it('keeps the legacy tagless-profile fallback with its real department', async () => {
    const user = userEvent.setup();
    await openServiceForm(user);
    await fillName(user, 'Синтетическая услуга');

    await openQueueTagSelect(user);
    await user.click(screen.getByRole('option', { name: /Легаси-процедуры/ }));
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/services',
        expect.objectContaining({ queue_tag: 'legacy-procedures', department_key: 'procedures' })
      );
    });
  });
});
