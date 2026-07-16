// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
// P-009 fix: shared doctor panel state hook
import { useDoctorPanelState } from '../hooks/useDoctorPanelState';
// S-M-2 fix: lucide-direct replaced with macos <Icon>
import {
  Button, MacOSCard, Badge, Input, MacOSEmptyState,
  Icon } from '../components/ui/macos';

import { useTheme } from '../contexts/ThemeContext';
import { adaptTimeFields } from '../utils/registrarAggregation';
import './dermatology.css';
import AppointmentSummaryBar from '../components/doctor/AppointmentSummaryBar';
import AIAssistant from '../components/ai/AIAssistant';
import ServiceChecklist from '../components/ServiceChecklist';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import SessionWarningModal from '../components/common/SessionWarningModal';
import EditPatientModal from '../components/common/EditPatientModal';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import QueueIntegration from '../components/QueueIntegration';
import { EMRContainerV2 } from '../components/emr-v2/EMRContainerV2';
import ProcedureTemplates from '../components/dermatology/ProcedureTemplates';
import DermaExamsTab from '../components/dermatology/DermaExamsTab';
import DermaHistoryTab from '../components/dermatology/DermaHistoryTab';
import DermaPhotosTab from '../components/dermatology/DermaPhotosTab';
import PrescriptionSystem from '../components/PrescriptionSystem';
import VisitTimeline from '../components/VisitTimeline';
import { printPanelTicket } from '../services/panelPrint';
import { queueService } from '../services/queue';
import { printService } from '../services/print';
import { getApiBaseUrl } from '../api/runtime';
import { api } from '../api/client';  // PR-53: replace raw fetch with axios
import { resolveCanonicalVisitId } from '../utils/canonicalVisit';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
import notify from '../services/notify';
// STRAT#33: useTranslation adapter for confirm/notify i18n.
import { useTranslation } from '../i18n/useTranslation';
import i18n from '../i18n';
import { useConfirm } from '../components/common/ConfirmDialog';
import { useSessionTimeoutWarning } from '../hooks/useSessionTimeoutWarning';
import { useDermaHotkeys } from '../hooks/useDermaHotkeys';
import RoleNotificationCenter from '../components/notifications/RoleNotificationCenter';
import {
  countAppointmentsByStatuses,
  getAllPatientServices,
  makeEnsureCanonicalVisitId,
  normalizeNumericId,
  SPECIALTY_KEYS,
} from '../utils/doctorPanelShared';
import { useVisitLifecycle } from '../hooks/useVisitLifecycle';

const API_V1_BASE = getApiBaseUrl();
const DERMATOLOGY_REQUEST_COOLDOWN_MS = 5000;
const DERMATOLOGY_WAITING_STATUSES = ['waiting', 'confirmed', 'pending'];
const DERMATOLOGY_CALLED_STATUSES = ['called', 'in_progress'];
const DERMATOLOGY_COMPLETED_STATUSES = ['completed', 'done'];
const dermatologyAppointmentsHeaderStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  gap: 'var(--mac-spacing-4)',
  marginBottom: 'var(--mac-spacing-5)',
  flexWrap: 'wrap'
};
const dermatologyAppointmentsTitleStyle = {
  fontSize: 'var(--mac-font-size-lg)',
  fontWeight: 'var(--mac-font-weight-semibold)',
  color: 'var(--mac-text-primary)',
  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
  display: 'flex',
  alignItems: 'center',
  margin: 0,
  minWidth: 'min(100%, 260px)'
};
const dermatologyRequestCache = {
  appointments: { promise: null, data: null, lastAttemptAt: 0 },
  services: { promise: null, data: null, lastAttemptAt: 0 },
  skinExaminations: { promise: null, data: null, lastAttemptAt: 0 },
  cosmeticProcedures: { promise: null, data: null, lastAttemptAt: 0 }
};

// countAppointmentsByStatuses is imported from utils/doctorPanelShared
// (unified implementation shared with Cardiology and Dentistry panels).

function resolveDoctorQueueEntryId(row) {
  const explicitQueueEntryId = row?.doctor_queue_entry_id ?? row?.queue_entry_id ?? null;
  if (explicitQueueEntryId !== null && explicitQueueEntryId !== undefined) {
    return explicitQueueEntryId;
  }

  return null;
}

function getRecentDermatologyCache(cacheEntry, fallbackValue) {
  if (cacheEntry.lastAttemptAt && Date.now() - cacheEntry.lastAttemptAt < DERMATOLOGY_REQUEST_COOLDOWN_MS) {
    return cacheEntry.data ?? fallbackValue;
  }
  return null;
}

// normalizeNumericId is imported from utils/doctorPanelShared
// (unified implementation shared with Cardiology and Dentistry panels).

function splitFullName(fullName) {
  const nameParts = String(fullName || '').trim().split(/\s+/).filter(Boolean);
  return {
    last_name: nameParts[0] || '',
    first_name: nameParts[1] || '',
    middle_name: nameParts[2] || ''
  };
}

function buildDermatologyPatientFromAppointment(appointment, t) {
  if (!appointment) {
    return null;
  }

  const patientId = appointment.patient_id || appointment.id || null;
  if (!patientId) {
    return null;
  }

  const patientName =
    appointment.patient_fio || appointment.patient_name || appointment.name || i18n.t('derma.derma_panel_patient_default');
  const nameParts = splitFullName(patientName);

  return {
    id: patientId,
    patient_id: patientId,
    appointment_id: appointment.appointment_id || null,
    visit_id: normalizeNumericId(appointment.visit_id),
    patient_name: patientName,
    patient_fio: patientName,
    name: patientName,
    last_name: appointment.last_name || nameParts.last_name,
    first_name: appointment.first_name || nameParts.first_name,
    middle_name: appointment.middle_name || nameParts.middle_name,
    phone: appointment.patient_phone || appointment.phone || '',
    birth_date: appointment.patient_birth_year
      ? `${appointment.patient_birth_year}-01-01`
      : appointment.birth_date || '',
    address: appointment.address || '',
    specialty: appointment.specialty || 'dermatology',
    source: appointment.source || 'appointments'
  };
}

function buildPatientsFromAppointments(appointments, t) {
  const patientsById = new Map();

  appointments.forEach((appointment) => {
    const patient = buildDermatologyPatientFromAppointment(appointment, i18n.t.bind(null));
    if (!patient || patientsById.has(patient.patient_id)) {
      return;
    }

    patientsById.set(patient.patient_id, patient);
  });

  return Array.from(patientsById.values());
}

/**
 * Унифицированная панель дерматолога
 * Объединяет: очередь + фото до/после + косметология + AI
 */
