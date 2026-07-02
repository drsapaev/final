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
 *   Handles partial success (some records already paid), shows toast,
 *   silent reload after 800ms.
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

export const useRegistrarActions = ({ appointments, loadAppointments }) => {
  const runRegistrarRecordAction = useCallback(async (record, action, payload = {}) => {
    const records = getRegistrarRecordRefs(record);
    if (records.length === 0) {
      logger.warn('RegistrarPanel: action requires backend record refs', { action, record });
      notify.error('Missing backend record data for action');
      return null;
    }
    if (!hasBackendAction(record, action)) {
      logger.warn('RegistrarPanel: backend did not expose requested action', { action, record });
      notify.error('Action is not available for this record');
      return null;
    }

    const response = await api.post('/registrar/records/actions', {
      ...payload,
      action,
      records,
    });
    return response.data;
  }, []);

  const handleStartVisit = useCallback(async (appointment) => {
    try {
      const result = await runRegistrarRecordAction(appointment, 'start_visit');
      if (!result) return null;
      if (!result.success) {
        throw new Error(result.results?.find((item) => !item.success)?.error || 'start_visit_failed');
      }

      logger.info('RegistrarPanel: start_visit completed through backend command contract', result);
      notify.success('Patient called successfully');
      await loadAppointments({ source: 'start_visit_success' });
      return result;
    } catch (error) {
      logger.error('RegistrarPanel: Start visit API error:', error);
      notify.error(getErrorMessage(error, 'Could not start visit. Check connection and try again.'));
      return null;
    }
  }, [loadAppointments, runRegistrarRecordAction]);

  const handlePayment = useCallback(async (appointment, paymentData = null) => {
    try {
      const result = await runRegistrarRecordAction(appointment, 'mark_paid', {
        amount: paymentData?.amount ?? null,
        method: paymentData?.method ?? null,
      });
      if (!result) return null;

      const successCount = Number(result.success_count || 0);
      const skippedCount = Number(result.skipped_count || 0);
      const failedCount = Number(result.failed_count || 0);

      if (successCount > 0 || skippedCount > 0) {
        const message = skippedCount > 0
          ? 'Payment completed: ' + successCount + ', already paid: ' + skippedCount
          : 'Payment completed: ' + successCount;
        notify.success(failedCount > 0 ? message + '. Failed: ' + failedCount : message);
        setTimeout(() => loadAppointments({ silent: true, source: 'payment_success' }), 800);
        return result.results || [];
      }

      notify.error(result.results?.find((item) => !item.success)?.error || 'Payment failed');
      return result.results || [];
    } catch (error) {
      logger.error('RegistrarPanel: Payment error:', error);
      notify.error(getErrorMessage(error, 'Payment failed'));
      return null;
    }
  }, [loadAppointments, runRegistrarRecordAction]);

  const updateAppointmentStatus = useCallback(async (recordSelectionKey, status, reason = '', sourceRecord = null) => {
    try {
      const record = sourceRecord || findRegistrarRecordBySelectionKey(appointments, recordSelectionKey);
      const requiredBackendAction = getRegistrarActionForStatus(status);
      if (!requiredBackendAction) {
        logger.warn('RegistrarPanel: unsupported status command', { recordSelectionKey, status, record });
        notify.error('Action is not available for this record');
        return null;
      }
      if (!record) {
        logger.warn('RegistrarPanel: selected record is missing for status command', { recordSelectionKey, status });
        notify.error('Action is not available for this record');
        return null;
      }

      const result = await runRegistrarRecordAction(record, requiredBackendAction, { reason });
      if (!result) return null;
      if (!result.success) {
        throw new Error(result.results?.find((item) => !item.success)?.error || 'status_update_failed');
      }

      await loadAppointments({ source: 'status_update' });
      notify.success('Status updated');
      return result;
    } catch (error) {
      logger.error('RegistrarPanel: Update status error:', error);
      notify.error(getErrorMessage(error, 'Could not update status. Check connection and try again.'));
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
