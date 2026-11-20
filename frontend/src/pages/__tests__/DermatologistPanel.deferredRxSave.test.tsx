/**
 * DERMARX-FE-004 (audit 3892, eighth group «dermatology prescription
 * state») — exact deferred-runtime regression that group103 required to
 * credit the merged #3906 fix.
 *
 * Scenario: the panel's `savePrescription` captures the visit context that
 * owns the save; after the POST resolves it must re-verify the context.
 * Visit A's prescription POST is held in flight while the clinician moves
 * to visit B (whose canonical prescription is resolved from the status
 * endpoint); A's POST is released LAST — it must be dropped entirely:
 *
 * - B's editor context is unchanged (visit 55 / patient 40);
 * - B's prescription state stays B's canonical record (id 9001) — no
 *   cross-visit write;
 * - no success toast fires for A's dropped save.
 *
 * Positive control: a fresh save on the active visit B resolves while B is
 * still current and must render B's saved prescription (id 9041) and fire
 * exactly one success toast.
 *
 * Source guard under test (main @ e3addd044):
 * src/pages/DermatologistPanelUnified.tsx — `savePrescription` captures
 * `saveContext = currentVisitContext` before the POST and bails when
 * `!isSameDermatologyVisit(saveContext, currentVisitContextRef.current)`
 * after it resolves. Group103 verdict for this ID was
 * SOURCE_GUARD_PRESENT / RUNTIME_REGRESSION_MISSING — this file supplies
 * the missing runtime proof.
 */
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useLocation, useNavigate } from 'react-router-dom';
import { renderWithProviders } from '../../test/renderWithProviders';

const holder = vi.hoisted(() => ({
  navigate: null as ((to: string) => void) | null,
}));

function NavigateProbe() {
  const navigate = useNavigate();
  const location = useLocation();
  holder.navigate = navigate as unknown as (to: string) => void;
  return <div data-testid="loc-probe">{location.search}</div>;
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
  default: (props: {
    prescription?: Record<string, unknown> | null;
    onSave?: (data: unknown) => void | Promise<void>;
  }) => (
    <div>
      <div data-testid="rx-prescription">
        {props.prescription ? String((props.prescription as { id?: unknown }).id ?? 'unknown') : 'none'}
      </div>
      <button
        type="button"
        data-testid="rx-save"
        onClick={() => {
          void props.onSave?.({
            medications: [{
              name: 'SYNTHETIC MED',
              dosage: '1 mg',
              frequency: '1x/day',
              duration: '5 days',
              instructions: null,
              quantity: 1,
            }],
            instructions: null,
            doctor_notes: null,
          });
        }}
      >
        save
      </button>
    </div>
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
import notify from '../../services/notify';
import DermatologistPanelUnified from '../DermatologistPanelUnified';

const mockedGet = vi.mocked(api.get);
const mockedPost = vi.mocked(api.post);
const mockedNotifySuccess = vi.mocked(notify.success);

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

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => { resolve = res; });
  return { promise, resolve };
}

let principalCounter = 0;

function mountPanel(initialEntry: string) {
  principalCounter += 1;
  vi.mocked(tokenManager.getAccessToken).mockReturnValue(`deferred-rx-principal-${principalCounter}`);
  mockedGet.mockReset();
  mockedNotifySuccess.mockReset();
  vi.mocked(notify.info).mockReset();
  vi.mocked(notify.error).mockReset();
  mockedGet.mockImplementation(async (url: unknown) => {
    const path = String(url);
    if (path === '/registrar/queues/today') return queueResponse([ROW_PATIENT_23, ROW_PATIENT_40]);
    if (path === '/appointments/40/status') {
      return { data: { visit_id: 98, emr: { id: 1, is_draft: false }, prescription: null, can_create_prescription: true, can_complete: true }, status: 200 } as never;
    }
    if (path === '/appointments/41/status') {
      // Visit B's canonical prescription — a record that belongs to B only.
      return { data: { visit_id: 55, emr: { id: 2, is_draft: false }, prescription: { id: 9001, is_draft: false }, can_create_prescription: true, can_complete: true }, status: 200 } as never;
    }
    if (path.startsWith('/v2/emr/')) {
      return { data: { id: 3, is_draft: false, visit_id: Number(path.split('/').pop()) }, status: 200 } as never;
    }
    throw new Error(`unexpected GET ${path}`);
  });
  mockedPost.mockReset();
  return renderWithProviders(
    <>
      <DermatologistPanelUnified />
      <NavigateProbe />
    </>,
    {
      routerProps: { initialEntries: [initialEntry] },
    },
  );
}

