import { useCallback, useEffect, useRef, useState } from 'react';

import { apiClient } from '../../api/client';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import { adaptTimeFields } from '../../utils/registrarAggregation';
import { isDentistrySpecialty } from '../../utils/dentistrySpecialty';
import { getAllPatientServices, makeEnsureCanonicalVisitId } from '../../utils/doctorPanelShared';
import { resolveCanonicalVisitId } from '../../utils/canonicalVisit';
import type { Appointment } from '../../types/domain/clinic';
import {
  buildPatientsFromAppointments,
  dentistCache,
  resolveDoctorQueueEntryId,
  type SelectedPatient,
} from './dentistContracts';

/**
 * PR-UI-15-3: the dentistry worklist data lifecycle extracted verbatim from
 * pages/DentistPanelUnified.tsx (registrar/cashier decomposition precedent).
 *
 * Owns:
 *  - patients / appointmentsTableData (+ ref) / appointmentsLoading / services state
 *  - loadServices (module-cached)
 *  - loadDentistryAppointments — /registrar/queues/today → dentistry-filtered
 *    Appointment[] with the SSOT queue DTO mapping (payment_status /
 *    canonical_status / available_actions / can_* guards /
 *    doctor_queue_entry_id — DoctorPanels.contract.test.tsx surface)
 *  - loadPatients (derived from appointments, P0-14 single-call semantics)
 *  - loadData mount lifecycle
 *  - the queueUpdated window-listener (refresh on 'appointments' tab)
 *  - ensureCanonicalVisitId (canonical visit resolution on row click)
 */
