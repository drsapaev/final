/**
 * DERMACACHE-FE-001 (audit 3892, post-merge group 7) — fail-first
 * regression for the dermatology module-scope queue cache:
 *
 * The module-level `dermatologyRequestCache` must be scoped to the
 * authenticated principal. When the token changes (staff A logs out and
 * staff B logs in without a hard document reload), the next panel mount
 * must issue its OWN request instead of reusing principal A's cached
 * queue rows or in-flight promise (which carry A's PHI).
 *
 * Red-first: on the pre-fix source the second mount performs no network
 * call (the 5-second cooldown serves A's rows to B). The control proves
 * the same principal still gets the cooldown behaviour.
 */
import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));
vi.mock('../../api/runtime', () => ({
  getApiBaseUrl: () => 'http://synthetic.test/api/v1',
  getApiOrigin: () => 'http://synthetic.test',
}));
vi.mock('../../utils/tokenManager', () => ({
  default: { getAccessToken: vi.fn(() => 'principal-A-token') },
}));
vi.mock('../../utils/canonicalVisit', () => ({
  resolveCanonicalVisitId: async (row: { visit_id?: unknown }) =>
    (row?.visit_id ?? null) as string | number | null,
}));
vi.mock('../../utils/logger', () => ({
  default: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}));
vi.mock('../../services/notify', () => ({
  default: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));
vi.mock('../../services/queue', () => ({
  queueService: { completeVisit: vi.fn(), callNextWaiting: vi.fn(), startVisit: vi.fn() },
}));
vi.mock('../../services/print', () => ({
  printService: { printPrescription: vi.fn() },
}));
vi.mock('../../services/panelPrint', () => ({
  printPanelTicket: vi.fn(),
}));
vi.mock('../../stores/auth', () => ({
  subscribe: () => () => undefined,
}));
vi.mock('../../components/emr-v2/EMRContainerV2', () => ({
  EMRContainerV2: (props: { visitId?: unknown; patientId?: unknown }) => (
    <div
      data-testid="emr-editor"
      data-visit={String(props.visitId ?? '')}
      data-patient={String(props.patientId ?? '')}
    />
  ),
}));
vi.mock('../../components/dermatology/DermaVisitGallery', () => ({
  default: () => <div data-testid="derma-gallery" />,
}));
vi.mock('../../components/QueueIntegration', () => ({
  default: () => <div data-testid="queue-integration" />,
}));
vi.mock('../../components/tables/EnhancedAppointmentsTable', () => ({
  default: () => <div data-testid="appointments-table" />,
}));
vi.mock('../../components/dermatology/DermaPatientsTab', () => ({
  default: () => <div data-testid="patients-tab" />,
}));
vi.mock('../../components/ai/AIAssistant', () => ({ default: () => <div /> }));
vi.mock('../../components/VisitTimeline', () => ({ default: () => <div /> }));
vi.mock('../../components/doctor/AppointmentSummaryBar', () => ({ default: () => <div /> }));
vi.mock('../../components/common/EditPatientModal', () => ({ default: () => <div /> }));
vi.mock('../../components/common/ScheduleNextModal', () => ({
  default: () => <div data-testid="schedule-next-modal" />,
}));
vi.mock('../../components/common/SessionWarningModal', () => ({ default: () => <div /> }));
vi.mock('../../components/common/ConfirmDialog', () => ({
  useConfirm: () => [() => Promise.resolve(true), null],
}));
vi.mock('../../hooks/useSessionTimeoutWarning', () => ({
  useSessionTimeoutWarning: () => undefined,
}));
vi.mock('../../hooks/useDermaHotkeys', () => ({ useDermaHotkeys: vi.fn() }));
vi.mock('../../hooks/useVisitLifecycle', () => ({ useVisitLifecycle: vi.fn() }));
vi.mock('../../useDermatologyPatientHistory', () => ({
  useDermatologyPatientHistory: () => ({
    appointments: [],
    skinExaminations: [],
    cosmeticProcedures: [],
    skinExaminationsTotal: 0,
    cosmeticProceduresTotal: 0,
    hasMoreExaminations: false,
    hasMoreProcedures: false,
    loadingMoreExaminations: false,
    loadingMoreProcedures: false,
    loadMoreExaminations: () => undefined,
    loadMoreProcedures: () => undefined,
    loading: false,
    ready: true,
    error: null,
  }),
}));

import { api } from '../../api/client';
import tokenManager from '../../utils/tokenManager';
import { renderWithProviders } from '../../test/renderWithProviders';
import DermatologistPanelUnified from '../DermatologistPanelUnified';

const mockedGet = vi.mocked(api.get);
const mockedToken = vi.mocked(tokenManager.getAccessToken);

const queueLoadCalls = () =>
  mockedGet.mock.calls.filter(([url]) => String(url) === '/registrar/queues/today').length;

const ROWS_A = [{
  id: 501,
  appointment_id: 40,
  patient_id: 1,
  patient_name: 'PATIENT-A-ROW',
  phone: '100',
  status: 'waiting',
  visit_id: 98,
}];

const ROWS_B = [{
  id: 502,
  appointment_id: 41,
  patient_id: 2,
  patient_name: 'PATIENT-B-ROW',
  phone: '200',
  status: 'waiting',
  visit_id: 55,
}];

beforeEach(() => {
  vi.clearAllMocks();
  mockedToken.mockReturnValue('principal-A-token');
  mockedGet.mockReset();
});

describe('DERMACACHE-FE-001 — the module queue cache is principal-scoped', () => {
  // NOTE: the cooldown control runs FIRST so the module cache starts cold;
  // the principal-change test then starts from the warm same-principal
  // cache the control leaves behind, which is exactly the leak window the
  // finding describes.
  it('positive control: the same principal still benefits from the cooldown within the window', async () => {
    mockedGet.mockImplementation(async (url: unknown) => {
      const path = String(url);
      if (path === '/registrar/queues/today') {
        return { data: { queues: [{ specialty: 'derma', entries: ROWS_A }] }, status: 200 } as never;
      }
      if (path.startsWith('/v2/emr/')) {
        return { data: { id: 3, is_draft: false, visit_id: Number(path.split('/').pop()) }, status: 200 } as never;
      }
      throw new Error(`unexpected GET ${path}`);
    });

    const first = renderWithProviders(<DermatologistPanelUnified />, {
      routerProps: { initialEntries: ['/doctor/dermatology?patientId=1&visitId=98'] },
    });
    await waitFor(() => expect(queueLoadCalls()).toBe(1));
    first.unmount();

    // Same principal, immediate remount: the cooldown still applies.
    renderWithProviders(<DermatologistPanelUnified />, {
      routerProps: { initialEntries: ['/doctor/dermatology?patientId=1&visitId=98'] },
    });
    await waitFor(() => {
      expect(screen.getByTestId('emr-editor').getAttribute('data-patient')).toBe('1');
    }, { timeout: 2500 });

    await new Promise((resolve) => { setTimeout(resolve, 80); });
    expect(queueLoadCalls()).toBe(1);
  });

  it('re-requests the queue after the authenticated principal changes (pre-fix: A\'s rows reused for B)', async () => {
    mockedGet.mockImplementation(async (url: unknown) => {
      const path = String(url);
      if (path === '/registrar/queues/today') {
        return { data: { queues: [{ specialty: 'derma', entries: ROWS_B }] }, status: 200 } as never;
      }
      if (path.startsWith('/v2/emr/')) {
        return { data: { id: 3, is_draft: false, visit_id: Number(path.split('/').pop()) }, status: 200 } as never;
      }
      if (path.startsWith('/appointments/')) {
        return { data: { visit_id: 55, emr: { id: 2, is_draft: false }, prescription: null, can_create_prescription: true }, status: 200 } as never;
      }
      throw new Error(`unexpected GET ${path}`);
    });

    // The cooldown control above left principal A's rows cached. Staff A
    // logs out and staff B logs in without a document reload.
    mockedToken.mockReturnValue('principal-B-token');

    // Principal B mounts the panel well within the 5-second cooldown.
    renderWithProviders(<DermatologistPanelUnified />, {
      routerProps: { initialEntries: ['/doctor/dermatology?patientId=2&visitId=55'] },
    });

    // B must get B's OWN authorized snapshot: a fresh request whose rows
    // are matched and applied — never principal A's cached rows.
    await waitFor(() => {
      expect(queueLoadCalls()).toBe(1);
    }, { timeout: 2500 });
    await waitFor(() => {
      expect(screen.getByTestId('emr-editor').getAttribute('data-patient')).toBe('2');
      expect(screen.getByTestId('emr-editor').getAttribute('data-visit')).toBe('55');
    }, { timeout: 2500 });
    expect(screen.queryByText('PATIENT-A-ROW')).toBeNull();
  });
});
