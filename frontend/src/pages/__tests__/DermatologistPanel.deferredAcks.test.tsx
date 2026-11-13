/**
 * Audit 3892 wave-2 self-review — fail-first regressions for the two
 * deferred-acknowledgement UI paths of the dermatologist panel:
 *
 * **[P2] A deferred visit-completion acknowledgement must not fire the
 * unqualified success toast over a NEWER visit context.** The completion
 * POST for visit A may resolve after the clinician switched to visit B;
 * the success toast, the state reset, the schedule-next modal and the
 * auto next-call all belong to the CAPTURED visit only — on the pre-fix
 * source `notify.success(derma.visit_completed)` fires before the
 * `isSameDermatologyVisit` guard.
 *
 * **[P2] A delayed Escape discard confirmation must not clear a newly
 * selected visit.** The confirmation dialog is opened for a dirty visit
 * A; while it is pending, a deep link selects visit B. Accepting the OLD
 * confirmation must not reset B — on the pre-fix source
 * `setSelectedPatient(null)` runs unconditionally in the `.then`.
 */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { useCallback, useEffect, useRef } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useNavigate } from 'react-router-dom';
import type { ReactElement } from 'react';
import {
  LabDirtyGuardProvider,
  useLabDirtyGuard,
} from '../../components/laboratory/LabDirtyGuardContext';

const holder = vi.hoisted(() => ({
  navigate: null as ((to: string) => void) | null,
  confirmResolve: null as ((ok: boolean) => void) | null,
  emrDirty: false,
  saveForVisit: vi.fn(async (_visitId?: unknown, _options?: Record<string, unknown>) => ({ status: 'in_progress', row_version: 3 })),
  discardForVisit: vi.fn(),
  events: [] as string[],
}));

function DirtyGuardProbe() {
  const guard = useLabDirtyGuard();
  return (
    <output data-testid="dirty-guard-probe">
      {`${guard.hasDirtySources()}|${guard.hasPendingOperations}`}
    </output>
  );
}

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
  default: { getAccessToken: vi.fn(() => 'principal-token') },
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
  EMRContainerV2: (props: {
    visitId?: unknown;
    patientId?: unknown;
    onPersisted?: () => void;
  }) => {
    const visitId = props.visitId;
    const onPersistedRef = useRef(props.onPersisted);
    onPersistedRef.current = props.onPersisted;
    const saveEMR = useCallback(
      (options?: Record<string, unknown>) => holder.saveForVisit(visitId, options),
      [visitId],
    );
    const reloadFromServer = useCallback(async () => undefined, []);
    const { suppressOnDiscard } = useEMRAutosave({
      isDirty: true,
      isSaving: false,
      isSigned: false,
      status: 'in_progress',
      saveEMR,
      debounceMs: 60_000,
      maxWaitMs: 120_000,
      enabled: true,
    });
    useEMRLeaveGuard({
      visitId: visitId as string | number,
      isDirty: true,
      isSaving: false,
      saveEMR,
      reloadFromServer,
      onDiscard: () => {
        suppressOnDiscard();
        holder.events.push(`discard:${String(visitId)}`);
        holder.discardForVisit(visitId);
      },
    });
    // Keep a dirty draft registered for Escape, and refresh the queue's
    // can_complete contract after persistence.
    useEffect(() => {
      holder.emrDirty = true;
      onPersistedRef.current?.();
    }, []);
    return (
      <div
        data-testid="emr-editor"
        data-visit={String(props.visitId ?? '')}
        data-patient={String(props.patientId ?? '')}
      />
    );
  },
}));
vi.mock('../../components/dermatology/DermaVisitGallery', () => ({
  default: () => <div data-testid="derma-gallery" />,
}));
vi.mock('../../components/QueueIntegration', () => ({
  default: (props: {
    onStartVisit?: (patient: { id?: unknown; name?: unknown; number?: unknown }) => void | boolean | Promise<void | boolean>;
  }) => (
    <div data-testid="queue-integration">
      <button
        data-testid="livequeue-start-501"
        type="button"
        onClick={() => props.onStartVisit?.({ id: 501, name: 'SYNTHETIC PATIENT A', number: 1 })}
      >
        start 501
      </button>
    </div>
  ),
}));
vi.mock('../../components/tables/EnhancedAppointmentsTable', () => ({
  default: () => <div data-testid="appointments-table" />,
}));
vi.mock('../../components/dermatology/DermaPatientsTab', () => ({
  default: (props: {
    onSelectPatient?: (patient: Record<string, unknown>) => void;
  }) => (
    <div data-testid="patients-tab">
      <button
        data-testid="patients-select-b"
        type="button"
        onClick={() =>
          props.onSelectPatient?.({
            id: 2,
            patient_id: 2,
            visit_id: 55,
            appointment_id: 41,
            patient_name: 'SYNTHETIC PATIENT B',
            patient_fio: 'SYNTHETIC PATIENT B',
            source: 'patients',
          })
        }
      >
        select B
      </button>
    </div>
  ),
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
  useConfirm: () => [() => new Promise<boolean>((resolve) => { holder.confirmResolve = resolve; }), null],
}));
vi.mock('../../hooks/useSessionTimeoutWarning', () => ({
  useSessionTimeoutWarning: () => undefined,
}));
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
import { useEMRAutosave } from '../../hooks/useEMRAutosave';
import { useEMRLeaveGuard } from '../../hooks/useEMRLeaveGuard';
import { queueService } from '../../services/queue';
import notifyService from '../../services/notify';
import { renderWithProviders } from '../../test/renderWithProviders';
import DermatologistPanelUnified from '../DermatologistPanelUnified';

