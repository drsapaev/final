/**
 * Registrar Panel — reschedule logic hook.
 *
 * Decomposition step: extracted from RegistrarPanel.jsx (lines 477-510).
 *
 * Three helpers:
 * - getRescheduleVisitIds(appointmentRow): REG-FE-041 (#3820) — the full
 *   ordered list of candidate visit ids for reschedule. A grouped row
 *   (multi-visit wizard booking) carries several ids in visit_ids; a plain
 *   row has visit_id/visitId. The dialog uses this list to require an
 *   EXPLICIT target-visit choice instead of silently picking the first one.
 * - resolveRescheduleVisitId(appointmentRow): returns the canonical visit id
 *   to use for reschedule API calls. Looks at visit_ids[0], visit_id,
 *   visitId in that order. (Kept for single-visit consumers; grouped rows
 *   must NOT use it — see getRescheduleVisitIds.)
 * - removeRescheduledAppointmentFromView(appointmentRow, visitId): optimistically
 *   removes the rescheduled appointment from the local state. Collects all
 *   possible IDs (id, visit_id, visitId, appointment_id, queue_entry_id,
 *   visit_ids[], appointment_ids[], queue_entry_ids[], aggregated_ids[])
 *   and filters them out of the appointments array. For a GROUPED row
 *   (visit_ids with more than one entry) nothing is removed — only one
 *   visit moved, the remaining visits must stay visible, and the backend
 *   read model (refreshed by loadAppointments) owns the grouping truth.
 *
 * @param {Function} setAppointments - state setter for appointments array
 */
import { useCallback } from 'react';

export const useRegistrarReschedule = ({ setAppointments }: {
  setAppointments: (updater: (prev: Record<string, unknown>[]) => Record<string, unknown>[]) => void;
}) => {
  // REG-FE-041 (#3820): expose every candidate visit so the reschedule
  // dialog can make the target-visit choice explicit. Never silently
  // reduce a group to its first visit id.
  const getRescheduleVisitIds = useCallback((appointmentRow: Record<string, unknown>): unknown[] => {
    const visitIds = Array.isArray(appointmentRow?.visit_ids)
      ? (appointmentRow.visit_ids as unknown[]).filter(
          (id) => id !== null && id !== undefined && id !== '')
      : [];
    if (visitIds.length > 0) return visitIds;
    const single = appointmentRow?.visit_id ?? appointmentRow?.visitId ?? null;
    return single !== null && single !== undefined ? [single] : [];
  }, []);

  const resolveRescheduleVisitId = useCallback((appointmentRow: Record<string, unknown>) => {
    const visitIds = appointmentRow?.visit_ids as unknown[] | undefined;
    return visitIds?.[0] ||
           appointmentRow?.visit_id ||
           appointmentRow?.visitId ||
           null;
  }, []);

  const removeRescheduledAppointmentFromView = useCallback((appointmentRow: Record<string, unknown>, visitId: unknown) => {
    if (!appointmentRow) return;

    // REG-FE-041 (#3820): a grouped row carries several visits, but only ONE
    // of them was rescheduled. Removing the whole group row would imply the
    // entire group moved and would hide the remaining visits from the
    // registrar. Keep the row on screen; the caller's loadAppointments
    // refresh rebuilds it from the canonical backend read model.
    const groupVisitIds = Array.isArray(appointmentRow.visit_ids)
      ? (appointmentRow.visit_ids as unknown[]).filter(
          (id) => id !== null && id !== undefined && id !== '')
      : [];
    if (groupVisitIds.length > 1) return;

    const idsToRemove = new Set<string>();
    [
      appointmentRow.id,
      appointmentRow.visit_id,
      appointmentRow.visitId,
      appointmentRow.appointment_id,
      appointmentRow.queue_entry_id,
      visitId,
    ].forEach((id: unknown) => {
      if (id !== undefined && id !== null) {
        idsToRemove.add(String(id));
      }
    });

    [
      appointmentRow.visit_ids,
      appointmentRow.appointment_ids,
      appointmentRow.queue_entry_ids,
    ].forEach((ids: unknown) => {
      if (Array.isArray(ids)) {
        ids.forEach((id: unknown) => {
          if (id !== undefined && id !== null) {
            idsToRemove.add(String(id));
          }
        });
      }
    });

    if (Array.isArray(appointmentRow.aggregated_ids)) {
      (appointmentRow.aggregated_ids as unknown[]).forEach((id: unknown) => {
        if (id !== undefined && id !== null) {
          idsToRemove.add(String(id));
        }
      });
    }

    setAppointments((prev: Record<string, unknown>[]) => prev.filter((apt: Record<string, unknown>) => {
      const candidateIds = [
        apt.id,
        apt.visit_id,
        apt.visitId,
        apt.appointment_id,
        apt.queue_entry_id,
      ];
      return !candidateIds.some((id: unknown) =>
        id !== undefined && id !== null && idsToRemove.has(String(id))
      );
    }));
  }, [setAppointments]);

  return {
    getRescheduleVisitIds,
    resolveRescheduleVisitId,
    removeRescheduledAppointmentFromView,
  };
};

export default useRegistrarReschedule;