export function useDentistWorklistData({
  tI18n,
  activeTab,
}: {
  tI18n: (key: string, params?: Record<string, unknown>) => string;
  activeTab: string;
}) {
  const [patients, setPatients] = useState<SelectedPatient[]>([]);
  const [appointmentsTableData, setAppointmentsTableData] = useState<Appointment[]>([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [services, setServices] = useState<Record<string, unknown>>({});
  const appointmentsTableDataRef = useRef<Appointment[]>([]);
  const appointmentsLoadPromiseRef = useRef<Promise<Appointment[]> | null>(null);

  useEffect(() => {
    appointmentsTableDataRef.current = appointmentsTableData;
  }, [appointmentsTableData]);

  // Загрузка данных
  // Загрузка услуг для правильного отображения в tooltips
  const loadServices = useCallback(async () => {
    if (dentistCache.services) {
      setServices(dentistCache.services);
      return dentistCache.services;
    }

    if (dentistCache.servicesLoadPromise) {
      return dentistCache.servicesLoadPromise;
    }

    const loadPromise = (async () => {
      try {
        const token = tokenManager.getAccessToken();
        if (!token) return null;
        const response = await apiClient.get('/registrar/services');
        if (response.status < 400) {
          const data = response.data;
          const servicesData = data.services_by_group || {};
          dentistCache.services = servicesData;
          setServices(servicesData);
          logger.info('[Dentist] Услуги загружены:', Object.keys(servicesData).length, 'групп');
          return servicesData;
        }

        return null;
      } catch (error: unknown) {
        logger.error('[Dentist] Ошибка загрузки услуг:', error);
        return null;
      }
    })();

    dentistCache.servicesLoadPromise = loadPromise;

    try {
      return await loadPromise;
    } finally {
      if (dentistCache.servicesLoadPromise === loadPromise) {
        dentistCache.servicesLoadPromise = null;
      }
    }
  }, []);

  // Функция для получения всех услуг пациента из всех записей
  const getAllPatientServicesCb = useCallback((patientId: string | number | null | undefined, allAppointments: Appointment[] | null | undefined) => {
    return getAllPatientServices(patientId, allAppointments as unknown as Array<Record<string, unknown>> | null | undefined);
  }, []);

  // Загрузка записей стоматолога
  const loadDentistryAppointments = useCallback(async (forceRefresh = false): Promise<Appointment[]> => {
    if (!forceRefresh && dentistCache.appointments) {
      appointmentsTableDataRef.current = dentistCache.appointments;
      setAppointmentsTableData(dentistCache.appointments);
      setPatients((prev) => {
        const derivedPatients = buildPatientsFromAppointments(dentistCache.appointments, tI18n);
        return derivedPatients.length > 0 ? derivedPatients : prev;
      });
      return dentistCache.appointments;
    }

    if (appointmentsLoadPromiseRef.current || dentistCache.appointmentsLoadPromise) {
      return (appointmentsLoadPromiseRef.current || dentistCache.appointmentsLoadPromise) as Promise<Appointment[]>;
    }

    const loadPromise = (async (): Promise<Appointment[]> => {
      setAppointmentsLoading(true);
      try {
        const token = tokenManager.getAccessToken();
        if (!token) {
          logger.info('Нет токена аутентификации');
          return [];
        }

        // Загружаем ВСЕ очереди для получения полной картины услуг пациентов
        const response = await apiClient.get('/registrar/queues/today');

        if (response.status < 400) {
          const data = response.data as Record<string, unknown>;

          // Собираем ВСЕ записи из всех очередей для получения полной картины услуг
          const allAppointments: Appointment[] = [];
          if (data && data.queues && Array.isArray(data.queues)) {
            (data.queues as Record<string, unknown>[]).forEach((queue) => {
              const entries = queue?.entries as Record<string, unknown>[] | undefined;
              if (entries) {
                entries.forEach((entry) => {
                  const doctorQueueEntryId = resolveDoctorQueueEntryId(entry);
                  const patientObj = entry.patient as { first_name?: string; last_name?: string; [k: string]: unknown } | undefined;
                  const entryWithTimes = { ...entry, ...adaptTimeFields(entry, data) };
                  allAppointments.push({
                    id: entry.id as string | number,
                    appointment_id: (entry.appointment_id as string | number | null | undefined) || null,
                    visit_id: (entry.visit_id as string | number | null | undefined) || null,
                    patient_id: entry.patient_id as string | number,
                    patient_fio: (entry.patient_name as string) || `${patientObj?.first_name || ''} ${patientObj?.last_name || ''}`.trim(),
                    patient_phone: (entry.phone as string) || '',
                    patient_birth_year: (entry.patient_birth_year as number | undefined) || undefined,
                    address: (entry.address as string) || '',
                    visit_type:
                      entry.discount_mode === 'repeat' ? tI18n('dental.dental_panel_discount_repeat') :
                      entry.discount_mode === 'benefit' ? tI18n('dental.dental_panel_discount_benefit') :
                      entry.discount_mode === 'all_free' ? 'All Free' :
                      tI18n('dental.dental_panel_discount_paid'),
                    discount_mode: (entry.discount_mode as string) || 'none',
                    services: (entry.services as unknown as Appointment['services']) || [],
                    service_codes: (entry.service_codes as string[]) || [],
                    payment_type: (entry.payment_type as string) || null,
                    payment_status: (entry.payment_status as string | undefined) ?? null,
                    available_actions: (entry.available_actions as unknown[]) || [],
                    can_mark_paid: Boolean(entry.can_mark_paid),
                    can_start_visit: Boolean(entry.can_start_visit) && doctorQueueEntryId !== null,
                    can_print_ticket: Boolean(entry.can_print_ticket),
                    can_complete: Boolean(entry.can_complete) && doctorQueueEntryId !== null,
                    can_cancel: Boolean(entry.can_cancel),
                    queue_entry_id: (entry.queue_entry_id as string | number | null | undefined) ?? null,
                    doctor_queue_entry_id: doctorQueueEntryId,
                    canonical_record_id: (entry.canonical_record_id as string | number | undefined) || entry.id as string | number,
                    record_kind: entry.record_kind,
                    source_kind: entry.source_kind,
                    canonical_status: (entry.canonical_status as string | null | undefined) ?? null,
                    queue_status: (entry.queue_status as string | null | undefined) ?? null,
                    queue_position: entry.queue_position,
                    doctor: (entry.doctor_name as string) || tI18n('dental.dental_panel_doctor_default'),
                    specialty: queue.specialty as string,
                    ...entryWithTimes,
                    status: (entry.status as string | null | undefined) ?? null,
                    cost: (entry.cost as number) || 0
                  } as unknown as Appointment);
                });
              }
            });
          }

          // Фильтруем только стоматологические записи для отображения
          const appointmentsData = allAppointments.filter((apt) =>
            isDentistrySpecialty(apt.specialty)
          );

          // Добавляем информацию о всех услугах пациента в каждую запись
          const enrichedAppointmentsData = appointmentsData.map((apt) => {
            const allPatientServices = getAllPatientServicesCb(apt.patient_id, allAppointments);
            return {
              ...apt,
              all_patient_services: allPatientServices.services,
              all_patient_service_codes: allPatientServices.service_codes
            };
          });

        dentistCache.appointments = enrichedAppointmentsData;
        appointmentsTableDataRef.current = enrichedAppointmentsData;
        setAppointmentsTableData(enrichedAppointmentsData);
        setPatients((prev) => {
          const derivedPatients = buildPatientsFromAppointments(enrichedAppointmentsData, tI18n);
            return derivedPatients.length > 0 ? derivedPatients : prev;
          });
          return enrichedAppointmentsData;
        }

        logger.error('Ошибка загрузки очередей:', response.status);
        return [];
      } catch (error: unknown) {
        logger.error('Ошибка загрузки записей стоматолога:', error);
        return [];
      } finally {
        setAppointmentsLoading(false);
      }
    })();

    appointmentsLoadPromiseRef.current = loadPromise;
    dentistCache.appointmentsLoadPromise = loadPromise;

    try {
      return await loadPromise;
    } finally {
      if (appointmentsLoadPromiseRef.current === loadPromise) {
        appointmentsLoadPromiseRef.current = null;
      }
      if (dentistCache.appointmentsLoadPromise === loadPromise) {
        dentistCache.appointmentsLoadPromise = null;
      }
    }
  }, [getAllPatientServicesCb, tI18n]);

  // Загружаем записи при переключении на вкладку
  useEffect(() => {
    if (activeTab === 'appointments') {
      loadDentistryAppointments();
    }

    // Слушаем глобальные события обновления очереди
    const handleQueueUpdate = (event: Event) => {
      const customEvent = event as CustomEvent<unknown>;
      logger.info('[Dentist] Получено событие обновления очереди:', customEvent.detail);
      if (activeTab === 'appointments') {
        loadDentistryAppointments(true);
      }
    };
    window.addEventListener('queueUpdated', handleQueueUpdate);

    return () => {
      window.removeEventListener('queueUpdated', handleQueueUpdate);
    };
  }, [activeTab, loadDentistryAppointments]);

  const ensureCanonicalVisitId = useCallback(
    (row: Appointment | Record<string, unknown>) => makeEnsureCanonicalVisitId(setAppointmentsTableData as unknown as React.Dispatch<React.SetStateAction<unknown[]>>, resolveCanonicalVisitId)(row as Record<string, unknown>),
    []
  );

  const loadPatients = useCallback(async () => {
    try {
      const derivedPatients = buildPatientsFromAppointments(appointmentsTableDataRef.current, tI18n);
      if (derivedPatients.length > 0) {
        logger.info('[Dentist] Загружаю пациентов из уже загруженных записей', {
          count: derivedPatients.length,
        });
        setPatients(derivedPatients);
        return;
      }

      logger.info('[Dentist] Пациенты будут загружены из очереди и записей стоматолога');
      const refreshedAppointments = await loadDentistryAppointments();
      const refreshedPatients = buildPatientsFromAppointments(
        Array.isArray(refreshedAppointments) && refreshedAppointments.length > 0
          ? refreshedAppointments
          : appointmentsTableDataRef.current,
        tI18n,
      );

      if (refreshedPatients.length > 0) {
        setPatients(refreshedPatients);
      }
    } catch (e: unknown) {
      logger.error('Ошибка загрузки пациентов:', e);
    }
  }, [loadDentistryAppointments, tI18n]);

  const loadData = useCallback(async () => {
    // PR-35 / P0-14: Removed duplicate loadPatients() call — was calling
    // Promise.all([loadPatients(), loadPatients()]) which fetched the
    // patient list twice on every mount.
    await Promise.all([
      loadPatients(),
      loadServices(),
    ]);
  }, [loadPatients, loadServices]);

  return {
    patients,
    setPatients,
    appointmentsTableData,
    setAppointmentsTableData,
    appointmentsTableDataRef,
    appointmentsLoading,
    services,
    loadServices,
    loadDentistryAppointments,
    loadPatients,
    loadData,
    ensureCanonicalVisitId,
  };
}
