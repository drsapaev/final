/**
 * WelcomeView honest-states contracts (registrar audit ledger):
 *
 * - REG-FE-008  manual refresh toasts success ONLY for a verified outcome
 *               (the data hook resolves a typed RegistrarWorklistLoadOutcome).
 * - REG-FE-027  morning checklist groups by the canonical queue owner
 *               (queue_owner_kind/queue_owner_id), counts DISTINCT patients
 *               (or honestly labels records), and is a today-only instrument.
 * - REG-FE-028  filters narrowing a non-empty scope to zero rows render
 *               «no matches», never the empty-queue state + create CTA.
 * - REG-FE-029  a failed primary load renders a visible error + retry state
 *               instead of a blank history region.
 * - REG-FE-030  quick filters mutate only the status key; «Все записи» clears
 *               the narrowing (status/q) but keeps date/dept/doctor scope.
 * - REG-FE-031  selection checkboxes are disabled until a bulk consumer
 *               exists (same dead-UI removal as the worklist).
 * - REG-FE-032  date-only history values are Tashkent calendar days and are
 *               rendered in the clinic timezone, never the browser zone.
 *
 * The suite pins the REGRESSED contracts; on the pre-fix source each block
 * fails (merged «Врач #undefined» card, record counts labelled «Пациентов»,
 * synchronous success toast, whole-query replacement, orphaned checkboxes,
 * UTC-rebased date labels, missing error/no-matches states).
 */

// REG-FE-032 red-check precondition: render date-only values from a
// UTC-negative operator zone — the pre-fix code showed the PREVIOUS day.
// PR #3851 review (P3): the override is process-global — capture the
// original zone and restore it in afterAll so a reused worker/process
// (vitest without per-file isolation) never inherits America/New_York.
const originalProcessTz = process.env.TZ;
process.env.TZ = 'America/New_York';

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterAll, afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/components/ui/macos', () => ({
  Button: (props: Record<string, unknown>) => <button {...props} />,
  Badge: (props: Record<string, unknown>) => <span {...props} />,
  Card: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  CardHeader: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  CardContent: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Input: (props: Record<string, unknown>) => <input {...props} />,
}));

vi.mock('@/components/ui', () => ({
  AnimatedTransition: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/statistics/ModernStatistics', () => ({
  default: () => <div data-testid="modern-statistics" />,
}));

vi.mock('@/components/tables/EnhancedAppointmentsTable', () => ({
  default: ({ showCheckboxes, data }: { showCheckboxes?: boolean; data?: unknown[] }) => (
    <div
      data-testid="appointments-stub"
      data-show-checkboxes={String(Boolean(showCheckboxes))}
      data-rows={String(data?.length ?? 0)} />
  ),
}));

vi.mock('@/services/notify', () => ({
  default: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warn: vi.fn() },
}));

vi.mock('@/utils/tokenManager', () => ({
  default: { getAccessToken: () => 'synthetic-token', hasToken: () => true },
}));

vi.mock('@/utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn() },
}));

import notify from '@/services/notify';
import WelcomeView, { formatClinicDayLong, formatClinicTodayLong } from '../WelcomeView';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// PR #3851 review (P3): TZ is a process-wide knob — undo the suite-wide
// override so sibling suites in a shared worker keep their own zone.
afterAll(() => {
  if (originalProcessTz === undefined) {
    delete process.env.TZ;
  } else {
    process.env.TZ = originalProcessTz;
  }
});

const makeProps = (overrides: Record<string, unknown> = {}) => ({
  t: (key: string) => key,
  language: 'ru',
  theme: 'light',
  textColor: '#000000',
  appointments: [] as Record<string, unknown>[],
  departmentStats: {},
  dataSource: 'api',
  appointmentsLoading: false,
  filteredAppointments: [] as Record<string, unknown>[],
  services: {},
  activeTab: null,
  historyDate: '2026-10-30',
  showCalendar: false,
  tempDateInput: '',
  loadAppointments: vi.fn(),
  setShowWizard: vi.fn(),
  setWizardEditMode: vi.fn(),
  setWizardInitialData: vi.fn(),
  setShowPaymentManager: vi.fn(),
  setHistoryDate: vi.fn(),
  setShowCalendar: vi.fn(),
  setTempDateInput: vi.fn(),
  setSearchParams: vi.fn(),
  navigate: vi.fn(),
  setPaymentDialog: vi.fn(),
  setPrintDialog: vi.fn(),
  setContextMenu: vi.fn(),
  openRecordPreview: vi.fn(),
  openRecordEditor: vi.fn(),
  updateAppointmentStatus: vi.fn(),
  handleStartVisit: vi.fn(),
  generateCSV: vi.fn(),
  downloadCSV: vi.fn(),
  DataSourceIndicator: () => <div data-testid="dsi" />,
  ...overrides,
});

