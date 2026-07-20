/**
 * Registrar Panel — data loading hook (partial extraction).
 *
 * Decomposition step 4: extracted from RegistrarPanel.jsx.
 *
 * Extracted functions:
 * - loadIntegratedData: loads doctors, services, departments in parallel
 *   from /registrar/* endpoints. Sets state via provided setters.
 * - fetchPatientData: fetches single patient by ID from /api/v1/patients/:id.
 *   Returns null for demo patients (ID >= 1000) or on error.
 * - enrichAppointmentsWithPatientData: enriches appointment records with
 *   patient display fields (FIO, phone, birth year, gender, address) if
 *   missing from backend response. Also applies local overrides.
 *
 * NOT extracted (remain in RegistrarPanel due to complex ref dependencies):
 * - loadAppointments: depends on loadAppointmentsInFlightRef,
 *   autoRefreshCooldownUntilRef, autoRefreshCooldownLoggedRef,
 *   filteredAppointmentsRef, and calls enrichAppointmentsWithPatientData.
 * - loadMoreAppointments: depends on paginationInfo state and loadAppointments.
 *
 * @param {Object} deps
 * @param {Function} deps.setDoctors - state setter for doctors array
 * @param {Function} deps.setServices - state setter for services object
 * @param {Function} deps.setDynamicDepartments - state setter for departments
 */
import { useCallback } from 'react';
import { api } from '../../api/client';
// UX Audit Registrar #1: getPatient() — централизованный доступ к /patients/{id}.
// Раньше здесь был raw fetch() с ручным Authorization-хедером.
import { getPatient } from '../../api/patients';
import logger from '../../utils/logger';
// tokenManager всё ещё используется в loadIntegratedData для diagnostic-лога.
import tokenManager from '../../utils/tokenManager';
import notify from '../../services/notify';
import { formatNetworkErrorMessage, isNetworkFetchError } from '../../utils/networkErrorMessages';
import {
  hasBackendPatientDisplayContract,
  hasBackendPatientGenderContract,
  normalizePatientGender,
} from './registrarHelpers';

