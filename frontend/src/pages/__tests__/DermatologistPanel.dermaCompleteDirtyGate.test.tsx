/**
 * DERMACOMPLETE-FE-001 (audit 3892) — queue completion must honour the
 * child EMR dirty/save boundary registered in the shared app-level
 * dirty-source registry (`emr-visit-<visitId>` via `useEMRLeaveGuard`).
 *
 * Scenario (source-confirmed residual on main @ 1532acda4): the unified
 * `handleSaveVisit` flow validates completion eligibility, the queue entry
 * identity and the completion ack, but never consults the shared registry
 * the rest of the panel honours (the Escape `clearSelection` handler scopes
 * `guardTransition` to `emr-visit-<id>`). Completing a visit while the child
 * autosave debounce has not fired clears the selection and unmounts the
 * editor — `useEMRAutosave` cleanup cancels the pending timers and the
 * clinician's edits within the debounce window are lost silently.
 *
 * Required behaviour (fail closed, the child still owns saves):
 * - a clean editor completes immediately (canonical path unchanged);
 * - unsaved EMR edits route the completion through the canonical
 *   Save/Discard guard dialog: Save flushes the draft through the
 *   registry's `save()` (awaited, rejected outcomes keep the visit open),
 *   Discard drops the draft explicitly, Cancel keeps the visit open;
 * - the completion POST never bypasses a registered dirty source.
 *
 * The child is stubbed with a controllable dirty flag registered through
 * the REAL `useEMRLeaveGuard` (same sourceId convention as the real
 * editor) inside the REAL `LabDirtyGuardProvider`; the parent-side
 * completion gate is the behavior under test.
 */
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useCallback, useEffect, useRef, useState } from 'react';
import { renderWithProviders } from '../../test/renderWithProviders';

const holder = vi.hoisted(() => ({
  events: [] as string[],
  saveForVisit: vi.fn(async (_visitId?: unknown, _options?: Record<string, unknown>) => ({
    status: 'in_progress',
    row_version: 3,
  })),
  discardForVisit: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));
vi.mock('../../api/runtime', () => ({
  getApiBaseUrl: () => 'http://synthetic.test/api/v1',
  getApiOrigin: () => 'http://synthetic.test',
}));
vi.mock('../../utils/tokenManager', () => ({
  default: { getAccessToken: vi.fn(() => 'derma-complete-dirty-principal') },
}));
vi.mock('../../utils/canonicalVisit', () => ({
  resolveCanonicalVisitId: async (row: { visit_id?: unknown }) =>
    (row?.visit_id ?? null) as string | number | null,
}));
vi.mock('../../utils/logger', () => ({
  default: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}));
vi.mock('../../services/notify', () => ({
  default: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
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
    const [dirty, setDirty] = useState(false);
    const saveEMR = useCallback(
      (options?: Record<string, unknown>) => holder.saveForVisit(visitId, options),
      [visitId],
    );
    const reloadFromServer = useCallback(async () => undefined, []);
    const { suppressOnDiscard } = useEMRAutosave({
      isDirty: dirty,
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
      isDirty: dirty,
      isSaving: false,
      saveEMR,
      reloadFromServer,
      onDiscard: () => {
        suppressOnDiscard();
        holder.events.push(`discard:${String(visitId)}`);
        holder.discardForVisit(visitId);
      },
    });
    // Refresh the queue's can_complete contract after persistence.
    useEffect(() => {
      onPersistedRef.current?.();
    }, []);
    return (
      <div data-testid="emr-editor" data-visit={String(visitId ?? '')}>
        <button type="button" data-testid="stub-emr-dirty-on" onClick={() => setDirty(true)}>
          dirty-on
        </button>
        <button type="button" data-testid="stub-emr-dirty-off" onClick={() => setDirty(false)}>
          dirty-off
        </button>
        <span data-testid="stub-emr-dirty-state">{dirty ? 'dirty' : 'clean'}</span>
      </div>
    );
  },
}));
vi.mock('../../components/PrescriptionSystem', () => ({
  default: () => <div data-testid="rx-prescription" />,
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
    loading: false,
    ready: true,
    error: null,
  }),
}));

import { api } from '../../api/client';
import { useEMRAutosave } from '../../hooks/useEMRAutosave';
import { useEMRLeaveGuard } from '../../hooks/useEMRLeaveGuard';
import { LabDirtyGuardProvider } from '../../components/laboratory/LabDirtyGuardContext';
import { queueService } from '../../services/queue';
import DermatologistPanelUnified from '../DermatologistPanelUnified';

const mockedGet = vi.mocked(api.get);

const START_VISIT_ACK = {
  success: true,
  entry_id: 501,
  patient_id: 1,
  visit_id: 98,
  status: 'in_progress',
};

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

