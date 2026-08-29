/**
 * Registrar Panel — appointment wizard state + completion flow.
 *
 * PR-UI-13-3: extracted from RegistrarPanel.tsx (plan §PR-UI-13 names this
 * hook: useRegistrarWizard). Consolidates showWizard / wizardEditMode /
 * wizardInitialData into a useReducer; isProcessing stays a flag (it is
 * co-owned with AppointmentWizardV2 via setIsProcessing).
 *
 * EXACT-PORT NOTE on setter semantics (deliberate, do not "fix"):
 * - setShowWizard(open) flips ONLY the open flag — it does NOT reset
 *   editMode/initialData. The original hotkey Esc path closes the wizard
 *   via setShowWizard(false) without resetting, so a subsequent plain
 *   setShowWizard(true) reopens with stale edit state. That latent quirk is
 *   preserved verbatim (behavior-preservation contract of PR-UI-13).
 * - closeWizard() (the wizard's own onClose) resets ALL three fields —
 *   matching the original onClose handler.
 * - openWizardForCreate() replays the original three-setter sequence.
 *
 * handleWizardComplete ports the original onComplete verbatim: optimistic UI
 * (close + notify + payment/print handoff) then background reload with a
 * single silent retry (P-004 fix: no artificial 1500ms wait).
 */
import { useCallback, useReducer, useState } from 'react';
import logger from '../../utils/logger';
import notify from '../../services/notify';
import type { Appointment } from '../../types/domain/clinic';
import { buildPostWizardPaymentRow } from './registrarHelpers';
import type { PaymentDialogState, PrintDialogState } from './useRegistrarDialogs';

export interface RegistrarWizardState {
  open: boolean;
  editMode: boolean;
  initialData: Record<string, unknown> | null;
}

export type RegistrarWizardAction =
  | { type: 'SET_OPEN'; open: boolean }
  | { type: 'SET_EDIT_MODE'; editMode: boolean }
  | { type: 'SET_INITIAL_DATA'; data: Record<string, unknown> | null }
  | { type: 'OPEN_EDIT'; data: Record<string, unknown> }
  | { type: 'CLOSE_RESET' };

export const initialRegistrarWizardState: RegistrarWizardState = {
  open: false,
  editMode: false,
  initialData: null,
};

export const registrarWizardReducer = (
  state: RegistrarWizardState,
  action: RegistrarWizardAction,
): RegistrarWizardState => {
  switch (action.type) {
    case 'SET_OPEN':
      return { ...state, open: action.open };
    case 'SET_EDIT_MODE':
      return { ...state, editMode: action.editMode };
    case 'SET_INITIAL_DATA':
      return { ...state, initialData: action.data };
    case 'OPEN_EDIT':
      return { open: true, editMode: true, initialData: action.data };
    case 'CLOSE_RESET':
      return { open: false, editMode: false, initialData: null };
    default:
      return state;
  }
};