const mockedGet = vi.mocked(api.get);
const mockedCompleteVisit = vi.mocked(queueService.completeVisit);
const mockedCallNext = vi.mocked(queueService.callNextWaiting);

const ROW_A = {
  id: 501,
  appointment_id: 40,
  patient_id: 1,
  patient_name: 'SYNTHETIC PATIENT A',
  patient_fio: 'SYNTHETIC PATIENT A',
  phone: '100',
  status: 'waiting',
  visit_id: 98,
  can_complete: true,
  doctor_queue_entry_id: 501,
  queue_entry_id: 501,
};

const ROW_B = {
  id: 502,
  appointment_id: 41,
  patient_id: 2,
  patient_name: 'SYNTHETIC PATIENT B',
  patient_fio: 'SYNTHETIC PATIENT B',
  phone: '200',
  status: 'waiting',
  visit_id: 55,
};

let releaseCompletion: ((value: { success?: boolean }) => void) | null = null;

// The start-visit ack resolves the canonical patient/visit through the
// backend (fail-closed contract), so the panel opens the visit with the
// queue identity the completion contract requires.
const START_VISIT_ACK_A = {
  success: true,
  entry_id: 501,
  patient_id: 1,
  visit_id: 98,
  status: 'in_progress',
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedGet.mockReset();
  holder.navigate = null;
  holder.confirmResolve = null;
  holder.emrDirty = false;
  holder.events = [];
  releaseCompletion = null;
  vi.mocked(queueService.startVisit).mockReset();
  vi.mocked(queueService.startVisit).mockResolvedValue(START_VISIT_ACK_A as never);
  holder.saveForVisit.mockImplementation(async (visitId?: unknown) => {
    holder.events.push(`save:${String(visitId)}`);
    return { status: 'in_progress', row_version: 3 };
  });
  mockedGet.mockImplementation(async (url: unknown) => {
    const path = String(url);
    if (path === '/registrar/queues/today') {
      return { data: { queues: [{ specialty: 'derma', entries: [ROW_A, ROW_B] }] }, status: 200 } as never;
    }
    if (path === '/appointments/40/status') {
      return {
        data: { visit_id: 98, emr: { id: 1, is_draft: false }, prescription: null, can_create_prescription: true, can_complete: true },
        status: 200,
      } as never;
    }
    if (path === '/appointments/41/status') {
      return {
        data: { visit_id: 55, emr: { id: 2, is_draft: false }, prescription: null, can_create_prescription: true, can_complete: true },
        status: 200,
      } as never;
    }
    if (path.startsWith('/v2/emr/')) {
      const visitId = Number(path.split('/').pop());
      return { data: { id: 3, is_draft: false, visit_id: visitId, patient_id: visitId === 98 ? 1 : 2 }, status: 200 } as never;
    }
    if (path.startsWith('/doctor/dermatology/queue/today')) {
      return { data: { entries: [ROW_A, ROW_B] }, status: 200 } as never;
    }
    throw new Error(`unexpected GET ${path}`);
  });
});

