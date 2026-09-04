/**
 * Registrar Panel — dialog/modal state machine (useReducer).
 *
 * PR-UI-13-3: consolidates the 8 separate dialog useState hooks from
 * RegistrarPanel.tsx into one reducer (plan §PR-UI-13 "Вынести state в
 * useReducer"; hooks named in the plan: useRegistrarDialogs).
 *
 * Ports the original state shapes AND reset shapes verbatim:
 * - print close resets to { open: false, type: 'ticket', data: null }
 *   (type stays 'ticket' — PrintDialog's documentType fallback depends on it)
 * - contextMenu close resets position to { x: 0, y: 0 }
 * - force-majeure close resets specialist fields to null/''
 *
 * Two API layers:
 * 1. Semantic helpers (openPaymentDialog / closePaymentDialog / …) — used by
 *    the panel's own action routing.
 * 2. Setter-compatible shims (setPaymentDialog / setPrintDialog /
 *    setContextMenu / setRescheduleDialog / setShowPaymentManager) — plain
 *    full-value replacement, preserving the exact call shapes WelcomeView,
 *    QueueView and legacy JSX use (`set*({ open: true, … })`). No functional
 *    updater is used anywhere in the tree (verified by grep), so a plain
 *    value shim is a faithful port.
 */
import { useCallback, useReducer } from 'react';
import type { Appointment } from '../../types/domain/clinic';

export interface PrintDialogState {
  open: boolean;
  type: string;
  data: Record<string, unknown> | null;
}
export interface CancelDialogState {
  open: boolean;
  row: Appointment | null;
  reason: string;
}
export interface PaymentDialogState {
  open: boolean;
  row: Appointment | null;
  paid: boolean;
  source: string | null;
}
export interface RecordPreviewDialogState {
  open: boolean;
  row: Appointment | null;
}
export interface ForceMajeureModalState {
  open: boolean;
  specialistId: string | number | null;
  specialistName: string;
}
export interface ContextMenuState {
  open: boolean;
  row: Record<string, unknown> | null;
  position: { x: number; y: number };
}
export interface RescheduleDialogState {
  open: boolean;
  data: Record<string, unknown> | null;
}

export interface RegistrarDialogsState {
  printDialog: PrintDialogState;
  cancelDialog: CancelDialogState;
  paymentDialog: PaymentDialogState;
  recordPreviewDialog: RecordPreviewDialogState;
  forceMajeureModal: ForceMajeureModalState;
  contextMenu: ContextMenuState;
  rescheduleDialog: RescheduleDialogState;
  showPaymentManager: boolean;
}

export type RegistrarDialogsAction =
  | { type: 'SET_PRINT_DIALOG'; value: PrintDialogState }
  | { type: 'SET_CANCEL_DIALOG'; value: CancelDialogState }
  | { type: 'SET_PAYMENT_DIALOG'; value: PaymentDialogState }
  | { type: 'SET_RECORD_PREVIEW_DIALOG'; value: RecordPreviewDialogState }
  | { type: 'SET_CONTEXT_MENU'; value: ContextMenuState }
  | { type: 'SET_FORCE_MAJEURE_MODAL'; value: ForceMajeureModalState }
  | { type: 'SET_RESCHEDULE_DIALOG'; value: RescheduleDialogState }
  | { type: 'SET_PAYMENT_MANAGER'; value: boolean };

export const initialRegistrarDialogsState: RegistrarDialogsState = {
  printDialog: { open: false, type: 'ticket', data: null },
  cancelDialog: { open: false, row: null, reason: '' },
  paymentDialog: { open: false, row: null, paid: false, source: null },
  recordPreviewDialog: { open: false, row: null },
  forceMajeureModal: { open: false, specialistId: null, specialistName: '' },
  contextMenu: { open: false, row: null, position: { x: 0, y: 0 } },
  rescheduleDialog: { open: false, data: null },
  showPaymentManager: false,
};

export const registrarDialogsReducer = (
  state: RegistrarDialogsState,
  action: RegistrarDialogsAction,
): RegistrarDialogsState => {
  switch (action.type) {
    case 'SET_PRINT_DIALOG':
      return { ...state, printDialog: action.value };
    case 'SET_CANCEL_DIALOG':
      return { ...state, cancelDialog: action.value };
    case 'SET_PAYMENT_DIALOG':
      return { ...state, paymentDialog: action.value };
    case 'SET_RECORD_PREVIEW_DIALOG':
      return { ...state, recordPreviewDialog: action.value };
    case 'SET_CONTEXT_MENU':
      return { ...state, contextMenu: action.value };
    case 'SET_FORCE_MAJEURE_MODAL':
      return { ...state, forceMajeureModal: action.value };
    case 'SET_RESCHEDULE_DIALOG':
      return { ...state, rescheduleDialog: action.value };
    case 'SET_PAYMENT_MANAGER':
      return { ...state, showPaymentManager: action.value };
    default:
      return state;
  }
};