async function openCompletableVisit() {
  mockedGet.mockReset();
  holder.saveForVisit.mockClear();
  holder.discardForVisit.mockClear();
  holder.events.length = 0;
  mockedGet.mockImplementation(async (url: unknown) => {
    const path = String(url);
    if (path === '/registrar/queues/today') {
      return { data: { queues: [{ specialty: 'derma', entries: [ROW_A] }] }, status: 200 } as never;
    }
    if (path === '/appointments/40/status') {
      return { data: { visit_id: 98, emr: { id: 1, is_draft: false }, prescription: null, can_create_prescription: true, can_complete: true }, status: 200 } as never;
    }
    if (path.startsWith('/v2/emr/')) {
      const visitId = Number(path.split('/').pop());
      return { data: { id: 3, is_draft: false, visit_id: visitId, patient_id: visitId === 98 ? 1 : 2 }, status: 200 } as never;
    }
    if (path.startsWith('/doctor/dermatology/queue/today')) {
      return { data: { entries: [ROW_A] }, status: 200 } as never;
    }
    throw new Error(`unexpected GET ${path}`);
  });
  vi.mocked(queueService.startVisit).mockReset();
  vi.mocked(queueService.completeVisit).mockReset();
  vi.mocked(queueService.callNextWaiting).mockReset();
  vi.mocked(queueService.startVisit).mockResolvedValue(START_VISIT_ACK as never);
  vi.mocked(queueService.completeVisit).mockResolvedValue({ success: true } as never);
  vi.mocked(queueService.callNextWaiting).mockResolvedValue({ success: false } as never);
  renderWithProviders(
    <LabDirtyGuardProvider>
      <DermatologistPanelUnified />
    </LabDirtyGuardProvider>,
    { routerProps: { initialEntries: ['/doctor/dermatology'] } },
  );

  // The clinician starts visit A from the live queue: the backend ack
  // resolves the canonical patient/visit (fail-closed contract).
  fireEvent.click(await screen.findByTestId('livequeue-start-501', {}, { timeout: 2500 }));
  const editor = await screen.findByTestId('emr-editor', {}, { timeout: 2500 });
  expect(editor.getAttribute('data-visit')).toBe('98');

  const completeButton = await waitFor(() => {
    const button = screen.getByRole('button', { name: /Qabulni yaklash|Завершить прием/i });
    expect((button as HTMLButtonElement).disabled).toBe(false);
    return button as HTMLButtonElement;
  }, { timeout: 2500 });
  return completeButton;
}

describe('DERMACOMPLETE-FE-001 — queue completion honours the shared EMR dirty registry', () => {
  it('completes immediately when the editor reports no unsaved changes', async () => {
    const completeButton = await openCompletableVisit();

    fireEvent.click(completeButton);

    await waitFor(() => {
      expect(queueService.completeVisit).toHaveBeenCalledTimes(1);
    });
    expect(queueService.completeVisit).toHaveBeenCalledWith(501, {});
    // The canonical success flow runs: no dirty-guard dialog interfered.
    expect(screen.queryByText('Несохранённые изменения')).toBeNull();
  });

  it('routes a dirty editor through the guard dialog; Save flushes the draft then completes', async () => {
    const completeButton = await openCompletableVisit();

    // The clinician edits a field — the editor registers `emr-visit-98` dirty.
    fireEvent.click(screen.getByTestId('stub-emr-dirty-on'));
    await waitFor(() => expect(screen.getByTestId('stub-emr-dirty-state').textContent).toBe('dirty'));
    fireEvent.click(completeButton);

    // The completion POST must not bypass the dirty source.
    await waitFor(() => {
      expect(screen.getByText('Несохранённые изменения')).toBeTruthy();
    });
    expect(queueService.completeVisit).not.toHaveBeenCalled();

    // Canonical Save-and-continue flushes the draft through the registry save.
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить и перейти' }));

    await waitFor(() => {
      expect(queueService.completeVisit).toHaveBeenCalledTimes(1);
    });
    expect(holder.saveForVisit).toHaveBeenCalledWith(98, { isDraft: true });
    expect(queueService.completeVisit).toHaveBeenCalledWith(501, {});
  });

  it('routes a dirty editor through the guard dialog; Discard completes without saving', async () => {
    const completeButton = await openCompletableVisit();

    fireEvent.click(screen.getByTestId('stub-emr-dirty-on'));
    await waitFor(() => expect(screen.getByTestId('stub-emr-dirty-state').textContent).toBe('dirty'));
    fireEvent.click(completeButton);

    await waitFor(() => {
      expect(screen.getByText('Несохранённые изменения')).toBeTruthy();
    });
    expect(queueService.completeVisit).not.toHaveBeenCalled();

    // Explicit Discard drops the draft and then completes the visit.
    fireEvent.click(screen.getByRole('button', { name: 'Выйти без сохранения' }));

    await waitFor(() => {
      expect(queueService.completeVisit).toHaveBeenCalledTimes(1);
    });
    expect(holder.discardForVisit).toHaveBeenCalledWith(98);
    expect(holder.saveForVisit).not.toHaveBeenCalled();
  });

  it('keeps the visit open when the clinician cancels the guard dialog', async () => {
    const completeButton = await openCompletableVisit();

    fireEvent.click(screen.getByTestId('stub-emr-dirty-on'));
    await waitFor(() => expect(screen.getByTestId('stub-emr-dirty-state').textContent).toBe('dirty'));
    fireEvent.click(completeButton);

    await waitFor(() => {
      expect(screen.getByText('Несохранённые изменения')).toBeTruthy();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Отмена' }));

    await act(async () => {
      await Promise.resolve();
    });
    expect(queueService.completeVisit).not.toHaveBeenCalled();
    // The editor (and its unsaved draft) stays mounted.
    expect(screen.getByTestId('emr-editor')).toBeTruthy();
  });
});
