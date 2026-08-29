/**
 * Registrar Panel — row-action routing hook (table + context menu).
 *
 * PR-UI-13-5: extracts openRecordPreview / openRecordEditor /
 * handleTableAction / handleContextMenuAction from RegistrarPanel.tsx
 * (verbatim port — plan §PR-UI-13 "separation of responsibilities without
 * behavior change"). These are the two row-level command routers:
 * - handleTableAction — EnhancedAppointmentsTable onActionClick routing
 *   (view/edit/payment/in_cabinet/call/complete/print/reschedule/cancel/more)
 * - handleContextMenuAction — AppointmentContextMenu onAction routing
 *   (same set + call_patient tel: link + force_majeure modal)
 *
 * Confirm-gated branches (UX Audit Registrar #2 / R-1.2) keep the shared
 * useConfirm hook; in_cabinet/complete in the context-menu variant also
 * notify on success exactly like the original inline panel code.
 */
import { useCallback } from 'react';
import notify from '../../services/notify';
import logger from '../../utils/logger';
import type { Appointment } from '../../types/domain/clinic';
import { isMultiRecordAggregateRow } from './registrarHelpers';
import type {
  CancelDialogState,
  ContextMenuState,
  ForceMajeureModalState,
  PaymentDialogState,
  PrintDialogState,
  RecordPreviewDialogState,
} from './useRegistrarDialogs';

export interface UseRegistrarRowActionsParams {
  /** useConfirm() raw confirm callback (P-013: shared ConfirmDialog). */
  confirm: (options: Record<string, unknown>) => Promise<boolean>;
  /** Unified i18n t (registrar.* namespace for confirm/notify strings). */
  tI18n: (key: string, options?: Record<string, unknown>) => string;
  /** useRegistrarActions().updateAppointmentStatus */
  updateAppointmentStatus: (
    recordSelectionKey: unknown,
    status: string,
    reason?: string,
    sourceRecord?: Record<string, unknown> | null,
  ) => Promise<void> | void;
  /** useRegistrarActions().handleStartVisit */
  handleStartVisit: (appointment: Record<string, unknown>) => Promise<void> | void;
  /** Dialog setter shims from useRegistrarDialogs(). */
  setRecordPreviewDialog: (value: RecordPreviewDialogState) => void;
  setPaymentDialog: (value: PaymentDialogState) => void;
  setPrintDialog: (value: PrintDialogState) => void;
  setCancelDialog: (value: CancelDialogState) => void;
  setContextMenu: (value: ContextMenuState) => void;
  setForceMajeureModal: (value: ForceMajeureModalState) => void;
  openRescheduleDialog: (data: Record<string, unknown>) => void;
  /** Wizard setters from useRegistrarWizard(). */
  setWizardEditMode: (value: boolean) => void;
  setWizardInitialData: (value: Record<string, unknown> | null) => void;
  setShowWizard: (value: boolean) => void;
}