export const useRegistrarData = ({
  setDoctors,
  setServices,
  setDynamicDepartments,
}) => {
  // ───────────────────────────────────────────────────────────
  // loadIntegratedData: parallel fetch of doctors + services + departments
  // ───────────────────────────────────────────────────────────
  const loadIntegratedData = useCallback(async () => {
    logger.info('🔧 loadIntegratedData called at:', new Date().toISOString());
    try {
      // Сбрасываем устаревшие значения перед загрузкой truth из API.
      setDoctors([]);
      setServices({});
      setDynamicDepartments([]);

      try {
        const token = tokenManager.getAccessToken();
        logger.info('🔍 RegistrarPanel: token present:', Boolean(token));

        // ✅ ОПТИМИЗАЦИЯ: Загружаем все данные параллельно с Promise.allSettled
        logger.info('🚀 Загружаем данные параллельно...');
        const [doctorsResult, servicesResult, departmentsResult] = await Promise.allSettled([
          api.get('/registrar/doctors'),
          api.get('/registrar/services'),
          api.get('/registrar/departments?active_only=true'),
        ]);

        const doctorsRes = (doctorsResult.status === 'fulfilled' ? doctorsResult.value : { ok: false }) as any;
        const servicesRes = (servicesResult.status === 'fulfilled' ? servicesResult.value : { ok: false }) as any;
        const departmentsRes = (departmentsResult.status === 'fulfilled' ? departmentsResult.value : { success: false }) as any;

        if (doctorsResult.status === 'fulfilled') {
          logger.info('📊 Ответ врачей: OK');
        } else {
          const reason = doctorsResult.reason as { message?: string };
          logger.error('❌ Ошибка загрузки врачей:', reason?.message);
        }
        if (servicesResult.status === 'fulfilled') {
          logger.info('📊 Ответ услуг: OK');
        } else {
          const reason = servicesResult.reason as { message?: string };
          logger.error('❌ Ошибка загрузки услуг:', reason?.message);
        }
        if (departmentsResult.status === 'fulfilled') {
          logger.info('📊 Ответ отделений: OK', departmentsRes.data);
        } else {
          logger.error('❌ Ошибка загрузки отделений:', departmentsResult.reason);
        }

        logger.info('🔄 Обрабатываем ответы API...');

        const allSuccess = doctorsRes && doctorsRes.data && servicesRes && servicesRes.data;
        logger.info('📊 Статус ответов:', {
          doctors: doctorsRes && doctorsRes.data ? 'OK' : 'ERROR',
          services: servicesRes && servicesRes.data ? 'OK' : 'ERROR',
          allSuccess,
        });

        if (!allSuccess) {
          logger.warn('⚠️ Некоторые API недоступны, но продолжаем работу');
        }

        if (doctorsRes && doctorsRes.data) {
          try {
            const doctorsData = doctorsRes.data;
            const apiDoctors = doctorsData.doctors || [];
            logger.info('✅ Данные врачей получены:', apiDoctors.length, 'врачей');
            if (apiDoctors.length > 0) {
              setDoctors(apiDoctors);
              logger.info('✅ Врачи обновлены из API');
            }
          } catch (error) {
            const err = error as { message?: string };
            logger.warn('Ошибка обработки данных врачей:', err?.message);
          }
        } else {
          logger.warn('❌ API врачей недоступен, оставляем пустое состояние');
        }

        // Обработка отделений
        if (departmentsRes && departmentsRes.data) {
          const depts = departmentsRes.data.data || [];
          if (Array.isArray(depts) && depts.length > 0) {
            setDynamicDepartments(depts);
            logger.info('✅ Отделения обновлены из API:', depts.length);
          }
        }

        if (servicesRes && servicesRes.data) {
          try {
            const servicesData = servicesRes.data;
            const apiServices = servicesData.services_by_group || {};
            logger.info('✅ Данные услуг получены:', Object.keys(apiServices));
            if (Object.keys(apiServices).length > 0) {
              setServices(apiServices);
              logger.info('✅ Услуги обновлены из API');
            }
          } catch (error) {
            const err = error as { message?: string };
            logger.warn('Ошибка обработки данных услуг:', err?.message);
          }
        } else {
          logger.warn('❌ API услуг недоступен, оставляем пустое состояние');
        }

        logger.info('🎯 Загрузка интегрированных данных завершена');
      } catch (fetchError) {
        logger.warn('Backend недоступен для загрузки интегрированных данных, оставляем пустое состояние:', fetchError.message);
      }
    } catch (error) {
      logger.error('Ошибка загрузки интегрированных данных:', error);
      notify.error('Ошибка загрузки данных из админ панели');
    }
  }, [setDoctors, setServices, setDynamicDepartments]);

  // ───────────────────────────────────────────────────────────
  // fetchPatientData: fetch single patient by ID
  // ───────────────────────────────────────────────────────────
  const fetchPatientData = useCallback(async (patientId: number | string) => {
    const pid = Number(patientId);
    // Проверяем, является ли это демо-пациентом (ID >= 1000)
    if (pid >= 1000) {
      // Возвращаем null для демо-пациентов, так как их данные уже есть в записи
      return null;
    }

    try {
      // UX Audit Registrar #1: raw fetch() с ручным Authorization-хедером
      // заменён на getPatient() из api/patients.
      // Auth-token добавляется автоматически axios-interceptor'ом в api/client.js.
      // 401/403 обрабатываются интерсептором (redirect to login или refresh).
      return await getPatient(pid);
    } catch (error) {
      const err = error as { response?: { status?: number }; message?: string };
      const status = err?.response?.status;
      const rawMessage = err?.message || '';

      // 404 — пациент не найден. Не логируем как ошибку, просто возвращаем null.
      if (status === 404) {
        return null;
      }

      if (isNetworkFetchError(rawMessage)) {
        logger.warn('[Registrar] Не удалось загрузить пациента из URL: backend недоступен', {
          patientId,
          rawMessage,
        });
        return null;
      }

      logger.error(`Error fetching patient ${patientId}:`, {
        error: formatNetworkErrorMessage({
          rawMessage,
          fallbackMessage: 'Не удалось загрузить пациента из URL',
        }),
        rawMessage,
      });
    }
    return null;
  }, []);

  // ───────────────────────────────────────────────────────────
  // enrichAppointmentsWithPatientData: enrich records with patient display fields
  // ───────────────────────────────────────────────────────────
  const enrichAppointmentsWithPatientData = useCallback(async (appointments: any[]) => {
    const enrichedAppointments = await Promise.all(appointments.map(async (apt: any) => {
      let enrichedApt = { ...apt };

      // Обогащаем данными пациента
      if (apt.patient_id && (!hasBackendPatientDisplayContract(apt) || !hasBackendPatientGenderContract(apt))) {
        const patient: any = await fetchPatientData(apt.patient_id);
        if (patient) {
          let patient_fio: string = '';
          if (patient.last_name && patient.first_name) {
            patient_fio = `${patient.last_name} ${patient.first_name}`;
            if (patient.middle_name) {
              patient_fio += ` ${patient.middle_name}`;
            }
          } else if (patient.last_name) {
            patient_fio = patient.last_name;
          } else if (patient.first_name) {
            patient_fio = patient.first_name;
          } else {
            patient_fio = `Пациент ID=${patient.id}`;
          }

          const patientGender = normalizePatientGender(patient);
          enrichedApt = {
            ...enrichedApt,
            patient_fio: patient_fio.trim() || `Пациент ID=${patient.id}`,
            patient_phone: patient.phone,
            patient_birth_year: patient.birth_date ? new Date(patient.birth_date).getFullYear() : null,
            patient_gender: patientGender,
            gender: patientGender,
            sex: patientGender,
            address: patient.address || 'Не указан',
          };
        }
      }

      // R-29 fix: override block removed — appointmentOverridesRef was dead code
      // (never populated). Local overrides after payment are handled by
      // loadAppointments silent refresh instead.
      enrichedApt = {
        ...enrichedApt,
        visit_type: enrichedApt.visit_type ?? null,
        payment_type: enrichedApt.payment_type ?? null,
        payment_status: enrichedApt.payment_status ?? null,
        services: enrichedApt.services || [],
        cost: Number(enrichedApt.cost ?? 0),
      };

      return enrichedApt;
    }));
    return enrichedAppointments;
  }, [fetchPatientData]);

  return {
    loadIntegratedData,
    fetchPatientData,
    enrichAppointmentsWithPatientData,
  };
};

export default useRegistrarData;
