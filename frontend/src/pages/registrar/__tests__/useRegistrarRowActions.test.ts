/**
 * PR-UI-13-5 unit contract: useRegistrarRowActions — the row-action routing
 * extracted from RegistrarPanel (table onActionClick router + context-menu
 * router). Test-only follow-up: the hook shipped in #2903 without unit
 * tests; these were ported from the superseded #2904 branch onto the
 * merged hook API.
 *
 * Pins the verbatim-port behavior:
 * - confirm-gated branches (in_cabinet / complete) run the status command
 *   only after confirmation, and skip it when declined (UX Audit #2 / R-1.2)
 * - the context-menu variant awaits the status command and notifies on
 *   success exactly like the original inline panel code
 * - dialog-opening branches route to the exact dialog setter shapes
 *   (payment source 'table' vs 'context', print ticket, cancel, reschedule
 *   consolidated reducer action)
 * - openRecordEditor flips the wizard into edit mode with the row payload
 * - call_patient keeps the sanitized tel: anchor (R-24) — asserted by the
 *   source contract in RegistrarPanel.contract.test.tsx
 */
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useRegistrarRowActions } from '../useRegistrarRowActions';

vi.mock('../../../services/notify', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

import notify from '../../../services/notify';

function createSetters() {
  const setters = {
    setRecordPreviewDialog: vi.fn(),
    setPaymentDialog: vi.fn(),
    setPrintDialog: vi.fn(),
    setCancelDialog: vi.fn(),
    setContextMenu: vi.fn(),
    setForceMajeureModal: vi.fn(),
    openRescheduleDialog: vi.fn(),
    setWizardEditMode: vi.fn(),
    setWizardInitialData: vi.fn(),
    setShowWizard: vi.fn(),
  };
  return setters;
}

function renderRowActions(overrides: Partial<Record<string, unknown>> = {}) {
  const setters = createSetters();
  const params = {
    confirm: vi.fn().mockResolvedValue(true),
    tI18n: vi.fn((key: string) => key),
    updateAppointmentStatus: vi.fn().mockResolvedValue(undefined),
    handleStartVisit: vi.fn().mockResolvedValue(undefined),
    ...setters,
    ...overrides,
  };
  const hook = renderHook(() => useRegistrarRowActions(params as never)).result;
  return { hook, setters, ...params };
}

describe('useRegistrarRowActions (PR-UI-13-5)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('view action opens the record preview dialog', async () => {
    const { hook, setters } = renderRowActions();
    const row = { id: 7, patient_fio: 'A B' };
    await act(async () => { await hook.current.handleTableAction('view', row); });
    expect(setters.setRecordPreviewDialog).toHaveBeenCalledWith({ open: true, row });
  });

  it('edit action opens the wizard in edit mode with the row payload', async () => {
    const { hook, setters } = renderRowActions();
    const row = { id: 7, patient_fio: 'A B' };
    await act(async () => { await hook.current.handleTableAction('edit', row); });
    expect(setters.setWizardEditMode).toHaveBeenCalledWith(true);
    expect(setters.setWizardInitialData).toHaveBeenCalledWith(row);
    expect(setters.setShowWizard).toHaveBeenCalledWith(true);
  });

  it('payment action from the table opens the payment dialog with source table', async () => {
    const { hook, setters } = renderRowActions();
    await act(async () => { await hook.current.handleTableAction('payment', { id: 7 }); });
    expect(setters.setPaymentDialog).toHaveBeenCalledWith({
      open: true, row: { id: 7 }, paid: false, source: 'table',
    });
  });

  it('payment action from the context menu opens the payment dialog with source context', async () => {
    const { hook, setters } = renderRowActions();
    await act(async () => { await hook.current.handleContextMenuAction('payment', { id: 7 } as never); });
    expect(setters.setPaymentDialog).toHaveBeenCalledWith({
      open: true, row: { id: 7 }, paid: false, source: 'context',
    });
  });

  it('in_cabinet from the table requires confirmation, then updates the status without awaiting', async () => {
    const { hook, confirm, updateAppointmentStatus } = renderRowActions();
    const row = { id: 7, patient_fio: 'A B' };
    await act(async () => { await hook.current.handleTableAction('in_cabinet', row); });
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(updateAppointmentStatus).toHaveBeenCalledWith(7, 'in_cabinet', '', row);
  });

  it('in_cabinet from the table is skipped when confirmation is declined', async () => {
    const { hook, confirm, updateAppointmentStatus } = renderRowActions({
      confirm: vi.fn().mockResolvedValue(false),
    });
    await act(async () => { await hook.current.handleTableAction('in_cabinet', { id: 7 }); });
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(updateAppointmentStatus).not.toHaveBeenCalled();
  });

  it('in_cabinet from the context menu awaits the status command and notifies on success', async () => {
    const row = { id: 7, patient_fio: 'A B' };
    const updateAppointmentStatus = vi.fn().mockResolvedValue(undefined);
    const { hook } = renderRowActions({ updateAppointmentStatus });
    await act(async () => { await hook.current.handleContextMenuAction('in_cabinet', row as never); });
    expect(updateAppointmentStatus).toHaveBeenCalledWith(7, 'in_cabinet', '', row);
  });

  it('complete from the table routes to the done status after confirmation', async () => {
    const { hook, updateAppointmentStatus } = renderRowActions();
    const row = { id: 9, patient_name: 'C D' };
    await act(async () => { await hook.current.handleTableAction('complete', row); });
    expect(updateAppointmentStatus).toHaveBeenCalledWith(9, 'done', '', row);
  });

  it('print action opens the print dialog with a ticket payload', async () => {
    const { hook, setters } = renderRowActions();
    await act(async () => { await hook.current.handleTableAction('print', { id: 7 }); });
    expect(setters.setPrintDialog).toHaveBeenCalledWith({ open: true, type: 'ticket', data: { id: 7 } });
  });

  it('reschedule action routes through the consolidated reschedule dialog action', async () => {
    const { hook, setters } = renderRowActions();
    await act(async () => { await hook.current.handleTableAction('reschedule', { id: 7 }); });
    expect(setters.openRescheduleDialog).toHaveBeenCalledWith({ id: 7 });
  });

  it('cancel action opens the cancel dialog with an empty reason', async () => {
    const { hook, setters } = renderRowActions();
    await act(async () => { await hook.current.handleTableAction('cancel', { id: 7 }); });
    expect(setters.setCancelDialog).toHaveBeenCalledWith({ open: true, row: { id: 7 }, reason: '' });
  });

  it('more action opens the context menu anchored to the event target', async () => {
    const { hook, setters } = renderRowActions();
    const target = { getBoundingClientRect: () => ({ right: 111, top: 222 }) };
    await act(async () => {
      await hook.current.handleTableAction('more', { id: 7 }, { target, clientX: 5, clientY: 6 });
    });
    expect(setters.setContextMenu).toHaveBeenCalledWith({
      open: true,
      row: { id: 7 },
      position: { x: 111, y: 222 },
    });
  });

  it('more action falls back to client coordinates without a target rect', async () => {
    const { hook, setters } = renderRowActions();
    await act(async () => {
      await hook.current.handleTableAction('more', { id: 7 }, { clientX: 5, clientY: 6 });
    });
    expect(setters.setContextMenu).toHaveBeenCalledWith({
      open: true,
      row: { id: 7 },
      position: { x: 5, y: 6 },
    });
  });

  // #3808 (CR-01 / REG-FE-025): the force-majeure target comes from the
  // canonical per-row owner facts of the registrar read model — never from
  // the legacy doctor fallback, which can silently retarget a whole-queue
  // financial mutation onto an incidental doctor.
  it('force_majeure targets the canonical doctor owner when legacy doctor fields are absent', async () => {
    const { hook, setters, tI18n } = renderRowActions();
    await act(async () => {
      await hook.current.handleContextMenuAction('force_majeure', {
        id: 7,
        queue_owner_kind: 'doctor',
        queue_owner_id: 3,
        daily_queue_id: 41,
        record_date: '2026-10-30',
        doctor_name: 'Dr X',
      } as never);
    });
    expect(setters.setForceMajeureModal).toHaveBeenCalledTimes(1);
    expect(setters.setForceMajeureModal).toHaveBeenCalledWith({
      open: true,
      specialistId: 3,
      specialistName: 'Dr X',
      targetDate: '2026-10-30',
    });
    expect(tI18n).not.toHaveBeenCalledWith('registrarPanel.rp_all_specialists');
    expect(notify.warning).not.toHaveBeenCalled();
  });

  it('force_majeure falls back to the queue day field when record_date is absent', async () => {
    const { hook, setters } = renderRowActions();
    await act(async () => {
      await hook.current.handleContextMenuAction('force_majeure', {
        id: 71,
        queue_owner_kind: 'doctor',
        queue_owner_id: 3,
        daily_queue_id: 41,
        date: '2026-10-29',
        queue_name: 'Терапия',
      } as never);
    });
    expect(setters.setForceMajeureModal).toHaveBeenCalledWith({
      open: true,
      specialistId: 3,
      specialistName: 'Терапия',
      targetDate: '2026-10-29',
    });
  });

  it('force_majeure does not retarget a resource-owned row onto its incidental doctor', async () => {
    const { hook, setters, tI18n } = renderRowActions();
    await act(async () => {
      await hook.current.handleContextMenuAction('force_majeure', {
        id: 8,
        queue_owner_kind: 'resource',
        queue_owner_id: 7,
        daily_queue_id: 12,
        doctor_id: 3,
        doctor_name: 'Dr X',
        record_date: '2026-10-30',
      } as never);
    });
    expect(setters.setForceMajeureModal).not.toHaveBeenCalled();
    expect(notify.warning).toHaveBeenCalledTimes(1);
    expect(tI18n).toHaveBeenCalledWith('misc.fm_owner_unsupported');
  });

  it('force_majeure is unavailable for unknown-owner rows even with legacy specialist fields', async () => {
    const { hook, setters } = renderRowActions();
    await act(async () => {
      await hook.current.handleContextMenuAction('force_majeure', {
        id: 9,
        queue_owner_kind: null,
        queue_owner_id: null,
        daily_queue_id: null,
        specialist_id: 5,
        specialist_name: 'Dr Y',
      } as never);
    });
    expect(setters.setForceMajeureModal).not.toHaveBeenCalled();
    expect(notify.warning).toHaveBeenCalledTimes(1);
  });

  it('force_majeure no longer consults the legacy doctor fallback when owner facts are absent', async () => {
    const { hook, setters } = renderRowActions();
    await act(async () => {
      await hook.current.handleContextMenuAction('force_majeure', {
        id: 10,
        doctor_id: 3,
        doctor_name: 'Dr X',
      } as never);
    });
    expect(setters.setForceMajeureModal).not.toHaveBeenCalled();
    expect(notify.warning).toHaveBeenCalledTimes(1);
  });

  it('unknown actions are a no-op', async () => {
    const { hook, setters } = renderRowActions();
    await act(async () => { await hook.current.handleTableAction('nonsense', { id: 7 }); });
    expect(Object.values(setters).every((fn) => fn.mock.calls.length === 0)).toBe(true);
  });
});
