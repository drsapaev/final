import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';

import { getProfile } from '../../stores/auth';
import type { UserProfile } from '../../types/domain/auth';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import { getApiOrigin } from '../../api/runtime';
import type { AppointmentDto, PatientRecord, TranslateFn } from './doctorStatus';

/**
 * PR-UI-15-1: panel data lifecycle extracted verbatim from
 * pages/DoctorPanel.tsx (registrar/cashier decomposition precedent).
 *
 * Owns:
 *  - patients / appointments / loading / loadError state
 *  - appointmentStats memo (UX Audit Doctor M-46)
 *  - doctorSpecialty resolved from the auth profile (PR-27)
 *  - loadData lifecycle (UX Audit Doctor H-08: honest empty state)
 *  - handleScheduleNextSuccess (DOC-05 appointments refresh)
 *  - the ?patientId= deep-link effect (auto-load + open patient modal)
 *
 * The deep-link effect keeps the original wiring: it feeds the loaded
 * patient into the tab-state setters and the patient modal via the deps
 * object (cashier 14-4 deps-object precedent) so behavior stays
 * byte-identical to the inline original.
 */
export function useDoctorPanelData({
  t,
  setSearchQuery,
  setActiveTab,
  openPatientModal,
}: {
  t: TranslateFn;
  setSearchQuery: (query: string) => void;
  setActiveTab: (tab: string) => void;
  openPatientModal: (patient: PatientRecord | Record<string, unknown> | null) => void;
}) {
  const location = useLocation();

  const [patients, setPatients] = useState<PatientRecord[]>([]);
  const [appointments, setAppointments] = useState<AppointmentDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // UX Audit Doctor M-46: useMemo for stat calculations (was 3 filter calls per render).
  const appointmentStats = useMemo(() => ({
    scheduled: appointments.filter((a) => a.status === 'scheduled').length,
    inProgress: appointments.filter((a) => a.status === 'in_progress').length,
    completed: appointments.filter((a) => a.status === 'completed').length,
  }), [appointments]);

  // PR-27: read specialty from profile instead of hardcoding 'general'
  const [doctorSpecialty, setDoctorSpecialty] = useState('general');

  useEffect(() => {
    getProfile().then((profile: UserProfile | null) => {
      if (profile?.specialty) {
        setDoctorSpecialty(String(profile.specialty ?? ''));
      }
    }).catch(() => {});
  }, []);

  // Загрузка данных
  // UX Audit Doctor H-08: убрана эмуляция загрузки (setPatients([]) + Skeleton).
  // Теперь честно показываем empty-state без имитации skeleton-загрузки.
  const loadData = useCallback(async () => {
    setLoading(false);
    setLoadError(null);
    // Данные загружаются через useDoctorQueue (очередь) и useDoctorHistory (история).
    // Пациенты и записи на сегодня загружаются из реального API, когда он будет готов.
    // Пока — честный empty-state без имитации.
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleScheduleNextSuccess = useCallback((result?: Record<string, unknown>, submittedFormData?: Record<string, unknown>) => {
    const confirmation = (result?.confirmation as Record<string, unknown> | undefined) ?? {};
    const patientIdRaw = submittedFormData?.patient_id;
    const normalizedPatientId = patientIdRaw ? Number(patientIdRaw) : null;
    const selectedPatient = normalizedPatientId
      ? patients.find((patient) => Number(patient.id) === normalizedPatientId)
      : null;
    const visitDate = String(confirmation.visit_date ?? submittedFormData?.visit_date ?? '');
    const visitTime = String(confirmation.visit_time ?? submittedFormData?.visit_time ?? '');
    const servicesRaw = submittedFormData?.services as unknown[] | undefined;

    const nextAppointment: AppointmentDto = {
      id: (result?.visit_id as string | number | undefined) ?? Date.now(),
      patientId: normalizedPatientId,
      patientName: String(confirmation.patient_name ?? selectedPatient?.name ?? t('doctor.new_patient')),
      time: visitTime,
      type:
        submittedFormData?.discount_mode === 'repeat'
          ? t('doctor.repeat_visit')
          : submittedFormData?.discount_mode === 'benefit'
            ? t('doctor.benefit_visit')
            : t('doctor.next_visit'),
      status: 'scheduled',
      notes: String(result?.message ?? (visitDate ? t('doctor.awaiting_confirmation_on_date', { date: visitDate }) : t('doctor.awaiting_confirmation'))),
      appointmentDate: visitDate,
      confirmationToken: (confirmation.token as string | null | undefined) ?? null,
      confirmationChannel: String(confirmation.channel ?? submittedFormData?.confirmation_channel ?? 'telegram'),
      totalAmount: (confirmation.total_amount as number | null | undefined) ?? null,
      servicesCount: Number(confirmation.services_count ?? servicesRaw?.length ?? 1),
      source: 'schedule-next'
    };

    setAppointments((prev) => [
      nextAppointment,
      ...prev.filter((appointment) => Number(appointment.id) !== Number(nextAppointment.id))
    ]);

    logger.info('[DOC-05] Appointments table refreshed after schedule-next', {
      visitId: nextAppointment.id,
      patientId: nextAppointment.patientId,
      patientName: nextAppointment.patientName,
      status: nextAppointment.status
    });
  }, [patients, t]);

  // ✅ Получаем patientId из URL для автоматического выбора пациента
  const getPatientIdFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search);
    const pid = params.get('patientId');
    return pid ? parseInt(pid, 10) : null;
  }, [location.search]);

  // ✅ Автоматическая загрузка пациента из URL параметра patientId
  useEffect(() => {
    const loadPatientFromUrl = async () => {
      const patientIdFromUrl = getPatientIdFromUrl();
      if (!patientIdFromUrl) return;

      try {
        const token = tokenManager.getAccessToken();
        if (!token) return;

        const API_BASE = getApiOrigin();

        // Загружаем данные пациента
        const patientResponse = await fetch(`${API_BASE}/api/v1/patients/${patientIdFromUrl}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (patientResponse.ok) {
          const patientData: Record<string, unknown> = await patientResponse.json();

          // Создаем объект пациента для отображения
          const patientObj: PatientRecord = {
            id: patientData.id as string | number,
            name: `${patientData.last_name || ''} ${patientData.first_name || ''} ${patientData.middle_name || ''}`.trim(),
            phone: String(patientData.phone ?? ''),
            gender: String(patientData.sex ?? ''),
            diagnosis: '',
            status: 'active',
            age: patientData.birth_date ? new Date().getFullYear() - new Date(patientData.birth_date as string).getFullYear() : null
          };

          // Добавляем пациента в список и устанавливаем поисковый запрос
          setPatients((prev) => {
            const exists = prev.some((p) => p.id === patientObj.id);
            if (!exists) {
              return [patientObj, ...prev];
            }
            return prev;
          });

          setSearchQuery(patientObj.name ?? '');
          setActiveTab('patients');

          // Открываем модальное окно с данными пациента
          openPatientModal(patientObj);

          logger.info('[Doctor] Загружен пациент из URL:', patientObj.name);
        }
      } catch (error) {
        logger.error('[Doctor] Не удалось загрузить пациента из URL:', error);
      }
    };

    loadPatientFromUrl();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search, getPatientIdFromUrl]);

  return {
    patients,
    appointments,
    loading,
    loadError,
    loadData,
    appointmentStats,
    doctorSpecialty,
    handleScheduleNextSuccess,
  };
}