describe('DERMARX-FE-004 — a late prescription POST is dropped after the visit changed', () => {
  it('does not write visit A\'s saved prescription into visit B and does not toast it (group103-required exact case)', async () => {
    mountPanel('/doctor/dermatology?patientId=23&visitId=98');

    // Visit A is opened via the deep link; its EMR editor is active.
    const editorA = await screen.findByTestId('emr-editor');
    expect(editorA.getAttribute('data-visit')).toBe('98');
    await waitFor(() => expect(screen.getByTestId('rx-prescription').textContent).toBe('none'));

    // Defer visit A's prescription POST (appointment 40) in flight.
    const deferredA = createDeferred<{ data: unknown; status: number }>();
    mockedPost.mockImplementation(async (url: unknown) => {
      const path = String(url);
      if (path === '/appointments/40/prescription') return deferredA.promise as never;
      if (path === '/appointments/41/prescription') {
        return { data: { id: 9041, is_draft: false }, status: 200 } as never;
      }
      throw new Error(`unexpected POST ${path}`);
    });

    fireEvent.click(screen.getByTestId('rx-save'));
    await waitFor(() => expect(mockedPost).toHaveBeenCalledWith('/appointments/40/prescription', expect.anything()));

    // The clinician moves to visit B while A's POST is still in flight;
    // B's canonical prescription (9001) resolves from the status endpoint.
    await act(async () => {
      holder.navigate?.('/doctor/dermatology?patientId=40&visitId=55');
    });
    const editorB = await screen.findByTestId('emr-editor');
    await waitFor(() => {
      expect(editorB.getAttribute('data-visit')).toBe('55');
      expect(editorB.getAttribute('data-patient')).toBe('40');
      expect(screen.getByTestId('rx-prescription').textContent).toBe('9001');
    }, { timeout: 2500 });

    // Release A's POST LAST — its continuation must observe the changed
    // visit context and drop the response entirely.
    deferredA.resolve({ data: { id: 9040, is_draft: false }, status: 200 });
    await new Promise((resolve) => { setTimeout(resolve, 200); });

    expect(screen.getByTestId('emr-editor').getAttribute('data-visit')).toBe('55');
    expect(screen.getByTestId('emr-editor').getAttribute('data-patient')).toBe('40');
    // No cross-visit write: B's prescription state is still B's canonical.
    expect(screen.getByTestId('rx-prescription').textContent).toBe('9001');
    // No success toast for the dropped A save.
    expect(mockedNotifySuccess).not.toHaveBeenCalled();
  });

  it('positive control: a fresh save on the active visit B renders its saved prescription and toasts success', async () => {
    mountPanel('/doctor/dermatology?patientId=40&visitId=55');

    const editor = await screen.findByTestId('emr-editor');
    expect(editor.getAttribute('data-visit')).toBe('55');
    await waitFor(() => expect(screen.getByTestId('rx-prescription').textContent).toBe('9001'));

    mockedPost.mockImplementation(async (url: unknown) => {
      const path = String(url);
      if (path === '/appointments/41/prescription') {
        return { data: { id: 9041, is_draft: false }, status: 200 } as never;
      }
      throw new Error(`unexpected POST ${path}`);
    });

    fireEvent.click(screen.getByTestId('rx-save'));

    await waitFor(() => {
      expect(screen.getByTestId('rx-prescription').textContent).toBe('9041');
    }, { timeout: 2500 });
    expect(mockedNotifySuccess).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('emr-editor').getAttribute('data-visit')).toBe('55');
  });
});
