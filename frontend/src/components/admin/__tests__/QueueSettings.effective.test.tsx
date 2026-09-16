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
        active: true,
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
  },
];

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
    expect(parsed.active_day).toHaveLength(1);
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
        return { data: { profiles: profilesFixture } };
      }
      if (url.startsWith('/admin/doctors')) {
        return { data: doctorsFixture };
      }
      if (url.startsWith('/admin/departments')) {
        return { data: departmentsFixture };
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
      if (url.startsWith('/queues/profiles')) return { data: { profiles: profilesFixture } };
      if (url.startsWith('/admin/doctors')) return { data: doctorsFixture };
      if (url.startsWith('/admin/departments')) return { data: departmentsFixture };
      return { data: {} };
    });

    renderPanel();
    const region = await getEffectiveRegion();
    expect(
      await within(region).findByText(/Не удалось загрузить отчёт эффективных настроек/),
    ).toBeInTheDocument();
  });
});
