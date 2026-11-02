/**
 * Registrar Panel — record action handlers hook.
 *
 * Decomposition step 5: extracted from RegistrarPanel.jsx.
 *
 * Extracted functions:
 * - runRegistrarRecordAction: posts to /registrar/records/actions batch
 *   endpoint. Validates record refs and backend action availability
 *   before calling API.
 * - handleStartVisit: wraps runRegistrarRecordAction for 'start_visit'.
 *   Shows success/error toast, reloads appointments.
 * - handlePayment: wraps runRegistrarRecordAction for 'mark_paid'.
 *   Returns the confirmed server balance, propagates payment failures,
 *   and refreshes the worklist independently after a receipt is saved.
 * - updateAppointmentStatus: maps status string to backend action,
 *   calls runRegistrarRecordAction, reloads appointments.
 *
 * NOT extracted (remain in RegistrarPanel — simple state setters):
 * - openRecordPreview: just calls setRecordPreviewDialog({open: true, row})
 * - openRecordEditor: just calls setWizardEditMode/InitialData/ShowWizard
 * - handleContextMenuAction: switch statement calling the above + setters
 *
 * @param {Object} deps
 * @param {Array} deps.appointments - current appointments array
 * @param {Function} deps.loadAppointments - reload function
 */
import { useCallback } from 'react';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import notify from '../../services/notify';
import { getErrorMessage } from '../../utils/errorHandler';
import {
  getRegistrarRecordRefs,
  findRegistrarRecordBySelectionKey,
  hasBackendAction,
  getRegistrarActionForStatus,
} from './registrarHelpers';
import type { RegistrarRecordLike } from './registrarHelpers';
import type { RegistrarPaymentInput, RegistrarPaymentSummary } from '../../api/registrarPayments';

/**
 * REG-FE-015 (audit #3803): серверный /registrar/records/actions батч
 * исполняется по-записи и не атомарен — success_count>0 при failed_count>0
 * означает, что часть записей УЖЕ изменена. Результат батча классифицируется
 * до какого-либо пользовательского сообщения.
 */
type RegistrarBatchResult = {
  success?: boolean;
  success_count?: number;
  failed_count?: number;
  results?: { success?: boolean; error?: string }[];
};

type RegistrarBatchOutcome =
  | { kind: 'all_success' }
  | { kind: 'partial'; successCount: number; failedCount: number }
  | { kind: 'failed' };

export const classifyRegistrarBatchResult = (result: RegistrarBatchResult): RegistrarBatchOutcome => {
  const successCount = Number(result?.success_count ?? 0);
  const failedCount = Number(result?.failed_count ?? 0);
  if (result?.success && failedCount === 0) return { kind: 'all_success' };
  if (successCount > 0 && failedCount > 0) return { kind: 'partial', successCount, failedCount };
  return { kind: 'failed' };
};

