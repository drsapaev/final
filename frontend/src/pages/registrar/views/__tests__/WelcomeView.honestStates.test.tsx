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
 * - REG-FE-030  the calendar mutates only the date key; clearing filters clears
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
  Tooltip: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  Card: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  CardHeader: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  CardContent: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Input: ({ icon: _icon, ...props }: Record<string, unknown>) => <input {...props} />,
  Select: ({ options, ...props }: { options: { value: string; label: string }[] }) => (
    <select {...props}>{options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
  ),
}));

vi.mock('@/components/tables/EnhancedAppointmentsTable', () => ({
  default: ({ showCheckboxes, data, onRowClick, filteredExport }: import('@/components/tables/appointmentsTableContracts').EnhancedAppointmentsTableProps) => (
    <div data-testid="appointments-stub" data-show-checkboxes={String(Boolean(showCheckboxes))}>
      {data?.map((row, index) => <button key={index} onClick={() => onRowClick?.(row)}>Open {index}</button>)}
      {filteredExport && <button disabled={filteredExport.disabled}
        onClick={() => filteredExport.onExport(data?.slice(0, 1) ?? [])}>{filteredExport.label}</button>}
    </div>
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
import { ThemeProvider } from '@/contexts/ThemeContext';
import ru from '@/i18n/locales/ru';
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
  t: (key: string, options?: Record<string, unknown>) => {
    const value = key.startsWith('rp_welcome_')
      ? ru.registrarPanel[key as keyof typeof ru.registrarPanel]
      : key;
    return String(value).replace(/{(\w+)}/g, (_match, param: string) => String(options?.[param] ?? ''));
  },
  language: 'ru',
  theme: 'light',
  textColor: '#000000',
  appointments: [] as Record<string, unknown>[],
  dataSource: 'api',
  appointmentsLoading: false,
  filteredAppointments: [] as Record<string, unknown>[],
  services: {},
  today: '2026-11-02',
  selectedDate: '2026-11-02',
  loadedDate: '2026-11-02',
  stale: false,
  hasUrlFilters: true,
  showCalendar: false,
  loadAppointments: vi.fn(),
  setShowWizard: vi.fn(),
  setWizardEditMode: vi.fn(),
  setWizardInitialData: vi.fn(),
  setShowPaymentManager: vi.fn(),
  setShowCalendar: vi.fn(),
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
    expect(screen.getByText('Без привязки к очереди')).toBeInTheDocument();
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
    render(<WelcomeView {...makeProps({ appointments: summaryRows, selectedDate: '2026-10-30', loadedDate: '2026-10-30' })} />);

    expect(screen.queryByText('Сегодня: записи по очередям и врачам')).toBeNull();
    expect(screen.queryByText('Иванов Иван')).toBeNull();
  });

  it('no rows → no checklist block (and no crash)', () => {
    render(<WelcomeView {...makeProps({ appointments: [] })} />);

    expect(screen.queryByText('Сегодня: записи по очередям и врачам')).toBeNull();
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
    // THE defect: this used to render «На выбранную дату нет записей» + «Создать первую
    // запись» — inviting a duplicate registration.
    expect(screen.queryByText('На выбранную дату нет записей')).toBeNull();
    expect(screen.queryByText('Создать первую запись')).toBeNull();
  });

  it('a genuinely empty scope keeps the empty-queue state and its CTA', () => {
    render(
      <WelcomeView
        {...makeProps({ appointments: [], filteredAppointments: [], dataSource: 'api', emptyScopeKind: 'queue-empty' })}
      />,
    );

    expect(screen.getByText('На выбранную дату нет записей')).toBeInTheDocument();
    expect(screen.getByText('Создать первую запись')).toBeInTheDocument();
    expect(screen.queryByText('rp_worklist_no_matches')).toBeNull();
  });

  it('absent emptyScopeKind prop → backward-compatible queue-empty default', () => {
    render(
      <WelcomeView {...makeProps({ appointments: [], filteredAppointments: [], dataSource: 'api' })} />,
    );

    expect(screen.getByText('На выбранную дату нет записей')).toBeInTheDocument();
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
    expect(screen.queryByText('На выбранную дату нет записей')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'ds_retry' }));
    expect(loadAppointments).toHaveBeenCalledWith({ source: 'welcome_retry' });
  });

  it('an error with kept rows keeps the table visible (stale data stays on screen)', () => {
    render(
      <WelcomeView
        {...makeProps({
          appointments: [{ id: 1 }],
          filteredAppointments: [{ id: 1, patient_fio: 'SYNTHETIC PATIENT' }],
          dataSource: 'api',
          stale: true,
        })}
      />,
    );

    expect(screen.getByTestId('appointments-stub')).toBeInTheDocument();
    expect(screen.getByTestId('dsi')).toBeInTheDocument();
    expect(screen.queryByText('ds_error_message')).toBeNull();
  });
});

