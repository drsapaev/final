/**
 * DERMAURL-FE-002 (audit 3892, eighth group «dermatology deep links») —
 * exact deferred-runtime regression that group103 required to credit the
 * merged #3906 fix.
 *
 * Scenario: a deep-link resolution that awaits a queue refresh while the
 * URL/selection moves on must be discarded — a stale continuation must not
 * override the newer context.
 *
 * - Stale case: deep link A (?patientId=23&visitId=98) starts with only
 *   patient B in the queue, so the resolution awaits a deferred
 *   `loadDermatologyAppointments()` refresh. While it is in flight the
 *   clinician navigates to B's own pair (?patientId=40&visitId=55) and B
 *   is applied from the current queue state. The refresh is released LAST
 *   with A's row present — the stale A continuation must drop entirely:
 *   B stays active, A is never selected (no A status GET), no A-loaded
 *   toast fires.
 * - Positive control: the SAME deferred refresh released while the URL
 *   still points at A must apply A (editor opens at patient 23 / visit 98)
 *   — proving the guard drops only stale continuations, not the
 *   same-URL resolution.
 *
 * Source guard under test (main @ e3addd044):
 * src/pages/DermatologistPanelUnified.tsx — `urlResolutionGenerationRef`
 * generation token; the awaited-refresh continuation bails when
 * `urlResolutionGenerationRef.current !== generation ||
 * location.search !== searchKey`. Group103 verdict for this ID was
 * SOURCE_GUARD_PRESENT / EXACT_DEFERRED_REGRESSION_MISSING — this file
 * supplies the missing exact proof (the existing deepLink test covers only
 * a manual selection after an APPLIED deep link).
 */
import { act, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useNavigate } from 'react-router-dom';
import { renderWithProviders } from '../../test/renderWithProviders';

const holder = vi.hoisted(() => ({
  navigate: null as ((to: string) => void) | null,
}));