export const useRegistrarActions = ({ appointments, loadAppointments }: {
  appointments: unknown[];
  loadAppointments: (opts?: Record<string, unknown>) => Promise<void> | void;
}) => {
  const runRegistrarRecordAction = useCallback(async (record: Record<string, unknown>, action: string, payload: Record<string, unknown> = {}) => {
    const records = getRegistrarRecordRefs(record);
    if (records.length === 0) {
      logger.warn('RegistrarPanel: action requires backend record refs', { action });
      notify.error('Недостаточно данных для выполнения действия');
      return null;
    }
    if (!hasBackendAction(record, action)) {
      logger.warn('RegistrarPanel: backend did not expose requested action', { action });
      notify.error('Действие недоступно для этой записи');
      return null;
    }

    const response = await api.post('/registrar/records/actions', {
      ...payload,
      action,
      records,
    });
    return response.data;
  }, []);

  const handleStartVisit = useCallback(async (appointment: Record<string, unknown>) => {
    try {
      const result = await runRegistrarRecordAction(appointment, 'start_visit') as RegistrarBatchResult | null;
      if (!result) return null;
      const batch = classifyRegistrarBatchResult(result);
      if (batch.kind === 'failed') {
        throw new Error(result.results?.find((item: { success?: boolean }) => !item.success)?.error || 'start_visit_failed');
      }
      if (batch.kind === 'partial') {
        // REG-FE-015: часть записей уже изменена сервером — выравниваем
        // ворклист по каноническому read-model и честно сообщаем частичный
        // результат. Сбой обновления не превращает частичный успех в ошибку.
        await Promise.resolve(loadAppointments({ source: 'start_visit_partial' }))
          .catch(() => logger.warn('RegistrarPanel: refresh after partial start_visit failed'));
        notify.warning(`Команда выполнена частично: успешно ${batch.successCount}, отклонено ${batch.failedCount}`);
        return result;
      }

      logger.info('RegistrarPanel: start_visit completed through backend command contract', result);
      notify.success('Пациент вызван в кабинет');
      await loadAppointments({ source: 'start_visit_success' });
      return result;
    } catch (error) {
      logger.error('RegistrarPanel: Start visit API error:', error);
      notify.error(getErrorMessage(error, 'Could not start visit. Check connection and try again.'));
      return null;
    }
  }, [loadAppointments, runRegistrarRecordAction]);

  const handlePayment = useCallback(async (appointment: Record<string, unknown>, paymentData: RegistrarPaymentInput): Promise<RegistrarPaymentSummary> => {
    const result = await runRegistrarRecordAction(appointment, 'mark_paid', paymentData as unknown as Record<string, unknown>);
    if (!result?.success || Number(result.failed_count) > 0 || !result.payment_summary) {
      throw new Error('Payment was not confirmed. Refresh payment details.');
    }
    // A failed refresh must not turn a committed receipt into a retryable payment.
    void Promise.resolve().then(() => loadAppointments({ silent: true, source: 'payment_success' }))
      .catch(() => logger.warn('RegistrarPanel: refresh after payment failed'));
    return result.payment_summary;
  }, [loadAppointments, runRegistrarRecordAction]);
  const updateAppointmentStatus = useCallback(async (recordSelectionKey: unknown, status: string, reason = '', sourceRecord: Record<string, unknown> | null = null) => {
    try {
      const record = sourceRecord || findRegistrarRecordBySelectionKey(appointments as unknown as RegistrarRecordLike[], String(recordSelectionKey ?? ''));
      const requiredBackendAction = getRegistrarActionForStatus(status);
      if (!requiredBackendAction) {
        logger.warn('RegistrarPanel: unsupported status command', { recordSelectionKey, status, record });
        notify.error('Действие недоступно для этой записи');
        return null;
      }
      if (!record) {
        logger.warn('RegistrarPanel: selected record is missing for status command', { recordSelectionKey, status });
        notify.error('Действие недоступно для этой записи');
        return null;
      }

      const result = await runRegistrarRecordAction(record, requiredBackendAction, { reason }) as RegistrarBatchResult | null;
      if (!result) return null;
      const batch = classifyRegistrarBatchResult(result);
      if (batch.kind === 'failed') {
        throw new Error(result.results?.find((item: { success?: boolean }) => !item.success)?.error || 'status_update_failed');
      }
      if (batch.kind === 'partial') {
        // REG-FE-015: см. handleStartVisit — частичный батч требует
        // реконсиляции списка и правдивого сообщения, а не только ошибки.
        await Promise.resolve(loadAppointments({ source: 'status_update_partial' }))
          .catch(() => logger.warn('RegistrarPanel: refresh after partial status update failed'));
        notify.warning(`Статус обновлён частично: успешно ${batch.successCount}, отклонено ${batch.failedCount}`);
        return result;
      }

      await loadAppointments({ source: 'status_update' });
      notify.success('Статус обновлён');
      return result;
    } catch (error) {
      logger.error('RegistrarPanel: Update status error:', error);
      notify.error(getErrorMessage(error, 'Не удалось обновить статус. Проверьте соединение и попробуйте снова.'));
      return null;
    }
  }, [appointments, loadAppointments, runRegistrarRecordAction]);

  return {
    runRegistrarRecordAction,
    handleStartVisit,
    handlePayment,
    updateAppointmentStatus,
  };
};

export default useRegistrarActions;
