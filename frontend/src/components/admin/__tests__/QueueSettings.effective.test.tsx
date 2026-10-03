/**
 * RQ-23.ui (S-20, D-06): the queue settings panel must show, for every
 * managed setting, WHERE its effective value comes from (clinic →
 * department → owner → day snapshot) and WHEN it applies — or say
 * honestly that the field is not applied at all (F-19 dead department
 * fields except queue_prefix).
 *
 * The report is strictly read-only: the active day is a frozen snapshot
 * (D-06 — живые настройки не переписывают действующий день), so the
 * panel must not offer any write path for it.
 *
 * Scope selectors (department / queue tag) must refetch the report with
 * explicit query parameters — no client-side merging of partial data.
 */
import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
  me: vi.fn(),
  setToken: vi.fn(),
  setSessionInvalidationListener: vi.fn(),
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
      live: true,
      applied_when: ['day_creation_snapshot'],
      runtime_consumers: ['v1_online_admission_gate', 'queue_auto_close'],
      snapshot_field: 'DailyQueue.online_end_time',
      note: 'Только новые v1 очереди фиксируют cutoff; существующие legacy очереди сохраняют старые правила.',
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
      policy_version: 'daily_online_issuances_v1',
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
      policy_version: 'legacy',
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
    const cutoff = parsed.fields.find((f) => f.field === 'auto_close_time');
    expect(cutoff?.live).toBe(true);
    expect(cutoff?.applied_when).toEqual(['day_creation_snapshot']);
    expect(parsed.active_day[0].policy_version).toBe('daily_online_issuances_v1');
    expect(parsed.active_day[1].policy_version).toBe('legacy');
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
    window.sessionStorage.clear();
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

  it('shows auto_close_time as a v1-only snapshot setting and keeps the current day read-only', async () => {
    const user = userEvent.setup();
    renderPanel();
    const region = await getEffectiveRegion();

    // Clinic-level fields are listed with their source level.
    expect(within(region).getByText('Часовой пояс')).toBeInTheDocument();
    expect(within(region).getAllByText('клиника').length).toBeGreaterThan(0);

    // Applied-when chips: immediate + day-creation snapshot semantics.
    expect(within(region).getAllByText('сразу').length).toBeGreaterThan(0);
    expect(within(region).getAllByText('снимок при создании дня').length).toBeGreaterThan(0);

    // The end time applies only to new v1 queues; existing day snapshots remain unchanged.
    const cutoffRow = within(region).getByText('Время автозакрытия (клиника)').closest('[data-field-row]');
    expect(cutoffRow).not.toBeNull();
    expect(within(cutoffRow as HTMLElement).getByText('применяется')).toBeInTheDocument();
    expect(within(cutoffRow as HTMLElement).getByText('снимок при создании дня')).toBeInTheDocument();
    expect(within(cutoffRow as HTMLElement).getByText(/DailyQueue\.online_end_time/)).toBeInTheDocument();
    const activeDay = region.querySelector('[data-day-row]');
    expect(activeDay).not.toBeNull();
    expect(within(activeDay as HTMLElement).getByText('V1: онлайн-запись закрывается в указанное время')).toBeInTheDocument();
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
    window.sessionStorage.clear();
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
    fireEvent.change(await screen.findByDisplayValue('09:00'), { target: { value: '10:00' } });
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
    expect(mockedPut).toHaveBeenCalledTimes(1);
    expect(mockedPut.mock.calls[0]?.[1]).not.toHaveProperty('dev_mode_enabled');
  });

  it('P2-2 round 2: post-save refresh targets the LATEST selected scope', async () => {
    let releasePut!: (value: { data: unknown }) => void;
    const putGate = new Promise<{ data: unknown }>((resolve) => {
      releasePut = resolve;
    });
    mockedPut.mockImplementation(async () => {
      return await putGate;
    });

    const user = userEvent.setup();
    renderPanel();
    await getEffectiveRegion();

    // Save starts under department scope 2 (PUT held pending).
    await user.click(screen.getByRole('button', { name: 'Область: отделение' }));
    await user.click(await screen.findByRole('option', { name: 'Дерматология SYNTH' }));
    await waitFor(() => {
      expect(mockedGet.mock.calls.some(([url]) => String(url).includes('department_id=2'))).toBe(true);
    });
    fireEvent.change(await screen.findByDisplayValue('09:00'), { target: { value: '10:00' } });
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    // While the PUT is in flight the admin switches the scope back to clinic.
    await user.click(screen.getByRole('button', { name: 'Область: отделение' }));
    await user.click(await screen.findByRole('option', { name: 'Уровень клиники (без отделения)' }));

    releasePut({ data: { message: 'Настройки сохранены', settings: settingsFixture } });
    await waitFor(() => {
      // 1: mount, 2: department scope, 3: back to clinic, 4: post-save refresh.
      const effectiveGets = mockedGet.mock.calls.filter(([url]) =>
        String(url).includes('/admin/queue/settings/effective'),
      );
      expect(effectiveGets.length).toBeGreaterThanOrEqual(4);
      // The LAST request must match the CURRENT (clinic) scope: the save
      // refresh may not resurrect the stale department scope.
      const lastUrl = String(effectiveGets[effectiveGets.length - 1][0]);
      expect(lastUrl).not.toContain('department_id=2');
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
    expect(within(region).getByText(/Только новые v1 очереди фиксируют cutoff/)).toBeInTheDocument();

    try {
      await i18n.changeLanguage('en');
      expect(within(region).queryByText(/Только новые v1 очереди фиксируют cutoff/)).toBeNull();
      expect(within(region).getAllByText('applied').length).toBeGreaterThan(0);
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

describe('QueueSettings draft safeguards (T02)', () => {
  const draftKey = 'admin.queue.settings.draft.v2';

  beforeEach(() => {
    vi.clearAllMocks();
    window.sessionStorage.clear();
    window.sessionStorage.setItem('auth_profile', JSON.stringify({ id: 1, clinic_id: 1, role: 'admin' }));
    mockedGet.mockImplementation(async (url: string) => {
      if (url.startsWith('/admin/queue/settings/effective')) {
        return { data: url.includes('department_id=2') ? scopedReport : baseReport };
      }
      if (url === '/admin/queue/settings') return { data: settingsFixture };
      if (url.startsWith('/queues/profiles')) return { data: { profiles: [...profilesFixture, archivedProfileFixture] } };
      if (url.startsWith('/admin/doctors')) return { data: doctorsFixture };
      if (url.startsWith('/admin/departments')) {
        return { data: { success: true, data: departmentsFixture, count: departmentsFixture.length } };
      }
      return { data: {} };
    });
  });
  it('does not offer saving when the settings GET fails', async () => {
    mockedGet.mockImplementation(async (url: string) => {
      if (url === '/admin/queue/settings') throw new Error('synthetic GET failure');
      if (url.startsWith('/admin/queue/settings/effective')) return { data: baseReport };
      return { data: {} };
    });

    renderPanel();

    expect(await screen.findByRole('alert')).toHaveTextContent('Ошибка загрузки настроек очередей.');
    expect(screen.queryByRole('button', { name: 'Сохранить' })).not.toBeInTheDocument();
    expect(mockedPut).not.toHaveBeenCalled();
  });

  it('restores an unsaved draft after the settings screen is left and reopened', async () => {
    const firstVisit = renderPanel();
    const autoCloseInput = await screen.findByDisplayValue('09:00');
    fireEvent.change(autoCloseInput, { target: { value: '10:30' } });

    firstVisit.unmount();
    renderPanel();

    expect(await screen.findByDisplayValue('10:30')).toBeInTheDocument();
  });

  it('does not silently restore a stale draft over newer server settings and rebases only the draft changes on request', async () => {
    const currentSettings = { ...settingsFixture, max_per_day: { cardiology: 30 } };
    window.sessionStorage.setItem(draftKey, JSON.stringify({
      version: 2,
      ownerId: '1:1',
      baseSettings: settingsFixture,
      settings: { ...settingsFixture, auto_close_time: '10:30' },
    }));
    mockedGet.mockImplementation(async (url: string) => {
      if (url === '/admin/queue/settings') return { data: currentSettings };
      if (url.startsWith('/admin/queue/settings/effective')) return { data: baseReport };
      return { data: {} };
    });
    mockedPut.mockResolvedValue({
      data: {
        message: 'Настройки сохранены',
        settings: { ...currentSettings, auto_close_time: '10:30' },
      },
    } as never);

    const user = userEvent.setup();
    renderPanel();

    expect(await screen.findByDisplayValue('09:00')).toBeInTheDocument();
    expect(screen.getByDisplayValue('09:00')).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent('Настройки на сервере изменились после создания черновика.');
    expect(screen.getByRole('button', { name: 'Сохранить' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Применить мои изменения' }));
    expect(await screen.findByDisplayValue('10:30')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => expect(mockedPut).toHaveBeenCalledTimes(1));
    expect(mockedPut.mock.calls[0]?.[1]).toMatchObject({
      auto_close_time: '10:30',
      max_per_day: { cardiology: 30 },
    });
  });

  it('discards a draft owned by a different signed-in principal', async () => {
    window.sessionStorage.setItem('auth_profile', JSON.stringify({ id: 2, clinic_id: 1, role: 'admin' }));
    window.sessionStorage.setItem(draftKey, JSON.stringify({
      version: 2,
      ownerId: '1:1',
      baseSettings: settingsFixture,
      settings: { ...settingsFixture, auto_close_time: '10:30' },
    }));

    renderPanel();

    expect(await screen.findByDisplayValue('09:00')).toBeInTheDocument();
    expect(await screen.findByText('Черновик не привязан к текущей учётной записи и удалён. Загружены актуальные настройки сервера.')).toBeInTheDocument();
    expect(window.sessionStorage.getItem(draftKey)).toBeNull();
  });

  it('requires explicit confirmation before refresh discards an unsaved draft', async () => {
    const user = userEvent.setup();
    renderPanel();
    const autoCloseInput = await screen.findByDisplayValue('09:00');
    fireEvent.change(autoCloseInput, { target: { value: '10:30' } });
    const settingsGetsBefore = mockedGet.mock.calls.filter(([url]) => url === '/admin/queue/settings').length;

    await user.click(screen.getByRole('button', { name: 'Обновить' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Несохранённые изменения будут удалены. Обновить настройки?')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    expect(mockedGet.mock.calls.filter(([url]) => url === '/admin/queue/settings')).toHaveLength(settingsGetsBefore);
    expect(screen.getByDisplayValue('10:30')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Обновить' }));
    const confirmDialog = await screen.findByRole('dialog');
    await user.click(within(confirmDialog).getByRole('button', { name: 'Обновить' }));
    await waitFor(() => {
      expect(mockedGet.mock.calls.filter(([url]) => url === '/admin/queue/settings')).toHaveLength(settingsGetsBefore + 1);
    });
    expect(await screen.findByDisplayValue('09:00')).toBeInTheDocument();
  });

  it('does not keep a confirmed-discard draft active when refresh GET fails', async () => {
    let settingsGets = 0;
    mockedGet.mockImplementation(async (url: string) => {
      if (url === '/admin/queue/settings') {
        settingsGets += 1;
        if (settingsGets === 2) throw new Error('synthetic refresh failure');
        return { data: settingsFixture };
      }
      if (url.startsWith('/admin/queue/settings/effective')) return { data: baseReport };
      return { data: {} };
    });

    const user = userEvent.setup();
    renderPanel();
    fireEvent.change(await screen.findByDisplayValue('09:00'), { target: { value: '10:30' } });
    await user.click(screen.getByRole('button', { name: 'Обновить' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Обновить' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Ошибка загрузки настроек очередей.');
    await user.click(screen.getByRole('button', { name: 'Обновить' }));

    expect(await screen.findByDisplayValue('09:00')).toBeInTheDocument();
    expect(settingsGets).toBe(3);
  });

  it('continues refreshing after sessionStorage rejects draft removal', async () => {
    window.sessionStorage.setItem(draftKey, JSON.stringify({
      version: 2,
      ownerId: '1:1',
      baseSettings: settingsFixture,
      settings: { ...settingsFixture, auto_close_time: '10:30' },
    }));

    const user = userEvent.setup();
    renderPanel();
    expect(await screen.findByDisplayValue('10:30')).toBeInTheDocument();
    const settingsGetsBefore = mockedGet.mock.calls.filter(([url]) => url === '/admin/queue/settings').length;
    const originalRemoveItem = window.sessionStorage.removeItem.bind(window.sessionStorage);
    const removeSpy = vi.spyOn(window.sessionStorage, 'removeItem').mockImplementationOnce((key: string) => {
      if (key === draftKey) throw new DOMException('Storage access denied', 'SecurityError');
      originalRemoveItem(key);
    });

    await user.click(screen.getByRole('button', { name: 'Обновить' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Обновить' }));

    expect(await screen.findByDisplayValue('09:00')).toBeInTheDocument();
    expect(mockedGet.mock.calls.filter(([url]) => url === '/admin/queue/settings')).toHaveLength(settingsGetsBefore + 1);
    removeSpy.mockRestore();
  });

  it('keeps newer edits when an older save response arrives late', async () => {
    let releasePut!: (value: { data: unknown }) => void;
    const putGate = new Promise<{ data: unknown }>((resolve) => {
      releasePut = resolve;
    });
    mockedPut.mockImplementation(async () => await putGate as never);

    const user = userEvent.setup();
    renderPanel();
    const autoCloseInput = await screen.findByDisplayValue('09:00');
    fireEvent.change(autoCloseInput, { target: { value: '10:30' } });
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));
    await waitFor(() => expect(mockedPut).toHaveBeenCalledTimes(1));

    fireEvent.change(autoCloseInput, { target: { value: '11:00' } });
    releasePut({
      data: {
        message: 'Настройки сохранены',
        settings: { ...settingsFixture, auto_close_time: '10:30' },
      },
    });

    expect(await screen.findByText('Предыдущие изменения сохранены. Остались новые несохранённые изменения.')).toBeInTheDocument();
    expect(screen.getByDisplayValue('11:00')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Сохранить' })).toBeEnabled();
  });

  it('shows no fake QR test and does not fabricate a quota or number range', async () => {
    renderPanel();
    await getEffectiveRegion();

    await screen.findByDisplayValue('09:00');
    expect(screen.queryByRole('button', { name: /Test queue generation/i })).not.toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
    const numberInputs = screen.getAllByRole('spinbutton');
    expect((numberInputs[1] as HTMLInputElement).value).toBe('');
    expect(screen.queryByText('10 - 10')).not.toBeInTheDocument();
  });
});
