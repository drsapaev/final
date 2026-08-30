import { lazy, Suspense, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import './dentistry.css';
import { useLocation } from 'react-router-dom';
// P-009 fix: shared doctor panel state hook
import { useDoctorPanelState } from '../hooks/useDoctorPanelState';
import { useTheme } from '../contexts/ThemeContext';
import { getLocalDateString, parseRegistrarTimestamp } from '../utils/dateUtils';
import {
  Button, Badge, Card } from '../components/ui/macos';
import AppointmentSummaryBar from '../components/doctor/AppointmentSummaryBar';
import auth from '../stores/auth';
import { apiClient } from '../api/client';
import AIAssistant from '../components/ai/AIAssistant';
import TeethChart from '../components/dental/TeethChart';
import ToothModal from '../components/dental/ToothModal';
import DentalVisitScreen from '../components/dental/DentalVisitScreen';
import TreatmentPlanner from '../components/dental/TreatmentPlanner';
import PatientCard from '../components/dental/PatientCard';
import type { PatientFormData } from '../components/dental/PatientCard';
import DentalPriceManager from '../components/dental/DentalPriceManager';
import DiagnosisForm from '../components/dental/DiagnosisForm';
import VisitProtocol from '../components/dental/VisitProtocol';
import PhotoArchive from '../components/dental/PhotoArchive';
import ProtocolTemplates from '../components/dental/ProtocolTemplates';
import DentalReportsTab from '../components/dental/DentalReportsTab';
import DentalTemplatesTab from '../components/dental/DentalTemplatesTab';
import DentalDashboardTab, { type DentalDashboardAppointment } from '../components/dental/DentalDashboardTab';
import DentalPatientsTab from '../components/dental/DentalPatientsTab';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import SessionWarningModal from '../components/common/SessionWarningModal';
import EnhancedAppointmentsTable, { type AppointmentRow } from '../components/tables/EnhancedAppointmentsTable';
import QueueIntegration from '../components/QueueIntegration';

import {
  Calendar,
  XCircle } from
'lucide-react';
import '../styles/animations.css';
import { printPanelTicket } from '../services/panelPrint';
import notify from '../services/notify';
// STRAT#34: useTranslation adapter for confirm/notify i18n.
import { useTranslation } from '../i18n/useTranslation';
import type { Appointment } from '../types/domain/clinic';
import { useConfirm } from '../components/common/ConfirmDialog';
import { useSessionTimeoutWarning } from '../hooks/useSessionTimeoutWarning';
import { useDentalHotkeys } from '../hooks/useDentalHotkeys';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
import { queueService } from '../services/queue';
import {
  countAppointmentsByStatuses,
  normalizeNumericId,
  SPECIALTY_KEYS,
} from '../utils/doctorPanelShared';
import { useVisitLifecycle } from '../hooks/useVisitLifecycle';
import { getErrorMessage } from '../utils/type-guards';

const LazyReportsAndAnalytics = lazy(() => import('../components/dental/ReportsAndAnalytics'));

// PR-UI-15-3: module-level contracts infra (types, status constants, caches +
// BS-42 invalidation, queue-id resolution, patient derivation, localStorage
// bootstrap) extracted verbatim to ./dentist/dentistContracts.
import {
  DENTISTRY_WAITING_STATUSES,
  DENTISTRY_CALLED_STATUSES,
  DENTISTRY_COMPLETED_STATUSES,
  invalidateDentistPanelCaches,
  resolveDoctorQueueEntryId,
  dentistCache,
  type SelectedPatient,
  type DoctorPanelState,
} from './dentist/dentistContracts';
// PR-UI-15-3: worklist data lifecycle (queues/today fetch + DTO mapping +
// services + patients + queueUpdated listener) extracted verbatim to
// ./dentist/useDentistWorklistData.
import { useDentistWorklistData } from './dentist/useDentistWorklistData';
// PR-UI-15-4: dialog view-state + EMR v2 visit-protocol lifecycle extracted
// verbatim to ./dentist/useDentistDialogs + ./dentist/useDentistVisitProtocols.
import { useDentistDialogs } from './dentist/useDentistDialogs';
import { useDentistVisitProtocols } from './dentist/useDentistVisitProtocols';

/**
 * Объединенная стоматологическая панель с полным функционалом
 * Включает:
 * - Схемы зубов и планирование лечения
 * - AI помощник
 * - Управление пациентами
 * - Интеграция с очередями
 * - Современный UI
 */
const DentistPanelUnified = () => {
  const location = useLocation();
  // P-009: navigate removed — useDoctorPanelState handles tab URL sync
  const [authState, setAuthState] = useState(auth.getState());

  useEffect(() => {
    const unsubscribe = auth.subscribe(setAuthState);
    return unsubscribe;
  }, []);

  const user = authState.profile;

  // P-009 fix: use shared useDoctorPanelState hook for tab/URL/patient state.
  // Dentistry uses 'visits' (plural) for visitDeepLinkTab.
  const {
    activeTab,
    handleTabChange,
    patientIdFromUrl,
    visitIdFromUrl,
    selectedPatient,
    setSelectedPatient,
  } = useDoctorPanelState({
    // Phase 4: sidebar reduced to 4 tabs — queue / visit / patients / photos.
    defaultTab: 'queue',
    visitDeepLinkTab: 'visit',
    patientDeepLinkTab: 'patients',
  }) as DoctorPanelState;

  // STRAT#34: useTranslation adapter for confirm/notify i18n.
  // PR-UI-15-3: moved above the worklist hook — the hook needs tI18n for the
  // DTO labels (hook order stays consistent across renders).
  const { t: tI18n } = useTranslation();

  const handleCardKeyDown = useCallback((event: React.KeyboardEvent<HTMLElement>, action: () => void) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  }, []);
  const [loading, setLoading] = useState(true);
  // P-009: selectedPatient / setSelectedPatient now come from useDoctorPanelState
  // PR-UI-15-4: savedVisitProtocols + protocol loaders/persist/reopen moved
  // verbatim to ./dentist/useDentistVisitProtocols (EMR v2 lifecycle).

  // PR-UI-15-3: worklist state (patients + appointments table + services +
  // refs) + the queues/today data lifecycle moved verbatim to
  // ./dentist/useDentistWorklistData.
  const {
    patients,
    appointmentsTableData,
    appointmentsTableDataRef,
    appointmentsLoading,
    services,
    loadDentistryAppointments,
    ensureCanonicalVisitId,
    loadData,
  } = useDentistWorklistData({ tI18n, activeTab });
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  // PR-UI-15-4: dialog/tooth/price/schedule view-state slice moved verbatim
  // to ./dentist/useDentistDialogs (plain useState — no cross-field reset
  // shapes, unlike the registrar/cashier dialog state machines).
  const {
    showDentalChart, setShowDentalChart,
    showTreatmentPlanner, setShowTreatmentPlanner,
    showPatientCard, setShowPatientCard,
    showDiagnosisForm, setShowDiagnosisForm,
    showVisitProtocol, setShowVisitProtocol,
    showPhotoArchive, setShowPhotoArchive,
    showProtocolTemplates, setShowProtocolTemplates,
    showReports, setShowReports,
    dentalChartData, setDentalChartData,
    showPriceManager, setShowPriceManager,
    selectedServiceForPrice, setSelectedServiceForPrice,
    selectedTooth, setSelectedTooth,
    toothModalOpen, setToothModalOpen,
    protocolTemplateDraft, setProtocolTemplateDraft,
    scheduleNextModal, setScheduleNextModal,
  } = useDentistDialogs();

  // PR-UI-15-4: EMR v2 visit-protocol lifecycle (saved protocols + loaders +
  // persist + reopen + hydrate) — verbatim port; deps-object wiring keeps the
  // original setSelectedPatient / setShowVisitProtocol semantics.
  const {
    savedVisitProtocols,
    loadDentistVisitProtocolByVisitId,
    persistVisitProtocol,
    reopenVisitProtocol,
  } = useDentistVisitProtocols({
    tI18n,
    selectedPatient,
    setSelectedPatient,
    setShowVisitProtocol,
  });

  // P-022 (workflow audit): wire useVisitLifecycle so the in-memory cache
  // is invalidated when the doctor switches between visits or patients.
  // Mirrors the CardiologistPanelUnified wiring (commit 5ee3de3).
  //
  // When currentVisitId / currentPatientId change, the hook:
  //   1. aborts all in-flight requests via AbortController
  //   2. calls cacheService.invalidateByVisit(prevVisitId)
  //   3. calls cacheService.invalidateByPatient(prevPatientId)
  //   4. invokes our onCleanup callback (resets local visit-protocol state)
  //
  // This prevents PHI leaks between patients on rapid visit switches.
  // Non-breaking: existing persistVisitProtocol, handleCompleteVisit, and
  // queue handlers are untouched.
  const lifecycleVisitId = selectedPatient?.visit_id || visitIdFromUrl || null;
  const lifecyclePatientId =
    selectedPatient?.patient?.id ||
    selectedPatient?.patient_id ||
    selectedPatient?.id ||
    patientIdFromUrl ||
    null;
  useVisitLifecycle(
    lifecycleVisitId as unknown as string | number,
    lifecyclePatientId as unknown as string | number,
    {
    invalidateCacheOnChange: true,
    onCleanup: () => {
      // Reset local protocol state so stale data does not bleed into the
      // next visit's view. persistVisitProtocol will be re-invoked by the
      // existing useEffect when selectedPatient changes.
      setShowVisitProtocol(false);
      setProtocolTemplateDraft(null);
      // audit/phase-1, BS-42: also clear the 7 module-level mutable caches
      // so the next patient's appointments / services / visit-protocols are
      // refetched from the backend instead of being served stale from the
      // previous patient's session. Without this, on a shared workstation
      // the previous patient's PHI could be displayed to the next clinician.
      invalidateDentistPanelCaches();
    },
  },
  );
  useEffect(() => {
    appointmentsTableDataRef.current = appointmentsTableData;
  }, [appointmentsTableData]);

  // PR-UI-15-4: loadDentistVisitProtocolsForPatient +
  // loadDentistVisitProtocolByVisitId moved verbatim to
  // ./dentist/useDentistVisitProtocols.

  // Формы данных


  // Refs

  // Используем централизованную систему темизации
  const {
    isDark,
    getColor,
    getSpacing,
    getFontSize
  } = useTheme();

  // C-1 (UX audit): confirm hook for visit completion
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw;
  // C-2 (UX audit): session timeout warning
  const [sessionWarning, setSessionWarning] = useState<{ active: boolean } | null>(null);

  useSessionTimeoutWarning({
    onWarning: () => setSessionWarning({ active: true }),
    onExpired: () => {
      setSessionWarning(null);
      notify.error(tI18n('dental.session_expired'));
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    },
  });

  // Deferred #2: keyboard shortcuts for tab switching, refresh, clear selection.
  useDentalHotkeys({
    handleTabChange,
    refreshData: () => loadDentistryAppointments(true),
    clearSelection: () => setSelectedPatient(null),
  });

  // PR-UI-15-3: loadServices / loadDentistryAppointments / getAllPatientServicesCb
  // / queueUpdated-listener / ensureCanonicalVisitId moved verbatim to
  // ./dentist/useDentistWorklistData.

  const resolvePatientId = useCallback((patient: SelectedPatient | Record<string, unknown> | null | undefined) => {
    const record = (patient ?? {}) as Record<string, unknown>;
    const nestedPatient = record.patient as { id?: string | number; [k: string]: unknown } | undefined;
    return nestedPatient?.id || record.patient_id || record.id || null;
  }, []);

  const resolvePatientName = useCallback((patient: SelectedPatient | Record<string, unknown> | null | undefined) => {
    const record = (patient ?? {}) as Record<string, unknown>;
    return (record.patient_name as string) || (record.patient_fio as string) || (record.name as string) || tI18n('dental.dental_panel_patient_default');
  }, [tI18n]);

  // Обработчики для таблицы записей
  const handleAppointmentRowClick = async (row: Appointment) => {
    logger.info('Клик по записи:', row);
    // Можно открыть детали записи или переключиться на прием
    if (row.patient_fio) {
      const visitId = await ensureCanonicalVisitId(row);
      if (!visitId) {
        logger.error('[Dentist] Не удалось определить канонический visit_id', row);
        return;
      }

      // Создаем объект пациента для переключения на прием
      const patientData: SelectedPatient = {
        id: row.id,
        appointment_id: (row.appointment_id as string | number | null | undefined) || null,
        visit_id: visitId,
        patient_name: row.patient_fio,
        phone: row.patient_phone || (row.phone as string) || '',
        number: row.id,
        doctor_queue_entry_id: resolveDoctorQueueEntryId(row as Record<string, unknown>),
        source: 'appointments'
      };
      setSelectedPatient(patientData);
      handleTabChange('visit');
    }
  };

  const handleAppointmentActionClick = async (action: string, row: Appointment, event: React.MouseEvent<HTMLElement>) => {
    logger.info('[Dentist] handleAppointmentActionClick:', action, row);
    event.stopPropagation();

    switch (action) {
      case 'view':
        await handleAppointmentRowClick(row);
        break;
      case 'call':
        // Вызвать пациента
        try {
          const queueEntryId = resolveDoctorQueueEntryId(row as Record<string, unknown>);
          if (queueEntryId === null) {
            logger.warn('[Dentist] Cannot start visit without OnlineQueueEntry id', row);
            notify.error(tI18n('dental.no_queue_id_for_visit'));
            break;
          }
          const token = tokenManager.getAccessToken();
          const response = await apiClient.post(`/doctor/queue/${queueEntryId}/start-visit`);

          if (response.status < 400) {
            logger.info('[Dentist] Пациент вызван:', row.patient_fio);
            await loadDentistryAppointments(true);
          }
        } catch (error: unknown) {
          logger.error('[Dentist] Ошибка вызова пациента:', error);
        }
        break;
      case 'payment':
        logger.info('[Dentist] Открытие окна оплаты для:', row.patient_fio);
        notify.info(tI18n('dental.dental_panel_payment_todo', { name: row.patient_fio }));
        break;
      case 'print':
        logger.info('[Dentist] Печать талона для:', row.patient_fio);
        try {
          const printResult = await printPanelTicket(row as Record<string, unknown>, {
            specialtyName: tI18n('dental.dental_panel_specialty_name')
          }) as { message?: string } | undefined;
          notify.success(printResult?.message || tI18n('dental.dental_panel_ticket_printed', { name: row.patient_fio }));
        } catch (error: unknown) {
          logger.error('[Dentist] Ошибка печати талона:', error);
          notify.error(getErrorMessage(error) || tI18n('dental.dental_panel_ticket_print_failed'));
        }
        break;
      case 'complete':
        // Завершить приём
        try {
          const visitId = await ensureCanonicalVisitId(row);
          if (!visitId) {
            logger.error('[Dentist] Нельзя открыть протокол без канонического visit_id', row);
            break;
          }

          const patient: SelectedPatient = {
            id: row.id,
            appointment_id: (row.appointment_id as string | number | null | undefined) || null,
            visit_id: visitId,
            patient_name: row.patient_fio,
            phone: row.patient_phone || (row.phone as string) || '',
            number: row.id,
            doctor_queue_entry_id: resolveDoctorQueueEntryId(row as Record<string, unknown>),
            source: 'appointments',
            status: 'in_cabinet'
          };
          logger.info('[Dentist] Завершение приёма для:', patient.patient_name);
          setSelectedPatient(patient);
          handleTabChange('visit');
        } catch (error: unknown) {
          logger.error('[Dentist] Ошибка при завершении приёма:', error);
        }
        break;
      case 'edit':
        // Логика редактирования записи
        break;
      case 'cancel':
        // Логика отмены записи
        break;
      default:
        break;
    }
  };

  // Проверяем демо-режим после всех хуков
  const isDemoMode = window.location.pathname.includes('/medilab-demo');

  // PR-UI-15-3: authHeader (dead, definition-only) + loadPatients +
  // loadTreatmentPlans / loadProsthetics no-op stubs (dead, PR-43/Medium-24
  // endpoints pending backend) dropped; loadData moved verbatim to
  // ./dentist/useDentistWorklistData. The panel keeps only the loading gate
  // around the hook's loadData (verbatim setLoading semantics).
  useEffect(() => {
    const runLoad = async () => {
      setLoading(true);
      try {
        await loadData();
      } catch (error: unknown) {
        logger.error('Ошибка загрузки данных:', error);
      } finally {
        setLoading(false);
      }
    };
    runLoad();
  }, [loadData]);

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
  }, [location.search, patientIdFromUrl, visitIdFromUrl, appointmentsTableData, loadDentistryAppointments]); // eslint-disable-line react-hooks/exhaustive-deps

  // Обработчики
  const handlePatientSelect = (patient: SelectedPatient | Record<string, unknown> | null) => {
    const normalizedPatient: SelectedPatient = {
      ...(patient as Record<string, unknown>),
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    } as SelectedPatient;
    setSelectedPatient(normalizedPatient);

    if (normalizedPatient.visit_id) {
      handleTabChange('visit');
      return;
    }

    notify.info(tI18n('dental.no_active_visit'));
    handleTabChange('patients');
  };

  // Сохранение EMR






































  // Завершение визита
  //
  // Унифицированная функция завершения приёма для стоматолога.
  // Следует тому же контракту, что и Cardiologist/Dermatologist:
  //   1. resolveDoctorQueueEntryId(selectedPatient) — canonical entry id
  //   2. queueService.completeVisit(entryId, payload) — POST /doctor/queue/{id}/complete
  //   3. Сброс состояния и возврат на вкладку очереди
  //   4. callNextWaiting('dentistry') — автовызов следующего пациента
  //
  // Контракт SSOT (DoctorPanels.contract.test.jsx) требует:
  //   - НЕ использовать row.id / selectedPatient.id напрямую
  //   - НЕ использовать /registrar/queue/${...}/start-visit
  //   - использовать resolveDoctorQueueEntryId + /doctor/queue/${queueEntryId}/complete
  // C-3 (UX audit, port of cardio P-020): critical ICD-10 codes that require
  // secondary confirmation before the visit can be completed. These are
  // dental diagnoses with high clinical stakes — an erroneous entry could
  // trigger unnecessary surgical intervention, hospitalization, or IV
  // antibiotics. The doctor must explicitly confirm when one of these codes
  // is present in the visit's icd10 field.
  const CRITICAL_ICD10_CODES = useRef(['K04', 'K10']).current;

  const getCriticalDiagnosisWarning = useCallback(
    (icd10Code: unknown) => {
      if (!icd10Code || typeof icd10Code !== 'string') return null;
      const code = icd10Code.trim().toUpperCase();
      // Match by prefix (e.g. "K04" matches "K04.0", "K04.9", "K049")
      for (const prefix of CRITICAL_ICD10_CODES) {
        if (code.startsWith(prefix)) {
          return {
            code: prefix,
            label: tI18n(`dental.dental_panel_critical_${prefix}`),
            fullCode: code,
          };
        }
      }
      return null;
    },
    [CRITICAL_ICD10_CODES, tI18n]
  );

  const handleCompleteVisit = async () => {
    if (!selectedPatient) {
      notify.error(tI18n('dental.no_patient_for_complete'));
      return;
    }

    const queueEntryId = resolveDoctorQueueEntryId(selectedPatient);
    if (queueEntryId === null) {
      logger.error('[Dentistry] handleCompleteVisit: нет queueEntryId', { selectedPatient });
      notify.error(tI18n('dental.no_queue_id_for_complete'));
      return;
    }

    // C-1 + C-3 (UX audit): tiered confirmation before completing the visit.
    // C-3: if the ICD-10 code matches a critical dental diagnosis (K04 —
    // pulp/periapical diseases, K10 — jaw diseases including osteomyelitis
    // and abscess), we show the strongest warning (intent='danger') and
    // require explicit confirmation. This prevents accidental entry of a
    // diagnosis that could trigger unnecessary surgical intervention,
    // hospitalization, or IV antibiotics.
    const visitProtocol = selectedPatient?.visitData || null;
    const icd10ForCheck = visitProtocol?.icd10 || visitProtocol?.icdCode || '';
    const criticalWarning = getCriticalDiagnosisWarning(icd10ForCheck);

    let confirmOptions;
    if (criticalWarning) {
      confirmOptions = {
        title: tI18n('dental.dental_panel_critical_title', { label: criticalWarning.label, code: criticalWarning.code }),
        message: tI18n('dental.dental_panel_critical_message', { fullCode: criticalWarning.fullCode, label: criticalWarning.label }),
        description: tI18n('dental.dental_panel_critical_description'),
        confirmLabel: tI18n('dental.dental_panel_critical_confirm'),
        cancelLabel: tI18n('dental.dental_panel_critical_cancel'),
        intent: 'danger',
      };
    } else {
      confirmOptions = {
        title: tI18n('dental.dental_panel_complete_title'),
        message: tI18n('dental.dental_panel_complete_message'),
        description: tI18n('dental.dental_panel_complete_description'),
        confirmLabel: tI18n('dental.dental_panel_complete_confirm'),
        cancelLabel: tI18n('dental.dental_panel_complete_cancel'),
        intent: 'primary',
      };
    }

    const ok = await confirm(confirmOptions);
    if (!ok) {
      return;
    }

    try {
      setLoading(true);
      logger.info('[Dentistry] handleCompleteVisit: start', { queueEntryId, selectedPatient });

      const patientId =
        selectedPatient?.patient?.id ||
        selectedPatient?.patient_id ||
        selectedPatient?.id ||
        null;

      // Минимальный payload: стоматолог использует EMR v2 для протокола визита,
      // а в queue completeVisit передаём только ключевые поля для закрытия очереди.
      const visitProtocol = selectedPatient?.visitData || null;
      const visitPayload = {
        patient_id: patientId,
        complaint: visitProtocol?.chiefComplaint || visitProtocol?.complaint || '',
        diagnosis: visitProtocol?.diagnosis || '',
        icd10: visitProtocol?.icd10 || visitProtocol?.icdCode || '',
        services: [],
        notes: visitProtocol?.recommendations || visitProtocol?.notes || '',
      };

      logger.info('[Dentistry] handleCompleteVisit: payload', visitPayload);
      await queueService.completeVisit(queueEntryId, visitPayload);
      logger.info('[Dentistry] handleCompleteVisit: completeVisit OK');
      notify.success(tI18n('dental.visit_completed'));

      // Сброс состояния
      setSelectedPatient(null);
      setShowVisitProtocol(false);
      setProtocolTemplateDraft(null);
      handleTabChange('queue');

      // Автовызов следующего пациента по стоматологии
      try {
        logger.info('[Dentistry] callNextWaiting(dentistry): start');
        const next = await queueService.callNextWaiting(SPECIALTY_KEYS.DENTISTRY);
        logger.info('[Dentistry] callNextWaiting(dentistry): result', next);
        if (next?.success && next?.entry?.number) {
          notify.success(tI18n('dental.dental_panel_next_patient_called', { number: next.entry.number }));
        }
      } catch (err) {
        logger.warn('[Dentistry] callNextWaiting(dentistry): failed', err);
        // Не блокируем UI: визит уже завершён, просто информируем
      }
    } catch (error: unknown) {
      logger.error('[Dentistry] handleCompleteVisit: error', error);
      notify.error(
        getErrorMessage(error) || tI18n('dental.dental_panel_complete_failed')
      );
    } finally {
      logger.info('[Dentistry] handleCompleteVisit: finish');
      setLoading(false);
    }
  };























  const handleDiagnosis = (patient: SelectedPatient | Record<string, unknown> | null) => {
    setSelectedPatient({
      ...(patient as Record<string, unknown>),
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    } as SelectedPatient);
    setShowDiagnosisForm(true);
  };

  const handleVisitProtocol = async (patient: SelectedPatient | Record<string, unknown> | null) => {
    const patientRecord = (patient ?? {}) as Record<string, unknown>;
    const visitId = (patientRecord.visit_id as string | number | null | undefined) || await ensureCanonicalVisitId(patientRecord);
    if (!visitId) {
      notify.error(tI18n('dental.protocol_needs_visit_id'));
      return;
    }

    const backendProtocol = await loadDentistVisitProtocolByVisitId(visitId, patient);
    const backendRecord = (backendProtocol ?? {}) as Record<string, unknown>;
    setSelectedPatient({
      ...(patient as Record<string, unknown>),
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient),
      visit_id: visitId,
      visitData: (backendRecord.visitData as Record<string, unknown> | null) || (patientRecord.visitData as Record<string, unknown> | null) || null,
      source: (backendRecord.source as string) || (patientRecord.source as string) || 'appointments',
    } as SelectedPatient);
    setShowVisitProtocol(true);
  };

  const handlePhotoArchive = (patient: SelectedPatient | Record<string, unknown> | null) => {
    setSelectedPatient({
      ...(patient as Record<string, unknown>),
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    } as SelectedPatient);
    setShowPhotoArchive(true);
  };

  const handleProtocolTemplates = () => {
    setShowProtocolTemplates(true);
  };

  const buildVisitProtocolDraftFromTemplate = useCallback((template: Record<string, unknown> | null) => {
    if (!template) {
      return null;
    }

    const templatePhotos = template.photos as Array<Record<string, unknown>> | undefined;
    const templateSteps = template.steps as Array<Record<string, unknown> | string> | undefined;
    const templateMaterials = template.materials as Array<Record<string, unknown>> | undefined;
    const templateAnesthesia = template.anesthesia as Array<Record<string, unknown>> | undefined;
    const templatePrescriptions = template.prescriptions as Array<Record<string, unknown>> | undefined;

    const mapPhotoList = (type: string) => (
      Array.isArray(templatePhotos)
        ? templatePhotos.filter((photo) => photo?.type === type).map((photo: Record<string, unknown>, index: number) => ({
          id: `${type}-${index}-${Date.now()}`,
          url: '',
          filename: (photo.description as string) || `${type} photo ${index + 1}`,
          size: 0,
          type,
          uploadedAt: new Date().toISOString(),
          description: (photo.description as string) || '',
        }))
        : []
    );

    return {
      chiefComplaint: (template.description as string) || (template.name as string) || '',
      historyOfPresentIllness: (template.description as string) || '',
      procedures: Array.isArray(templateSteps)
        ? templateSteps.map((step: Record<string, unknown> | string, index: number) => ({
          name: typeof step === 'string' ? step : (step?.name as string) || tI18n('dental.dental_panel_step_label', { index: index + 1 }),
          teeth: '',
          notes: '',
          duration: typeof step === 'object' && step !== null ? (step as Record<string, unknown>).duration as number || 0 : 0,
        }))
        : [],
      materials: Array.isArray(templateMaterials)
        ? templateMaterials.map((material: Record<string, unknown>) => ({
          name: (material?.name as string) || '',
          quantity: (material?.quantity as string) || '',
          notes: material?.required ? tI18n('dental.dental_panel_required_material') : '',
        }))
        : [],
      anesthesia: Array.isArray(templateAnesthesia)
        ? templateAnesthesia.map((anesthesia: Record<string, unknown>) => ({
          drug: (anesthesia?.drug as string) || '',
          dose: (anesthesia?.dose as string) || '',
          method: (anesthesia?.method as string) || '',
          required: Boolean(anesthesia?.required),
        }))
        : [],
      photos: {
        before: mapPhotoList('before'),
        during: mapPhotoList('during'),
        after: mapPhotoList('after'),
      },
      radiographs: [],
      prescriptions: Array.isArray(templatePrescriptions)
        ? templatePrescriptions.map((prescription: Record<string, unknown>) => ({
          medication: (prescription?.medication as string) || '',
          dosage: (prescription?.dosage as string) || '',
          instructions: (prescription?.instructions as string) || '',
          required: Boolean(prescription?.required),
        }))
        : [],
      recommendations: (template.aftercare as string) || '',
      nextVisit: { date: '', time: '', purpose: '' },
    };
  }, [tI18n]);

  const handleProtocolTemplateSelect = useCallback((template: Record<string, unknown> | null) => {
    const templateName = (template?.name as string) || tI18n('dental.dental_panel_template_default');
    const currentPatientName = resolvePatientName(selectedPatient);
    const draft: SelectedPatient = {
      patient_id: (selectedPatient?.patient_id as string | number | null) || (selectedPatient?.id as string | number | null) || null,
      patient_name: currentPatientName || tI18n('dental.dental_panel_template_label', { name: templateName }),
      patient_fio: currentPatientName || tI18n('dental.dental_panel_template_label', { name: templateName }),
      visit_id: (selectedPatient?.visit_id as string | number | null) || null,
      source: 'protocol-template',
      visitData: buildVisitProtocolDraftFromTemplate(template),
    };

    logger.info('[Dentist] Использую шаблон протокола', {
      template: templateName,
      patient: draft.patient_name,
    });

    setProtocolTemplateDraft(draft);
    setShowProtocolTemplates(false);
    setShowVisitProtocol(true);
  }, [buildVisitProtocolDraftFromTemplate, resolvePatientName, selectedPatient, tI18n]);

  const handleReports = () => {
    setShowReports(true);
  };

  // PR-UI-15-4: persistVisitProtocol + reopenVisitProtocol moved verbatim
  // to ./dentist/useDentistVisitProtocols (EMR v2 POST + reopen flow).

  const handleDentalChart = (patient: SelectedPatient | Record<string, unknown> | null) => {
    setSelectedPatient({
      ...(patient as Record<string, unknown>),
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    } as SelectedPatient);
    setDentalChartData((patient as Record<string, unknown>)?.dentalChart as Record<string, unknown> | null | undefined || null);
    setShowDentalChart(true);
  };

  const handleTreatmentPlanner = async (patient: SelectedPatient | Record<string, unknown> | null) => {
    const patientRecord = (patient ?? {}) as Record<string, unknown>;
    const visitId = (patientRecord.visit_id as string | number | null | undefined) || await ensureCanonicalVisitId(patientRecord);
    if (!visitId) {
      notify.error(tI18n('dental.treatment_plan_needs_visit_id'));
      return;
    }

    setSelectedPatient({
      ...(patient as Record<string, unknown>),
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient),
      visit_id: visitId
    } as SelectedPatient);
    setShowTreatmentPlanner(true);
  };



  // Фильтрация пациентов
  const filteredPatients = patients.filter((patient) => {
    const matchesSearch = !searchQuery ||
    patient.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    patient.phone?.includes(searchQuery);

    const matchesStatus = filterStatus === 'all' || patient.status === filterStatus;

    return matchesSearch && matchesStatus;
  });

  // Статистика
  const stats = useMemo(() => {
    // PR-13: use getLocalDateString() instead of new Date().toDateString()
    // to avoid browser-local timezone issues (off-by-one for early-morning Tashkent)
    const todayString = getLocalDateString();
    const todayAppointmentsCount = appointmentsTableData.filter((apt) => {
      if (!apt.appointment_date && !apt.queue_time && !apt.created_at) {
        return false;
      }
      // Try to get the date from queue_time/created_at (timezone-aware) first,
      // then fall back to appointment_date
      const ts = apt.queue_time || apt.created_at;
      if (ts) {
        const parsedDate = parseRegistrarTimestamp(ts);
        if (!parsedDate) {
          return false;
        }
        const aptDate = getLocalDateString(parsedDate);
        return aptDate === todayString;
      }
      // Fall back to appointment_date (may be YYYY-MM-DD already)
      return apt.appointment_date === todayString;
    }).length;

    const activeTreatmentPlansCount = appointmentsTableData.filter((apt) => apt.status === 'in_progress' || apt.status === 'waiting').length;
    const completedProstheticsCount = appointmentsTableData.filter((apt) => apt.status === 'completed').length;

    return {
      totalPatients: patients.length,
      todayAppointments: todayAppointmentsCount,
      activeTreatmentPlans: activeTreatmentPlansCount,
      completedProsthetics: completedProstheticsCount
    };
  }, [appointmentsTableData, patients]);

  const appointmentSummaryItems = useMemo(() => [
    {
      key: 'total',
      label: tI18n('dental.dental_panel_stat_total'),
      value: appointmentsTableData.length,
      variant: 'info'
    },
    {
      key: 'waiting',
      label: tI18n('dental.dental_panel_stat_waiting'),
      value: countAppointmentsByStatuses(appointmentsTableData, DENTISTRY_WAITING_STATUSES),
      variant: 'warning'
    },
    {
      key: 'called',
      label: tI18n('dental.dental_panel_stat_called'),
      value: countAppointmentsByStatuses(appointmentsTableData, DENTISTRY_CALLED_STATUSES),
      variant: 'primary'
    },
    {
      key: 'completed',
      label: tI18n('dental.dental_panel_stat_completed'),
      value: countAppointmentsByStatuses(appointmentsTableData, DENTISTRY_COMPLETED_STATUSES),
      variant: 'success'
    }
  ], [appointmentsTableData, tI18n]);

  // Вкладки
  // Рендер дашборда
  const renderDashboard = () =>
    <DentalDashboardTab
      appointments={appointmentsTableData as unknown as DentalDashboardAppointment[]}
      patients={patients}
      onGoToAppointments={() => handleTabChange('appointments')}
      onGoToPatients={() => handleTabChange('patients')}
    />;
  const renderPatients = () =>
    <DentalPatientsTab
      patients={patients as unknown as Array<Record<string, unknown>>}
      onSelectPatient={handlePatientSelect as unknown as (patient: Record<string, unknown>) => void}
      onDentalChart={handleDentalChart as unknown as (patient: Record<string, unknown>) => void}
    />;
  const renderAppointments = () =>
  <div className="dental-appointments-root">
      <Card padding="large" className="dental-appointments-card">
        <div className="dental-appointments-header">
          <h3 className="dental-appointments-title">
            <Calendar className="dental-icon-20 dental-text-success dental-mr-8" />
            {tI18n('dental.dental_panel_appointments_title')}
          </h3>
          <AppointmentSummaryBar
            ariaLabel={tI18n('dental.dental_panel_appointments_summary_aria')}
            items={appointmentSummaryItems}
            onRefresh={loadDentistryAppointments}
            refreshDisabled={appointmentsLoading}
            BadgeComponent={Badge}
            ButtonComponent={Button}
            buttonProps={{ variant: 'secondary', size: 'sm' }}
          />
        </div>

        <EnhancedAppointmentsTable
        data={appointmentsTableData as unknown as unknown as AppointmentRow[]}
        loading={appointmentsLoading}
        theme="light"
        language="ru"
        view="doctor"
        selectedRows={new Set()}
        outerBorder={false}
        services={services}
        showCheckboxes={false}
        onRowClick={handleAppointmentRowClick as unknown as (row: unknown) => void}
        onActionClick={handleAppointmentActionClick as unknown as (action: string, row: unknown, event?: unknown) => void} />

      </Card>
    </div>;


  // Рендер осмотров удалён (C-2, UI_AUDIT_PLAN.md): вкладка examinations не входит в
  // 5-tab sidebar (routeRegistry Phase 4: «examinations/diagnoses merged into EMR v2
  // visit screen»), renderExaminations не имел reachable caller.


  // Рендер диагнозов
  const renderDiagnoses = () =>
  <div className="dental-flex-col dental-gap-24">
      <Card padding="large">
        <h3 className="dental-text-primary">{tI18n('dental.dental_panel_diagnoses_title')}</h3>
        <p className="dental-text-desc dental-text-secondary">
          {tI18n('dental.dental_panel_diagnoses_subtitle')}
        </p>

        <div className="dental-grid-auto-fill-250">
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label={tI18n('dental.dental_panel_aria_diagnosis')}
          className="dental-card-btn"
          onClick={() => handleDiagnosis(patient)}
          onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleCardKeyDown(event, () => handleDiagnosis(patient))}
          onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'transparent';
          }}>

              <div className="dental-flex dental-gap-12">
                <div className="dental-icon-bg dental-icon-bg-blue dental-icon-bg-full">
                  <span className="dental-text-value dental-text-white">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="dental-text-primary">{patient.name}</p>
                  <p className="dental-text-desc dental-text-secondary">{tI18n('dental.dental_panel_diagnosis_action')}</p>
                </div>
              </div>
            </div>
        )}
        </div>
      </Card>
    </div>;


  // Рендер протоколов визитов
  const renderVisits = () => {
    // Если выбран пациент из очереди - показываем минималистичный DentalVisitScreen
    if (selectedPatient) {
      return (
        <DentalVisitScreen
          patient={selectedPatient as Record<string, unknown>}
          onCompleteVisit={handleCompleteVisit}
          onBackToQueue={() => {
            setSelectedPatient(null);
            handleTabChange('queue');
          }}
          loading={loading}
        />
      );
    }

    // Иначе показываем список пациентов для выбора протокола
    return (
      <div className="dental-flex-col dental-gap-24">
        <Card padding="large">
          <h3 className="dental-text-primary">{tI18n('dental.dental_panel_visits_title')}</h3>
          <p className="dental-text-desc dental-text-secondary">
            {tI18n('dental.dental_panel_visits_subtitle')}
          </p>

          <div className="dental-grid-auto-fill-250">
            {patients.map((patient) =>
            <div
              key={patient.id}
              role="button"
              tabIndex={0}
              aria-label={tI18n('dental.dental_panel_aria_visit')}
              className="dental-card-btn"
              onClick={() => handleVisitProtocol(patient)}
              onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleCardKeyDown(event, () => handleVisitProtocol(patient))}
              onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.background = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.background = 'transparent';
              }}>

                <div className="dental-flex dental-gap-12">
                  <div className="dental-icon-bg dental-icon-bg-purple dental-icon-bg-full">
                    <span className="dental-text-value dental-text-white">
                      {patient.name?.charAt(0)}
                    </span>
                  </div>
                  <div>
                    <p className="dental-text-primary">{patient.name}</p>
                    <p className="dental-text-desc dental-text-secondary">{tI18n('dental.dental_panel_visit_action')}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>);

  };

  // Рендер фото архива
  const renderPhotos = () =>
  <div className="dental-flex-col dental-gap-24">
      <Card padding="large">
        <h3 className="dental-text-primary">{tI18n('dental.dental_panel_photos_title')}</h3>
        <p className="dental-text-desc dental-text-secondary">
          {tI18n('dental.dental_panel_photos_subtitle')}
        </p>

        <div className="dental-grid-auto-fill-250">
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label={tI18n('dental.dental_panel_aria_photos')}
          className="dental-card-btn"
          onClick={() => handlePhotoArchive(patient)}
          onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleCardKeyDown(event, () => handlePhotoArchive(patient))}
          onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'transparent';
          }}>

              <div className="dental-flex dental-gap-12">
                <div className="dental-icon-bg dental-icon-bg-warning dental-icon-bg-full">
                  <span className="dental-text-value dental-text-white">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="dental-text-primary">{patient.name}</p>
                  <p className="dental-text-desc dental-text-secondary">{tI18n('dental.dental_panel_photos_action')}</p>
                </div>
              </div>
            </div>
        )}
        </div>
      </Card>
    </div>;


  // Рендер шаблонов
  const renderTemplates = () =>
    <DentalTemplatesTab
      onManageTemplates={handleProtocolTemplates}
      templates={[]}
      onApplyTemplate={() => notify.info(tI18n('dental.templates_future'))}
    />;
  const renderReports = () =>
    <DentalReportsTab
      savedVisitProtocols={savedVisitProtocols as unknown as Array<{ visit_id: string | number; patient_name: string; saved_at: string; visitData?: Record<string, unknown> }>}
      onReopenProtocol={reopenVisitProtocol as unknown as (protocol: { visit_id: string | number; patient_name: string; saved_at: string; visitData?: Record<string, unknown> }) => void}
      patients={patients as unknown as Array<Record<string, unknown>>}
      diagnoses={[]}
    />;
  const renderDentalChart = () =>
  <div className="dental-flex-col dental-gap-24">
      <Card padding="large">
        <h3 className="dental-text-primary">{tI18n('dental.dental_panel_chart_title')}</h3>
        <p className="dental-text-desc dental-text-secondary">
          {tI18n('dental.dental_panel_chart_subtitle')}
        </p>

        <div className="dental-grid-auto-fill-250">
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label={tI18n('dental.dental_panel_aria_chart')}
          className="dental-card-btn"
          onClick={() => handleDentalChart(patient)}
          onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleCardKeyDown(event, () => handleDentalChart(patient))}
          onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'transparent';
          }}>

              <div className="dental-flex dental-gap-12">
                <div className="dental-icon-bg dental-icon-bg-blue dental-icon-bg-full">
                  <span className="dental-text-value dental-text-white">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="dental-text-primary">{patient.name}</p>
                  <p className="dental-text-desc dental-text-secondary">{tI18n('dental.dental_panel_chart_action')}</p>
                </div>
              </div>
            </div>
        )}
        </div>
      </Card>
    </div>;


  // Рендер планов лечения


  const renderAIAssistant = () =>
  <div className="dental-flex-col dental-gap-24">
      <Card padding="large">
        <h3 className="dental-text-primary">{tI18n('dental.dental_panel_ai_title')}</h3>
        <AIAssistant
        specialty="dentistry"
        onSuggestionSelect={(type, suggestion) => {
          logger.info('[Dentistry] AI suggestion:', { type, suggestion });
          if (type === 'icd10') {
            notify.success(tI18n('dental.icd_added_from_ai'));
          }
        }} />

      </Card>
    </div>;


  // Рендер контента
  const renderContent = () => {
    switch (activeTab) {
      case 'queue':
        return (
          <QueueIntegration
            specialistId={String(user?.doctor_id || user?.specialist_id || '')}
            specialty="dentistry"
            onPatientSelect={handlePatientSelect}
            onStartVisit={(appointment: Appointment) => {
              setSelectedPatient(appointment as unknown as SelectedPatient);
              handleTabChange('visit');
            }} />);


      case 'patients':
        return renderPatients();
      case 'visit':
      case 'visits':
        // Phase 4: 'visit' is the new sidebar tab; 'visits' kept as
        // alias for back-compat with deep links and old saved URLs.
        return renderVisits();
      case 'photos':
        return renderPhotos();
      case 'ai-assistant':
        return renderAIAssistant();
      default:
        return renderDashboard();
    }
  };

  if (isDemoMode) {
    logger.info('DentistPanelUnified: Skipping render in demo mode');
    return null;
  }

  if (loading) {
    return (
      <div className="dental-p-8">
        <div className="dental-flex-col dental-gap-24">
          <div className="dental-skeleton-bar"></div>
          <div className="dental-skeleton-grid">
            {[...Array(4)].map((_, i) =>
            <div key={i} className="dental-skeleton-card"></div>
            )}
          </div>
        </div>
      </div>);

  }

  const selectedPatientId: string | number | undefined = selectedPatient?.patient?.id || selectedPatient?.patient_id || selectedPatient?.id || undefined;
  const selectedPatientDisplayName =
    selectedPatient?.patient_name || selectedPatient?.patient_fio || selectedPatient?.name || tI18n('dental.dental_panel_patient_default');

  return (
    <div className="dentist-panel dental-text-primary">
      {renderContent()}

      {/* Модальные окна */}
      {showPatientCard && selectedPatient &&
      <PatientCard
        patient={selectedPatient as unknown as PatientFormData}
        onSave={(updatedPatient: unknown) => {
          logger.info('Сохранение пациента:', updatedPatient);
          setShowPatientCard(false);
        }}
        onClose={() => setShowPatientCard(false)} />

      }

      {showDiagnosisForm && selectedPatient &&
      <DiagnosisForm
        patientId={selectedPatientId}
        patientName={selectedPatientDisplayName}
        initialData={selectedPatient.diagnosisData}
        onSave={(diagnosisData: unknown) => {
          logger.info('Сохранение диагнозов:', diagnosisData);
          setShowDiagnosisForm(false);
        }}
        onClose={() => setShowDiagnosisForm(false)} />

      }

      {showVisitProtocol && (selectedPatient || protocolTemplateDraft) &&
      <VisitProtocol
        patientId={((selectedPatient || protocolTemplateDraft)?.patient_id as string | number | undefined) || selectedPatientId}
        patientName={(selectedPatient || protocolTemplateDraft)?.patient_name || selectedPatientDisplayName}
        visitId={((selectedPatient || protocolTemplateDraft)?.visit_id as string | number | undefined) || (selectedPatient?.visit_id as string | number | undefined)}
        initialData={((selectedPatient || protocolTemplateDraft)?.visitData as Record<string, unknown> | null | undefined) || (selectedPatient?.visitData as Record<string, unknown> | null | undefined)}
        onSave={async (visitData: unknown) => {
          logger.info('Сохранение протокола визита:', visitData);
          await persistVisitProtocol(selectedPatient || protocolTemplateDraft, visitData as Record<string, unknown>);
          setShowVisitProtocol(false);
          setProtocolTemplateDraft(null);
        }}
        onComplete={handleCompleteVisit}
        onClose={() => {
          setShowVisitProtocol(false);
          setProtocolTemplateDraft(null);
        }} />

      }

      {showPhotoArchive && selectedPatient &&
      <PhotoArchive
        patientId={selectedPatientId as string | number}
        patientName={selectedPatientDisplayName}
        initialData={selectedPatient.photoArchive}
        onSave={(archiveData: unknown) => {
          logger.info('Сохранение фото архива:', archiveData);
          setShowPhotoArchive(false);
        }}
        onClose={() => setShowPhotoArchive(false)} />

      }

      {showProtocolTemplates &&
      <ProtocolTemplates
        onSelectTemplate={handleProtocolTemplateSelect as unknown as (template: unknown) => void}
        onClose={() => setShowProtocolTemplates(false)} />

      }

      {showReports &&
      <Suspense
        fallback={
          <Card role="status" aria-live="polite" className="dental-lazy-fallback">
            {tI18n('dental.dental_panel_reports_loading')}
          </Card>
        }>
        <LazyReportsAndAnalytics
        patientId={selectedPatient?.id}
        doctorId={user?.id}
        clinicId={user?.clinic_id as string | number | null | undefined}
        initialData={null}
        onSave={(reportData) => {
          logger.info('Сохранение отчета:', reportData);
          setShowReports(false);
        }}
          onClose={() => setShowReports(false)} />
      </Suspense>

      }

      {showDentalChart && selectedPatient &&
      <div className="dental-modal-overlay">
          <div className="dental-modal-card-xl">
            <div className="dental-flex-between-16">
              <h2 className="dental-heading-xl dental-text-primary">
                {tI18n('dental.dental_panel_chart_modal_title', { name: selectedPatientDisplayName })}
              </h2>
              <button
              onClick={() => setShowDentalChart(false)}
              aria-label={tI18n('dental.dental_panel_chart_modal_close', { name: selectedPatientDisplayName })}
              className="dental-text-desc dental-text-secondary"
              onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.color = 'var(--mac-text-primary)';
                e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.color = 'var(--mac-text-secondary)';
                e.currentTarget.style.backgroundColor = 'transparent';
              }}>

                <XCircle className="dental-icon-20" />
              </button>
            </div>
            <TeethChart
            patientId={selectedPatientId}
            initialData={(dentalChartData ?? {}) as Record<string, { status?: string; updatedAt?: string; [key: string]: unknown }>}
            onToothClick={(toothNumber, toothData) => {
              logger.info('Клик по зубу:', toothNumber, toothData);
              setSelectedTooth({ number: toothNumber, data: toothData });
              setToothModalOpen(true);
            }}
            readOnly={false} />

          </div>
        </div>
      }

      {showTreatmentPlanner && selectedPatient &&
      <div className="dental-modal-overlay">
          <div className="dental-modal-card-xl">
            <div className="dental-flex-between-16">
              <h2 className="dental-heading-xl dental-text-primary">
                {tI18n('dental.dental_panel_plan_modal_title', { name: selectedPatientDisplayName })}
              </h2>
              <button
              onClick={() => setShowTreatmentPlanner(false)}
              aria-label={tI18n('dental.dental_panel_plan_modal_close', { name: selectedPatientDisplayName })}
              className="dental-text-desc dental-text-secondary"
              onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.color = 'var(--mac-text-primary)';
                e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.color = 'var(--mac-text-secondary)';
                e.currentTarget.style.backgroundColor = 'transparent';
              }}>

                <XCircle className="dental-icon-20" />
              </button>
            </div>
            <TreatmentPlanner
            patientId={selectedPatientId}
            visitId={(selectedPatient.visit_id as string | number | undefined)}
            teethData={dentalChartData || {}}
            onUpdate={() => {
              logger.info('План лечения обновлен');
            }} />

          </div>
        </div>
      }

      {/* C-2 cleanup (UI_AUDIT_PLAN.md): inline examination modal removed —
           unreachable dead cluster (see git history / renderExaminations note). */}

      {/* Phase 4+ cleanup: treatment + prosthetic forms removed (dead UI) */}

      {/* Модальное окно для работы с зубом */}
      {toothModalOpen && selectedTooth &&
      <ToothModal
        open={toothModalOpen}
        onClose={() => {
          setToothModalOpen(false);
          setSelectedTooth(null);
        }}
        toothNumber={(selectedTooth as { number?: string | number } | null | undefined)?.number}
        toothData={(selectedTooth as { data?: Record<string, unknown> } | null | undefined)?.data}
        onSave={(data: unknown) => {
          logger.info('Сохранение данных зуба:', data);
          // Обновляем данные зубной карты
          setDentalChartData((prev) => ({
            ...prev,
            [(selectedTooth as { number?: string | number })?.number ?? '']: data
          }));
          setToothModalOpen(false);
        }}
        patientId={selectedPatient?.id}
        visitId={(selectedPatient?.visit_id as string | number | undefined)} />

      }

      {/* DentalPriceManager Modal */}
      {showPriceManager && selectedServiceForPrice &&
      <DentalPriceManager
        visitId={(selectedPatient?.visit_id as string | number | undefined)}
        serviceId={selectedServiceForPrice.id}
        serviceName={selectedServiceForPrice.name}
        originalPrice={selectedServiceForPrice.price}
        isOpen={showPriceManager}
        onClose={() => {
          setShowPriceManager(false);
          setSelectedServiceForPrice(null);
        }}
        onPriceSet={(priceData) => {
          logger.info('Price set:', priceData);
          // Можно добавить логику обновления состояния
        }} />

      }

      {/* Модальное окно Schedule Next */}
      {scheduleNextModal.open &&
      <ScheduleNextModal
        isOpen={scheduleNextModal.open}
        onClose={() => setScheduleNextModal({ open: false, patient: null })}
        patient={(scheduleNextModal.patient ?? undefined) as Record<string, unknown> | undefined}
        theme={{ isDark, getColor, getSpacing, getFontSize }}
        specialtyFilter="dentistry" />

      }
      {/* X-13: AIChatWidget removed — AiTab in sidebar provides the same functionality */}


      {/* C-1 (UX audit): portal-mounted ConfirmDialog */}
      {confirmDialog}

      {/* C-2 (UX audit): session timeout warning dialog */}
      {sessionWarning && (
        <SessionWarningModal
          visible={!!sessionWarning}
          onDismiss={() => setSessionWarning(null)}
          onExtend={() => notify.info(tI18n('dental.session_extending'))}
        />
      )}
    </div>);

};

export default DentistPanelUnified;
