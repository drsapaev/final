/**
 * RQ-23.ui (S-20, D-06): the queue settings panel must show, for every
 * managed setting, WHERE its effective value comes from (clinic →
 * department → owner → day snapshot) and WHEN it applies — or say
 * honestly that the field is not applied at all (F-19 dead fields:
 * the DepartmentQueueSettings block except queue_prefix and the clinic
 * auto_close_time display-only field).
 *
 * The report is strictly read-only: the active day is a frozen snapshot
 * (D-06 — живые настройки не переписывают действующий день), so the
 * panel must not offer any write path for it.
 *
 * Scope selectors (department / queue tag) must refetch the report with
 * explicit query parameters — no client-side merging of partial data.
 */
import '@testing-library/jest-dom';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';
import QueueSettings from '../QueueSettings';
import { api } from '@/api/client';
import {
  parseEffectiveQueueSettingsReport,
  SOURCE_LEVEL_KEYS,
  APPLIED_WHEN_KEYS,
} from '@/utils/queueSettingsEffective';

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockedGet = vi.mocked(api.get);
const mockedPut = vi.mocked(api.put);

const baseReport = {
  timezone: 'Asia/Tashkent',
  clinic_today: '2026-09-17',
  chain_order: ['clinic', 'department', 'owner', 'day_snapshot'],
  clinic_settings: {
    timezone: 'Asia/Tashkent',
    queue_start_hour: 7,
    auto_close_time: '09:00',
    start_numbers: { cardiology: 10 },
    max_per_day: {},
  },
  fields: [
    {
      field: 'timezone',
      level: 'clinic',
      value: 'Asia/Tashkent',
      live: true,
      applied_when: ['immediate'],
      runtime_consumers: ['clinic_today_day_boundary'],
      note: 'Time SSOT (PR 3142): границы дня следуют этой таймзоне.',
    },
    {
      field: 'queue_start_hour',
      level: 'clinic',
      value: 7,
      live: true,
      applied_when: ['immediate', 'day_creation_snapshot'],
      runtime_consumers: ['online_entry_gate', 'day_creation_snapshot'],
      snapshot_field: 'DailyQueue.online_start_time',
      note: 'Гейт онлайн-записи + снимок при создании дня.',
    },
    {
      field: 'auto_close_time',
      level: 'clinic',
      value: '09:00',
      live: false,
      applied_when: [],
      runtime_consumers: ['display_only'],
      note: 'Движок автозакрытия читает СНИМОК дня DailyQueue.online_end_time, а не это поле.',
    },
    {
      field: 'start_numbers',
      level: 'clinic',
      value: { cardiology: 10 },
      live: true,
      applied_when: ['day_creation_snapshot'],
      runtime_consumers: ['effective_day_start_number'],
      snapshot_field: 'DailyQueue.start_number',
      note: 'Цепочка D-06 для нового дня: владелец → клиника → реестр.',
    },
    {
      field: 'max_per_day',
      level: 'clinic',
      value: {},
      live: true,
      applied_when: ['immediate'],
      runtime_consumers: ['online_issuance_cap'],
      note: 'Лимит онлайн-выдачи на живое чтение.',
    },
  ],
  department: null,
  resources: [],
  active_day: [
    {
      daily_queue_id: 9,
      day: '2026-09-17',
      specialist_id: 77,
      queue_resource_id: null,
      queue_tag: 'cardiology',
      active: true,
      opened_at: '2026-09-17T07:00:00',
      start_number: 12,
      online_start_time: '07:00',
      online_end_time: '09:00',
      max_online_entries: 25,
      source: 'day_snapshot',
      note: 'Снимок действующего дня заморожен при создании.',
    },
    {
      daily_queue_id: 10,
      day: '2026-09-17',
      specialist_id: 78,
      queue_resource_id: null,
      queue_tag: 'derm_old',
      active: false,
      opened_at: null,
      start_number: 1,
      online_start_time: null,
      online_end_time: null,
      max_online_entries: 0,
      source: 'day_snapshot',
      note: 'Снимок деактивированного дня (историческая строка).',
    },
  ],
};