// ─── REG-FE-027 — owner-aware morning checklist ─────────────────────────────

describe('REG-FE-027 — morning checklist owner groups and honest counts', () => {
  const summaryRows = [
    // Doctor 7: ONE patient with TWO records — the pre-fix code counted 2.
    { id: 1, queue_owner_kind: 'doctor', queue_owner_id: 7, queue_name: 'Иванов Иван', patient_id: 101 },
    { id: 2, queue_owner_kind: 'doctor', queue_owner_id: 7, queue_name: 'Иванов Иван', patient_id: 101 },
    // Doctor 9: two distinct patients.
    { id: 3, queue_owner_kind: 'doctor', queue_owner_id: 9, queue_name: 'Петрова Анна', patient_id: 102 },
    { id: 4, queue_owner_kind: 'doctor', queue_owner_id: 9, queue_name: 'Петрова Анна', patient_id: 103 },
    // Resource-owned queue — must NOT be merged into any doctor card.
    { id: 5, queue_owner_kind: 'resource', queue_owner_id: 4, queue_name: 'ЭКГ', patient_id: 104 },
    // Doctor owner without a queue name — honest numbered fallback.
    { id: 6, queue_owner_kind: 'doctor', queue_owner_id: 12, patient_id: 105 },
    // No queue owner at all — honest unowned bucket, one row lacks patient_id.
    { id: 7, patient_id: 106 },
    { id: 8 },
  ];

  it('groups by the canonical queue owner; owners are never collapsed into «Врач #undefined»', () => {
    render(<WelcomeView {...makeProps({ appointments: summaryRows })} />);

    expect(screen.getByText('Иванов Иван')).toBeInTheDocument();
    expect(screen.getByText('Петрова Анна')).toBeInTheDocument();
    expect(screen.getByText('ЭКГ')).toBeInTheDocument();
    expect(screen.getByText('Врач №12')).toBeInTheDocument();
    expect(screen.getByText('Без привязки к врачу')).toBeInTheDocument();
    // THE defect: canonical rows carry no legacy doctor_id — everything used
    // to collapse into one bogus «Врач #undefined» card.
    expect(screen.queryByText(/Врач #/)).toBeNull();
  });

  it('counts DISTINCT patients per owner; records-only groups are labelled «Записей»', () => {
    render(<WelcomeView {...makeProps({ appointments: summaryRows })} />);

    // Doctor 7: two records of one patient → «Пациентов: 1» (dedup proof).
    // Doctor 9: two distinct patients → «Пациентов: 2».
    expect(screen.getByText('Пациентов: 2')).toBeInTheDocument();
    // Doctor 7, doctor 12 and the ЭКГ resource each hold exactly one
    // distinct patient — the doctor-7 card proves the two-record dedup.
    expect(screen.getAllByText('Пациентов: 1').length).toBe(3);
    // Unowned group has a row WITHOUT patient_id — dedup is impossible, so
    // the label must honestly fall back to records, not invent patients.
    expect(screen.getByText('Записей: 2')).toBeInTheDocument();
  });

  it('the checklist is a TODAY instrument: a historical sample does not render it', () => {
    render(<WelcomeView {...makeProps({ appointments: summaryRows, loadedDateIsToday: false })} />);

    expect(screen.queryByText('Утренний статус приёма')).toBeNull();
    expect(screen.queryByText('Иванов Иван')).toBeNull();
  });

  it('no rows → no checklist block (and no crash)', () => {
    render(<WelcomeView {...makeProps({ appointments: [] })} />);

    expect(screen.queryByText('Утренний статус приёма')).toBeNull();
  });
});

// ─── REG-FE-028 — «no matches» vs «empty queue» ─────────────────────────────

describe('REG-FE-028 — filtered-to-zero scope is «no matches», not an empty queue', () => {
  it('non-empty scope narrowed to zero rows shows the no-matches state without the create CTA', () => {
    render(
      <WelcomeView
        {...makeProps({
          appointments: [{ id: 1, patient_fio: 'SYNTHETIC PATIENT' }],
          filteredAppointments: [],
          dataSource: 'api',
          emptyScopeKind: 'filtered-empty',
        })}
      />,
    );

    expect(screen.getByText('rp_worklist_no_matches')).toBeInTheDocument();
    expect(screen.getByText('rp_empty_filter_desc')).toBeInTheDocument();
    // THE defect: this used to render «Очередь пуста» + «Создать первую
    // запись» — inviting a duplicate registration.
    expect(screen.queryByText('Очередь пуста')).toBeNull();
    expect(screen.queryByText('Создать первую запись')).toBeNull();
  });

  it('a genuinely empty scope keeps the empty-queue state and its CTA', () => {
    render(
      <WelcomeView
        {...makeProps({ appointments: [], filteredAppointments: [], dataSource: 'api', emptyScopeKind: 'queue-empty' })}
      />,
    );

    expect(screen.getByText('Очередь пуста')).toBeInTheDocument();
    expect(screen.getByText('Создать первую запись')).toBeInTheDocument();
    expect(screen.queryByText('rp_worklist_no_matches')).toBeNull();
  });

  it('absent emptyScopeKind prop → backward-compatible queue-empty default', () => {
    render(
      <WelcomeView {...makeProps({ appointments: [], filteredAppointments: [], dataSource: 'api' })} />,
    );

    expect(screen.getByText('Очередь пуста')).toBeInTheDocument();
    expect(screen.queryByText('rp_worklist_no_matches')).toBeNull();
  });
});

// ─── REG-FE-029 — primary load failure is visible ───────────────────────────

describe('REG-FE-029 — primary queue load failure renders an error + retry state', () => {
  it('zero rows with dataSource=error show the error message and a retry that reloads', () => {
    const loadAppointments = vi.fn();
    render(
      <WelcomeView
        {...makeProps({ appointments: [], filteredAppointments: [], dataSource: 'error', loadAppointments })}
      />,
    );

    // THE defect: this exact state rendered NOTHING (blank history region).
    expect(screen.getByText('ds_error_message')).toBeInTheDocument();
    expect(screen.queryByText('Очередь пуста')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'ds_retry' }));
    expect(loadAppointments).toHaveBeenCalledWith({ source: 'welcome_retry' });
  });

  it('an error with kept rows keeps the table visible (stale data stays on screen)', () => {
    render(
      <WelcomeView
        {...makeProps({
          appointments: [{ id: 1 }],
          filteredAppointments: [{ id: 1, patient_fio: 'SYNTHETIC PATIENT' }],
          dataSource: 'error',
        })}
      />,
    );

    expect(screen.getByTestId('appointments-stub')).toBeInTheDocument();
    expect(screen.queryByText('ds_error_message')).toBeNull();
  });
});

