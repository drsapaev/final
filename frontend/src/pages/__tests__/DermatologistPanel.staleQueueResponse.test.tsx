/**
 * Audit 3892 wave-2 self-review — fail-first regression for the derma
 * module queue cache and the in-flight queue response ownership:
 *
 * **[P1] A previous principal's in-flight queue response must not
 * populate the next principal's state/cache.** `loadDermatologyAppointments`
 * captures the principal (owner key) at launch; a continuation that
 * resolves after an auth change (logout/login without a document reload)
 * must ignore the stale success and must not assign the OLD principal's
 * rows into the NEW cache object. The same guard covers `loadServices`
 * and the per-component `appointmentsLoadPromiseRef` (reset on auth
 * change so it is never handed to the next principal before the module
 * cache is consulted).
 *
 * Red-first: on the pre-fix source principal A's deferred response is
 * written into the module cache after principal B's own snapshot was
 * stored — the third mount then serves A's rows to B within the
 * cooldown window and the deep-link resolution for B's patient fails
 * closed (editor never opens).
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
  default: { getAccessToken: vi.fn() },
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

let queueCallCount = 0;
let releasePrincipalAResponse: (() => void) | null = null;

const queueLoadCalls = () =>
  mockedGet.mock.calls.filter(([url]) => String(url) === '/registrar/queues/today').length;

beforeEach(() => {
  vi.clearAllMocks();
  mockedToken.mockReset();
  mockedGet.mockReset();
  queueCallCount = 0;
  releasePrincipalAResponse = null;
});

describe('derma queue cache — an in-flight response is owned by the principal that launched it', () => {
  it('ignores principal A\'s late queue response after principal B took over (pre-fix: A\'s rows cached under B)', async () => {
    mockedGet.mockImplementation(async (url: unknown) => {
      const path = String(url);
      if (path === '/registrar/queues/today') {
        queueCallCount += 1;
        if (queueCallCount === 1) {
          // Principal A's request hangs until the test releases it AFTER
          // principal B's own snapshot has already been stored.
          return new Promise((resolve) => {
            releasePrincipalAResponse = () => {
              resolve({ data: { queues: [{ specialty: 'derma', entries: ROWS_A }] }, status: 200 } as never);
            };
          });
        }
        return { data: { queues: [{ specialty: 'derma', entries: ROWS_B }] }, status: 200 } as never;
      }
      if (path === '/registrar/services') {
        return { data: { services_by_group: {} }, status: 200 } as never;
      }
      if (path.startsWith('/appointments/')) {
        return {
          data: { visit_id: 55, emr: { id: 2, is_draft: false }, prescription: null, can_create_prescription: true, can_complete: true },
          status: 200,
        } as never;
      }
      if (path.startsWith('/v2/emr/')) {
        return { data: { id: 3, is_draft: false, visit_id: Number(path.split('/').pop()) }, status: 200 } as never;
      }
      if (path.startsWith('/doctor/dermatology/queue/today')) {
        return { data: { entries: [] }, status: 200 } as never;
      }
      throw new Error(`unexpected GET ${path}`);
    });

    // Principal A mounts; its queue request stays pending.
    mockedToken.mockReturnValue('principal-A-token');
    const a = renderWithProviders(<DermatologistPanelUnified />, {
      routerProps: { initialEntries: ['/doctor/dermatology?patientId=1&visitId=98'] },
    });
    await waitFor(() => expect(queueLoadCalls()).toBe(1));
    expect(releasePrincipalAResponse).not.toBeNull();
    a.unmount();

    // Staff A logs out, staff B logs in without a document reload: the
    // same module cache object is reused by the next principal.
    mockedToken.mockReturnValue('principal-B-token');
    const b = renderWithProviders(<DermatologistPanelUnified />, {
      routerProps: { initialEntries: ['/doctor/dermatology?patientId=2&visitId=55'] },
    });
    // B's own request resolves immediately and is applied.
    await waitFor(() => {
      expect(screen.getByTestId('emr-editor').getAttribute('data-patient')).toBe('2');
    }, { timeout: 2500 });

    // A's late response lands AFTER B's snapshot was stored.
    releasePrincipalAResponse?.();
    await new Promise((resolve) => { setTimeout(resolve, 120); });
    b.unmount();

    // Principal B remounts within the cooldown window: the cache must
    // still be B's snapshot. On the pre-fix source A's continuation
    // overwrote the cache object and B's resolution fails closed.
    renderWithProviders(<DermatologistPanelUnified />, {
      routerProps: { initialEntries: ['/doctor/dermatology?patientId=2&visitId=55'] },
    });
    const editor = await screen.findByTestId('emr-editor', {}, { timeout: 2500 });
    expect(editor.getAttribute('data-patient')).toBe('2');
    expect(editor.getAttribute('data-visit')).toBe('55');
    // The cooldown served B's snapshot: no third network call was needed.
    expect(queueLoadCalls()).toBe(2);
  });
});