function renderWithDirtyGuard(ui: ReactElement, options: Parameters<typeof renderWithProviders>[1]) {
  return renderWithProviders(
    <LabDirtyGuardProvider>{ui}</LabDirtyGuardProvider>,
    options,
  );
}

describe('derma deferred completion acknowledgement (DERMACOMPLETE-FE-002 follow-up)', () => {
  it('suppresses the success toast and all consequences for a stale completion (pre-fix: toast fires before the guard)', async () => {
    mockedCompleteVisit.mockImplementation(() => new Promise((resolve) => {
      releaseCompletion = (value) => resolve(value as never);
    }));
    mockedCallNext.mockResolvedValue({ success: true } as never);

    renderWithDirtyGuard(
      <>
        <DermatologistPanelUnified />
        <NavigateProbe />
      </>,
      { routerProps: { initialEntries: ['/doctor/dermatology'] } },
    );

    // The clinician starts visit A from the live queue: the backend ack
    // resolves the canonical patient/visit (fail-closed contract).
    fireEvent.click(await screen.findByTestId('livequeue-start-501', {}, { timeout: 2500 }));

    // The visit opens (patient 1 / visit 98) with a completable queue row.
    const editor = await screen.findByTestId('emr-editor', {}, { timeout: 2500 });
    expect(editor.getAttribute('data-patient')).toBe('1');
    // The completion POST is issued and hangs.
    const completeButton = await waitFor(() => {
      const button = screen.getByRole('button', { name: /Qabulni yaklash|Завершить прием/i });
      expect((button as HTMLButtonElement).disabled).toBe(false);
      return button as HTMLButtonElement;
    }, { timeout: 2500 });
    fireEvent.click(completeButton);
    // The confirm dialog resolves immediately for the completion path.
    holder.confirmResolve?.(true);
    await waitFor(() => expect(mockedCompleteVisit).toHaveBeenCalled());
    expect(releaseCompletion).not.toBeNull();

    // While the POST is in flight, the clinician switches to visit B.
    holder.navigate?.('/doctor/dermatology?patientId=2&visitId=55');
    await waitFor(() => {
      expect(screen.getByTestId('emr-editor').getAttribute('data-patient')).toBe('2');
    }, { timeout: 2500 });

    // A's confirmed acknowledgement arrives late.
    releaseCompletion?.({ success: true });
    await new Promise((resolve) => { setTimeout(resolve, 120); });

    // No unqualified success toast over B's context; no reset of B; no
    // schedule-next modal; no auto next-call for the stale visit.
    expect(notifyService.success).not.toHaveBeenCalledWith('Прием завершен успешно');
    expect(mockedCallNext).not.toHaveBeenCalled();
    expect(screen.getByTestId('emr-editor').getAttribute('data-patient')).toBe('2');
    expect(screen.getByTestId('emr-editor').getAttribute('data-visit')).toBe('55');
  });

  it('positive control: a fresh acknowledgement toasts, resets and auto-calls the next patient', async () => {
    mockedCompleteVisit.mockResolvedValue({ success: true } as never);
    mockedCallNext.mockResolvedValue({ success: true } as never);

    renderWithDirtyGuard(<DermatologistPanelUnified />, {
      routerProps: { initialEntries: ['/doctor/dermatology'] },
    });

    fireEvent.click(await screen.findByTestId('livequeue-start-501', {}, { timeout: 2500 }));
    await screen.findByTestId('emr-editor', {}, { timeout: 2500 });
    const completeButton = await waitFor(() => {
      const button = screen.getByRole('button', { name: /Qabulni yaklash|Завершить прием/i });
      expect((button as HTMLButtonElement).disabled).toBe(false);
      return button as HTMLButtonElement;
    }, { timeout: 2500 });
    fireEvent.click(completeButton);
    holder.confirmResolve?.(true);

    await waitFor(() => {
      expect(notifyService.success).toHaveBeenCalledWith('Прием завершен успешно');
    }, { timeout: 2500 });
    expect(mockedCallNext).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.queryByTestId('emr-editor')).toBeNull();
    }, { timeout: 2500 });
  });
});