// ─── REG-FE-030 — quick filters preserve unrelated URL scope ────────────────

describe('REG-FE-030 — quick filters mutate only the status key', () => {
  it('status quick filter keeps date/dept/doctor/search scope (functional URL update)', () => {
    const setSearchParams = vi.fn();
    render(<WelcomeView {...makeProps({ setSearchParams })} />);

    fireEvent.click(screen.getByRole('menuitem', { name: /Активная очередь/ }));

    expect(setSearchParams).toHaveBeenCalledTimes(1);
    const updater = setSearchParams.mock.calls[0][0] as (prev: URLSearchParams) => URLSearchParams;
    // THE defect: the pre-fix call passed `{ status: 'queued' }` — a plain
    // object that REPLACED the whole query.
    expect(typeof updater).toBe('function');
    const next = updater(new URLSearchParams('date=2026-10-28&dept=lab&q=синтетика&doctor_id=5'));
    expect(next.get('status')).toBe('queued');
    expect(next.get('date')).toBe('2026-10-28');
    expect(next.get('dept')).toBe('lab');
    expect(next.get('q')).toBe('синтетика');
    expect(next.get('doctor_id')).toBe('5');
  });

  it('the payment quick filter behaves the same way', () => {
    const setSearchParams = vi.fn();
    render(<WelcomeView {...makeProps({ setSearchParams })} />);

    fireEvent.click(screen.getByRole('menuitem', { name: /Ожидают оплаты/ }));

    const updater = setSearchParams.mock.calls[0][0] as (prev: URLSearchParams) => URLSearchParams;
    const next = updater(new URLSearchParams('date=2026-10-28&q=text'));
    expect(next.get('status')).toBe('paid_pending');
    expect(next.get('date')).toBe('2026-10-28');
    expect(next.get('q')).toBe('text');
  });

  it('«Все записи» clears the narrowing (status + search) but keeps the scope', () => {
    const setSearchParams = vi.fn();
    render(<WelcomeView {...makeProps({ setSearchParams })} />);

    fireEvent.click(screen.getByRole('button', { name: /Все записи/ }));

    const updater = setSearchParams.mock.calls[0][0] as (prev: URLSearchParams) => URLSearchParams;
    expect(typeof updater).toBe('function');
    const next = updater(new URLSearchParams('date=2026-10-28&dept=lab&status=queued&q=text&doctor_id=5'));
    expect(next.get('status')).toBeNull();
    expect(next.get('q')).toBeNull();
    // Scope keys survive — "all records" must not silently move the day.
    expect(next.get('date')).toBe('2026-10-28');
    expect(next.get('dept')).toBe('lab');
    expect(next.get('doctor_id')).toBe('5');
  });
});

