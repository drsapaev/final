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
      const result = await runRegistrarRecordAction(appointment, 'start_visit');
      if (!result) return null;
      if (!result.success) {
        throw new Error(result.results?.find((item: Record<string, unknown>) => !item.success)?.error || 'start_visit_failed');
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

      const result = await runRegistrarRecordAction(record, requiredBackendAction, { reason });
      if (!result) return null;
      if (!result.success) {
        throw new Error(result.results?.find((item: Record<string, unknown>) => !item.success)?.error || 'status_update_failed');
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