const scopedReport = {
  ...baseReport,
  department: {
    department_id: 2,
    key: 'dermatology',
    name_ru: 'Дерматология SYNTH',
    active: true,
    queue_settings: {
      queue_prefix: {
        value: 'DERM',
        live: true,
        runtime_consumers: ['registrar_department_list_display'],
        note: 'Единственное живое поле блока.',
      },
      enabled: { value: true, live: false, note: 'Ритейм не читает это поле.' },
    },
    owner_overrides: [
      {
        doctor_id: 77,
        specialty: 'cardiology',
        active: true,
        start_number_online: 4,
        max_online_per_day: 25,
        effective_start_number: 4,
        source: 'owner',
      },
      {
        doctor_id: 78,
        specialty: 'cardiology',
        active: false,
        start_number_online: 1,
        max_online_per_day: 0,
        effective_start_number: 10,
        source: 'clinic',
      },
    ],
  },
  resources: [
    {
      queue_resource_id: 5,
      code: 'ultrasound',
      display_name: 'УЗИ-кабинет SYNTH',
      start_number_online: 3,
      max_online_per_day: 40,
      effective_start_number: 3,
      source: 'registry',
    },
  ],
};

const profilesFixture = [
  {
    key: 'cardiology',
    title_ru: 'Кардиология SYNTH',
    icon: 'Heart',
    color: 'synthetic-accent',
    queue_tags: ['cardiology'],
    settings_key: 'cardiology',
    is_active: true,
  },
];

// Mirrors production: archived profiles only come back when the panel
// requests active_only=false (PR 3291 P2-3); the backend default keeps
// them hidden.
const archivedProfileFixture = {
  key: 'legacy_derm',
  title_ru: 'Легаси-дерматология SYNTH',
  icon: 'Sparkles',
  color: 'synthetic-accent',
  queue_tags: ['legacy_tag'],
  settings_key: 'legacy_derm',
  is_active: false,
};

const doctorsFixture = [
  {
    id: 77,
    active: true,
    cabinet: '101',
    specialty: 'cardiology',
    user: { full_name: 'Д-р Синтетический' },
  },
  {
    id: 78,
    active: true,
    cabinet: '102',
    specialty: 'cardiology',
    user: { full_name: 'Д-р Второй SYNTH' },
  },
];

const departmentsFixture = [
  { id: 1, key: 'cardiology', name_ru: 'Кардиология SYNTH', active: true },
  { id: 2, key: 'dermatology', name_ru: 'Дерматология SYNTH', active: true },
];

const settingsFixture = {
  timezone: 'Asia/Tashkent',
  queue_start_hour: 7,
  auto_close_time: '09:00',
  start_numbers: { cardiology: 10 },
  max_per_day: {},
  dev_mode_enabled: false,
};

const renderPanel = () =>
  render(
    <ThemeProvider>
      <QueueSettings />
    </ThemeProvider>,
  );

const getEffectiveRegion = async () =>
  await screen.findByRole('region', { name: /Эффективные настройки/ });

