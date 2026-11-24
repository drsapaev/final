/**
 * PATPORTAL-FE-002 + FE-003 (and the results half of FE-001 — owner
 * registry #4063; review-group audit comment 6739106445) — the patient
 * web-portal home is dishonest about appointments and lab results.
 *
 * The appointments half of PATPORTAL-FE-001 is already honest on main
 * (DTO-typed PatientAppointment + appointment_date/time rendering, see
 * PatientPanel.publicBookingRequests.test.tsx). Two defects remain:
 * - PATPORTAL-FE-001 (results) + FE-003: the results card renders
 *   `{r.title}` / `{r.date}` against a fixture type that has no such
 *   fields — the real contract is LabOrderOut = {id, status, notes,
 *   created_at, completed_at, …} — so every row is blank, and each row
 *   carries a dead «Открыть» button with no onClick (no patient
 *   result-detail route exists). A patient with real lab orders sees
 *   blank, inert rows.
 * - PATPORTAL-FE-002: the appointment badge collapses every
 *   non-`scheduled` status into a green «Завершён» — a cancelled,
 *   no-show or pending visit is presented as completed.
 *
 * Contract after the repair:
 * - the results row renders the lab order's own created date and
 *   status, and the dead button is removed;
 * - the appointment badge carries an honest label per status
 *   vocabulary (scheduled/completed/cancelled/no_show/pending,
 *   unknown otherwise) instead of the completed fallthrough.
 *
 * Red-first: on the pre-fix source the results assertions fail (blank
 * row, dead button present) and the cancelled appointment renders the
 * green «Завершён» label; the scheduled control stays green on main.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AxiosHeaders } from 'axios';
import type { MouseEventHandler, PropsWithChildren } from 'react';
import { MemoryRouter } from 'react-router-dom';

const { authState, currentLanguage } = vi.hoisted(() => ({
  authState: { token: 'patient-token' as string | null, profile: { role: 'Patient' } as { role: string } | null },
  currentLanguage: { value: 'ru' },
}));

vi.mock('../../api/publicBooking', () => ({
  listPatientPublicBookingRequests: vi.fn().mockResolvedValue([]),
  withdrawPatientPublicBookingRequest: vi.fn(),
}));

vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key, language: currentLanguage.value }),
}));

vi.mock('../../components/common/ConfirmDialog', () => ({
  useConfirm: () => [vi.fn().mockResolvedValue(true), null],
}));

vi.mock('../../components/ui/macos', () => ({
  Card: ({ children, ...props }: PropsWithChildren<Record<string, unknown>>) => (
    <div {...props}>{children}</div>
  ),
  Button: ({ children, onClick, ...props }: PropsWithChildren<Record<string, unknown>>) => (
    <button type="button" onClick={onClick as MouseEventHandler<HTMLButtonElement>} {...props}>
      {children}
    </button>
  ),
  Badge: ({ children }: PropsWithChildren) => <span>{children}</span>,
}));

vi.mock('../../components/patient/PanelEmptyState', () => ({
  default: ({ title }: { title: string }) => <div role="status">{title}</div>,
}));

vi.mock('../../stores/auth', () => ({
  subscribe: (callback: (state: typeof authState) => void) => { callback(authState); return () => {}; },
}));
vi.mock('../../api/client', () => ({ api: { get: vi.fn().mockResolvedValue({ data: [] }), post: vi.fn() } }));
vi.mock('../../hooks/useEnhancedMediaQuery', () => ({ useBreakpoint: vi.fn() }));
vi.mock('../../components/patient/PatientCabinetSummary', () => ({ default: () => <div>cabinet summary</div> }));
vi.mock('../../components/patient/WebAuthnRegistration', () => ({ default: () => <div>passkey management</div> }));
vi.mock('../../components/patient/PatientBookingPanel', () => ({ default: () => <div>booking panel</div> }));
vi.mock('../../components/patient/PatientFormsPreview', () => ({ default: () => <div>forms preview</div> }));
vi.mock('../../components/patient/PublicBookingRequestsPanel', () => ({ default: () => <div>requests panel</div> }));

import { api } from '../../api/client';
import type { components } from '../../types/api';
import PatientPanel from '../PatientPanel';

const appointments = (status: string) =>
  [
    { id: 1, appointment_date: '2026-11-10', appointment_time: '09:30', department: 'cardio', status },
  ] satisfies components['schemas']['AppointmentHistoryItem'][];

const labOrderOut = {
  id: 7,
  visit_id: 5,
  patient_id: 3,
  status: 'completed',
  notes: 'Общий анализ крови',
  created_at: '2026-11-20T10:00:00Z',
  completed_at: null,
} satisfies components['schemas']['LabOrderOut'];

function mockPatientData(appointmentStatus: string) {
  vi.mocked(api.get).mockImplementation((url: string) => {
    if (url === '/patients/appointments') {
      return Promise.resolve({
        data: appointments(appointmentStatus),
        status: 200,
        statusText: 'OK',
        headers: {},
        config: { headers: new AxiosHeaders() },
      });
    }
    if (url === '/patients/results') {
      return Promise.resolve({
        data: [labOrderOut],
        status: 200,
        statusText: 'OK',
        headers: {},
        config: { headers: new AxiosHeaders() },
      });
    }
    return Promise.resolve({
      data: [],
      status: 200,
      statusText: 'OK',
      headers: {},
      config: { headers: new AxiosHeaders() },
    });
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  currentLanguage.value = 'ru';
});

describe('PATPORTAL-FE-001/002/003 — the patient home is honest about its data', () => {
  it('the results card renders the lab order contract (created date + status) with no dead button', async () => {
    mockPatientData('scheduled');
    render(<MemoryRouter initialEntries={['/patient']}><PatientPanel /></MemoryRouter>);

    // The row is identified by its own contract fields, not blank.
    await waitFor(() => expect(screen.getByText('20.11.2026')).toBeInTheDocument());
    expect(screen.getByText('completed')).toBeInTheDocument();
    // The dead «Открыть» affordance is removed.
    expect(screen.queryByText('Открыть')).toBeNull();
  });

  it('a cancelled appointment renders an honest label instead of a green «Завершён»', async () => {
    mockPatientData('cancelled');
    render(<MemoryRouter initialEntries={['/patient']}><PatientPanel /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText('misc.pp_otmenyon')).toBeInTheDocument());
    expect(screen.queryByText('misc.pp_zavershyon')).toBeNull();
  });

  it('control: a scheduled appointment keeps its planned label', async () => {
    mockPatientData('scheduled');
    render(<MemoryRouter initialEntries={['/patient']}><PatientPanel /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText('misc.pp_zaplanirovan')).toBeInTheDocument());
    expect(screen.queryByText('misc.pp_zavershyon')).toBeNull();
  });
});