export const useRegistrarWizard = ({
  setPaymentDialog,
  setPrintDialog,
  loadAppointmentsRef,
  loadIntegratedData,
  tI18n,
}: {
  setPaymentDialog: (value: PaymentDialogState) => void;
  setPrintDialog: (value: PrintDialogState) => void;
  /**
   * Ref indirection (PR-UI-13-3): the panel wires useRegistrarWizard before
   * useRegistrarWorklistData (which needs this hook's showWizard flag) — a
   * cycle. The ref carries the latest committed render's loadAppointments,
   * which is exactly the closure the original inline onComplete captured
   * (React events fire against the latest committed render).
   */
  loadAppointmentsRef: { current: (options?: unknown) => Promise<void> | void };
  loadIntegratedData: () => Promise<void> | void;
  tI18n: (key: string, options?: Record<string, unknown>) => string;
}) => {
  const [state, dispatch] = useReducer(registrarWizardReducer, initialRegistrarWizardState);
  const { open: showWizard, editMode: wizardEditMode, initialData: wizardInitialData } = state;

  // Co-owned processing flag (AppointmentWizardV2 receives setIsProcessing).
  const [isProcessing, setIsProcessing] = useState(false);

  // ── Setter-compatible shims (exact original semantics) ────────────────────
  const setShowWizard = useCallback((open: boolean) => {
    dispatch({ type: 'SET_OPEN', open });
  }, []);
  const setWizardEditMode = useCallback((editMode: boolean) => {
    dispatch({ type: 'SET_EDIT_MODE', editMode });
  }, []);
  const setWizardInitialData = useCallback((data: Record<string, unknown> | null) => {
    dispatch({ type: 'SET_INITIAL_DATA', data });
  }, []);

  // ── Semantic helpers ───────────────────────────────────────────────────────
  const openWizardForCreate = useCallback(() => {
    // Original three-setter sequence (Ctrl+N / header CTA / empty-state CTA).
    dispatch({ type: 'SET_EDIT_MODE', editMode: false });
    dispatch({ type: 'SET_INITIAL_DATA', data: null });
    dispatch({ type: 'SET_OPEN', open: true });
  }, []);
  const openWizardForEdit = useCallback((row: Record<string, unknown>) => {
    dispatch({ type: 'OPEN_EDIT', data: row });
  }, []);
  const closeWizard = useCallback(() => {
    // Original onClose: reset mode + data + close.
    dispatch({ type: 'CLOSE_RESET' });
  }, []);

  // ── Completion flow (verbatim port of onComplete) ─────────────────────────
  const handleWizardComplete = useCallback(async (wizardData: unknown) => {
    logger.info('AppointmentWizardV2 completed successfully:', wizardData);
    const wasEditMode = state.editMode;
    const wizardDataObj = (wizardData && typeof wizardData === 'object' ? wizardData : {}) as Record<string, unknown>;
    const postWizardPaymentRow = (!wasEditMode || Number(wizardDataObj.total_amount ?? 0) > 0)
      ? buildPostWizardPaymentRow(wizardDataObj)
      : null;

    // Обновляем данные (работает и для создания, и для редактирования)
    try {
      // P-004 fix: removed hardcoded 1500ms delay (previously setTimeout(resolve, 1500)).
      // That dead time was added as a workaround for backend batch operations not
      // finishing fast enough — it cost registrars ~60 sec/day of pure wait time.
      // Strategy now: optimistic UI (close wizard + notify success immediately),
      // then reload appointments with force=true. If the first reload returns stale
      // data, a single silent retry is attempted after a short debounce.
      dispatch({ type: 'CLOSE_RESET' });

      const message = wasEditMode ?
        tI18n('registrarPanel.rp_notify_appointment_updated') :
        tI18n('registrarPanel.rp_notify_appointment_created');
      notify.success(message);

      // Open payment/print dialog immediately — user can act while data refreshes
      if (postWizardPaymentRow) {
        if (Number(postWizardPaymentRow.cost || 0) > 0) {
          setPaymentDialog({ open: true, row: postWizardPaymentRow as unknown as Appointment, paid: false, source: wasEditMode ? 'wizard-edit' : 'wizard-create' });
        } else {
          setPrintDialog({ open: true, type: 'ticket', data: postWizardPaymentRow });
        }
      }

      // Reload data in the background (does not block UI)
      try {
        await Promise.all([
          loadAppointmentsRef.current({ silent: true, source: 'wizard-complete' } as Record<string, unknown>),
          loadIntegratedData(),
        ]);
      } catch (refreshError) {
        // Background refresh failed — single silent retry
        logger.warn('First post-wizard reload failed, retrying once:', refreshError);
        try {
          await loadAppointmentsRef.current({ silent: true, source: 'wizard-complete-retry' } as Record<string, unknown>);
        } catch (retryError) {
          logger.error('Post-wizard reload retry also failed:', retryError);
        }
      }
    } catch (error: unknown) {
      logger.error('Error refreshing data after wizard completion:', error);
      // Не показываем ошибку пользователю, так как запись уже создана
      dispatch({ type: 'SET_OPEN', open: false });
      notify.success(tI18n('registrar.appointment_created'));
    }
  }, [state.editMode, setPaymentDialog, setPrintDialog, loadAppointmentsRef, loadIntegratedData, tI18n]);

  return {
    showWizard,
    wizardEditMode,
    wizardInitialData,
    isProcessing,
    setIsProcessing,
    // setter-compatible shims
    setShowWizard,
    setWizardEditMode,
    setWizardInitialData,
    // semantic helpers
    openWizardForCreate,
    openWizardForEdit,
    closeWizard,
    handleWizardComplete,
  };
};

export default useRegistrarWizard;