describe('queueSettingsEffective SSOT normalizer (RQ-23.ui)', () => {
  it('parses the raw report and keeps dead fields distinguishable', () => {
    const parsed = parseEffectiveQueueSettingsReport(baseReport);
    expect(parsed.timezone).toBe('Asia/Tashkent');
    expect(parsed.clinic_today).toBe('2026-09-17');
    expect(parsed.chain_order).toEqual(['clinic', 'department', 'owner', 'day_snapshot']);
    expect(parsed.fields).toHaveLength(5);
    const dead = parsed.fields.find((f) => f.field === 'auto_close_time');
    expect(dead?.live).toBe(false);
    expect(dead?.applied_when).toEqual([]);
    const live = parsed.fields.find((f) => f.field === 'queue_start_hour');
    expect(live?.live).toBe(true);
    expect(live?.snapshot_field).toBe('DailyQueue.online_start_time');
    expect(parsed.department).toBeNull();
    expect(parsed.active_day).toHaveLength(2);
  });

  it('degrades to an honest empty report instead of crashing on garbage', () => {
    const empty = parseEffectiveQueueSettingsReport(null);
    expect(empty.fields).toEqual([]);
    expect(empty.active_day).toEqual([]);
    expect(empty.department).toBeNull();
    const partial = parseEffectiveQueueSettingsReport({ timezone: 'Asia/Tashkent' });
    expect(partial.timezone).toBe('Asia/Tashkent');
    expect(partial.fields).toEqual([]);
  });

  it('maps source levels and applied-when codes to i18n keys', () => {
    expect(SOURCE_LEVEL_KEYS.clinic).toBe('admin2.qs_eff_source_clinic');
    expect(SOURCE_LEVEL_KEYS.owner).toBe('admin2.qs_eff_source_owner');
    expect(SOURCE_LEVEL_KEYS.registry).toBe('admin2.qs_eff_source_registry');
    expect(SOURCE_LEVEL_KEYS.day_snapshot).toBe('admin2.qs_eff_source_day');
    expect(APPLIED_WHEN_KEYS.immediate).toBe('admin2.qs_eff_applied_immediate');
    expect(APPLIED_WHEN_KEYS.day_creation_snapshot).toBe('admin2.qs_eff_applied_day_creation');
  });
});