export const useRegistrarDialogs = () => {
  const [state, dispatch] = useReducer(registrarDialogsReducer, initialRegistrarDialogsState);

  const {
    printDialog, cancelDialog, paymentDialog, recordPreviewDialog,
    forceMajeureModal, contextMenu, rescheduleDialog, showPaymentManager,
  } = state;

  // ── Semantic helpers (panel action routing) ──────────────────────────────
  const openPaymentDialog = useCallback((row: Appointment, source: string | null) => {
    dispatch({ type: 'SET_PAYMENT_DIALOG', value: { open: true, row, paid: false, source } });
  }, []);
  const closePaymentDialog = useCallback(() => {
    dispatch({ type: 'SET_PAYMENT_DIALOG', value: { open: false, row: null, paid: false, source: null } });
  }, []);
  const openPrintDialog = useCallback((data: Record<string, unknown>, type = 'ticket') => {
    dispatch({ type: 'SET_PRINT_DIALOG', value: { open: true, type, data } });
  }, []);
  const closePrintDialog = useCallback(() => {
    // Original close reset keeps type 'ticket' (PrintDialog documentType fallback).
    dispatch({ type: 'SET_PRINT_DIALOG', value: { open: false, type: 'ticket', data: null } });
  }, []);
  const openCancelDialog = useCallback((row: Appointment) => {
    dispatch({ type: 'SET_CANCEL_DIALOG', value: { open: true, row, reason: '' } });
  }, []);
  const closeCancelDialog = useCallback(() => {
    dispatch({ type: 'SET_CANCEL_DIALOG', value: { open: false, row: null, reason: '' } });
  }, []);
  const openRecordPreview = useCallback((row: Appointment) => {
    dispatch({ type: 'SET_RECORD_PREVIEW_DIALOG', value: { open: true, row } });
  }, []);
  const closeRecordPreview = useCallback(() => {
    dispatch({ type: 'SET_RECORD_PREVIEW_DIALOG', value: { open: false, row: null } });
  }, []);
  const openContextMenu = useCallback((row: Record<string, unknown>, position: { x: number; y: number }) => {
    dispatch({ type: 'SET_CONTEXT_MENU', value: { open: true, row, position } });
  }, []);
  const closeContextMenu = useCallback(() => {
    dispatch({ type: 'SET_CONTEXT_MENU', value: { open: false, row: null, position: { x: 0, y: 0 } } });
  }, []);
  const openForceMajeure = useCallback((specialistId: string | number | null, specialistName: string) => {
    dispatch({ type: 'SET_FORCE_MAJEURE_MODAL', value: { open: true, specialistId, specialistName } });
  }, []);
  const closeForceMajeure = useCallback(() => {
    dispatch({ type: 'SET_FORCE_MAJEURE_MODAL', value: { open: false, specialistId: null, specialistName: '' } });
  }, []);
  const openRescheduleDialog = useCallback((data: Record<string, unknown>) => {
    dispatch({ type: 'SET_RESCHEDULE_DIALOG', value: { open: true, data } });
  }, []);
  const closeRescheduleDialog = useCallback(() => {
    dispatch({ type: 'SET_RESCHEDULE_DIALOG', value: { open: false, data: null } });
  }, []);
  const setShowPaymentManager = useCallback((value: boolean) => {
    dispatch({ type: 'SET_PAYMENT_MANAGER', value });
  }, []);

  // ── Setter-compatible shims (WelcomeView / QueueView / legacy JSX) ────────
  // Plain full-value replacement — preserves the exact original call shapes.
  const setPrintDialog = useCallback((value: PrintDialogState) => {
    dispatch({ type: 'SET_PRINT_DIALOG', value });
  }, []);
  const setCancelDialog = useCallback((value: CancelDialogState) => {
    dispatch({ type: 'SET_CANCEL_DIALOG', value });
  }, []);
  const setPaymentDialog = useCallback((value: PaymentDialogState) => {
    dispatch({ type: 'SET_PAYMENT_DIALOG', value });
  }, []);
  const setRecordPreviewDialog = useCallback((value: RecordPreviewDialogState) => {
    dispatch({ type: 'SET_RECORD_PREVIEW_DIALOG', value });
  }, []);
  const setContextMenu = useCallback((value: ContextMenuState) => {
    dispatch({ type: 'SET_CONTEXT_MENU', value });
  }, []);
  const setForceMajeureModal = useCallback((value: ForceMajeureModalState) => {
    dispatch({ type: 'SET_FORCE_MAJEURE_MODAL', value });
  }, []);
  const setRescheduleData = useCallback((value: Record<string, unknown> | null) => {
    // Original: rescheduleData was a separate useState; open+data were set
    // together at call sites (`setRescheduleData(row); setShowSlotsModal(true)`).
    // The shim keeps data-only replacement semantics: null clears the payload
    // without touching the open flag.
    dispatch({ type: 'SET_RESCHEDULE_DIALOG', value: { open: state.rescheduleDialog.open, data: value } });
  }, [state.rescheduleDialog.open]);

  return {
    // state
    printDialog,
    cancelDialog,
    paymentDialog,
    recordPreviewDialog,
    forceMajeureModal,
    contextMenu,
    rescheduleDialog,
    showPaymentManager,
    // semantic helpers
    openPaymentDialog,
    closePaymentDialog,
    openPrintDialog,
    closePrintDialog,
    openCancelDialog,
    closeCancelDialog,
    openRecordPreview,
    closeRecordPreview,
    openContextMenu,
    closeContextMenu,
    openForceMajeure,
    closeForceMajeure,
    openRescheduleDialog,
    closeRescheduleDialog,
    setShowPaymentManager,
    // setter-compatible shims
    setPrintDialog,
    setCancelDialog,
    setPaymentDialog,
    setRecordPreviewDialog,
    setContextMenu,
    setForceMajeureModal,
    setRescheduleData,
  };
};

export default useRegistrarDialogs;