function NavigateProbe() {
  const navigate = useNavigate();
  holder.navigate = navigate as unknown as (to: string) => void;
  return null;
}

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
vi.mock('../../components/PrescriptionSystem', () => ({
  default: () => <div data-testid="rx-stub" />,
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
import notify from '../../services/notify';
import DermatologistPanelUnified from '../DermatologistPanelUnified';

const mockedGet = vi.mocked(api.get);

function queueResponse(rows: Array<Record<string, unknown>>) {
  return {
    data: { queues: [{ specialty: 'derma', entries: rows }] },
    status: 200,
  } as never;
}

const ROW_PATIENT_23 = {
  id: 501,
  appointment_id: 40,
  patient_id: 23,
  patient_name: 'SYNTHETIC PATIENT A',
  phone: '100',
  status: 'waiting',
  visit_id: 98,
};

const ROW_PATIENT_40 = {
  id: 502,
  appointment_id: 41,
  patient_id: 40,
  patient_name: 'SYNTHETIC PATIENT B',
  phone: '200',
  status: 'waiting',
  visit_id: 55,
};

let principalCounter = 0;

interface MountOptions {
  rows: Array<Record<string, unknown>>;
}

function mountPanel(initialEntry: string, options: MountOptions) {
  principalCounter += 1;
  vi.mocked(tokenManager.getAccessToken).mockReturnValue(`deferred-url-principal-${principalCounter}`);
  mockedGet.mockReset();
  vi.mocked(notify.info).mockReset();
  vi.mocked(notify.error).mockReset();
  let queueCallCount = 0;
  let releaseRefresh: (() => void) | null = null;
  mockedGet.mockImplementation(async (url: unknown) => {
    const path = String(url);
    if (path === '/registrar/queues/today') {
      queueCallCount += 1;
      if (queueCallCount === 1) {
        // The FIRST queue load is held in flight. The panel's mount load and
        // the deep-link resolution's awaited refresh share this in-flight
        // promise (appointmentsLoadPromiseRef dedup), so holding it holds
        // the resolution's continuation too.
        return await new Promise<{ data: unknown; status: number }>((resolve) => {
          releaseRefresh = () => resolve({ data: { queues: [{ specialty: 'derma', entries: options.rows }] }, status: 200 } as never);
        }) as never;
      }
      return queueResponse(options.rows);
    }
    if (path === '/appointments/40/status') {
      return { data: { visit_id: 98, emr: { id: 1, is_draft: false }, prescription: null, can_create_prescription: true, can_complete: true }, status: 200 } as never;
    }
    if (path === '/appointments/41/status') {
      return { data: { visit_id: 55, emr: { id: 2, is_draft: false }, prescription: { id: 9001, is_draft: false }, can_create_prescription: true, can_complete: true }, status: 200 } as never;
    }
    if (path.startsWith('/v2/emr/')) {
      return { data: { id: 3, is_draft: false, visit_id: Number(path.split('/').pop()) }, status: 200 } as never;
    }
    throw new Error(`unexpected GET ${path}`);
  });
  return {
    rendered: renderWithProviders(
      <>
        <DermatologistPanelUnified />
        <NavigateProbe />
      </>,
      {
        routerProps: { initialEntries: [initialEntry] },
      },
    ),
    waitForQueueCalls: async (count: number) => {
      await waitFor(() => expect(queueCallCount).toBeGreaterThanOrEqual(count), { timeout: 2500 });
    },
    releaseRefresh: () => {
      if (!releaseRefresh) throw new Error('deferred refresh was never started');
      releaseRefresh();
    },
  };
}

describe('DERMAURL-FE-002 — a stale deep-link continuation loses to a newer URL/selection', () => {
  it('drops the old A refresh released after the clinician navigated to B (group103-required exact case)', async () => {
    const panel = mountPanel('/doctor/dermatology?patientId=23&visitId=98', {
      rows: [ROW_PATIENT_23, ROW_PATIENT_40],
    });

    // The first queue load is held in flight; the deep-link A resolution
    // awaits the same in-flight promise, so its continuation is suspended.
    await panel.waitForQueueCalls(1);
    expect(screen.queryByTestId('emr-editor')).toBeNull();

    // The clinician navigates to B's own pair while the refresh is still
    // pending — the newer resolution owns the continuation now.
    await act(async () => {
      holder.navigate?.('/doctor/dermatology?patientId=40&visitId=55');
    });
    expect(screen.queryByTestId('emr-editor')).toBeNull();

    // Release the refresh LAST — with A's row present in the response. The
    // stale A continuation must be discarded entirely; B's newer one owns
    // the resolution and applies B.
    panel.releaseRefresh();
    const editorB = await screen.findByTestId('emr-editor', {}, { timeout: 2500 });
    expect(editorB.getAttribute('data-patient')).toBe('40');
    expect(editorB.getAttribute('data-visit')).toBe('55');
    await new Promise((resolve) => { setTimeout(resolve, 200); });

    // B remains active — A's row was never applied.
    expect(screen.getByTestId('emr-editor').getAttribute('data-patient')).toBe('40');
    expect(screen.getByTestId('emr-editor').getAttribute('data-visit')).toBe('55');
    // A was never selected: no A status fetch, no A-loaded toast.
    const statusGetsForA = mockedGet.mock.calls.filter(([url]) => String(url) === '/appointments/40/status');
    expect(statusGetsForA).toHaveLength(0);
    const aToasts = vi.mocked(notify.info).mock.calls.filter(
      ([message]) => typeof message === 'string' && message.includes('SYNTHETIC PATIENT A'),
    );
    expect(aToasts).toHaveLength(0);
  });

  it('positive control: the same held refresh released while the URL still points at A applies A', async () => {
    const panel = mountPanel('/doctor/dermatology?patientId=23&visitId=98', {
      rows: [ROW_PATIENT_23, ROW_PATIENT_40],
    });

    await panel.waitForQueueCalls(1);
    expect(screen.queryByTestId('emr-editor')).toBeNull();

    panel.releaseRefresh();

    const editorA = await screen.findByTestId('emr-editor', {}, { timeout: 2500 });
    expect(editorA.getAttribute('data-patient')).toBe('23');
    expect(editorA.getAttribute('data-visit')).toBe('98');
  });
});