describe('QueueSettings effective-settings report panel (RQ-23.ui, S-20)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGet.mockImplementation(async (url: string) => {
      if (url.startsWith('/admin/queue/settings/effective')) {
        return {
          data: url.includes('department_id=2') ? scopedReport : baseReport,
        };
      }
      if (url.startsWith('/admin/queue/settings')) {
        return { data: settingsFixture };
      }
      if (url.startsWith('/queues/profiles')) {
        // Production semantics: archived profiles come back only for
        // active_only=false.
        const includeArchived = String(url).includes('active_only=false');
        return {
          data: {
            profiles: includeArchived
              ? [...profilesFixture, archivedProfileFixture]
              : profilesFixture,
          },
        };
      }
      if (url.startsWith('/admin/doctors')) {
        return { data: doctorsFixture };
      }
      if (url.startsWith('/admin/departments')) {
        // PRODUCTION ENVELOPE (admin_departments list_departments):
        // { success, data, count } — a bare array would mask the P1
        // envelope bug this suite must catch (PR 3291).
        return {
          data: {
            success: true,
            data: departmentsFixture,
            count: departmentsFixture.length,
          },
        };
      }
      return { data: {} };
    });
  });

  it('shows source + applied-when for clinic fields and flags the dead auto_close_time honestly (F-19)', async () => {
    const user = userEvent.setup();
    renderPanel();
    const region = await getEffectiveRegion();

    // Clinic-level fields are listed with their source level.
    expect(within(region).getByText('Часовой пояс')).toBeInTheDocument();
    expect(within(region).getAllByText('клиника').length).toBeGreaterThan(0);

    // Applied-when chips: immediate + day-creation snapshot semantics.
    expect(within(region).getAllByText('сразу').length).toBeGreaterThan(0);
    expect(within(region).getAllByText('снимок при создании дня').length).toBeGreaterThan(0);

    // Dead clinic field: honest "не применяется" + the backend reason.
    const deadRow = within(region).getByText('Время автозакрытия (клиника)').closest('[data-field-row]');
    expect(deadRow).not.toBeNull();
    expect(within(deadRow as HTMLElement).getByText('не применяется')).toBeInTheDocument();
    expect(within(deadRow as HTMLElement).getByText(/DailyQueue\.online_end_time/)).toBeInTheDocument();
    expect(user).toBeTruthy();
  });

  it('refetches with explicit department_id and tag and renders owner overrides + dead department block', async () => {
    const user = userEvent.setup();
    renderPanel();
    await getEffectiveRegion();

    await user.click(screen.getByRole('button', { name: 'Область: отделение' }));
    await user.click(await screen.findByRole('option', { name: 'Дерматология SYNTH' }));

    await waitFor(() => {
      expect(mockedGet.mock.calls.some(([url]) => String(url).includes('department_id=2'))).toBe(true);
    });

    await user.click(screen.getByRole('button', { name: 'Область: тег' }));
    await user.click(await screen.findByRole('option', { name: 'cardiology' }));

    await waitFor(() => {
      const scopedCall = mockedGet.mock.calls.find(
        ([url]) => String(url).includes('department_id=2') && String(url).includes('tag=cardiology'),
      );
      expect(scopedCall).toBeTruthy();
    });

    const region = await getEffectiveRegion();
    // Owner override: doctor resolved by name from the loaded doctors list.
    expect(within(region).getByText('Д-р Синтетический')).toBeInTheDocument();
    // Sources of the two overrides: owner chip and clinic chip.
    expect(within(region).getAllByText('владелец').length).toBeGreaterThan(0);
    // Dead department block: honest markers, but queue_prefix is live.
    expect(within(region).getByText(/Настройки отделения/)).toBeInTheDocument();
    const enabledRow = within(region).getByText('Включено').closest('[data-dept-field-row]');
    expect(enabledRow).not.toBeNull();
    expect(within(enabledRow as HTMLElement).getByText('не применяется')).toBeInTheDocument();
    const prefixRow = within(region).getByText('Префикс очереди').closest('[data-dept-field-row]');
    expect(within(prefixRow as HTMLElement).getByText('применяется')).toBeInTheDocument();
    // Resource axis (tag scope): registry source.
    expect(within(region).getByText('УЗИ-кабинет SYNTH')).toBeInTheDocument();
    expect(within(region).getAllByText('реестр').length).toBeGreaterThan(0);
  });

  it('renders the active day as a frozen snapshot and offers no write path (D-06)', async () => {
    renderPanel();
    const region = await getEffectiveRegion();

    expect(within(region).getByText(/Активный день/)).toBeInTheDocument();
    expect(within(region).getAllByText('заморожено при создании').length).toBeGreaterThan(0);

    const dayRow = within(region).getByText('cardiology').closest('[data-day-row]');
    expect(dayRow).not.toBeNull();
    expect(within(dayRow as HTMLElement).getByText(/Старт\. номер/)).toBeInTheDocument();
    expect(within(dayRow as HTMLElement).getByText('12')).toBeInTheDocument();
    expect(within(dayRow as HTMLElement).getByText('07:00 – 09:00')).toBeInTheDocument();
    expect(within(dayRow as HTMLElement).getByText('25')).toBeInTheDocument();

    // Read-only contract: the panel exposes no save/write affordance and
    // no PUT is ever issued for the report.
    const writeButtons = within(region).queryAllByRole('button', { name: /Сохранить|Save/i });
    expect(writeButtons).toHaveLength(0);
    expect(mockedPut).not.toHaveBeenCalled();
  });

  it('shows an honest error state when the report fails to load', async () => {
    mockedGet.mockImplementation(async (url: string) => {
      if (url.startsWith('/admin/queue/settings/effective')) {
        throw new Error('report unavailable');
      }
      if (url.startsWith('/admin/queue/settings')) return { data: settingsFixture };
      if (url.startsWith('/queues/profiles')) {
        const includeArchived = String(url).includes('active_only=false');
        return {
          data: {
            profiles: includeArchived
              ? [...profilesFixture, archivedProfileFixture]
              : profilesFixture,
          },
        };
      }
      if (url.startsWith('/admin/doctors')) return { data: doctorsFixture };
      if (url.startsWith('/admin/departments')) {
        return {
          data: {
            success: true,
            data: departmentsFixture,
            count: departmentsFixture.length,
          },
        };
      }
      return { data: {} };
    });

    renderPanel();
    const region = await getEffectiveRegion();
    expect(
      await within(region).findByText(/Не удалось загрузить отчёт эффективных настроек/),
    ).toBeInTheDocument();
  });
});

