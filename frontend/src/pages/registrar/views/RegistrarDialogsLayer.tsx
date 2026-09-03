/**
 * Registrar Panel — dialogs layer (overlay surfaces composition).
 *
 * PR-UI-13-5: extracted verbatim from RegistrarPanel.tsx JSX — the mounting
 * point for every overlay surface of the registrar workspace: record preview,
 * cancel / payment / print dialogs, the ErrorBoundary-guarded
 * AppointmentWizardV2, the reschedule slots dialog, the row context menu, the
 * payment manager and the force-majeure modal. Handlers are passed in from
 * the orchestrator (the panel owns state via useRegistrarDialogs /
 * useRegistrarWizard; this layer only mounts and wires).
 */
import ErrorBoundary from '../../../components/common/ErrorBoundary';
import AppointmentContextMenu from '../../../components/tables/AppointmentContextMenu';
import CancelDialog from '../../../components/dialogs/CancelDialog';
import PaymentDialog from '../../../components/dialogs/PaymentDialog';
import PrintDialog from '../../../components/dialogs/PrintDialog';
import PaymentManager from '../../../components/payment/PaymentManager';
import AppointmentWizardV2 from '../../../components/wizard/AppointmentWizardV2';
import ForceMajeureModal from '../../../components/registrar/ForceMajeureModal';
import logger from '../../../utils/logger';
import notify from '../../../services/notify';
import { getErrorMessage } from '../../../utils/errorHandler';
import { printPanelTicketInBrowserAsync } from '../../../services/panelPrint';
import type { Appointment } from '../../../types/domain/clinic';
import RecordPreview from './RecordPreview';
import RescheduleSlots from './RescheduleSlots';
import type {
  CancelDialogState,
  ContextMenuState,
  ForceMajeureModalState,
  PaymentDialogState,
  PrintDialogState,
  RecordPreviewDialogState,
} from '../useRegistrarDialogs';

interface RegistrarDialogsLayerProps {
  // dialog state (useRegistrarDialogs)
  recordPreviewDialog: RecordPreviewDialogState;
  cancelDialog: CancelDialogState;
  paymentDialog: PaymentDialogState;
  printDialog: PrintDialogState;
  forceMajeureModal: ForceMajeureModalState;
  contextMenu: ContextMenuState;
  showSlotsModal: boolean;
  rescheduleData: Record<string, unknown> | null;
  showPaymentManager: boolean;
  // wizard state (useRegistrarWizard)
  showWizard: boolean;
  wizardEditMode: boolean;
  wizardInitialData: Record<string, unknown> | null;
  isProcessing: boolean;
  activeTab: string | null;
  // theme
  theme?: string;
  getColor: (color: string, shade?: number | string) => string;
  getSpacing: (size: string) => string;
  getFontSize: (size: string) => string;
  // dialog setters / helpers
  setRecordPreviewDialog: (value: RecordPreviewDialogState) => void;
  setPaymentDialog: (value: PaymentDialogState) => void;
  setPrintDialog: (value: PrintDialogState) => void;
  setCancelDialog: (value: CancelDialogState) => void;
  setContextMenu: (value: ContextMenuState) => void;
  setForceMajeureModal: (value: ForceMajeureModalState) => void;
  setShowPaymentManager: (value: boolean) => void;
  closeRescheduleDialog: () => void;
  // wizard setters
  setShowWizard: (open: boolean) => void;
  setWizardEditMode: (editMode: boolean) => void;
  setWizardInitialData: (data: Record<string, unknown> | null) => void;
  setIsProcessing: (value: boolean) => void;
  // data + actions
  appointments: Appointment[];
  loadAppointments: (options?: unknown) => Promise<void> | void;
  loadIntegratedData: () => Promise<void> | void;
  openRecordEditor: (row: unknown) => void;
  handleContextMenuAction: (action: string, row: Appointment) => void | Promise<void>;
  handleWizardComplete: (wizardData: unknown) => void | Promise<void>;
  runRegistrarRecordAction: (record: Record<string, unknown>, action: string, payload?: Record<string, unknown>) => Promise<{ success?: boolean; success_count?: number; failed_count?: number; results?: { success?: boolean; error?: string }[] } | null>;
  handlePayment: (appointment: Record<string, unknown>, paymentData?: { amount?: number | null; method?: string | null } | null) => Promise<unknown>;
  resolveRescheduleVisitId: (appointmentRow: Record<string, unknown>) => unknown;
  removeRescheduledAppointmentFromView: (appointmentRow: Record<string, unknown>, visitId: unknown) => void;
  confirm: (options: Record<string, unknown>) => Promise<boolean>;
  tI18n: (key: string, options?: Record<string, unknown>) => string;
}

