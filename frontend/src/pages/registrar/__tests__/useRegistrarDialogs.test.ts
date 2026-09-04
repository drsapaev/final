/**
 * PR-UI-13-3 unit contract: registrarDialogsReducer + registrarWizardReducer —
 * the dialog and wizard state machines consolidated from RegistrarPanel's
 * former useState hooks.
 *
 * Pins:
 * - every dialog's CLOSE reset shape (verbatim ports — e.g. print close keeps
 *   type 'ticket' because PrintDialog's documentType fallback reads it)
 * - the wizard SET_OPEN flag-only semantics (Esc-close keeps edit state —
 *   the original latent quirk, preserved deliberately)
 * - CLOSE_RESET / OPEN_EDIT transitions
 */
import { describe, expect, it } from 'vitest';

import {
  initialRegistrarDialogsState,
  registrarDialogsReducer,
} from '../useRegistrarDialogs';
import {
  initialRegistrarWizardState,
  registrarWizardReducer,
} from '../useRegistrarWizard';

describe('registrarDialogsReducer (PR-UI-13-3)', () => {
  it('initial state matches the original useState initializers', () => {
    expect(initialRegistrarDialogsState).toEqual({
      printDialog: { open: false, type: 'ticket', data: null },
      cancelDialog: { open: false, row: null, reason: '' },
      paymentDialog: { open: false, row: null, paid: false, source: null },
      recordPreviewDialog: { open: false, row: null },
      forceMajeureModal: { open: false, specialistId: null, specialistName: '' },
      contextMenu: { open: false, row: null, position: { x: 0, y: 0 } },
      rescheduleDialog: { open: false, data: null },
      showPaymentManager: false,
    });
  });

  it('SET_PAYMENT_DIALOG stores the full value (open + close shapes)', () => {
    const open = registrarDialogsReducer(initialRegistrarDialogsState, {
      type: 'SET_PAYMENT_DIALOG',
      value: { open: true, row: { id: '1' } as never, paid: false, source: 'table' },
    });
    expect(open.paymentDialog).toEqual({ open: true, row: { id: '1' }, paid: false, source: 'table' });
    const closed = registrarDialogsReducer(open, {
      type: 'SET_PAYMENT_DIALOG',
      value: { open: false, row: null, paid: false, source: null },
    });
    expect(closed.paymentDialog).toEqual({ open: false, row: null, paid: false, source: null });
    // other slices untouched
    expect(closed.printDialog).toBe(initialRegistrarDialogsState.printDialog);
  });

  it('SET_PRINT_DIALOG close shape keeps type "ticket" (PrintDialog documentType fallback)', () => {
    const closed = registrarDialogsReducer(initialRegistrarDialogsState, {
      type: 'SET_PRINT_DIALOG',
      value: { open: false, type: 'ticket', data: null },
    });
    expect(closed.printDialog).toEqual({ open: false, type: 'ticket', data: null });
  });

  it('SET_CONTEXT_MENU close shape resets position to origin', () => {
    const closed = registrarDialogsReducer(initialRegistrarDialogsState, {
      type: 'SET_CONTEXT_MENU',
      value: { open: false, row: null, position: { x: 0, y: 0 } },
    });
    expect(closed.contextMenu.position).toEqual({ x: 0, y: 0 });
  });

  it('SET_RESCHEDULE_DIALOG consolidates the former showSlotsModal + rescheduleData pair', () => {
    const opened = registrarDialogsReducer(initialRegistrarDialogsState, {
      type: 'SET_RESCHEDULE_DIALOG',
      value: { open: true, data: { id: '9', visit_id: 'v1' } },
    });
    expect(opened.rescheduleDialog).toEqual({ open: true, data: { id: '9', visit_id: 'v1' } });
    const closed = registrarDialogsReducer(opened, {
      type: 'SET_RESCHEDULE_DIALOG',
      value: { open: false, data: null },
    });
    expect(closed.rescheduleDialog).toEqual({ open: false, data: null });
  });

  it('SET_FORCE_MAJEURE_MODAL / SET_CANCEL_DIALOG / SET_RECORD_PREVIEW_DIALOG store full values', () => {
    const s1 = registrarDialogsReducer(initialRegistrarDialogsState, {
      type: 'SET_FORCE_MAJEURE_MODAL',
      value: { open: true, specialistId: 5, specialistName: 'Dr Test' },
    });
    expect(s1.forceMajeureModal.specialistName).toBe('Dr Test');
    const s2 = registrarDialogsReducer(s1, {
      type: 'SET_CANCEL_DIALOG',
      value: { open: true, row: { id: '2' } as never, reason: '' },
    });
    expect(s2.cancelDialog.open).toBe(true);
    const s3 = registrarDialogsReducer(s2, {
      type: 'SET_RECORD_PREVIEW_DIALOG',
      value: { open: true, row: { id: '3' } as never },
    });
    expect(s3.recordPreviewDialog.row).toEqual({ id: '3' });
    expect(s3.forceMajeureModal.open).toBe(true); // slices independent
  });

  it('SET_PAYMENT_MANAGER toggles the manager flag', () => {
    const s = registrarDialogsReducer(initialRegistrarDialogsState, { type: 'SET_PAYMENT_MANAGER', value: true });
    expect(s.showPaymentManager).toBe(true);
  });
});

describe('registrarWizardReducer (PR-UI-13-3)', () => {
  it('initial state: closed, create-mode, no data', () => {
    expect(initialRegistrarWizardState).toEqual({ open: false, editMode: false, initialData: null });
  });

  it('SET_OPEN flips ONLY the open flag (original setShowWizard semantics)', () => {
    const edited = { open: false, editMode: true, initialData: { id: '1' } };
    const opened = registrarWizardReducer(edited, { type: 'SET_OPEN', open: true });
    // Latent quirk preserved: reopening without reset keeps stale edit state —
    // exactly what the original separate useState setters did.
    expect(opened).toEqual({ open: true, editMode: true, initialData: { id: '1' } });
  });

  it('OPEN_EDIT sets editMode + initialData + open in one transition', () => {
    const s = registrarWizardReducer(initialRegistrarWizardState, { type: 'OPEN_EDIT', data: { id: '7' } });
    expect(s).toEqual({ open: true, editMode: true, initialData: { id: '7' } });
  });

  it('CLOSE_RESET clears all three fields (wizard onClose semantics)', () => {
    const s = registrarWizardReducer(
      { open: true, editMode: true, initialData: { id: '7' } },
      { type: 'CLOSE_RESET' },
    );
    expect(s).toEqual({ open: false, editMode: false, initialData: null });
  });

  it('SET_EDIT_MODE / SET_INITIAL_DATA are independent (original setter semantics)', () => {
    const s1 = registrarWizardReducer(initialRegistrarWizardState, { type: 'SET_EDIT_MODE', editMode: true });
    expect(s1).toEqual({ open: false, editMode: true, initialData: null });
    const s2 = registrarWizardReducer(s1, { type: 'SET_INITIAL_DATA', data: { id: '1' } });
    expect(s2).toEqual({ open: false, editMode: true, initialData: { id: '1' } });
  });
});