describe('QueueSettings panel fixes for PR 3291 review findings (owner audit, current main)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGet.mockImplementation(async (url: string) => {
      if (url.startsWith('/admin/queue/settings/effective')) {
        return {
          data: url.includes('department_id=2') ? scopedReport : baseReport,
        };
      }
      if (url.startsWith('/admin/queue/settings')) {
        return { data: settingsFixture };
      }
      if (url.startsWith('/queues/profiles')) {
        const includeArchived = String(url).includes('active_only=false');
        return {
          data: {
            profiles: includeArchived
              ? [...profilesFixture, archivedProfileFixture]
              : profilesFixture,
          },
        };
      }
      if (url.startsWith('/admin/doctors')) {
        return { data: doctorsFixture };
      }
      if (url.startsWith('/admin/departments')) {
        return {
          data: {
            success: true,
            data: departmentsFixture,
            count: departmentsFixture.length,
          },
        };
      }
      return { data: {} };
    });
  });

  it('P1: fills the department selector from the production { success, data, count } envelope', async () => {
    const user = userEvent.setup();
    renderPanel();
    await getEffectiveRegion();

    await user.click(screen.getByRole('button', { name: 'Область: отделение' }));
    expect(await screen.findByRole('option', { name: 'Кардиология SYNTH' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Дерматология SYNTH' })).toBeInTheDocument();
  });

  it('P2-1: ignores a stale report response that resolves after a newer scope request', async () => {
    let effectiveCalls = 0;
    let releaseStale!: (value: { data: unknown }) => void;
    const staleGate = new Promise<{ data: unknown }>((resolve) => {
      releaseStale = resolve;
    });
    mockedGet.mockImplementation(async (url: string) => {
      if (url.startsWith('/admin/queue/settings/effective')) {
        effectiveCalls += 1;
        // Call 2 = department scope (held pending), call 3 = tag scope (fast).
        if (effectiveCalls === 2) return await staleGate;
        return { data: baseReport };
      }
      if (url.startsWith('/admin/queue/settings')) return { data: settingsFixture };
      if (url.startsWith('/queues/profiles')) return { data: { profiles: profilesFixture } };
      if (url.startsWith('/admin/doctors')) return { data: doctorsFixture };
      if (url.startsWith('/admin/departments')) {
        return {
          data: {
            success: true,
            data: departmentsFixture,
            count: departmentsFixture.length,
          },
        };
      }
      return { data: {} };
    });

    const user = userEvent.setup();
    renderPanel();
    const region = await getEffectiveRegion();

    await user.click(screen.getByRole('button', { name: 'Область: отделение' }));
    await user.click(await screen.findByRole('option', { name: 'Дерматология SYNTH' }));
    await waitFor(() => expect(effectiveCalls).toBe(2));

    await user.click(screen.getByRole('button', { name: 'Область: тег' }));
    await user.click(await screen.findByRole('option', { name: 'cardiology' }));
    await waitFor(() => expect(effectiveCalls).toBe(3));

    // Release the STALE department-scope response after the newer one won.
    releaseStale({ data: scopedReport });
    await waitFor(() => {
      expect(within(region).queryByText(/Загрузка отчёта/)).not.toBeInTheDocument();
    });

    // The stale scoped payload must NOT win the race.
    expect(within(region).queryByText('Д-р Синтетический')).toBeNull();
  });

  it('P2-2: refetches the effective report after a successful save', async () => {
    mockedPut.mockResolvedValue({
      data: { message: 'Настройки сохранены', settings: settingsFixture },
    });
    const user = userEvent.setup();
    renderPanel();
    await getEffectiveRegion();
    const effectiveGetsBefore = mockedGet.mock.calls.filter(
      ([url]) => String(url).includes('/admin/queue/settings/effective'),
    ).length;

    await user.click(screen.getByRole('button', { name: 'Сохранить' }));
    await waitFor(() => {
      const effectiveGetsAfter = mockedGet.mock.calls.filter(
        ([url]) => String(url).includes('/admin/queue/settings/effective'),
      ).length;
      expect(effectiveGetsAfter).toBeGreaterThan(effectiveGetsBefore);
    });
  });

  it('P2-3: keeps archived-direction tags reachable while hiding their settings cards', async () => {
    const user = userEvent.setup();
    renderPanel();
    await getEffectiveRegion();

    await user.click(screen.getByRole('button', { name: 'Область: тег' }));
    expect(await screen.findByRole('option', { name: 'legacy_tag' })).toBeInTheDocument();
    expect(screen.queryByText('Легаси-дерматология SYNTH')).toBeNull();
  });

  it('P2-4: marks inactive day rows honestly instead of a blanket frozen badge', async () => {
    renderPanel();
    const region = await getEffectiveRegion();

    const inactiveRow = within(region).getByText('derm_old').closest('[data-day-row]');
    expect(inactiveRow).not.toBeNull();
    expect(
      within(inactiveRow as HTMLElement).getByText('день деактивирован (историческая строка)'),
    ).toBeInTheDocument();
    expect(
      within(inactiveRow as HTMLElement).queryByText('заморожено при создании'),
    ).toBeNull();
  });

  it('P2-5: labels clinic-level effective values as a default-key lookup when no tag is selected', async () => {
    const user = userEvent.setup();
    renderPanel();
    await getEffectiveRegion();

    await user.click(screen.getByRole('button', { name: 'Область: отделение' }));
    await user.click(await screen.findByRole('option', { name: 'Дерматология SYNTH' }));

    const region = await getEffectiveRegion();
    expect(await within(region).findByTestId('qs-eff-default-tag-note')).toBeInTheDocument();
  });

  it('P2-6 and P2-7: mark inactive doctors and surface the daily cap on owner/resource rows', async () => {
    const user = userEvent.setup();
    renderPanel();
    await getEffectiveRegion();

    await user.click(screen.getByRole('button', { name: 'Область: отделение' }));
    await user.click(await screen.findByRole('option', { name: 'Дерматология SYNTH' }));
    await user.click(screen.getByRole('button', { name: 'Область: тег' }));
    await user.click(await screen.findByRole('option', { name: 'cardiology' }));

    const region = await getEffectiveRegion();
    const ownerRow = within(region).getByText('Д-р Синтетический').closest('[data-owner-row]');
    expect(ownerRow).not.toBeNull();
    expect(within(ownerRow as HTMLElement).getByText('Лимит/день: 25')).toBeInTheDocument();

    const inactiveRow = within(region).getByText('Д-р Второй SYNTH').closest('[data-owner-row]');
    expect(inactiveRow).not.toBeNull();
    expect(within(inactiveRow as HTMLElement).getByText('врач неактивен')).toBeInTheDocument();

    const resourceRow = within(region).getByText('УЗИ-кабинет SYNTH').closest('[data-resource-row]');
    expect(resourceRow).not.toBeNull();
    expect(within(resourceRow as HTMLElement).getByText('Лимит/день: 40')).toBeInTheDocument();
  });

  it('P2-8: renders raw backend notes for ru and suppresses them for other locales', async () => {
    renderPanel();
    const region = await getEffectiveRegion();
    // ru: the raw backend note is shown as-is.
    expect(within(region).getAllByText(/DailyQueue\.online_end_time/).length).toBeGreaterThan(0);

    try {
      await i18n.changeLanguage('en');
      expect(within(region).queryByText(/DailyQueue\.online_end_time/)).toBeNull();
      expect(within(region).getAllByText('not applied').length).toBeGreaterThan(0);
    } finally {
      await i18n.changeLanguage('ru');
    }
  });

  it('P2-9: wraps the scope controls on narrow panels', async () => {
    renderPanel();
    const controls = await screen.findByTestId('qs-eff-controls');
    expect(controls.className).toContain('admin-flex-gap-12-wrap');
  });

  it('P2-10: re-titles the department block when live fields exist inside it', async () => {
    const user = userEvent.setup();
    renderPanel();
    await getEffectiveRegion();

    await user.click(screen.getByRole('button', { name: 'Область: отделение' }));
    await user.click(await screen.findByRole('option', { name: 'Дерматология SYNTH' }));

    const region = await getEffectiveRegion();
    expect(
      await within(region).findByText(
        /Настройки отделения \(display-only; живые поля помечены\)/,
      ),
    ).toBeInTheDocument();
  });
});