// ─── REG-FE-030 — quick filters preserve unrelated URL scope ────────────────

describe('REG-FE-030 — calendar and narrowing preserve unrelated URL scope', () => {
  it('changes only the date; returning to today removes the archive parameter', () => {
    const setSearchParams = vi.fn();
    const view = render(<WelcomeView {...makeProps({ setSearchParams, showCalendar: true })} />);

    fireEvent.click(screen.getByRole('button', { name: 'Вчера' }));
    const query = 'date=2026-11-01&dept=lab&status=queued&q=text&doctor_id=5';
    const next = setSearchParams.mock.calls[0][0](new URLSearchParams(query));
    expect(next.toString()).toBe(query);

    view.rerender(<WelcomeView {...makeProps({ setSearchParams, showCalendar: true,
      selectedDate: '2026-11-01', loadedDate: '2026-11-01' })} />);
    fireEvent.click(screen.getByRole('button', { name: 'Сегодня' }));
    expect(setSearchParams.mock.calls[1][0](new URLSearchParams(query)).toString())
      .toBe('dept=lab&status=queued&q=text&doctor_id=5');
  });

  it('clears search and status without losing date, department or doctor', () => {
    const setSearchParams = vi.fn();
    render(<WelcomeView {...makeProps({ setSearchParams })} />);

    fireEvent.click(screen.getByRole('button', { name: /Сбросить поиск и статус/ }));

    const updater = setSearchParams.mock.calls[0][0] as (prev: URLSearchParams) => URLSearchParams;
    expect(updater(new URLSearchParams('date=2026-10-28&dept=lab&status=queued&q=text&doctor_id=5')).toString())
      .toBe('date=2026-10-28&dept=lab&doctor_id=5');
  });
});

// ─── REG-FE-008 — refresh success only for a verified outcome ───────────────

describe('REG-FE-008 — manual refresh toasts success only after a verified outcome', () => {
  it('a failed refresh does NOT announce success', async () => {
    const loadAppointments = vi.fn().mockResolvedValue('failed');
    render(<WelcomeView {...makeProps({ loadAppointments })} />);

    fireEvent.click(screen.getByRole('button', { name: /Обновить данные/ }));

    await waitFor(() => expect(loadAppointments).toHaveBeenCalledTimes(1));
    // Flush the outcome .then chain before judging the toast.
    await Promise.resolve();
    await Promise.resolve();
    expect(notify.success).not.toHaveBeenCalled();
  });

  it('a successful refresh announces success exactly once', async () => {
    const loadAppointments = vi.fn().mockResolvedValue('loaded');
    render(<WelcomeView {...makeProps({ loadAppointments })} />);

    fireEvent.click(screen.getByRole('button', { name: /Обновить данные/ }));

    await waitFor(() => expect(notify.success).toHaveBeenCalledTimes(1));
    expect(notify.success).toHaveBeenCalledWith('misc.data_updated');
  });

  it('an authoritative empty day is still a successful refresh', async () => {
    const loadAppointments = vi.fn().mockResolvedValue('empty');
    render(<WelcomeView {...makeProps({ loadAppointments })} />);

    fireEvent.click(screen.getByRole('button', { name: /Обновить данные/ }));

    await waitFor(() => expect(notify.success).toHaveBeenCalledTimes(1));
  });

  it('a skipped/cooldown refresh does not announce success', async () => {
    const loadAppointments = vi.fn().mockResolvedValue('skipped');
    render(<WelcomeView {...makeProps({ loadAppointments })} />);

    fireEvent.click(screen.getByRole('button', { name: /Обновить данные/ }));

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
        {...makeProps({ showCalendar: false, selectedDate: '2026-10-30', loadedDate: '2026-10-30' })}
      />,
    );

    expect(screen.getByText(/30 октября 2026/)).toBeInTheDocument();
    expect(screen.queryByText(/29 октября/)).toBeNull();
  });
});