describe('derma deferred Escape discard confirmation (DERMAHOTKEY-FE-001 follow-up)', () => {
  it('does not clear a newly selected visit from a stale discard confirmation (pre-fix: unconditional reset)', async () => {
    renderWithDirtyGuard(
      <>
        <DermatologistPanelUnified />
        <DirtyGuardProbe />
        <NavigateProbe />
      </>,
      { routerProps: { initialEntries: ['/doctor/dermatology'] } },
    );

    fireEvent.click(await screen.findByTestId('livequeue-start-501', {}, { timeout: 2500 }));

    // Visit A opens; the mocked EMR reports a dirty draft.
    const editor = await screen.findByTestId('emr-editor', {}, { timeout: 2500 });
    expect(editor.getAttribute('data-patient')).toBe('1');
    await waitFor(() => expect(screen.getByTestId('dirty-guard-probe')).toHaveTextContent('true|false'));
    // Escape opens the discard confirmation for visit A; it stays pending.
    await waitFor(() => expect(holder.emrDirty).toBe(true));
    fireEvent.keyDown(document.body, { key: 'Escape' });
    const discardDialog = await screen.findByRole('dialog');

    // While the confirmation is pending, the clinician manually selects
    // visit B from the patients tab (no URL identity to re-apply it).
    act(() => holder.navigate?.('/doctor/dermatology?tab=patients'));
    fireEvent.click(await screen.findByTestId('patients-select-b'));
    act(() => holder.navigate?.('/doctor/dermatology?tab=visit'));
    await waitFor(() => {
      expect(screen.getByTestId('emr-editor').getAttribute('data-patient')).toBe('2');
    }, { timeout: 2500 });

    // The clinician accepts the OLD shared-guard decision — it must not clear
    // or discard B's draft after A's source has been replaced.
    fireEvent.click(within(discardDialog).getByRole('button', { name: 'Выйти без сохранения' }));
    await new Promise((resolve) => { setTimeout(resolve, 120); });

    const current = screen.getByTestId('emr-editor');
    expect(current.getAttribute('data-patient')).toBe('2');
    expect(current.getAttribute('data-visit')).toBe('55');
    expect(holder.discardForVisit).not.toHaveBeenCalledWith(55);
  });

  it('Escape discard suppresses unmount autosave before clearing the still-current visit', async () => {
    renderWithDirtyGuard(
      <>
        <DermatologistPanelUnified />
        <DirtyGuardProbe />
      </>,
      {
        routerProps: { initialEntries: ['/doctor/dermatology'] },
      },
    );

    fireEvent.click(await screen.findByTestId('livequeue-start-501', {}, { timeout: 2500 }));
    const editor = await screen.findByTestId('emr-editor', {}, { timeout: 2500 });
    expect(editor.getAttribute('data-patient')).toBe('1');
    await waitFor(() => expect(screen.getByTestId('dirty-guard-probe')).toHaveTextContent('true|false'));
    await waitFor(() => expect(holder.emrDirty).toBe(true));
    // The synthetic dirty editor can flush once while the queue identity
    // settles. Measure only writes caused by the explicit Escape discard.
    holder.saveForVisit.mockClear();
    holder.events = [];
    fireEvent.keyDown(document.body, { key: 'Escape' });
    const discardDialog = await screen.findByRole('dialog');
    expect(screen.getByTestId('emr-editor')).toBeInTheDocument();
    fireEvent.click(within(discardDialog).getByRole('button', { name: 'Выйти без сохранения' }));

    await waitFor(() => {
      expect(screen.queryByTestId('emr-editor')).toBeNull();
    }, { timeout: 2500 });
    expect(holder.discardForVisit).toHaveBeenCalledWith(98);
    expect(holder.events).toEqual(['discard:98']);
    expect(holder.saveForVisit).not.toHaveBeenCalled();
  });
});