const DermatologistPanelUnified = () => {
  // Всегда вызываем хуки первыми
  const { isDark, getColor, getSpacing, getFontSize } = useTheme();
  // QW-5 (UX audit): confirm hook for visit completion
  const [confirm, confirmDialog] = useConfirm();
  // STRAT#33: useTranslation adapter for confirm/notify i18n.
  const { t: tI18n } = useTranslation();
  // QW-6 (UX audit): session timeout warning
  const [sessionWarning, setSessionWarning] = useState(null);

  useSessionTimeoutWarning({
    onWarning: () => setSessionWarning({ active: true }),
    onExpired: () => {
      setSessionWarning(null);
      notify.error(tI18n('derma.session_expired'));
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    },
  });

  // Deferred #2: keyboard shortcuts for tab switching, refresh, clear selection.
  useDermaHotkeys({
    handleTabChange,
    refreshData: () => loadDermatologyAppointments(true),
    clearSelection: () => {
      setSelectedPatient(null);
      setCurrentAppointment(null);
    },
  });
  const location = useLocation();
  // P-009: navigate removed — useDoctorPanelState handles tab URL sync

  // P-009 fix: use shared useDoctorPanelState hook for tab/URL/patient state.
  const {
    activeTab,
    setActiveTab,
    handleTabChange,
    patientIdFromUrl,
    visitIdFromUrl,
    selectedPatient,
    setSelectedPatient,
  } = useDoctorPanelState({
    // Phase 4+: sidebar reduced to 4 tabs — queue / visit / patients / ai.
    defaultTab: 'queue',
    visitDeepLinkTab: 'visit',
    patientDeepLinkTab: 'patients',
  });
  const [selectedServices, setSelectedServices] = useState([]);
  const [visitData, setVisitData] = useState({
    complaint: '',
    diagnosis: '',
    icd10: '',
    notes: ''
  });
  const [loading, setLoading] = useState(false);
  const [scheduleNextModal, setScheduleNextModal] = useState({ open: false, patient: null });
  const [editPatientModal, setEditPatientModal] = useState({ open: false, patient: null, loading: false });

  // Состояния для таблицы записей
  const [appointments, setAppointments] = useState([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [services, setServices] = useState({});
  const appointmentsLoadPromiseRef = useRef(null);
  const urlResolutionRef = useRef({ search: '', refreshAttempted: false, notified: false });

  // Специализированные данные дерматолога
  const [skinExamination, setSkinExamination] = useState({
    patient_id: '',
    visit_id: '',
    examination_date: '',
    skin_type: '',
    skin_condition: '',
    lesions: '',
    distribution: '',
    symptoms: '',
    diagnosis: '',
    treatment_plan: ''
  });

  const [cosmeticProcedure, setCosmeticProcedure] = useState({
    patient_id: '',
    visit_id: '',
    procedure_date: '',
    procedure_type: '',
    area_treated: '',
    products_used: '',
    results: '',
    follow_up: ''
  });

  const [showSkinForm, setShowSkinForm] = useState(false);
  const [showCosmeticForm, setShowCosmeticForm] = useState(false);
  const [skinExaminations, setSkinExaminations] = useState([]);
  const [cosmeticProcedures, setCosmeticProcedures] = useState([]);
  // D-001 fix: photoData now receives state from PhotoUploader via onDataUpdate callback
  const [photoData, setPhotoData] = useState({ before: [], after: [] });

  // Дополнительные состояния из старого файла
  const [patients, setPatients] = useState([]);
  const [currentAppointment, setCurrentAppointment] = useState(null);
  const [emr, setEmr] = useState(null);
  const [prescription, setPrescription] = useState(null);
  const [canCreatePrescription, setCanCreatePrescription] = useState(false);
  const [doctorPrice, setDoctorPrice] = useState('');

  // P-022 (workflow audit): wire useVisitLifecycle so the in-memory cache
  // is invalidated when the doctor switches between visits or patients.
  // Mirrors the CardiologistPanelUnified wiring (commit 5ee3de3).
  //
  // When currentVisitId / currentPatientId change, the hook:
  //   1. aborts all in-flight requests via AbortController
  //   2. calls cacheService.invalidateByVisit(prevVisitId)
  //   3. calls cacheService.invalidateByPatient(prevPatientId)
  //   4. invokes our onCleanup callback (resets local EMR + prescription state)
  //
  // This prevents PHI leaks between patients on rapid visit switches.
  // Non-breaking: existing handleSaveVisit, loadEMR, and queue handlers are
  // untouched. The lifecycle hook only adds cache hygiene on top.
  const lifecycleVisitId =
    selectedPatient?.visit_id || currentAppointment?.visit_id || visitIdFromUrl || null;
  const lifecyclePatientId =
    selectedPatient?.patient?.id ||
    selectedPatient?.patient_id ||
    currentAppointment?.patient_id ||
    patientIdFromUrl ||
    null;
  useVisitLifecycle(lifecycleVisitId, lifecyclePatientId, {
    invalidateCacheOnChange: true,
    onCleanup: () => {
      // Reset local EMR + prescription state so stale data does not bleed
      // into the next visit's view. loadEMR / prescription endpoints will
      // be re-invoked by the existing useEffect when selectedPatient /
      // currentAppointment changes.
      setEmr(null);
      setPrescription(null);
    },
  });

  // PR-47: removed unused showPriceOverride / selectedServiceForPriceOverride state
  // (PriceOverrideManager import also removed — component was not rendered)

  // Локальный справочник цен для дерма/косметологии
  const dermaPriceMap = useMemo(() => ({
    derma_consultation: 50000,
    derma_biopsy: 150000,
    cosm_cleaning: 80000,
    cosm_botox: 300000,
    cosm_laser: 250000
  }), []);

  const servicesSubtotal = useMemo(() => {
    return selectedServices.reduce((sum, id) => sum + (dermaPriceMap[id] || 0), 0);
  }, [selectedServices, dermaPriceMap]);

  const doctorPriceNum = useMemo(() => {
    const n = Number(String(doctorPrice).replace(/[^0-9.-]/g, ''));
    return Number.isFinite(n) ? Math.max(0, n) : 0;
  }, [doctorPrice]);

  const totalCost = useMemo(() => servicesSubtotal + doctorPriceNum, [servicesSubtotal, doctorPriceNum]);

  // Загрузка услуг для правильного отображения в tooltips
  const loadServices = useCallback(async (force = false) => {
    if (!force) {
      if (dermatologyRequestCache.services.promise) {
        return dermatologyRequestCache.services.promise;
      }

      const cachedServices = getRecentDermatologyCache(dermatologyRequestCache.services, {});
      if (cachedServices !== null) {
        setServices(cachedServices);
        return cachedServices;
      }
    }

    const loadPromise = (async () => {
      dermatologyRequestCache.services.lastAttemptAt = Date.now();
      try {
        const token = tokenManager.getAccessToken();
        if (!token) return {};
        const response = await api.get('/registrar/services');
        if (response.status < 400) {
          const data = response.data;
          const servicesData = data.services_by_group || {};
          setServices(servicesData);
          dermatologyRequestCache.services.data = servicesData;
          logger.info('[Dermatology] Услуги загружены:', Object.keys(servicesData).length, 'групп');
          return servicesData;
        }
        return dermatologyRequestCache.services.data || {};
      } catch (error) {
        logger.error('[Dermatology] Ошибка загрузки услуг:', error);
        return dermatologyRequestCache.services.data || {};
      }
    })();

    dermatologyRequestCache.services.promise = loadPromise;
    try {
      return await loadPromise;
    } finally {
      if (dermatologyRequestCache.services.promise === loadPromise) {
        dermatologyRequestCache.services.promise = null;
      }
    }
  }, []);

  // Функция для получения всех услуг пациента из всех записей
  const getAllPatientServicesCb = useCallback((patientId, allAppointments) => {
    return getAllPatientServices(patientId, allAppointments);
  }, []);

  // Загрузка записей дерматолога
  const loadDermatologyAppointments = useCallback(async (force = false) => {
    if (!force) {
      if (appointmentsLoadPromiseRef.current) {
        return appointmentsLoadPromiseRef.current;
      }

      if (dermatologyRequestCache.appointments.promise) {
        return dermatologyRequestCache.appointments.promise;
      }

      const cachedAppointments = getRecentDermatologyCache(dermatologyRequestCache.appointments, []);
      if (cachedAppointments) {
        setAppointments(cachedAppointments);
        setPatients(buildPatientsFromAppointments(cachedAppointments, tI18n));
        return cachedAppointments;
      }
    }

    const loadPromise = (async () => {
      dermatologyRequestCache.appointments.lastAttemptAt = Date.now();
      setAppointmentsLoading(true);
      try {
        const token = tokenManager.getAccessToken();
        if (!token) {
          logger.info('[Dermatology] Нет токена аутентификации');
          return [];
        }

        // Используем комбинированный подход: получаем данные из queues для услуг и из БД для payment_status
        // PR-47: removed unused `today` variable
        // 1. Получаем очереди для информации об услугах
        const queuesResponse = await api.get('/registrar/queues/today');

        const allAppointments = [];
        if (queuesResponse.status < 400) {
          const queuesData = queuesResponse.data;

          // Собираем записи из очередей
          if (queuesData && queuesData.queues && Array.isArray(queuesData.queues)) {
            queuesData.queues.forEach((queue) => {
              if (queue.entries) {
                queue.entries.forEach((entry) => {
                  const doctorQueueEntryId = resolveDoctorQueueEntryId(entry);
                  allAppointments.push({
                    id: entry.id,
                    appointment_id: entry.appointment_id || null,
                    patient_id: entry.patient_id,
                    patient_fio: entry.patient_name || `${entry.patient?.first_name || ''} ${entry.patient?.last_name || ''}`.trim(),
                    patient_phone: entry.phone || '',
                    patient_birth_year: entry.patient_birth_year || '',
                    address: entry.address || '',
                    visit_type:
                      entry.discount_mode === 'repeat' ? tI18n('derma.derma_panel_visit_type_repeat') :
                      entry.discount_mode === 'benefit' ? tI18n('derma.derma_panel_visit_type_benefit') :
                      entry.discount_mode === 'all_free' ? tI18n('derma.derma_panel_visit_type_free') :
                      tI18n('derma.derma_panel_visit_type_paid'),
                    discount_mode: entry.discount_mode || 'none',
                    services: entry.services || [],
                    service_codes: entry.service_codes || [],
                    payment_type: entry.payment_type || null,
                    payment_status: entry.payment_status ?? null,
                    available_actions: entry.available_actions || [],
                    can_mark_paid: Boolean(entry.can_mark_paid),
                    can_start_visit: Boolean(entry.can_start_visit) && doctorQueueEntryId !== null,
                    can_print_ticket: Boolean(entry.can_print_ticket),
                    can_complete: Boolean(entry.can_complete) && doctorQueueEntryId !== null,
                    can_cancel: Boolean(entry.can_cancel),
                    queue_entry_id: entry.queue_entry_id ?? null,
                    doctor_queue_entry_id: doctorQueueEntryId,
                    canonical_record_id: entry.canonical_record_id || entry.id,
                    record_kind: entry.record_kind,
                    source_kind: entry.source_kind,
                    canonical_status: entry.canonical_status ?? null,
                    queue_status: entry.queue_status ?? null,
                    queue_position: entry.queue_position,
                    doctor: entry.doctor_name || tI18n('derma.derma_panel_doctor_default'),
                    specialty: queue.specialty,
                    ...adaptTimeFields(entry, queuesData),
                    status: entry.status ?? null,
                    cost: entry.cost || 0,
                    visit_id: entry.visit_id || null
                  });
                });
              }
            });
          }
        }

        // Фильтруем только дерматологические записи
        const appointmentsData = allAppointments.filter((apt) =>
        apt.specialty === 'derma' || apt.specialty === 'dermatology'
        );

        // Добавляем информацию о всех услугах пациента
        const enrichedAppointmentsData = appointmentsData.map((apt) => {
          const allPatientServices = getAllPatientServicesCb(apt.patient_id, allAppointments);
          return {
            ...apt,
            all_patient_services: allPatientServices.services,
            all_patient_service_codes: allPatientServices.service_codes
          };
        });

        setAppointments(enrichedAppointmentsData);
        setPatients(buildPatientsFromAppointments(enrichedAppointmentsData, tI18n));
        dermatologyRequestCache.appointments.data = enrichedAppointmentsData;
        logger.info('[Dermatology] Загружено записей:', enrichedAppointmentsData.length);
        return enrichedAppointmentsData;
      } catch (error) {
        logger.error('[Dermatology] Ошибка загрузки записей:', error);
        return [];
      } finally {
        setAppointmentsLoading(false);
      }
    })();

    appointmentsLoadPromiseRef.current = loadPromise;
    dermatologyRequestCache.appointments.promise = loadPromise;

    try {
      return await loadPromise;
    } finally {
      if (appointmentsLoadPromiseRef.current === loadPromise) {
        appointmentsLoadPromiseRef.current = null;
      }
      if (dermatologyRequestCache.appointments.promise === loadPromise) {
        dermatologyRequestCache.appointments.promise = null;
      }
    }
  }, [getAllPatientServicesCb]);

  // Загружаем записи при переключении на вкладку
  useEffect(() => {
    if (activeTab === 'appointments' || activeTab === 'patients') {
      loadDermatologyAppointments();
    }

    // Слушаем глобальные события обновления очереди
    const handleQueueUpdate = (event) => {
      logger.info('[Dermatology] Получено событие обновления очереди:', event.detail);
      if (activeTab === 'appointments') {
        loadDermatologyAppointments();
      }
    };
    window.addEventListener('queueUpdated', handleQueueUpdate);

    return () => {
      window.removeEventListener('queueUpdated', handleQueueUpdate);
    };
  }, [activeTab, loadDermatologyAppointments]);

  const ensureCanonicalVisitId = useCallback(
    (row) => makeEnsureCanonicalVisitId(setAppointments, resolveCanonicalVisitId)(row),
    []
  );

  // Функция для создания частичного объекта пациента из данных row (для QR-пациентов)
  const createPartialPatientFromRow = useCallback((row) => {
    const nameParts = (row.patient_fio || '').split(' ').filter(Boolean);
    return {
      firstName: nameParts[1] || '',
      lastName: nameParts[0] || '',
      middleName: nameParts[2] || '',
      phone: row.patient_phone || '',
      address: row.address || '',
      birthDate: row.patient_birth_year ? `${row.patient_birth_year}-01-01` : ''
    };
  }, []);

  // Обработчик редактирования пациента
  const handleEditPatient = useCallback(async (row) => {
    const patientFromCache = patients.find((patient) =>
      patient.patient_id === row.patient_id || patient.id === row.patient_id
    ) || null;

    // Если нет patient_id (QR-пациент), используем частичные данные из row
    if (!row.patient_id) {
      logger.info('[Dermatology] QR-пациент без patient_id, используем частичные данные из row');
      const partialPatient = createPartialPatientFromRow(row);
      setEditPatientModal({ open: true, patient: partialPatient, loading: false });
      return;
    }

    const patientForEdit =
      patientFromCache ||
      buildDermatologyPatientFromAppointment(row, tI18n) ||
      createPartialPatientFromRow(row);

    logger.info('[Dermatology] Открытие модального окна редактирования из локальных данных для:', row.patient_fio);
    setEditPatientModal({ open: true, patient: patientForEdit, loading: false });
  }, [patients, createPartialPatientFromRow]);

  // Обработчики для таблицы записей
  const handleAppointmentRowClick = async (row) => {
    logger.info('Клик по записи:', row);
    // Можно открыть детали записи или переключиться на прием
    if (row.patient_fio) {
      const visitId = await ensureCanonicalVisitId(row);
      if (!visitId) {
        logger.error('[Dermatology] Не удалось определить канонический visit_id', row);
        return;
      }

      // Создаем объект пациента для переключения на прием
      const patientData = {
        id: row.id,
        appointment_id: row.appointment_id || null,
        visit_id: normalizeNumericId(visitId),
        patient_id: row.patient_id,
        patient_name: row.patient_fio,
        phone: row.patient_phone,
        number: row.id,
        doctor_queue_entry_id: resolveDoctorQueueEntryId(row),
        source: 'appointments',
        status: row.status ?? null,
        specialty: row.specialty || 'dermatology'
      };
      setSelectedPatient(patientData);
      setCurrentAppointment(patientData);
      handleTabChange('visit');
    }
  };

  const handleAppointmentActionClick = async (action, row, event) => {
    logger.info('[Dermatology] handleAppointmentActionClick:', action, row);
    event.stopPropagation();

    switch (action) {
      case 'view':
        await handleAppointmentRowClick(row);
        break;
      case 'call':
        // Вызвать пациента
        try {
          const queueEntryId = resolveDoctorQueueEntryId(row);
          if (queueEntryId === null) {
            logger.warn('[Dermatology] Cannot start visit without OnlineQueueEntry id', row);
            notify.error(tI18n('derma.no_queue_id_for_visit'));
            break;
          }
          const token = tokenManager.getAccessToken();
          const response = await api.post(`/doctor/queue/${queueEntryId}/start-visit`);

          if (response.status < 400) {
            logger.info('[Dermatology] Пациент вызван:', row.patient_fio);
            await loadDermatologyAppointments();
          }
        } catch (error) {
          logger.error('[Dermatology] Ошибка вызова пациента:', error);
        }
        break;
      case 'payment':
        logger.info('[Dermatology] Открытие окна оплаты для:', row.patient_fio);
        logger.info('[Dermatology] payment action invoked (disabled for doctor view)', row);
        break;
      case 'print':
        logger.info('[Dermatology] Печать талона для:', row.patient_fio);
        try {
          const printResult = await printPanelTicket(row, {
            specialtyName: tI18n('derma.derma_panel_specialty_name')
          });
          notify.success(printResult?.message || tI18n('derma.derma_panel_ticket_printed', { name: row.patient_fio }));
        } catch (error) {
          logger.error('[Dermatology] Ошибка печати талона:', error);
          notify.error(error.message || tI18n('derma.derma_panel_ticket_print_failed'));
        }
        break;
      case 'complete':
        // Завершить приём
        try {
          const visitId = await ensureCanonicalVisitId(row);
          if (!visitId) {
            logger.error('[Dermatology] Нельзя завершить прием без канонического visit_id', row);
            break;
          }

          const patient = {
            id: row.id,
            appointment_id: row.appointment_id || null,
            visit_id: normalizeNumericId(visitId),
            patient_id: row.patient_id,
            patient_name: row.patient_fio,
            phone: row.patient_phone,
            number: row.id,
            doctor_queue_entry_id: resolveDoctorQueueEntryId(row),
            source: 'appointments',
            status: 'in_cabinet',
            specialty: row.specialty || 'dermatology'
          };
          logger.info('[Dermatology] Завершение приёма для:', patient.patient_name);
          setSelectedPatient(patient);
          setCurrentAppointment(patient);
          handleTabChange('visit');
        } catch (error) {
          logger.error('[Dermatology] Ошибка при завершении приёма:', error);
        }
        break;
      case 'edit':
        // Загружаем полные данные пациента перед открытием модального окна
        logger.info('[Dermatology] Открытие модального окна редактирования для:', row.patient_fio);
        await handleEditPatient(row);
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

  const authHeader = useCallback(() => ({
    Authorization: `Bearer ${tokenManager.getAccessToken()}`
  }), []);

  const getSelectedPatientId = useCallback(() => (
    selectedPatient?.patient?.id ||
    selectedPatient?.patient_id ||
    currentAppointment?.patient_id ||
    null
  ), [currentAppointment?.patient_id, selectedPatient]);

  const getSelectedVisitId = useCallback(() => (
    currentAppointment?.visit_id ||
    selectedPatient?.visit_id ||
    null
  ), [currentAppointment?.visit_id, selectedPatient]);

  const loadPatients = useCallback(async () => {
    try {
      setLoading(true);
      await loadDermatologyAppointments();
    } catch (error) {
      logger.error('Ошибка загрузки пациентов:', error);
    } finally {
      setLoading(false);
    }
  }, [loadDermatologyAppointments]);

  const loadSkinExaminations = useCallback(async (force = false) => {
    if (!force) {
      if (dermatologyRequestCache.skinExaminations.promise) {
        return dermatologyRequestCache.skinExaminations.promise;
      }

      const cachedSkinExaminations = getRecentDermatologyCache(dermatologyRequestCache.skinExaminations, []);
      if (cachedSkinExaminations !== null) {
        setSkinExaminations(cachedSkinExaminations);
        return cachedSkinExaminations;
      }
    }

    const loadPromise = (async () => {
      dermatologyRequestCache.skinExaminations.lastAttemptAt = Date.now();
      try {
        const response = await api.get('/derma/examinations?limit=100');
        if (response.status < 400) {
          const data = response.data;
          const nextSkinExaminations = Array.isArray(data) ? data : [];
          setSkinExaminations(nextSkinExaminations);
          dermatologyRequestCache.skinExaminations.data = nextSkinExaminations;
          return nextSkinExaminations;
        }
        return dermatologyRequestCache.skinExaminations.data || [];
      } catch {

        // эндпоинт может отсутствовать
        return dermatologyRequestCache.skinExaminations.data || [];
      }
    })();

    dermatologyRequestCache.skinExaminations.promise = loadPromise;
    try {
      return await loadPromise;
    } finally {
      if (dermatologyRequestCache.skinExaminations.promise === loadPromise) {
        dermatologyRequestCache.skinExaminations.promise = null;
      }
    }
  }, [authHeader]);

  const loadCosmeticProcedures = useCallback(async (force = false) => {
    if (!force) {
      if (dermatologyRequestCache.cosmeticProcedures.promise) {
        return dermatologyRequestCache.cosmeticProcedures.promise;
      }

      const cachedCosmeticProcedures = getRecentDermatologyCache(dermatologyRequestCache.cosmeticProcedures, []);
      if (cachedCosmeticProcedures !== null) {
        setCosmeticProcedures(cachedCosmeticProcedures);
        return cachedCosmeticProcedures;
      }
    }

    const loadPromise = (async () => {
      dermatologyRequestCache.cosmeticProcedures.lastAttemptAt = Date.now();
      try {
        const response = await api.get('/derma/procedures?limit=100');
        if (response.status < 400) {
          const data = response.data;
          const nextCosmeticProcedures = Array.isArray(data) ? data : [];
          setCosmeticProcedures(nextCosmeticProcedures);
          dermatologyRequestCache.cosmeticProcedures.data = nextCosmeticProcedures;
          return nextCosmeticProcedures;
        }
        return dermatologyRequestCache.cosmeticProcedures.data || [];
      } catch {

        // эндпоинт может отсутствовать
        return dermatologyRequestCache.cosmeticProcedures.data || [];
      }
    })();

    dermatologyRequestCache.cosmeticProcedures.promise = loadPromise;
    try {
      return await loadPromise;
    } finally {
      if (dermatologyRequestCache.cosmeticProcedures.promise === loadPromise) {
        dermatologyRequestCache.cosmeticProcedures.promise = null;
      }
    }
  }, [authHeader]);

  const loadPatientData = useCallback(async () => {
    const patientId = getSelectedPatientId();
    if (!patientId) return;

    try {
      const token = tokenManager.getAccessToken();
      if (!token) return;

      const skinResponse = await api.get(`/derma/examinations?patient_id=${patientId}&limit=10`);
      if (skinResponse.status < 400) {
        const skinData = skinResponse.data;
        setSkinExaminations(Array.isArray(skinData) ? skinData : []);
      }

      const cosmeticResponse = await api.get(`/derma/procedures?patient_id=${patientId}&limit=10`);
      if (cosmeticResponse.status < 400) {
        const cosmeticData = cosmeticResponse.data;
        setCosmeticProcedures(Array.isArray(cosmeticData) ? cosmeticData : []);
      }
    } catch (error) {
      logger.error('[Dermatology] Ошибка загрузки данных пациента:', error);
    }
  }, [getSelectedPatientId]);

  const openSkinExaminationForm = useCallback(() => {
    const patientId = getSelectedPatientId();
    const visitId = getSelectedVisitId();
    setSkinExamination((prev) => ({
      ...prev,
      patient_id: patientId || '',
      visit_id: visitId || ''
    }));
    setShowSkinForm(true);
  }, [getSelectedPatientId, getSelectedVisitId]);

  const openCosmeticProcedureForm = useCallback(() => {
    const patientId = getSelectedPatientId();
    const visitId = getSelectedVisitId();
    setCosmeticProcedure((prev) => ({
      ...prev,
      patient_id: patientId || '',
      visit_id: visitId || ''
    }));
    setShowCosmeticForm(true);
  }, [getSelectedPatientId, getSelectedVisitId]);

  useEffect(() => {
    loadPatients();
    loadSkinExaminations();
    loadCosmeticProcedures();
    loadServices();
  }, [loadPatients, loadSkinExaminations, loadCosmeticProcedures, loadServices]);

  // D-5 (UX audit): auto-promote selectedPatient to currentAppointment
  // so the first visit branch (with EMRContainerV2) renders correctly.
  useEffect(() => {
    if (selectedPatient && !currentAppointment && activeTab === 'visit') {
      setCurrentAppointment(selectedPatient);
    }
  }, [selectedPatient, currentAppointment, activeTab]);

  useEffect(() => {
    if (selectedPatient) {
      loadPatientData();
    }
  }, [selectedPatient, loadPatientData]);

  // ✅ Автоматическая загрузка пациента из URL параметра patientId / visitId
  useEffect(() => {
    const loadPatientFromUrl = async () => {
      // P-009: patientIdFromUrl / visitIdFromUrl come from useDoctorPanelState
      const searchKey = location.search;

      if (!patientIdFromUrl && !visitIdFromUrl) {
        urlResolutionRef.current = {
          search: searchKey,
          refreshAttempted: false,
          notified: false
        };
        return;
      }

      if (urlResolutionRef.current.search !== searchKey) {
        urlResolutionRef.current = {
          search: searchKey,
          refreshAttempted: false,
          notified: false
        };
      }

      // Если пациент уже загружен с этим ID и визитом, пропускаем
      const currentPatientId = selectedPatient?.patient_id || null;
      const currentVisitId = normalizeNumericId(currentAppointment?.visit_id || selectedPatient?.visit_id);
      if (
        patientIdFromUrl &&
        currentPatientId === patientIdFromUrl &&
        (!visitIdFromUrl || currentVisitId === visitIdFromUrl)
      ) {
        urlResolutionRef.current.notified = false;
        return;
      }
      if (
        visitIdFromUrl &&
        currentVisitId === visitIdFromUrl &&
        (!patientIdFromUrl || currentPatientId === patientIdFromUrl)
      ) {
        urlResolutionRef.current.notified = false;
        return;
      }

      try {
        const matchingAppointment = appointments.find((appointment) => {
          if (visitIdFromUrl && normalizeNumericId(appointment.visit_id) === visitIdFromUrl) {
            return true;
          }
          return patientIdFromUrl && appointment.patient_id === patientIdFromUrl;
        });

        const applyAppointmentSelection = (appointment) => {
          const patientObj = buildDermatologyPatientFromAppointment(appointment, i18n.t.bind(null));
          if (!patientObj) {
            return false;
          }

          const nextPatient = {
            ...patientObj,
            visit_id: visitIdFromUrl || normalizeNumericId(patientObj.visit_id) || null,
          };
          setSelectedPatient(nextPatient);
          setCurrentAppointment(nextPatient);
          setActiveTab(visitIdFromUrl ? 'visit' : 'appointments');
          urlResolutionRef.current.notified = false;
          notify.info(tI18n('derma.derma_panel_patient_loaded', { name: patientObj.patient_name }));
          return true;
        };

        if (matchingAppointment && applyAppointmentSelection(matchingAppointment)) {
          return;
        }

        if (!urlResolutionRef.current.refreshAttempted) {
          urlResolutionRef.current.refreshAttempted = true;
          const refreshedAppointments = await loadDermatologyAppointments();
          const refreshedMatch = (refreshedAppointments || []).find((appointment) => {
            if (visitIdFromUrl && normalizeNumericId(appointment.visit_id) === visitIdFromUrl) {
              return true;
            }
            return patientIdFromUrl && appointment.patient_id === patientIdFromUrl;
          });

          if (refreshedMatch && applyAppointmentSelection(refreshedMatch)) {
            return;
          }
        }

        if (visitIdFromUrl || patientIdFromUrl) {
          const fallbackPatientId = normalizeNumericId(patientIdFromUrl || null);
          const fallbackLabel = fallbackPatientId
            ? tI18n('derma.derma_panel_patient_hash', { id: fallbackPatientId })
            : tI18n('derma.derma_panel_visit_hash', { id: visitIdFromUrl });
          const fallbackPatient = {
            id: fallbackPatientId || visitIdFromUrl,
            appointment_id: null,
            visit_id: visitIdFromUrl || null,
            patient_id: fallbackPatientId,
            patient_name: fallbackLabel,
            patient_fio: fallbackLabel,
            phone: '',
            specialty: 'dermatology',
            source: 'url',
            status: 'open',
          };

          setSelectedPatient(fallbackPatient);
          setCurrentAppointment(fallbackPatient);
          setActiveTab(visitIdFromUrl ? 'visit' : 'appointments');
          urlResolutionRef.current.notified = false;
          logger.info('[Dermatology] Пациент из URL не найден в очереди, использую безопасный URL-fallback', {
            visitId: visitIdFromUrl,
            patientId: fallbackPatientId,
          });
          return;
        }

        if (!urlResolutionRef.current.notified) {
          urlResolutionRef.current.notified = true;
          setSelectedPatient(null);
          setCurrentAppointment(null);
          handleTabChange('patients');
          notify.info(
            visitIdFromUrl
              ? tI18n('derma.derma_panel_visit_not_found')
              : tI18n('derma.derma_panel_patient_not_found')
          );
        }
      } catch (error) {
        logger.error('[Dermatology] Не удалось загрузить пациента из URL:', error);
        notify.error(tI18n('derma.patient_load_failed'));
      }
    };

    loadPatientFromUrl();
  }, [location.search, patientIdFromUrl, visitIdFromUrl, selectedPatient?.patient_id, selectedPatient?.visit_id, currentAppointment?.visit_id, appointments, loadDermatologyAppointments, setActiveTab, setSelectedPatient]);

  useEffect(() => {
    const appointmentId = currentAppointment?.appointment_id || null;
    if (!appointmentId) {
      setEmr(null);
      setPrescription(null);
      setCanCreatePrescription(false);
      return;
    }

    let isMounted = true;
    setCanCreatePrescription(false);

    const loadCanonicalStatus = async () => {
      try {
        const response = await api.get(`/appointments/${appointmentId}/status`);

        if (response.status >= 400) {
          return;
        }

        const statusData = response.data;
        if (!isMounted) {
          return;
        }

        setEmr(statusData.emr || null);
        setPrescription(statusData.prescription || null);
        setCanCreatePrescription(statusData.can_create_prescription === true);

        const normalizedStatusVisitId = normalizeNumericId(statusData.visit_id);
        const normalizedCurrentVisitId = normalizeNumericId(currentAppointment?.visit_id);
        if (normalizedStatusVisitId && normalizedStatusVisitId !== normalizedCurrentVisitId) {
          setCurrentAppointment((prev) => prev ? { ...prev, visit_id: normalizedStatusVisitId } : prev);
        }

        const normalizedAppointmentStatus = statusData.appointment?.status || null;
        if (normalizedAppointmentStatus) {
          setCurrentAppointment((prev) => prev ? { ...prev, status: normalizedAppointmentStatus } : prev);
        }
      } catch (error) {
        logger.warn('[Dermatology] Не удалось загрузить canonical status:', error);
      }
    };

    loadCanonicalStatus();

    return () => {
      isMounted = false;
    };
  }, [currentAppointment?.appointment_id, currentAppointment?.id, currentAppointment?.visit_id]);


  const savePrescription = async (prescriptionData) => {
    try {
      const appointmentId = currentAppointment?.appointment_id || null;
      if (!appointmentId) {
        notify.error(tI18n('derma.no_entry_for_prescription'));
        return;
      }
      const response = await api.post(`/appointments/${appointmentId}/prescription`, prescriptionData);

      if (response.status < 400) {
        const savedPrescription = response.data;
        setPrescription(savedPrescription);
        notify.success(tI18n('derma.prescription_saved'));
      } else {
        const error = response.data;
        notify.error(error.detail || tI18n('derma.derma_panel_prescription_save_failed_short'));
      }
    } catch (error) {
      logger.error('DermatologistPanel: Save prescription error:', error);
      notify.error(tI18n('derma.prescription_save_failed'));
    }
  };

  const printPrescription = async (prescriptionData) => {
    const patientFullName =
      selectedPatient?.patient_name ||
      currentAppointment?.patient_fio ||
      currentAppointment?.patient_name ||
      selectedPatient?.name ||
      i18n.t('derma.derma_panel_patient_default');

    const payload = {
      prescription: {
        ...prescriptionData,
        recommendations: prescriptionData.instructions || ''
      },
      patient: {
        id: getSelectedPatientId(),
        full_name: patientFullName,
        birth_date: selectedPatient?.birth_date || currentAppointment?.birth_date || '',
        address: selectedPatient?.address || currentAppointment?.address || '',
        phone: selectedPatient?.phone || currentAppointment?.patient_phone || currentAppointment?.phone || ''
      },
      clinic: {}
    };

    try {
      const result = await printService.printPrescription(payload);

      if (!result.success) {
        throw new Error(result.error || tI18n('derma.derma_panel_prescription_print_failed'));
      }

      notify.success(result.data?.message || tI18n('derma.derma_panel_prescription_printed'));
      logger.info('[Dermatology] Prescription print success', {
        patientId: payload.patient.id,
        visitId: currentAppointment?.visit_id || null,
        printer: result.data?.printer || null,
        jobId: result.data?.job_id || null
      });
    } catch (error) {
      logger.error('[Dermatology] Prescription print error:', error);
      notify.error(error.message || tI18n('derma.derma_panel_prescription_print_failed'));
      throw error;
    }
  };

  // УДАЛЕНО: старая функция completeVisit заменена на унифицированную handleSaveVisit

  // Обработка AI предложений
  const handleAISuggestion = (type, suggestion) => {
    if (type === 'icd10') {
      setVisitData({ ...visitData, icd10: suggestion });
        notify.success(tI18n('derma.icd_added_from_ai'));
    } else if (type === 'diagnosis') {
      setVisitData({ ...visitData, diagnosis: suggestion });
        notify.success(tI18n('derma.diagnosis_added_from_ai'));
    }
  };

  // Унифицированная обработка сохранения визита
  const handleSaveVisit = async () => {
    // QW-5 (UX audit): confirm before completing the visit
    const ok = await confirm({
      title: tI18n('derma.complete_visit_title'),
      message: tI18n('derma.complete_visit_message'),
      description: tI18n('derma.derma_panel_complete_description'),
      confirmLabel: tI18n('derma.complete_visit_confirm'),
      cancelLabel: tI18n('derma.cancel'),
      intent: 'primary',
    });
    if (!ok) {
      return;
    }

    // Определяем ID записи: приоритет selectedPatient, потом currentAppointment
    const entryId = resolveDoctorQueueEntryId(selectedPatient) ?? resolveDoctorQueueEntryId(currentAppointment);
    if (!entryId) {
      logger.error('[Dermатology] handleSaveVisit: нет entryId');
      notify.error(tI18n('derma.no_patient_for_complete'));
      return;
    }

    try {
      setLoading(true);
      logger.info('[Dermatology] handleSaveVisit: start', { entryId, selectedPatient, currentAppointment });

      // Определяем patient_id из доступных источников
      const patientId = selectedPatient?.patient?.id ||
      selectedPatient?.patient_id ||
      currentAppointment?.patient_id ||
      selectedPatient?.id ||
      entryId;

      // X-2 (UX audit): fetch latest EMR data for the payload
      let emrPayload = { complaint: '', diagnosis: '', icd10: '', notes: '' };
      try {
        const emrRes = await api.get(`/v2/emr/${selectedPatient?.visit_id || currentAppointment?.visit_id}`);
        if (emrRes.status < 400) {
          const emrData = emrRes.data;
          emrPayload = {
            complaint: emrData?.complaints || '',
            diagnosis: emrData?.diagnosis || '',
            icd10: emrData?.icd10_code || emrData?.icd10 || '',
            notes: emrData?.notes || '',
          };
        }
      } catch (emrErr) {
        logger.warn('[Dermatology] Failed to fetch EMR for payload, using local visitData', emrErr);
        emrPayload = { complaint: visitData.complaint, diagnosis: visitData.diagnosis, icd10: visitData.icd10, notes: visitData.notes };
      }

      const visitPayload = {
        patient_id: patientId,
        complaint: emrPayload.complaint,
        diagnosis: emrPayload.diagnosis,
        icd10: emrPayload.icd10,
        services: selectedServices,
        notes: emrPayload.notes
      };

      logger.info('[Dermatology] handleSaveVisit: payload', visitPayload);
      await queueService.completeVisit(entryId, visitPayload);
      logger.info('[Dermatology] handleSaveVisit: completeVisit OK');

      notify.success(tI18n('derma.visit_completed'));

      // D-004 fix: offer to schedule next visit (was dead code — setScheduleNextModal was never called)
      if (selectedPatient) {
        setScheduleNextModal({ open: true, patient: selectedPatient });
      }

      // Очищаем форму и состояние
      setSelectedPatient(null);
      setCurrentAppointment(null);
      setSelectedServices([]);
      setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
      setEmr(null);
      setPrescription(null);
      handleTabChange('queue');

      // Автоматически вызвать следующего пациента по дерматологии
      try {
        logger.info('[Dermatology] callNextWaiting(dermatology): start');
        const next = await queueService.callNextWaiting(SPECIALTY_KEYS.DERMATOLOGY);
        logger.info('[Dermatology] callNextWaiting(dermatology): result', next);
        if (next?.success) {
            notify.success(tI18n('derma.derma_panel_next_patient_called', { number: next.entry.number }));
        }
      } catch (err) {
        logger.warn('[Dermatology] callNextWaiting(dermatology): failed', err);
      }

    } catch (error) {
      logger.error('[Dermatology] handleSaveVisit: error', error);
      notify.error(error.message || tI18n('derma.derma_panel_complete_failed'));
    } finally {
      logger.info('[Dermatology] handleSaveVisit: finish');
      setLoading(false);
    }
  };

  // Обработка осмотра кожи
  const handleSkinExaminationSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...skinExamination,
        patient_id: skinExamination.patient_id || getSelectedPatientId(),
        visit_id: skinExamination.visit_id || getSelectedVisitId() || null
      };
      logger.info('[Dermatology] Сохранение осмотра кожи', payload);

      const response = await api.post('/derma/examinations', payload);

      if (response.status < 400) {
        setShowSkinForm(false);
        setSkinExamination({
          patient_id: '',
          visit_id: '',
          examination_date: '',
          skin_type: '',
          skin_condition: '',
          lesions: '',
          distribution: '',
          symptoms: '',
          diagnosis: '',
          treatment_plan: ''
        });
        loadPatientData();
        notify.success(tI18n('derma.skin_exam_saved'));
      } else {
        const detail = await response.text();
        logger.error('[Dermatology] Ошибка ответа при сохранении осмотра', { status: response.status, detail });
        notify.error(tI18n('derma.skin_exam_save_failed'));
      }
    } catch (error) {
      logger.error('Ошибка сохранения осмотра:', error);
      notify.error(tI18n('derma.skin_exam_save_failed'));
    }
  };

  // Обработка косметической процедуры
  const handleCosmeticProcedureSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...cosmeticProcedure,
        patient_id: cosmeticProcedure.patient_id || getSelectedPatientId(),
        visit_id: cosmeticProcedure.visit_id || getSelectedVisitId() || null
      };
      logger.info('[Dermatology] Сохранение косметической процедуры', payload);

      const response = await api.post('/derma/procedures', payload);

      if (response.status < 400) {
        setShowCosmeticForm(false);
        setCosmeticProcedure({
          patient_id: '',
          visit_id: '',
          procedure_date: '',
          procedure_type: '',
          area_treated: '',
          products_used: '',
          results: '',
          follow_up: ''
        });
        loadPatientData();
        notify.success(tI18n('derma.procedure_saved'));
      } else {
        const detail = await response.text();
        logger.error('[Dermatology] Ошибка ответа при сохранении процедуры', { status: response.status, detail });
        notify.error(tI18n('derma.procedure_save_failed'));
      }
    } catch (error) {
      logger.error('Ошибка сохранения процедуры:', error);
      notify.error(tI18n('derma.procedure_save_failed'));
    }
  };

  if (isDemoMode) {
    logger.info('DermatologistPanelUnified: Skipping render in demo mode');
    return null;
  }

  const appointmentSummaryItems = [
    {
      key: 'total',
      label: tI18n('derma.derma_panel_summary_total'),
      value: appointments.length,
      variant: 'info'
    },
    {
      key: 'waiting',
      label: tI18n('derma.derma_panel_summary_waiting'),
      value: countAppointmentsByStatuses(appointments, DERMATOLOGY_WAITING_STATUSES),
      variant: 'warning'
    },
    {
      key: 'called',
      label: tI18n('derma.derma_panel_summary_called'),
      value: countAppointmentsByStatuses(appointments, DERMATOLOGY_CALLED_STATUSES),
      variant: 'primary'
    },
    {
      key: 'completed',
      label: tI18n('derma.derma_panel_summary_completed'),
      value: countAppointmentsByStatuses(appointments, DERMATOLOGY_COMPLETED_STATUSES),
      variant: 'success'
    }
  ];

  return (
    <div className="derma-page-root">

      <div className="derma-p-0"> {/* Убираем padding, так как он уже есть в main контейнере */}


        {/* Контент вкладок */}
        <div>
          {/* Записи дерматолога.
              Phase 4+: 'patients' tab combines appointments + history. */}
          {(activeTab === 'appointments' || activeTab === 'patients') &&
          <div className="derma-flex-col-24 derma-w-full derma-max-w-none">
              <MacOSCard className="derma-card-w-full">
                <div style={dermatologyAppointmentsHeaderStyle}>
                  <h3 style={dermatologyAppointmentsTitleStyle}>
                    <Icon name="calendar" size={20} className="derma-icon-mr-green" />
                    {tI18n('derma.derma_panel_appointments_title')}
                  </h3>
                  <AppointmentSummaryBar
                    ariaLabel={tI18n('derma.derma_panel_appointments_summary_aria')}
                    items={appointmentSummaryItems}
                    onRefresh={loadDermatologyAppointments}
                    refreshDisabled={appointmentsLoading}
                    buttonProps={{ variant: 'outline' }}
                  />
                </div>

                <EnhancedAppointmentsTable
                data={appointments}
                loading={appointmentsLoading}
                theme={isDark ? 'dark' : 'light'}
                language="ru"
                selectedRows={new Set()}
                outerBorder={false}
                services={services}
                showCheckboxes={false}
                view="doctor"
                onRowClick={handleAppointmentRowClick}
                onActionClick={handleAppointmentActionClick} />

              </MacOSCard>
            </div>
          }

          {/* Список пациентов */}
          {activeTab === 'patients' &&
          <div className="derma-flex-col-24">
              <MacOSCard className="derma-p-8">
                <div className="derma-flex-center">
                  <h3 className="derma-flex-center">
                    <Icon name="person" size={20} className="derma-icon-mr-green" />
                    {tI18n('derma.derma_panel_patients_title')}
                  </h3>
                  <Badge variant="info">{tI18n('derma.derma_panel_patients_count', { count: patients.length })}</Badge>
                </div>

                {loading ?
              <div className="derma-loading-state">
                    <Icon name="arrow.clockwise" size={32} className="derma-loading-icon" />
                    <p className="derma-p-14-secondary">{tI18n('derma.derma_panel_patients_loading')}</p>
                  </div> :

              <div className="derma-flex-col-24">
                    {patients.map((patient) =>
                <div key={patient.id} className="derma-patient-card">
                        <div className="derma-flex-between-top">
                          <div className="derma-flex-1">
                            <div className="derma-flex-center">
                              <h4 className="derma-h4-16-600">
                                {patient.last_name} {patient.first_name} {patient.middle_name}
                              </h4>
                              <Badge variant="success" className="derma-ml-12">{tI18n('derma.derma_panel_badge_dermatology')}</Badge>
                            </div>
                            <div className="derma-patient-info-list">
                              <div className="derma-flex-center">
                                <Icon name="phone" size={18} className="derma-icon-mr derma-text-accent" />
                                {patient.phone}
                              </div>
                              <div className="derma-flex-center">
                                <Icon name="calendar" size={14} className="derma-icon-mr" />
                                {patient.birth_date}
                              </div>
                              <div className="derma-flex-center">
                                <Icon name="person" size={14} className="derma-icon-mr" />
                                ID: {patient.id}
                              </div>
                            </div>
                          </div>
                          <div className="derma-flex-gap-16">
                            <Button
                        variant="outline"
                        onClick={() => {
                          setSelectedPatient(patient);
                          setSkinExamination((prev) => ({
                            ...prev,
                            patient_id: patient.id,
                            visit_id: patient.visit_id || ''
                          }));
                          setShowSkinForm(true);
                        }}
                        className="derma-flex-center">

                              <Icon name="waveform.path.ecg" size={16} />
                              {tI18n('derma.derma_panel_button_exam')}
                            </Button>
                            <Button
                        variant="outline"
                        onClick={() => {
                          setSelectedPatient(patient);
                          setCosmeticProcedure((prev) => ({
                            ...prev,
                            patient_id: patient.id,
                            visit_id: patient.visit_id || ''
                          }));
                          setShowCosmeticForm(true);
                        }}
                        className="derma-flex-center">

                              <Icon name="sparkles" size={16} />
                              {tI18n('derma.derma_panel_button_procedure')}
                            </Button>
                            <Button
                        variant="outline"
                        onClick={() => setSelectedPatient(patient)}
                        className="derma-flex-center">

                              <Icon name="person" size={16} />
                              {tI18n('derma.derma_panel_button_view')}
                            </Button>
                          </div>
                        </div>
                      </div>
                )}
                  </div>
              }
              </MacOSCard>
            </div>
          }

          {/* Прием пациента - EMR система */}
          {activeTab === 'queue' &&
          <QueueIntegration specialty="dermatology" />
          }

          {activeTab === 'visit' && currentAppointment &&
          <div className="derma-flex-col-24">
              <MacOSCard className="derma-p-8">
                <div className="derma-flex-center">
                  <h3 className="derma-flex-center">
                    <Icon name="stethoscope" size={20} className="derma-icon-mr-orange" />
                    {tI18n('derma.derma_panel_visit_title', { name: currentAppointment.patient_name || tI18n('derma.derma_panel_visit_name_unspecified') })}
                  </h3>
                  <Badge variant="info">
                    {tI18n('derma.derma_panel_status_inline', { status: currentAppointment.status })}
                  </Badge>
                </div>

                {/* Временная шкала приема */}
                <VisitTimeline
                appointment={currentAppointment}
                emr={emr}
                prescription={prescription} />


                {/* EMR система */}
                <div className="derma-mt-24">
                  <h4 className="derma-flex-center">
                    <Icon name="doc.text" size={20} className="derma-icon-mr-blue" />
                    {tI18n('derma.derma_panel_emr_title')}
                  </h4>
                  <EMRContainerV2
                  visitId={currentAppointment?.visit_id}
                  patientId={currentAppointment?.patient_id}
                  specialty="dermatology" />

                </div>

                {/* Система рецептов */}
                {emr && !emr.is_draft &&
              <div className="derma-mt-24">
                    <h4 className="derma-flex-center">
                      <Icon name="doc.text" size={20} className="derma-icon-mr-green" />
                      {tI18n('derma.derma_panel_prescription_title')}
                    </h4>
                    <PrescriptionSystem
                  appointment={currentAppointment}
                  emr={emr}
                  prescription={prescription}
                  canCreatePrescription={canCreatePrescription}
                  onSave={savePrescription}
                  onPrint={printPrescription} />

                  </div>
              }

                {/* Кнопка завершения приема */}
                {emr && !emr.is_draft &&
              <div className="derma-mt-24 derma-text-center">
                    <Button
                  onClick={handleSaveVisit}
                  disabled={loading}
                  className="derma-flex-center">

                      {loading ?
                  <Icon name="arrow.clockwise" size={20} className="animate-spin" /> :

                  <Icon name="checkmark.circle" size={20} />
                  }
                      {loading ? tI18n('derma.derma_panel_completing') : tI18n('derma.derma_panel_complete_button')}
                    </Button>
                  </div>
              }
              </MacOSCard>
            </div>
          }

          {/* Прием пациента - простая версия */}
          {/* D-5 (UX audit): removed duplicate visit branch (157 lines).
              The first visit branch (currentAppointment) handles all rendering via EMRContainerV2.
              If selectedPatient exists without currentAppointment, a useEffect auto-promotes it. */}

          {activeTab === 'visit' && !currentAppointment && !selectedPatient &&
          <MacOSCard className="derma-p-48">
              <MacOSEmptyState
              icon="calendar"
              title={tI18n('derma.derma_panel_select_visit_title')}
              description={tI18n('derma.derma_panel_select_visit_desc')}
              action={
              <Button variant="outline" onClick={() => handleTabChange('patients')} className="derma-p-4 derma-mt-16">
                    {tI18n('derma.derma_panel_go_to_appointments')}
                  </Button>
              } />
            </MacOSCard>
          }

          {/* Фото — R-15: extracted to DermaPhotosTab */}
          {activeTab === 'photos' &&
            <DermaPhotosTab
              hasPatient={!!(currentAppointment || selectedPatient)}
              currentAppointment={currentAppointment}
              selectedPatient={selectedPatient}
              photoData={photoData}
              onPhotoUpdate={(updatedPhotos) => {
                if (updatedPhotos) setPhotoData(updatedPhotos);
                loadPatientData();
              }}
              onGoToAppointments={() => handleTabChange('patients')}
            />
          }
          {(activeTab === 'skin' || activeTab === 'cosmetic') &&
            <DermaExamsTab
              activeTab={activeTab}
              skinExamination={skinExamination}
              setSkinExamination={setSkinExamination}
              showSkinForm={showSkinForm}
              skinExaminations={skinExaminations}
              onSkinSubmit={handleSkinExaminationSubmit}
              onOpenSkinForm={openSkinExaminationForm}
              onCancelSkinForm={() => setShowSkinForm(false)}
              cosmeticProcedure={cosmeticProcedure}
              setCosmeticProcedure={setCosmeticProcedure}
              showCosmeticForm={showCosmeticForm}
              cosmeticProcedures={cosmeticProcedures}
              onCosmeticSubmit={handleCosmeticProcedureSubmit}
              onOpenCosmeticForm={openCosmeticProcedureForm}
              onCancelCosmeticForm={() => setShowCosmeticForm(false)}
              getColor={getColor}
              getFontSize={getFontSize}
              getSpacing={getSpacing}
            />
          }
          {activeTab === 'ai' &&
          <AIAssistant
            specialty="dermatology"
            onSuggestionSelect={handleAISuggestion} />

          }

          {/* Управление услугами */}
          {activeTab === 'services' &&
          <div className="derma-flex-col-24">
              <MacOSCard className="derma-p-8">
                <h3 className="derma-flex-center">
                  <Icon name="scissors" size={20} className="derma-icon-mr-orange" />
                  {tI18n('derma.derma_panel_services_title')}
                </h3>

                <div className="derma-flex-col-16">
                  <div>
                    <label className="derma-label-13-mb8">
                      {tI18n('derma.derma_panel_services_select')}
                    </label>

                    {/* Шаблоны процедур */}
                    <ProcedureTemplates
                    visitId={selectedPatient?.visit_id}
                    onSelectProcedure={(procedure) => {
                      logger.info('Выбрана процедура:', procedure);
                      // Добавляем процедуру в список услуг
                      setSelectedServices((prev) => [...prev, {
                        id: Date.now(),
                        name: procedure.name,
                        price: procedure.price,
                        duration: procedure.duration
                      }]);
                    }} />


                    <div className="derma-p-4 derma-mt-16">
                      <ServiceChecklist
                      value={selectedServices}
                      onChange={setSelectedServices}
                      department="derma" />

                    </div>
                  </div>

                  <div className="derma-grid-auto-300">
                    <div>
                      <label className="derma-label-13-mb8">
                        {tI18n('derma.derma_panel_doctor_price_label')}
                      </label>
                      <div className="derma-flex-gap-8">
                        <div className="derma-pos-rel-flex-1">
                          <Icon name="dollarsign.circle" size={16} className="derma-dollar-icon-abs" />
                          <Input
                          type="text"
                          value={doctorPrice}
                          onChange={(e) => setDoctorPrice(e.target.value)}
                          placeholder={tI18n('derma.derma_panel_ph_doctor_price')}
                          inputMode="numeric"
                          className="derma-input-pl-40" />

                        </div>
                        <Button
                        onClick={() => {
                          // PR-47: PriceOverrideManager was dead code (imported but never rendered).
                          // Button now shows a toast instead of calling removed state setters.
                          notify.info(tI18n('derma.price_change_unavailable'));
                        }}
                        variant="primary"
                        aria-label={tI18n('derma.derma_panel_change_price_aria')}
                        title={tI18n('derma.derma_panel_change_price_aria')}>

                          <Icon name="dollarsign.circle" size={16} />
                        </Button>
                      </div>
                    </div>

                    <div>
                      <label className="derma-label-13-mb8">
                        {tI18n('derma.derma_panel_total_label')}
                      </label>
                      <div className="derma-flex-center">
                        <span className="derma-text-18-600-primary">
                          {totalCost.toLocaleString()} UZS
                        </span>
                        <span className="derma-ml-8-text-13-secondary">
                          {tI18n('derma.derma_panel_total_breakdown', {
                            services: servicesSubtotal.toLocaleString(),
                            doctor: doctorPriceNum ? tI18n('derma.derma_panel_doctor_inline', { amount: doctorPriceNum.toLocaleString() }) : ''
                          })}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="derma-price-info-box">
                    <h4 className="derma-price-h4">
                      {tI18n('derma.derma_panel_price_directory')}
                    </h4>
                    <div className="derma-grid-auto-200-13">
                      <div>{tI18n('derma.derma_panel_price_consultation')}</div>
                      <div>{tI18n('derma.derma_panel_price_biopsy')}</div>
                      <div>{tI18n('derma.derma_panel_price_cleaning')}</div>
                      <div>{tI18n('derma.derma_panel_price_botox')}</div>
                      <div>{tI18n('derma.derma_panel_price_laser')}</div>
                      <div>{tI18n('derma.derma_panel_price_doctor_extra')}</div>
                    </div>
                  </div>
                </div>
              </MacOSCard>
            </div>
          }

          {/* История */}
          {/* История — R-15: extracted to DermaHistoryTab.
              Phase 4+: also renders under 'patients' tab. */}
          {(activeTab === 'history' || activeTab === 'patients') &&
            <DermaHistoryTab
              skinExaminations={skinExaminations}
              cosmeticProcedures={cosmeticProcedures}
              getSpacing={getSpacing}
            />
          }

        </div>{/* End of tab content wrapper */}

        {/* Модальное окно Schedule Next */}
        {scheduleNextModal.open &&
        <ScheduleNextModal
          isOpen={scheduleNextModal.open}
          onClose={() => setScheduleNextModal({ open: false, patient: null })}
          patient={scheduleNextModal.patient}
          theme={{ isDark, getColor, getSpacing, getFontSize }}
          specialtyFilter="dermatology" />

        }

        {/* Модальное окно редактирования пациента */}
        {editPatientModal.open &&
        <EditPatientModal
          isOpen={editPatientModal.open}
          onClose={() => setEditPatientModal({ open: false, patient: null, loading: false })}
          patient={editPatientModal.patient}
          onSave={async () => {
            await loadDermatologyAppointments();
            setEditPatientModal({ open: false, patient: null, loading: false });
          }}
          loading={editPatientModal.loading}
          theme={{ isDark, getColor, getSpacing, getFontSize }} />

        }

        {/* AI Chat Widget */}
        {/* QW-5/QW-6 (UX audit): confirm dialog + session timeout warning */}
      {confirmDialog}
      {sessionWarning && (
        <SessionWarningModal
          visible={!!sessionWarning}
          onDismiss={() => setSessionWarning(null)}
          onExtend={() => notify.info(tI18n('derma.session_extending'))}
        />
      )}

      {/* X-13: AIChatWidget removed — AiTab in sidebar provides the same functionality */}

        <RoleNotificationCenter userRole="dermatologist" />
      </div>
    </div>);

};

export default DermatologistPanelUnified;