describe('Welcome workflow', () => {
  it('exposes the three start-of-shift actions first and uses the existing routes', () => {
    const props = makeProps();
    render(<WelcomeView {...props} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons.slice(0, 3).map(button => button.textContent))
      .toEqual(['new_appointment', 'Найти пациента', 'Открыть очередь']);
    buttons.slice(0, 3).forEach(button => fireEvent.click(button));
    expect(props.setShowWizard).toHaveBeenCalledWith(true);
    expect(props.navigate.mock.calls).toEqual([['/clinical/search'], ['/registrar/queue']]);
  });

  it('associates the calendar label and applies an explicitly submitted date', () => {
    const setSearchParams = vi.fn();
    render(<WelcomeView {...makeProps({ showCalendar: true, setSearchParams })} />);
    const input = screen.getByLabelText('Дата записей');
    expect(input).toHaveValue('2026-11-02');
    fireEvent.change(input, { target: { value: '2026-10-30' } });
    fireEvent.click(screen.getByRole('button', { name: 'Показать за дату' }));
    expect(setSearchParams.mock.calls[0][0](new URLSearchParams('dept=lab')).toString())
      .toBe('dept=lab&date=2026-10-30');
  });

  it('does not put an old sample, its counts or CSV under a newly selected date', () => {
    const props = makeProps({
      selectedDate: '2026-10-30',
      appointments: [{ id: 1, status: 'waiting' }],
      filteredAppointments: [{ id: 1, status: 'waiting' }],
    });
    const view = render(<WelcomeView {...props} appointmentsLoading />);
    expect(screen.queryByTestId('appointments-stub')).toBeNull();
    expect(screen.queryByText('Ждут вызова')).toBeNull();
    expect(screen.queryByText('На выбранную дату нет записей')).toBeNull();
    view.rerender(<WelcomeView {...props} stale />);
    expect(screen.getByRole('alert')).toHaveTextContent('ds_error_message');
    expect(screen.queryByTestId('appointments-stub')).toBeNull();
  });

  it('uses backend status counts without inventing trends or course-change claims', () => {
    render(<WelcomeView {...makeProps({
      appointments: [
        { id: 1, canonical_status: 'waiting', status: 'paid', payment_status: 'pending' },
        { id: 2, status: 'queued' },
        { id: 3, status: 'completed' },
        { id: 4, status: 'called' },
      ],
    })} />);
    expect(screen.getByText('Ждут вызова').nextElementSibling).toHaveTextContent(/^2$/);
    expect(screen.getByText('Ожидают оплаты').nextElementSibling).toHaveTextContent(/^1$/);
    expect(screen.getByText('status_done').nextElementSibling).toHaveTextContent(/^1$/);
    expect(screen.queryByText(/%/)).toBeNull();
  });

  it('exports the table’s filtered rows with the selected date and opens the same preview as row actions', () => {
    const aggregate = { id: 1, patient_fio: 'SYNTHETIC A', queue_numbers: [{ number: 1 }, { number: 2 }] };
    const props = makeProps({
      selectedDate: '2026-10-30', loadedDate: '2026-10-30',
      appointments: [{ id: 101 }, { id: 102 }, { id: 103 }],
      filteredAppointments: [aggregate, { id: 2, patient_fio: 'SYNTHETIC B' }],
      generateCSV: vi.fn().mockReturnValue('synthetic csv'),
    });
    render(<WelcomeView {...props} />);
    fireEvent.click(screen.getByRole('button', { name: 'Скачать CSV по фильтрам' }));
    expect(props.generateCSV).toHaveBeenCalledExactlyOnceWith([aggregate], { includeQueueNumber: true });
    expect(props.downloadCSV).toHaveBeenCalledExactlyOnceWith('synthetic csv', 'appointments_2026-10-30.csv');
    fireEvent.click(screen.getByRole('button', { name: 'Open 0' }));
    expect(props.openRecordPreview).toHaveBeenCalledExactlyOnceWith(aggregate);
  });

  it('does not invite a new appointment in an empty archive or export kept stale records', () => {
    const props = makeProps({ selectedDate: '2026-10-30', loadedDate: '2026-10-30' });
    const view = render(<WelcomeView {...props} />);
    expect(screen.getByText('На выбранную дату нет записей')).toBeInTheDocument();
    expect(screen.queryByText('Создать первую запись')).toBeNull();
    view.rerender(<WelcomeView {...props} stale filteredAppointments={[{ id: 1 }]} />);
    expect(screen.getByRole('button', { name: 'Скачать CSV по фильтрам' })).toBeDisabled();
  });
});

it('the real table exports matching rows across pagination and refuses an empty result', async () => {
  const { default: ActualTable } = await vi.importActual<typeof import('@/components/tables/EnhancedAppointmentsTable')>(
    '@/components/tables/EnhancedAppointmentsTable',
  );
  const onExport = vi.fn();
  const matches = Array.from({ length: 25 }, (_, id) => ({ id: id + 1, patient_fio: 'SYNTHETIC MATCH ' + id }));
  render(<ThemeProvider><ActualTable data={[...matches, { id: 100, patient_fio: 'SYNTHETIC OTHER' }]}
    showCheckboxes={false} filteredExport={{ label: 'filtered csv', onExport }} /></ThemeProvider>);

  const search = screen.getByRole('textbox');
  const exportButton = screen.getByRole('button', { name: 'filtered csv' });
  fireEvent.change(search, { target: { value: 'SYNTHETIC MATCH' } });
  fireEvent.click(exportButton);
  expect(onExport).toHaveBeenCalledTimes(1);
  expect(onExport.mock.calls[0][0]).toHaveLength(25);
  expect(onExport.mock.calls[0][0]).toEqual(expect.arrayContaining(matches));
  fireEvent.change(search, { target: { value: 'no matching text' } });
  expect(exportButton).toBeDisabled();
  fireEvent.click(exportButton);
  expect(onExport).toHaveBeenCalledTimes(1);
});
