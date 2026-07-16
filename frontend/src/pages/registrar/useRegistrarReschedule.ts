/**
 * Registrar Panel — reschedule logic hook.
 *
 * Decomposition step: extracted from RegistrarPanel.jsx (lines 477-510).
 *
 * Two helpers:
 * - resolveRescheduleVisitId(appointmentRow): returns the canonical visit id
 *   to use for reschedule API calls. Looks at visit_ids[0], visit_id,
 *   visitId in that order.
 * - removeRescheduledAppointmentFromView(appointmentRow, visitId): optimistically
 *   removes the rescheduled appointment from the local state. Collects all
 *   possible IDs (id, visit_id, visitId, appointment_id, queue_entry_id,
 *   visit_ids[], appointment_ids[], queue_entry_ids[], aggregated_ids[])
 *   and filters them out of the appointments array.
 *
 * @param {Function} setAppointments - state setter for appointments array
 */
import { useCallback } from 'react';

export const useRegistrarReschedule = ({ setAppointments }) => {
  const resolveRescheduleVisitId = useCallback((appointmentRow) => {
    return appointmentRow?.visit_ids?.[0] ||
           appointmentRow?.visit_id ||
           appointmentRow?.visitId ||
           null;
  }, []);

  const removeRescheduledAppointmentFromView = useCallback((appointmentRow, visitId) => {
    if (!appointmentRow) return;

    const idsToRemove = new Set();
    [
      appointmentRow.id,
      appointmentRow.visit_id,
      appointmentRow.visitId,
      appointmentRow.appointment_id,
      appointmentRow.queue_entry_id,
      visitId,
    ].forEach((id) => {
      if (id !== undefined && id !== null) {
        idsToRemove.add(String(id));
      }
    });

    [
      appointmentRow.visit_ids,
      appointmentRow.appointment_ids,
      appointmentRow.queue_entry_ids,
    ].forEach((ids) => {
      if (Array.isArray(ids)) {
        ids.forEach((id) => {
          if (id !== undefined && id !== null) {
            idsToRemove.add(String(id));
          }
        });
      }
    });

    if (Array.isArray(appointmentRow.aggregated_ids)) {
      appointmentRow.aggregated_ids.forEach((id) => {
        if (id !== undefined && id !== null) {
          idsToRemove.add(String(id));
        }
      });
    }

    setAppointments((prev) => prev.filter((apt) => {
      const candidateIds = [
        apt.id,
        apt.visit_id,
        apt.visitId,
        apt.appointment_id,
        apt.queue_entry_id,
      ];
      return !candidateIds.some((id) =>
        id !== undefined && id !== null && idsToRemove.has(String(id))
      );
    }));
  }, [setAppointments]);

  return {
    resolveRescheduleVisitId,
    removeRescheduledAppointmentFromView,
  };
};

export default useRegistrarReschedule;
