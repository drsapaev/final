/**
 * Registrar Panel — reference data hook (doctors / services / departments).
 *
 * Decomposition step 4: extracted from RegistrarPanel.jsx.
 * PR-UI-13-4: the hook now OWNS the reference-data state (doctors, services,
 * dynamicDepartments) instead of receiving external setters — the panel's
 * useState count drops to 5 (plan §PR-UI-13 AC).
 *
 * Exported functions:
 * - loadIntegratedData: loads doctors, services, departments in parallel
 *   from /registrar/* endpoints.
 * - fetchPatientData: fetches single patient by ID from /api/v1/patients/:id.
 *   Returns null for demo patients (ID >= 1000) or on error.
 * - enrichAppointmentsWithPatientData: enriches appointment records with
 *   patient display fields (FIO, phone, birth year, gender, address) if
 *   missing from backend response. Also applies local overrides.
 *
 * NOT extracted (remain in useRegistrarWorklistData — PR-UI-13-1):
 * - loadAppointments / loadMoreAppointments.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
// UX Audit Registrar #1: getPatient() — централизованный доступ к /patients/{id}.
// Раньше здесь был raw fetch() с ручным Authorization-хедером.
import { getPatient } from '../../api/patients';
import type { Doctor } from '../../types/domain/clinic';
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

export const useRegistrarData = () => {
  // PR-UI-13-4: reference-data state owned by the hook (former panel
  // useState + external setters). Non-silent loads keep the original reset
  // semantics: cleared before fetch, set only on success. RQ-27.a adds a
  // silent focus/visibility revalidation that keeps previous data instead.
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [services, setServices] = useState<Record<string, unknown>>({});
  const [dynamicDepartments, setDynamicDepartments] = useState<unknown[]>([]);
  // RQ-27.a (F-23): silent-refresh flag for the focus/visibility revalidation
  // below. Set right before the call, consumed inside loadIntegratedData —
  // the public signature stays `async ()` (pinned by the panel contract
  // test's source-block marker).
  const silentRefreshRef = useRef(false);
  // ───────────────────────────────────────────────────────────
  // loadIntegratedData: parallel fetch of doctors + services + departments
  // ───────────────────────────────────────────────────────────
  const loadIntegratedData = useCallback(async () => {
    // RQ-27.a (F-23): a focus/visibility revalidation must behave like the
    // RQ-22 worklist silent refresh — previous data stays on screen while
    // the fetch is in flight AND after a failure (no wipe, no error toast).
    // The non-silent paths (initial load, departments:updated, post-wizard)
    // keep the original cleared-before-fetch semantics byte-for-byte.
    const silent = silentRefreshRef.current;
    silentRefreshRef.current = false;
    logger.info('🔧 loadIntegratedData called at:', new Date().toISOString());
    try {
      if (!silent) {
        // Сбрасываем устаревшие значения перед загрузкой truth из API.
        setDoctors([]);
        setServices({});
        setDynamicDepartments([]);
      }

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

        const doctorsRes = (doctorsResult.status === 'fulfilled' ? doctorsResult.value : { ok: false }) as { ok?: boolean; data?: unknown[]; [k: string]: unknown };
        const servicesRes = (servicesResult.status === 'fulfilled' ? servicesResult.value : { ok: false }) as { ok?: boolean; data?: unknown[]; [k: string]: unknown };
        const departmentsRes = (departmentsResult.status === 'fulfilled' ? departmentsResult.value : { success: false }) as { success?: boolean; data?: unknown[]; [k: string]: unknown };

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
            const doctorsData = doctorsRes.data as { doctors?: unknown[] };
            const apiDoctors = (doctorsData.doctors as Doctor[]) || [];
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
          const depts = ((departmentsRes.data as unknown as { data?: unknown[] }).data) || [];
          if (Array.isArray(depts) && depts.length > 0) {
            setDynamicDepartments(depts);
            logger.info('✅ Отделения обновлены из API:', depts.length);
          }
        }

        if (servicesRes && servicesRes.data) {
          try {
            const servicesData = servicesRes.data as unknown as Record<string, unknown>;
            const apiServices = (servicesData.services_by_group as Record<string, unknown>) || {};
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
        const fetchErr = fetchError as { message?: string };
        logger.warn('Backend недоступен для загрузки интегрированных данных, оставляем пустое состояние:', fetchErr?.message);
      }
    } catch (error) {
      logger.error('Ошибка загрузки интегрированных данных:', error);
      // RQ-27.a (F-23): a failed silent revalidation keeps previous data and
      // stays quiet for the user (logger only) — same philosophy as RQ-22.
      if (!silent) {
        notify.error('Ошибка загрузки данных из админ панели');
      }
    }
  }, [setDoctors, setServices, setDynamicDepartments]);

  // RQ-27.a (F-23): cross-session catalog revalidation. `departments:updated`
  // / `queue-profiles:updated` are window events — they never cross browser
  // contexts, so a catalog change made by an administrator in ANOTHER session
  // (window, tab, device) used to stay invisible here until a full reload.
  // Understandable refresh without polling: when the user returns to this
  // tab/window, revalidate the reference data silently. A 5s throttle
  // collapses the focus+visibilitychange burst browsers fire together into
  // one refresh (extra-requests budget per ACCEPTANCE S-28).
  const lastFocusRefreshAtRef = useRef(0);
  useEffect(() => {
    const FOCUS_REFRESH_MIN_INTERVAL_MS = 5000;
    const refreshIfDue = () => {
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - lastFocusRefreshAtRef.current < FOCUS_REFRESH_MIN_INTERVAL_MS) return;
      lastFocusRefreshAtRef.current = now;
      logger.info('🔄 RQ-27.a: silent reference-data revalidation on return to the session');
      silentRefreshRef.current = true;
      void loadIntegratedData();
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') refreshIfDue();
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', refreshIfDue);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', refreshIfDue);
    };
  }, [loadIntegratedData]);

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
  const enrichAppointmentsWithPatientData = useCallback(async (appointments: Record<string, unknown>[]) => {
    const enrichedAppointments = await Promise.all(appointments.map(async (apt: Record<string, unknown>) => {
      let enrichedApt = { ...apt };

      // Обогащаем данными пациента
      if (apt.patient_id as string | number && (!hasBackendPatientDisplayContract(apt) || !hasBackendPatientGenderContract(apt))) {
        const patient: Record<string, unknown> | null = (await fetchPatientData(apt.patient_id as string | number)) as unknown as Record<string, unknown> | null;
        if (patient) {
          let patient_fio: string = '';
          if (String(patient.last_name ?? '') && String(patient.first_name ?? '')) {
            patient_fio = `${String(patient.last_name ?? '')} ${String(patient.first_name ?? '')}`;
            if (String(patient.middle_name ?? '')) {
              patient_fio += ` ${String(patient.middle_name ?? '')}`;
            }
          } else if (String(patient.last_name ?? '')) {
            patient_fio = String(patient.last_name ?? '');
          } else if (String(patient.first_name ?? '')) {
            patient_fio = String(patient.first_name ?? '');
          } else {
            patient_fio = `Пациент ID=${patient.id}`;
          }

          const patientGender = normalizePatientGender(patient);
          enrichedApt = {
            ...enrichedApt,
            patient_fio: patient_fio.trim() || `Пациент ID=${patient.id}`,
            patient_phone: patient.phone,
            patient_birth_year: patient.birth_date ? new Date(String(patient.birth_date)).getFullYear() : null,
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
    doctors,
    services,
    dynamicDepartments,
    loadIntegratedData,
    fetchPatientData,
    enrichAppointmentsWithPatientData,
  };
};

export default useRegistrarData;