export function useRegistrarRowActions({
  confirm,
  tI18n,
  updateAppointmentStatus,
  handleStartVisit,
  setRecordPreviewDialog,
  setPaymentDialog,
  setPrintDialog,
  setCancelDialog,
  setContextMenu,
  setForceMajeureModal,
  openRescheduleDialog,
  setWizardEditMode,
  setWizardInitialData,
  setShowWizard,
}: UseRegistrarRowActionsParams) {
  const openRecordPreview = useCallback((row: unknown) => {
    setRecordPreviewDialog({ open: true, row: row as Appointment });
  }, [setRecordPreviewDialog]);

  const openRecordEditor = useCallback((row: unknown) => {
    const appt = row as Appointment;
    if (isMultiRecordAggregateRow(appt as Record<string, unknown>)) {
      logger.info('[RegistrarPanel] Opening edit wizard for aggregate all-departments row', {
        patient: appt?.patient_fio || appt?.patient_name,
        groupedRecords: appt?.grouped_records?.length || 0,
        recordRefs: appt?.grouped_record_refs?.length || 0,
        aggregatedIds: appt?.aggregated_ids?.length || 0
      });
    }

    // UX Audit R-3.6: убрано логирование patient_fio (PII leak).
    logger.info('[RegistrarPanel] Opening edit wizard for appointment:', appt?.id);
    setWizardEditMode(true);
    setWizardInitialData(appt as Record<string, unknown>);
    setShowWizard(true);
  }, [setWizardEditMode, setWizardInitialData, setShowWizard]);

  // PR-UI-13-4: table row-action routing extracted from the EAT JSX prop into
  // a callback — verbatim switch body. PR-UI-13-5: moved from the panel into
  // this hook; passed to WorklistView as onActionClick.
  const handleTableAction = useCallback(async (action: string, row: Record<string, unknown>, event?: unknown) => {
    switch (action) {
        case 'view':
          logger.info('Просмотр записи:', row);
          openRecordPreview(row as unknown as Appointment);
          break;
        case 'edit':
          // UX Audit R-3.6: убрано логирование patient_fio (PII leak).
          logger.info('[RegistrarPanel] Открытие мастера редактирования для appointment:', row.id);
          openRecordEditor(row);
          break;
        case 'payment':
          logger.info('Открытие модального окна оплаты для записи:', row);
          setPaymentDialog({ open: true, row: row as unknown as Appointment, paid: false, source: 'table' });
          break;
        case 'in_cabinet': {
          // UX Audit Registrar #2: window.confirm() → useConfirm hook.
          // Раньше: if (!window.confirm(`Отправить пациента "..." в кабинет?`)) break;
          // Теперь: macOS-style ConfirmDialog через useConfirm.
          const inCabinetName = row.patient_fio || row.patient_name || '';
          const inCabinetOk = await confirm({
            title: tI18n('registrar.send_to_cabinet_title'),
            message: tI18n('registrar.send_to_cabinet_message', { name: inCabinetName }),
            confirmLabel: tI18n('registrar.send_to_cabinet_confirm'),
            cancelLabel: tI18n('registrar.cancel'),
            intent: 'primary',
          });
          if (!inCabinetOk) break;
          logger.info('Отправка пациента в кабинет:', row);
          updateAppointmentStatus(row.id, 'in_cabinet', '', row as Record<string, unknown>);
          break;
        }
        case 'call':
          logger.info('Вызов пациента:', row);
          handleStartVisit(row as Record<string, unknown>);
          break;
        case 'complete': {
          // UX Audit Registrar #2: window.confirm() → useConfirm hook.
          const completeName = row.patient_fio || row.patient_name || '';
          const completeOk = await confirm({
            title: tI18n('registrar.complete_visit_title'),
            message: tI18n('registrar.complete_visit_message', { name: completeName }),
            confirmLabel: tI18n('registrar.complete_visit_confirm'),
            cancelLabel: tI18n('registrar.cancel'),
            intent: 'primary',
          });
          if (!completeOk) break;
          logger.info('Завершение приёма:', row);
          updateAppointmentStatus(row.id, 'done', '', row as Record<string, unknown>);
          break;
        }
        case 'print':
          logger.info('Печать талона:', row);
          setPrintDialog({ open: true, type: 'ticket', data: row as Record<string, unknown> });
          break;
        // UX Audit Registrar #4: cancel и reschedule теперь доступны
        // как inline кнопки, а не только через context menu.
        case 'reschedule':
          // PR-UI-13-3: former setRescheduleData(row) + setShowSlotsModal(true)
          // consolidated into one reducer action.
          openRescheduleDialog(row as Record<string, unknown>);
          break;
        case 'cancel':
          setCancelDialog({ open: true, row: row as unknown as Appointment, reason: '' });
          break;
        case 'more':{
            // Показать контекстное меню с дополнительными действиями
            const evt = event as { target?: HTMLElement; clientX?: number; clientY?: number } | undefined;
            const rect = evt?.target?.getBoundingClientRect();
            setContextMenu({
              open: true,
              row,
              position: {
                x: rect?.right || evt?.clientX || 0,
                y: rect?.top || evt?.clientY || 0
              }
            });
            break;
          }
        default:
          break;
    }
  }, [openRecordPreview, openRecordEditor, confirm, updateAppointmentStatus, handleStartVisit, setPaymentDialog, setPrintDialog, setCancelDialog, setContextMenu, openRescheduleDialog]);

  const handleContextMenuAction = useCallback(async (action: string, row: Appointment) => {
    switch (action) {
      case 'view':
        openRecordPreview(row as unknown as Appointment);
        break;
      case 'edit':
        openRecordEditor(row);
        logger.info('Редактирование записи:', row);
        break;
      case 'in_cabinet': {
        // UX Audit R-1.2: добавлен confirm для критичных действий в context menu.
        // Раньше: handleContextMenuAction вызывал updateAppointmentStatus напрямую,
        // без подтверждения. В то же время inline onActionClick в таблице требовал
        // confirm. Это нарушение Nielsen #4 (consistency) + #5 (error prevention).
        const inCabinetName = row.patient_fio || row.patient_name || '';
        const inCabinetOk = await confirm({
          title: tI18n('registrar.send_to_cabinet_title'),
          message: tI18n('registrar.send_to_cabinet_message', { name: inCabinetName }),
          confirmLabel: tI18n('registrar.send_to_cabinet_confirm'),
          cancelLabel: tI18n('registrar.cancel'),
          intent: 'primary',
        });
        if (!inCabinetOk) break;
        await updateAppointmentStatus(row.id, 'in_cabinet', '', row as Record<string, unknown>);
        notify.success(tI18n('registrar.sent_to_cabinet'));
        break;
      }
      case 'call':
        await handleStartVisit(row as Record<string, unknown>);
        break;
      case 'complete': {
        // UX Audit R-1.2: confirm для завершения приёма в context menu.
        const completeName = row.patient_fio || row.patient_name || '';
        const completeOk = await confirm({
          title: tI18n('registrar.complete_visit_title'),
          message: tI18n('registrar.complete_visit_message', { name: completeName }),
          confirmLabel: tI18n('registrar.complete_visit_confirm'),
          cancelLabel: tI18n('registrar.cancel'),
          intent: 'primary',
        });
        if (!completeOk) break;
        await updateAppointmentStatus(row.id, 'done', '', row as Record<string, unknown>);
        notify.success(tI18n('registrar.visit_completed'));
        break;
      }
      case 'payment':
        setPaymentDialog({ open: true, row: row as unknown as Appointment, paid: false, source: 'context' });
        break;
      case 'print':
        setPrintDialog({ open: true, type: 'ticket', data: row as Record<string, unknown> });
        break;
      case 'reschedule':
        // PR-UI-13-3: former setRescheduleData(row) + setShowSlotsModal(true)
        // consolidated into one reducer action.
        openRescheduleDialog(row as Record<string, unknown>);
        break;
      case 'cancel':
        setCancelDialog({ open: true, row: row as unknown as Appointment, reason: '' });
        break;
      case 'call_patient':
        if (row.patient_phone) {
          // R-24 fix: санитизация tel: URL — оставляем только digits и +.
          // Предотвращает injection через специальные символы в phone field.
          const sanitizedPhone = String(row.patient_phone).replace(/[^\d+]/g, '');
          // UX Audit R-2.5: используем нативный <a> anchor вместо window.open().
          // window.open() может блокироваться браузером как pop-up, т.к. этот
          // handler вызывается не из прямого user-gesture (через context menu).
          // Нативный anchor — стандартный паттерн для tel: ссылок.
          const link = document.createElement('a');
          link.href = `tel:${sanitizedPhone}`;
          link.style.display = 'none';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        }
        break;
      case 'force_majeure':
        // Открываем модальное окно форс-мажора для специалиста
        setForceMajeureModal({
          open: true,
          specialistId: row.doctor_id || row.specialist_id || null,
          specialistName: row.doctor_name || row.specialist_name || tI18n('registrarPanel.rp_all_specialists')
        });
        break;
      default:
        logger.info('Неизвестное действие:', action);
        break;
    }
  }, [updateAppointmentStatus, handleStartVisit, openRecordPreview, openRecordEditor, confirm, setPaymentDialog, setPrintDialog, setCancelDialog, setForceMajeureModal, openRescheduleDialog]);

  return {
    openRecordPreview,
    openRecordEditor,
    handleTableAction,
    handleContextMenuAction,
  };
}

export default useRegistrarRowActions;
