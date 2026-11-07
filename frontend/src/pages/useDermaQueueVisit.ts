/**
 * useDermaQueueVisit — DERMAQUEUE-FE-001 (audit 3892, post-merge group 10):
 * the dermatologist's live queue gets the same Start Visit handoff
 * dentistry already has (`useDentistActions.handleStartQueueVisit`).
 *
 * The handler resolves the canonical patient/visit identity through the
 * backend `POST /doctor/queue/{entry_id}/start-visit` acknowledgement and
 * fails closed on any unconfirmed or identity-less response — the panel
 * only ever opens an EMR context the server explicitly acknowledged.
 */
import { useCallback } from 'react';
import { queueService } from '../services/queue';
import notify from '../services/notify';
import { useTranslation } from '../i18n/useTranslation';

interface CalledQueuePatient {
  id?: unknown;
  name?: unknown;
  number?: unknown;
}

interface UseDermaQueueVisitDeps {
  selectPatient: (patient: Record<string, unknown>) => void;
}

export function useDermaQueueVisit({ selectPatient }: UseDermaQueueVisitDeps) {
  const { t } = useTranslation();

  return useCallback(async (calledPatient: CalledQueuePatient | null | undefined): Promise<boolean> => {
    if (
      !calledPatient ||
      calledPatient.id === null ||
      calledPatient.id === undefined ||
      calledPatient.id === ''
    ) {
      notify.error(t('derma.no_queue_id_for_visit'));
      return false;
    }

    const queueEntryId = calledPatient.id as string | number;
    try {
      const response = await queueService.startVisit(queueEntryId) as Record<string, unknown>;
      const patientId = response.patient_id as string | number | null | undefined;
      const visitId = response.visit_id as string | number | null | undefined;
      if (
        response.success !== true ||
        patientId === null ||
        patientId === undefined ||
        visitId === null ||
        visitId === undefined
      ) {
        notify.error(t('derma.derma_panel_start_visit_failed'));
        return false;
      }

      const patientName =
        (typeof calledPatient.name === 'string' && calledPatient.name) ||
        t('derma.derma_panel_patient_default');
      selectPatient({
        id: patientId,
        patient_id: patientId,
        visit_id: visitId,
        doctor_queue_entry_id: queueEntryId,
        queue_entry_id: queueEntryId,
        patient_name: patientName,
        patient_fio: patientName,
        number: (calledPatient.number as string | number | undefined) ?? null,
        source: 'queue',
        status: (typeof response.status === 'string' && response.status) || 'in_progress',
      });
      return true;
    } catch {
      notify.error(t('derma.derma_panel_start_visit_failed'));
      return false;
    }
  }, [selectPatient, t]);
}

export default useDermaQueueVisit;