const RegistrarDialogsLayer = ({
  recordPreviewDialog,
  cancelDialog,
  paymentDialog,
  printDialog,
  forceMajeureModal,
  contextMenu,
  showSlotsModal,
  rescheduleData,
  showPaymentManager,
  showWizard,
  wizardEditMode,
  wizardInitialData,
  isProcessing,
  activeTab,
  theme,
  getColor,
  getSpacing,
  getFontSize,
  setRecordPreviewDialog,
  setPaymentDialog,
  setPrintDialog,
  setCancelDialog,
  setContextMenu,
  setForceMajeureModal,
  setShowPaymentManager,
  closeRescheduleDialog,
  setShowWizard,
  setWizardEditMode,
  setWizardInitialData,
  setIsProcessing,
  appointments,
  loadAppointments,
  loadIntegratedData,
  openRecordEditor,
  handleContextMenuAction,
  handleWizardComplete,
  runRegistrarRecordAction,
  handlePayment,
  resolveRescheduleVisitId,
  removeRescheduledAppointmentFromView,
  confirm,
  tI18n,
}: RegistrarDialogsLayerProps) => (
  <>
    <RecordPreview
      isOpen={recordPreviewDialog.open}
      row={recordPreviewDialog.row}
      onClose={() => setRecordPreviewDialog({ open: false, row: null })}
      onEdit={(row) => {
        setRecordPreviewDialog({ open: false, row: null });
        openRecordEditor(row);
      }}
      tI18n={tI18n}
    />

    <CancelDialog
      isOpen={cancelDialog.open}
      onClose={() => setCancelDialog({ open: false, row: null, reason: '' })}
      appointment={cancelDialog.row}
      onCancel={async (appointmentId, reason) => {
        try {
          const data = appointmentId === cancelDialog.row?.id
            ? cancelDialog.row
            : appointments.find((a) => a.id === appointmentId);
          const result = await runRegistrarRecordAction(data as Record<string, unknown>, 'cancel', { reason });
          if (!result) return;
          if (!result.success) {
            const successCount = Number(result.success_count || 0);
            const failedCount = Number(result.failed_count || 0);
            if (successCount === 0) {
              throw new Error(result.results?.find((item: { success?: boolean; error?: string }) => !item.success)?.error || 'cancel_failed');
            }
            notify.warning('Cancelled ' + successCount + '; failed ' + failedCount);
          }
          await loadAppointments({ silent: true, source: 'cancel_complete' } as Record<string, unknown>);
        } catch (error: unknown) {
          logger.error('RegistrarPanel: cancellation failed:', error);
          notify.error(getErrorMessage(error, 'Could not cancel record. Check connection and try again.'));
          throw error;
        }
      }} />


    <PaymentDialog
      isOpen={paymentDialog.open}
      onClose={() => setPaymentDialog({ open: false, row: null, paid: false, source: null })}
      appointment={paymentDialog.row}
      onPaymentSuccess={async (paymentData) => {
        // ✅ ИСПРАВЛЕНО: используем реальный API вызов через handlePayment
        const appointment = paymentDialog.row;
        if (appointment) {
          const updated = await handlePayment(appointment as Record<string, unknown>, paymentData as { amount?: number | null; method?: string | null } | null);
          if (updated) {
            // Canonical state is refreshed by handlePayment via loadAppointments.
            logger.info('PaymentDialog: Оплата успешна, данные обновлены:', updated);
          }
        }
      }}
      onPrintTicket={(appointment: unknown) => {
        const rowObj = (paymentDialog.row && typeof paymentDialog.row === 'object' ? paymentDialog.row : {}) as Record<string, unknown>;
        const apptObj = (appointment && typeof appointment === 'object' ? appointment : {}) as Record<string, unknown>;
        const printSource = {
          ...rowObj,
          ...apptObj
        };
        // UX Audit: закрываем PaymentDialog при открытии PrintDialog.
        setPaymentDialog({ open: false, row: null, paid: false, source: null });
        setPrintDialog({
          open: true,
          type: 'ticket',
          data: printSource
        });
      }} />

    <PrintDialog
      isOpen={printDialog.open}
      onClose={() => setPrintDialog({ open: false, type: 'ticket', data: null })}
      documentType={printDialog.type || 'ticket'}
      documentData={printDialog.data}
      onPrint={async (data, printerId) => {
        logger.info('Printing:', { printerId, documentType: printDialog.type, data });

        if (printDialog.type !== 'ticket') {
          throw new Error(tI18n('registrarPanel.rp_err_unsupported_doc_type', { docType: printDialog.type }));
        }

        const result = await printPanelTicketInBrowserAsync((data ?? {}) as Record<string, unknown>);
        if (result?.opened && result?.success) {
          return;
        }

        if (!result?.opened) {
          throw new Error(tI18n('registrarPanel.rp_err_print_blocked'));
        }

        throw result?.error || new Error(tI18n('registrarPanel.rp_err_print_prepare'));
      }} />


    {/* ✅ Используется только новый мастер (V2) */}
    {/* ✅ PR-UI-13 (plan item 4): локальный ErrorBoundary вокруг wizard —
        сбой в мастере записи не должен ронять весь рабочий стол регистратора;
        fallback UI отрендерится внутри контейнера панели. */}
    <ErrorBoundary
      onError={(error, errorInfo) => {
        logger.error('[RegistrarPanel] AppointmentWizardV2 crashed:', error, errorInfo);
        // Codex P2-1 (PR-UI-13-4): reset the wizard-open state from the crash
        // path — otherwise showWizard stays true while the boundary holds
        // hasError, the auto-refresh effect keeps treating the wizard as an
        // open dialog, and the wizard cannot be reopened normally.
        setWizardEditMode(false);
        setWizardInitialData(null);
        setShowWizard(false);
      }}
      theme={{
        // Codex P2-2 (PR-UI-13-4): ErrorBoundary's fallback styles read the
        // theme helper functions — passing only the mode string left the
        // recovery screen with unstyled raw fallback values.
        theme,
        getColor,
        getSpacing,
        getFontSize,
      }}>
      <AppointmentWizardV2
      isOpen={showWizard}
      editMode={wizardEditMode} // ✨ НОВОЕ: Передаем режим
      initialData={wizardInitialData as unknown as null} // ✨ НОВОЕ: Передаем данные
      activeTab={activeTab as unknown as null} // ✅ ПЕРЕДАЕМ activeTab для фильтрации услуг
      onClose={() => {
        logger.info('AppointmentWizardV2 closing');
        setShowWizard(false);
        setWizardEditMode(false); // ✨ Сброс режима
        setWizardInitialData(null); // ✨ Сброс данных
      }}
      isProcessing={isProcessing}
      setIsProcessing={setIsProcessing}
      // PR-UI-13-3: completion flow extracted to useRegistrarWizard
      // (handleWizardComplete — verbatim port: optimistic close + notify +
      // payment/print handoff, then background reload with one silent retry).
      onComplete={handleWizardComplete} />
    </ErrorBoundary>

    <RescheduleSlots
      isOpen={showSlotsModal}
      rescheduleData={rescheduleData}
      onClose={closeRescheduleDialog}
      confirm={confirm}
      resolveRescheduleVisitId={resolveRescheduleVisitId}
      removeRescheduledAppointmentFromView={removeRescheduledAppointmentFromView}
      loadAppointments={loadAppointments}
      tI18n={tI18n}
    />

    {/* Контекстное меню */}
    {contextMenu.open && contextMenu.row &&
    <AppointmentContextMenu
      row={contextMenu.row}
      position={contextMenu.position}
      theme={theme}
      onClose={() => setContextMenu({ open: false, row: null, position: { x: 0, y: 0 } })}
      onAction={handleContextMenuAction} />

    }

    {/* Модуль оплаты */}
    <PaymentManager
      isOpen={showPaymentManager}
      onClose={(result: unknown) => {
        setShowPaymentManager(false);
        if ((result as Record<string, unknown>)?.success) {
          // Обновляем данные после успешной оплаты
          loadAppointments();
          loadIntegratedData();
        }
      }} />


    {/* ✅ Форс-мажор модальное окно */}
    <ForceMajeureModal
      isOpen={forceMajeureModal.open}
      onClose={() => setForceMajeureModal({ open: false, specialistId: null, specialistName: '' })}
      specialistId={forceMajeureModal.specialistId}
      specialistName={forceMajeureModal.specialistName}
      onSuccess={(action, result) => {
        logger.info('[RegistrarPanel] Force majeure action completed:', action, result);
        notify.success(action === 'transfer' ? tI18n('registrarPanel.rp_notify_force_majeure_transfer') : tI18n('registrarPanel.rp_notify_force_majeure_cancel'));
        loadAppointments({ source: 'force_majeure' });
      }} />
  </>
);

export default RegistrarDialogsLayer;