// ─── REG-FE-008 — refresh success only for a verified outcome ───────────────

describe('REG-FE-008 — manual refresh toasts success only after a verified outcome', () => {
  it('a failed refresh does NOT announce success', async () => {
    const loadAppointments = vi.fn().mockResolvedValue('failed');
    render(<WelcomeView {...makeProps({ loadAppointments })} />);

    fireEvent.click(screen.getByRole('menuitem', { name: /Обновить данные/ }));

    await waitFor(() => expect(loadAppointments).toHaveBeenCalledTimes(1));
    // Flush the outcome .then chain before judging the toast.
    await Promise.resolve();
    await Promise.resolve();
    expect(notify.success).not.toHaveBeenCalled();
  });

  it('a successful refresh announces success exactly once', async () => {
    const loadAppointments = vi.fn().mockResolvedValue('loaded');
    render(<WelcomeView {...makeProps({ loadAppointments })} />);

    fireEvent.click(screen.getByRole('menuitem', { name: /Обновить данные/ }));

    await waitFor(() => expect(notify.success).toHaveBeenCalledTimes(1));
    expect(notify.success).toHaveBeenCalledWith('misc.data_updated');
  });

  it('an authoritative empty day is still a successful refresh', async () => {
    const loadAppointments = vi.fn().mockResolvedValue('empty');
    render(<WelcomeView {...makeProps({ loadAppointments })} />);

    fireEvent.click(screen.getByRole('menuitem', { name: /Обновить данные/ }));

    await waitFor(() => expect(notify.success).toHaveBeenCalledTimes(1));
  });

  it('a skipped/cooldown refresh does not announce success', async () => {
    const loadAppointments = vi.fn().mockResolvedValue('skipped');
    render(<WelcomeView {...makeProps({ loadAppointments })} />);

    fireEvent.click(screen.getByRole('menuitem', { name: /Обновить данные/ }));

    await waitFor(() => expect(loadAppointments).toHaveBeenCalledTimes(1));
    await Promise.resolve();
    await Promise.resolve();
    expect(notify.success).not.toHaveBeenCalled();
  });
});

// ─── REG-FE-031 — no orphaned selection checkboxes ──────────────────────────

describe('REG-FE-031 — selection checkboxes stay off without a bulk consumer', () => {
  it('the welcome table opts out of checkboxes (same dead-UI removal as the worklist)', () => {
    render(
      <WelcomeView
        {...makeProps({ filteredAppointments: [{ id: 1, patient_fio: 'SYNTHETIC PATIENT' }] })}
      />,
    );

    expect(screen.getByTestId('appointments-stub')).toHaveAttribute('data-show-checkboxes', 'false');
  });
});

// ─── REG-FE-032 — clinic-timezone date labels ───────────────────────────────

describe('REG-FE-032 — clinic-timezone date labels', () => {
  it('history date-only values stay on the Tashkent calendar day (pure helper)', () => {
    // '2026-10-30' parsed as UTC midnight used to display as 29 October in
    // a UTC-negative browser zone; the clinic zone pins the calendar day.
    expect(formatClinicDayLong('2026-10-30', 'ru-RU')).toMatch(/30 октября 2026/);
    expect(formatClinicDayLong('2026-10-30', 'ru-RU')).not.toMatch(/29 октября/);
  });

  it('the hero "today" follows the clinic clock, not the operator clock (pure helper)', () => {
    // 2026-10-30T20:30Z = 2026-10-31 01:30 Tashkent = 2026-10-30 16:30 New York.
    expect(formatClinicTodayLong('ru-RU', new Date('2026-10-30T20:30:00Z'))).toMatch(/31 октября/);
  });

  it('the rendered history badge shows the Tashkent day under a UTC-negative operator zone', () => {
    // process.env.TZ = 'America/New_York' (top of file): the pre-fix
    // new Date('2026-10-30').toLocaleDateString(...) rendered «29 октября».
    render(
      <WelcomeView
        {...makeProps({ showCalendar: true, historyDate: '2026-10-30' })}
      />,
    );

    expect(screen.getByText(/30 октября 2026/)).toBeInTheDocument();
    expect(screen.queryByText(/29 октября/)).toBeNull();
  });
});
