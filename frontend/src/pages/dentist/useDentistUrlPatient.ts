import { useEffect, useRef } from 'react';

import logger from '../../utils/logger';
import { normalizeNumericId } from '../../utils/doctorPanelShared';
import { apiClient } from '../../api/client';
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
 *
 * DENTURL-FE-002 (audit 3892): every async resolution is bound to the URL
 * target it was started for AND to the selection state at resolution time.
 * A URL change or unmount cancels the run; a manual navigation to another
 * patient/visit revokes the stale resolution — a slow older URL load can
 * never overwrite a newer selection.
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
  // Live view of the panel's selection for resolution-time checks (the
  // effect deps intentionally omit it — the verbatim PR-UI-15-6 contract).
  const selectedPatientRef = useRef(selectedPatient);
  selectedPatientRef.current = selectedPatient;

  // ✅ Автоматическая загрузка пациента из URL параметра patientId
  useEffect(() => {
    // DENTURL-FE-002 (audit 3892): cancellation for URL changes/unmount.
    let cancelled = false;

    const loadPatientFromUrl = async () => {
      // P-009: patientIdFromUrl / visitIdFromUrl come from useDoctorPanelState
      if (!patientIdFromUrl && !visitIdFromUrl) return;

      // The selection state observed when this run started. A resolution is
      // stale when the selection has since moved to a DIFFERENT target than
      // the one this URL run is about to select (manual navigation wins).
      const startedSelection = selectedPatientRef.current;
      const staleResolution = () => {
        const current = selectedPatientRef.current;
        if (!current || current === startedSelection) return false;
        if (patientIdFromUrl) {
          return String(current.patient_id ?? '') !== String(patientIdFromUrl);
        }
        if (visitIdFromUrl) {
          return String(normalizeNumericId(current.visit_id) ?? '') !== String(visitIdFromUrl);
        }
        return false;
      };

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
          // DENTURL-FE-002 (audit 3892): the URL or the selection may have
          // moved on while the queue refresh was in flight.
          if (cancelled || staleResolution()) return;
          matchingAppointment = findMatchingAppointment(refreshedAppointments || []);
        }

        if (matchingAppointment) {
          if (cancelled || staleResolution()) return;
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
          logger.info('[Dentist] Загружен пациент из URL');
          return;
        }

        if (visitIdFromUrl || patientIdFromUrl) {
          if (patientIdFromUrl) {
            if (cancelled || staleResolution()) return;
            // Patient-scoped deep link: the patient id in the URL is the
            // canonical identity — keep the historical safe fallback.
            const fallbackLabel = tI18n('dental.dental_panel_patient_url_fallback', { id: patientIdFromUrl });

            const patientObj: SelectedPatient = {
              id: patientIdFromUrl,
              patient_id: patientIdFromUrl,
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
              logger.info('[Dentist] Пациент из URL не найден в очереди, использую безопасный URL-fallback');
            }
            return;
          }

          // DENTURL-FE-001 (audit 3892): visitId-only deep link. Never
          // fabricate patient_id from the visit id — ids from distinct tables
          // are not interchangeable. Resolve the authoritative patient/visit
          // relationship through an authorized EMR read and fail closed
          // (no selection) when the visit is missing, unauthorized or carries
          // no patient identity.
          try {
            const response = await apiClient.get(`/v2/emr/${visitIdFromUrl}`, {
              silent: true,
              validateStatus: (status: number) => status === 404 || (status >= 200 && status < 300),
            } as Record<string, unknown>) as { status?: number; data?: { patient_id?: unknown } };
            if (cancelled || staleResolution()) return;
            const authoritativePatientId = response?.data?.patient_id;
            const visitResolved =
              response && response.status !== 404 && response.status !== undefined && response.status < 400 &&
              authoritativePatientId !== null && authoritativePatientId !== undefined &&
              (typeof authoritativePatientId === 'number' || typeof authoritativePatientId === 'string');

            if (!visitResolved) {
              const fallbackLogKey = `${patientIdFromUrl || ''}:${visitIdFromUrl || ''}`;
              if (!dentistCache.fallbackLoggedKeys.has(fallbackLogKey)) {
                dentistCache.fallbackLoggedKeys.add(fallbackLogKey);
                logger.warn('[Dentist] Визит из URL не разрешается к пациенту — выбор не изменён (fail-closed)');
              }
              return;
            }

            const fallbackLabel = tI18n('dental.dental_panel_visit_url_fallback', { id: visitIdFromUrl });
            const patientObj: SelectedPatient = {
              id: authoritativePatientId as string | number,
              patient_id: authoritativePatientId as string | number,
              appointment_id: null,
              visit_id: visitIdFromUrl,
              patient_name: fallbackLabel,
              patient_fio: fallbackLabel,
              phone: '',
              source: 'url',
              specialty: 'dental'
            };

            setSelectedPatient(patientObj);
            handleTabChange('visit');
            logger.info('[Dentist] Пациент из URL разрешён через авторизованный визит');
          } catch (_visitReadError: unknown) {
            logger.error('[Dentist] Не удалось разрешить визит из URL к пациенту');
          }
        }
      } catch (_error: unknown) {
        logger.error('[Dentist] Не удалось загрузить пациента из URL');
      }
    };

    loadPatientFromUrl();

    // DENTURL-FE-002 (audit 3892): a URL change or unmount revokes the
    // pending run — its late resolution can no longer touch the selection.
    return () => {
      cancelled = true;
    };
  }, [locationSearch, patientIdFromUrl, visitIdFromUrl, appointmentsTableData, loadDentistryAppointments]); // eslint-disable-line react-hooks/exhaustive-deps
}
