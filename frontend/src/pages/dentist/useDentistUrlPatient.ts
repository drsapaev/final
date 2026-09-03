import { useEffect } from 'react';

import logger from '../../utils/logger';
import { normalizeNumericId } from '../../utils/doctorPanelShared';
import type { Appointment } from '../../types/domain/clinic';
import { dentistCache, type SelectedPatient } from './dentistContracts';

/**
 * PR-UI-15-6: the ?patientId / ?visitId URL deep-link hydration effect —
 * verbatim move of the former DentistPanelUnified effect (registrar/cashier
 * decomposition precedent; deps array and eslint-disable preserved exactly).
 *
 * Behaviour: skips when nothing to load or the patient is already loaded;
 * matches the deep link against the current appointments table (refreshing
 * once if needed); falls back to a safe URL-fallback patient object (with a
 * once-per-key logger guard) so stale deep links never crash the panel.
 */
export function useDentistUrlPatient({
  locationSearch,
  patientIdFromUrl,
  visitIdFromUrl,
  selectedPatient,
  appointmentsTableData,
  loadDentistryAppointments,
  setSelectedPatient,
  handleTabChange,
  tI18n,
}: {
  locationSearch: string;
  patientIdFromUrl: number | null;
  visitIdFromUrl: number | null;
  selectedPatient: SelectedPatient | null;
  appointmentsTableData: Appointment[];
  loadDentistryAppointments: (forceRefresh?: boolean) => Promise<Appointment[]>;
  setSelectedPatient: (patient: SelectedPatient | Record<string, unknown> | null) => void;
  handleTabChange: (tab: string) => void;
  tI18n: (key: string, params?: Record<string, unknown>) => string;
}) {
  // ✅ Автоматическая загрузка пациента из URL параметра patientId
  useEffect(() => {
    const loadPatientFromUrl = async () => {
      // P-009: patientIdFromUrl / visitIdFromUrl come from useDoctorPanelState
      if (!patientIdFromUrl && !visitIdFromUrl) return;

      // Если пациент уже загружен с этим ID/визитом, пропускаем
      const currentPatientId = selectedPatient?.patient_id || null;
      const currentVisitId = normalizeNumericId(selectedPatient?.visit_id);
      if (
        patientIdFromUrl &&
        currentPatientId === patientIdFromUrl &&
        (!visitIdFromUrl || currentVisitId === visitIdFromUrl)
      ) {
        return;
      }
      if (
        visitIdFromUrl &&
        currentVisitId === visitIdFromUrl &&
        (!patientIdFromUrl || currentPatientId === patientIdFromUrl)
      ) {
        return;
      }

      try {
        const findMatchingAppointment = (appointments: Appointment[]) => {
          if (!Array.isArray(appointments)) {
            return null;
          }

          return appointments.find((appointment: Appointment) => {
            if (visitIdFromUrl && normalizeNumericId(appointment.visit_id) === visitIdFromUrl) {
              return true;
            }
            return patientIdFromUrl && String(appointment.patient_id) === String(patientIdFromUrl);
          }) || null;
        };

        let matchingAppointment = findMatchingAppointment(appointmentsTableData);
        if (!matchingAppointment) {
          const refreshedAppointments = await loadDentistryAppointments();
          matchingAppointment = findMatchingAppointment(refreshedAppointments || []);
        }

        if (matchingAppointment) {
          const patientName =
            matchingAppointment.patient_fio ||
            matchingAppointment.patient_name ||
            (matchingAppointment.name as string | undefined) ||
            tI18n('dental.dental_panel_patient_default');

          const patientObj: SelectedPatient = {
            id: (matchingAppointment.appointment_id as string | number | undefined) || matchingAppointment.id || patientIdFromUrl || visitIdFromUrl,
            patient_id: matchingAppointment.patient_id || patientIdFromUrl || matchingAppointment.id,
            appointment_id: (matchingAppointment.appointment_id as string | number | null | undefined) || null,
            visit_id: visitIdFromUrl || normalizeNumericId(matchingAppointment.visit_id) || null,
            patient_name: patientName,
            patient_fio: patientName,
            phone: matchingAppointment.patient_phone || (matchingAppointment.phone as string) || '',
            source: (matchingAppointment.source as string) || 'appointments',
            specialty: matchingAppointment.specialty || 'dental'
          };

          setSelectedPatient(patientObj);
          handleTabChange(patientObj.visit_id ? 'visit' : 'patients');
          logger.info('[Dentist] Загружен пациент из URL:', patientObj.patient_name);
          return;
        }

        if (visitIdFromUrl || patientIdFromUrl) {
          const fallbackLabel = patientIdFromUrl
            ? tI18n('dental.dental_panel_patient_url_fallback', { id: patientIdFromUrl })
            : tI18n('dental.dental_panel_visit_url_fallback', { id: visitIdFromUrl });

          const patientObj: SelectedPatient = {
            id: patientIdFromUrl || visitIdFromUrl,
            patient_id: patientIdFromUrl || visitIdFromUrl,
            appointment_id: null,
            visit_id: visitIdFromUrl || null,
            patient_name: fallbackLabel,
            patient_fio: fallbackLabel,
            phone: '',
            source: 'url',
            specialty: 'dental'
          };

          setSelectedPatient(patientObj);
          handleTabChange(visitIdFromUrl ? 'visit' : 'patients');
          const fallbackLogKey = `${patientIdFromUrl || ''}:${visitIdFromUrl || ''}`;
          if (!dentistCache.fallbackLoggedKeys.has(fallbackLogKey)) {
            dentistCache.fallbackLoggedKeys.add(fallbackLogKey);
            logger.info('[Dentist] Пациент из URL не найден в очереди, использую безопасный URL-fallback:', patientObj.patient_name);
          }
        }
      } catch (error: unknown) {
        logger.error('[Dentist] Не удалось загрузить пациента из URL:', error);
      }
    };

    loadPatientFromUrl();
  }, [locationSearch, patientIdFromUrl, visitIdFromUrl, appointmentsTableData, loadDentistryAppointments]); // eslint-disable-line react-hooks/exhaustive-deps
}
