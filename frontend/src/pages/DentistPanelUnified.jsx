import { lazy, Suspense, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import './dentistry.css';
import { useLocation } from 'react-router-dom';
// P-009 fix: shared doctor panel state hook
import { useDoctorPanelState } from '../hooks/useDoctorPanelState';
import { useTheme } from '../contexts/ThemeContext';
import {
  Button, Badge, Card,
  Input } from '../components/ui/macos';
import AppointmentSummaryBar from '../components/doctor/AppointmentSummaryBar';
import auth from '../stores/auth.js';
import { apiClient } from '../api/client';
import AIAssistant from '../components/ai/AIAssistant';
import TeethChart from '../components/dental/TeethChart';
import ToothModal from '../components/dental/ToothModal';
import DentalVisitScreen from '../components/dental/DentalVisitScreen';
import TreatmentPlanner from '../components/dental/TreatmentPlanner';
import PatientCard from '../components/dental/PatientCard';
import DentalPriceManager from '../components/dental/DentalPriceManager';
import ExaminationForm from '../components/dental/ExaminationForm';
import DiagnosisForm from '../components/dental/DiagnosisForm';
import VisitProtocol from '../components/dental/VisitProtocol';
import PhotoArchive from '../components/dental/PhotoArchive';
import ProtocolTemplates from '../components/dental/ProtocolTemplates';
import DentalReportsTab from '../components/dental/DentalReportsTab';
import DentalTemplatesTab from '../components/dental/DentalTemplatesTab';
import DentalDashboardTab from '../components/dental/DentalDashboardTab';
import DentalPatientsTab from '../components/dental/DentalPatientsTab';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import SessionWarningModal from '../components/common/SessionWarningModal';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import QueueIntegration from '../components/QueueIntegration';

import { EMRContainerV2 } from '../components/emr-v2/EMRContainerV2';
import {
  Calendar,
  Stethoscope,
  FileText,
  Eye,
  Search,
  Plus,
  Edit,
  XCircle,
  Smile,
  BarChart3,
  Users,
  DollarSign,
  Scissors,
  Save,
  Building } from
'lucide-react';
import '../styles/animations.css';
import { getApiBaseUrl } from '../api/runtime';
import { resolveCanonicalVisitId } from '../utils/canonicalVisit';
import { printPanelTicket } from '../services/panelPrint';
import notify from '../services/notify';
import { useConfirm } from '../components/common/ConfirmDialog';
import { useSessionTimeoutWarning } from '../hooks/useSessionTimeoutWarning';
import { useDentalHotkeys } from '../hooks/useDentalHotkeys';
import RoleNotificationCenter from '../components/notifications/RoleNotificationCenter';
import {
  DENTIST_DOCUMENTS_STORAGE_KEY,
  parseDentistDocuments,
  upsertDentistVisitProtocol,
} from '../utils/dentistryDocuments';
import {
  buildDentistVisitProtocolCard,
  buildDentistVisitProtocolSaveRequest,
  mapDentistVisitProtocolFromEmr,
  mergeDentistVisitProtocolCards,
} from '../utils/dentistVisitProtocolBridge';
import { isDentistrySpecialty } from '../utils/dentistrySpecialty';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
import { queueService } from '../services/queue';
import {
  countAppointmentsByStatuses,
  getAllPatientServices,
  makeEnsureCanonicalVisitId,
  normalizeNumericId,
  SPECIALTY_KEYS,
} from '../utils/doctorPanelShared';
import { useVisitLifecycle } from '../hooks/useVisitLifecycle';

const LazyReportsAndAnalytics = lazy(() => import('../components/dental/ReportsAndAnalytics'));

const API_V1_BASE = getApiBaseUrl();
const DENTISTRY_WAITING_STATUSES = ['waiting', 'confirmed', 'pending'];
const DENTISTRY_CALLED_STATUSES = ['called', 'in_progress'];
const DENTISTRY_COMPLETED_STATUSES = ['completed', 'done'];
let dentistAppointmentsCache = null;
let dentistAppointmentsLoadPromise = null;
let dentistServicesCache = null;
let dentistServicesLoadPromise = null;
const dentistVisitProtocolsCache = new Map();
const dentistVisitProtocolsLoadPromises = new Map();
const dentistFallbackLoggedKeys = new Set();

// countAppointmentsByStatuses and normalizeNumericId are imported from
// utils/doctorPanelShared (unified across Cardiology / Dermatology / Dentistry).

function resolveDoctorQueueEntryId(row) {
  const explicitQueueEntryId = row?.doctor_queue_entry_id ?? row?.queue_entry_id ?? null;
  if (explicitQueueEntryId !== null && explicitQueueEntryId !== undefined) {
    return explicitQueueEntryId;
  }

  return null;
}

function buildPatientsFromAppointments(appointments) {
  const patientsById = new Map();

  appointments.forEach((appointment) => {
    const patientId = appointment.patient_id || appointment.id;
    if (!patientId || patientsById.has(patientId)) {
      return;
    }

    const patientName =
      appointment.patient_fio || appointment.patient_name || appointment.name || 'Пациент';

    patientsById.set(patientId, {
      id: patientId,
      patient_id: patientId,
      appointment_id: appointment.appointment_id || null,
      visit_id: normalizeNumericId(appointment.visit_id),
      name: patientName,
      patient_name: patientName,
      patient_fio: patientName,
      phone: appointment.patient_phone || appointment.phone || '',
      specialty: appointment.specialty || 'dentistry',
      source: appointment.source || 'appointments',
    });
  });

  return Array.from(patientsById.values());
}

function loadStoredDentistDocuments() {
  if (typeof window === 'undefined') {
    return parseDentistDocuments(null);
  }

  return parseDentistDocuments(window.localStorage.getItem(DENTIST_DOCUMENTS_STORAGE_KEY));
}

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
  });

  const handleCardKeyDown = useCallback((event, action) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  }, []);
  const [patients, setPatients] = useState([]);
  // Phase 4+ cleanup: treatmentPlans/prosthetics state removed (dead UI).
  const [loading, setLoading] = useState(true);
  // P-009: selectedPatient / setSelectedPatient now come from useDoctorPanelState
  const [savedVisitProtocols, setSavedVisitProtocols] = useState(
    () => loadStoredDentistDocuments().visitProtocols
  );
  const [scheduleNextModal, setScheduleNextModal] = useState({ open: false, patient: null });
  const [protocolTemplateDraft, setProtocolTemplateDraft] = useState(null);

  // Состояния для таблицы записей
  const [appointmentsTableData, setAppointmentsTableData] = useState([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [services, setServices] = useState({});
  const appointmentsTableDataRef = useRef([]);
  const appointmentsLoadPromiseRef = useRef(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [showDentalChart, setShowDentalChart] = useState(false);
  const [showTreatmentPlanner, setShowTreatmentPlanner] = useState(false);
  const [showPatientCard, setShowPatientCard] = useState(false);
  const [showExaminationForm, setShowExaminationForm] = useState(false);
  const [showDiagnosisForm, setShowDiagnosisForm] = useState(false);
  const [showVisitProtocol, setShowVisitProtocol] = useState(false);
  const [showPhotoArchive, setShowPhotoArchive] = useState(false);
  const [showProtocolTemplates, setShowProtocolTemplates] = useState(false);
  const [showReports, setShowReports] = useState(false);
  // Phase 4+ cleanup: showTreatmentForm/showProstheticForm removed (dead UI).
  const [dentalChartData, setDentalChartData] = useState(null);

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
  useVisitLifecycle(lifecycleVisitId, lifecyclePatientId, {
    invalidateCacheOnChange: true,
    onCleanup: () => {
      // Reset local protocol state so stale data does not bleed into the
      // next visit's view. persistVisitProtocol will be re-invoked by the
      // existing useEffect when selectedPatient changes.
      setShowVisitProtocol(false);
      setProtocolTemplateDraft(null);
    },
  });
  // Состояние для DentalPriceManager
  const [showPriceManager, setShowPriceManager] = useState(false);
  const [selectedServiceForPrice, setSelectedServiceForPrice] = useState(null);
  const [selectedTooth, setSelectedTooth] = useState(null);
  const [toothModalOpen, setToothModalOpen] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      window.localStorage.setItem(
        DENTIST_DOCUMENTS_STORAGE_KEY,
        JSON.stringify({ visitProtocols: savedVisitProtocols })
      );
    } catch (error) {
      logger.warn('[Dentist] Не удалось сохранить локальные протоколы визита:', error);
    }
  }, [savedVisitProtocols]);

  useEffect(() => {
    appointmentsTableDataRef.current = appointmentsTableData;
  }, [appointmentsTableData]);

  const loadDentistVisitProtocolsForPatient = useCallback(async (patient) => {
    const patientId = patient?.patient?.id || patient?.patient_id || patient?.id || null;
    if (!patientId) {
      return [];
    }

    const cacheKey = String(patientId);
    const cachedProtocols = dentistVisitProtocolsCache.get(cacheKey);
    if (cachedProtocols) {
      return cachedProtocols;
    }

    const inFlightProtocols = dentistVisitProtocolsLoadPromises.get(cacheKey);
    if (inFlightProtocols) {
      return inFlightProtocols;
    }

    logger.info('[Dentist] Загружаю протоколы визитов из EMR v2', {
      patientId,
      patientName: patient?.patient_name || patient?.patient_fio || patient?.name || 'Пациент',
    });

    const loadPromise = (async () => {
      try {
        const response = await apiClient.get(`/v2/emr/patient/${patientId}`, {
          params: { limit: 20 },
          silent: true,
        });

        const summaries = Array.isArray(response.data) ? response.data : [];
        const records = await Promise.all(
          summaries.map(async (summary) => {
            try {
              const emrResponse = await apiClient.get(`/v2/emr/${summary.visit_id}`, {
                silent: true,
                validateStatus: (status) => status === 404 || (status >= 200 && status < 300),
              });

              if (emrResponse.status === 404) {
                return null;
              }

              const protocolRecord = mapDentistVisitProtocolFromEmr(
                emrResponse.data,
                patient,
              );

              if (!protocolRecord) {
                return null;
              }

              return protocolRecord;
            } catch (error) {
              logger.warn('[Dentist] Не удалось загрузить EMR визита для протокола', {
                patientId,
                visitId: summary.visit_id,
                error: error?.message || error,
              });
              return null;
            }
          })
        );

        const filteredRecords = records.filter(Boolean);
        dentistVisitProtocolsCache.set(cacheKey, filteredRecords);
        return filteredRecords;
      } catch (error) {
        dentistVisitProtocolsCache.delete(cacheKey);
        throw error;
      } finally {
        dentistVisitProtocolsLoadPromises.delete(cacheKey);
      }
    })();

    dentistVisitProtocolsLoadPromises.set(cacheKey, loadPromise);
    return loadPromise;
  }, []);

  const loadDentistVisitProtocolByVisitId = useCallback(async (visitId, patient = null) => {
    if (!visitId) {
      return null;
    }

    try {
      const response = await apiClient.get(`/v2/emr/${visitId}`, {
        silent: true,
        validateStatus: (status) => status === 404 || (status >= 200 && status < 300),
      });

      if (response.status === 404) {
        return null;
      }

      const protocolRecord = mapDentistVisitProtocolFromEmr(response.data, patient);
      if (!protocolRecord) {
        return null;
      }

      logger.info('[Dentist] Протокол визита загружен из EMR v2', {
        visitId,
        emrId: response.data?.id,
        status: response.data?.status,
      });

      return protocolRecord;
    } catch (error) {
      logger.warn('[Dentist] Не удалось загрузить протокол визита из EMR v2', {
        visitId,
        error: error?.message || error,
      });
      return null;
    }
  }, []);

  // Формы данных
  const [examinationForm, setExaminationForm] = useState({
    patient_id: '',
    examination_date: '',
    oral_hygiene: '',
    caries_status: '',
    periodontal_status: '',
    occlusion: '',
    missing_teeth: '',
    dental_plaque: '',
    gingival_bleeding: '',
    diagnosis: '',
    recommendations: ''
  });



  // Refs

  // Используем централизованную систему темизации
  const {
    isDark,
    getColor,
    getSpacing,
    getFontSize
  } = useTheme();

  // C-1 (UX audit): confirm hook for visit completion
  const [confirm, confirmDialog] = useConfirm();
  // C-2 (UX audit): session timeout warning
  const [sessionWarning, setSessionWarning] = useState(null);

  useSessionTimeoutWarning({
    onWarning: () => setSessionWarning({ active: true }),
    onExpired: () => {
      setSessionWarning(null);
      notify.error('Сессия истекла. Пожалуйста, войдите снова.');
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

  // Загрузка данных
  // Загрузка услуг для правильного отображения в tooltips
  const loadServices = useCallback(async () => {
    if (dentistServicesCache) {
      setServices(dentistServicesCache);
      return dentistServicesCache;
    }

    if (dentistServicesLoadPromise) {
      return dentistServicesLoadPromise;
    }

    const loadPromise = (async () => {
      try {
        const token = tokenManager.getAccessToken();
        if (!token) return null;
        const response = await fetch(`${API_V1_BASE}/registrar/services`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
          const data = await response.json();
          const servicesData = data.services_by_group || {};
          dentistServicesCache = servicesData;
          setServices(servicesData);
          logger.info('[Dentist] Услуги загружены:', Object.keys(servicesData).length, 'групп');
          return servicesData;
        }

        return null;
      } catch (error) {
        logger.error('[Dentist] Ошибка загрузки услуг:', error);
        return null;
      }
    })();

    dentistServicesLoadPromise = loadPromise;

    try {
      return await loadPromise;
    } finally {
      if (dentistServicesLoadPromise === loadPromise) {
        dentistServicesLoadPromise = null;
      }
    }
  }, []);

  // Функция для получения всех услуг пациента из всех записей
  const getAllPatientServicesCb = useCallback((patientId, allAppointments) => {
    return getAllPatientServices(patientId, allAppointments);
  }, []);

  // Загрузка записей стоматолога
  const loadDentistryAppointments = useCallback(async (forceRefresh = false) => {
    if (!forceRefresh && dentistAppointmentsCache) {
      appointmentsTableDataRef.current = dentistAppointmentsCache;
      setAppointmentsTableData(dentistAppointmentsCache);
      setPatients((prev) => {
        const derivedPatients = buildPatientsFromAppointments(dentistAppointmentsCache);
        return derivedPatients.length > 0 ? derivedPatients : prev;
      });
      return dentistAppointmentsCache;
    }

    if (appointmentsLoadPromiseRef.current || dentistAppointmentsLoadPromise) {
      return appointmentsLoadPromiseRef.current || dentistAppointmentsLoadPromise;
    }

    const loadPromise = (async () => {
      setAppointmentsLoading(true);
      try {
        const token = tokenManager.getAccessToken();
        if (!token) {
          logger.info('Нет токена аутентификации');
          return [];
        }

        // Загружаем ВСЕ очереди для получения полной картины услуг пациентов
        const response = await fetch(`${API_V1_BASE}/registrar/queues/today`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          const data = await response.json();

          // Собираем ВСЕ записи из всех очередей для получения полной картины услуг
          const allAppointments = [];
          if (data && data.queues && Array.isArray(data.queues)) {
            data.queues.forEach((queue) => {
              if (queue.entries) {
                queue.entries.forEach((entry) => {
                  const doctorQueueEntryId = resolveDoctorQueueEntryId(entry);
                  allAppointments.push({
                    id: entry.id,
                    appointment_id: entry.appointment_id || null,
                    visit_id: entry.visit_id || null,
                    patient_id: entry.patient_id,
                    patient_fio: entry.patient_name || `${entry.patient?.first_name || ''} ${entry.patient?.last_name || ''}`.trim(),
                    patient_phone: entry.phone || '',
                    patient_birth_year: entry.patient_birth_year || '',
                    address: entry.address || '',
                    visit_type:
                      entry.discount_mode === 'repeat' ? 'Повторный' :
                      entry.discount_mode === 'benefit' ? 'Льготный' :
                      entry.discount_mode === 'all_free' ? 'All Free' :
                      'Платный',
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
                    doctor: entry.doctor_name || 'Врач',
                    specialty: queue.specialty,
                    created_at: entry.created_at,
                    appointment_date: entry.created_at ? entry.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
                    appointment_time: entry.visit_time || '',
                    status: entry.status ?? null,
                    cost: entry.cost || 0
                  });
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

        dentistAppointmentsCache = enrichedAppointmentsData;
        appointmentsTableDataRef.current = enrichedAppointmentsData;
        setAppointmentsTableData(enrichedAppointmentsData);
        setPatients((prev) => {
          const derivedPatients = buildPatientsFromAppointments(enrichedAppointmentsData);
            return derivedPatients.length > 0 ? derivedPatients : prev;
          });
          return enrichedAppointmentsData;
        }

        logger.error('Ошибка загрузки очередей:', response.status);
        return [];
      } catch (error) {
        logger.error('Ошибка загрузки записей стоматолога:', error);
        return [];
      } finally {
        setAppointmentsLoading(false);
      }
    })();

    appointmentsLoadPromiseRef.current = loadPromise;
    dentistAppointmentsLoadPromise = loadPromise;

    try {
      return await loadPromise;
    } finally {
      if (appointmentsLoadPromiseRef.current === loadPromise) {
        appointmentsLoadPromiseRef.current = null;
      }
      if (dentistAppointmentsLoadPromise === loadPromise) {
        dentistAppointmentsLoadPromise = null;
      }
    }
  }, [getAllPatientServicesCb]);

  // Загружаем записи при переключении на вкладку
  useEffect(() => {
    if (activeTab === 'appointments') {
      loadDentistryAppointments();
    }

    // Слушаем глобальные события обновления очереди
    const handleQueueUpdate = (event) => {
      logger.info('[Dentist] Получено событие обновления очереди:', event.detail);
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
    (row) => makeEnsureCanonicalVisitId(setAppointmentsTableData, resolveCanonicalVisitId)(row),
    []
  );

  const resolvePatientId = useCallback((patient) => (
    patient?.patient?.id || patient?.patient_id || patient?.id || null
  ), []);

  const resolvePatientName = useCallback((patient) => (
    patient?.patient_name || patient?.patient_fio || patient?.name || 'Пациент'
  ), []);

  // Обработчики для таблицы записей
  const handleAppointmentRowClick = async (row) => {
    logger.info('Клик по записи:', row);
    // Можно открыть детали записи или переключиться на прием
    if (row.patient_fio) {
      const visitId = await ensureCanonicalVisitId(row);
      if (!visitId) {
        logger.error('[Dentist] Не удалось определить канонический visit_id', row);
        return;
      }

      // Создаем объект пациента для переключения на прием
      const patientData = {
        id: row.id,
        appointment_id: row.appointment_id || null,
        visit_id: visitId,
        patient_name: row.patient_fio,
        phone: row.patient_phone,
        number: row.id,
        doctor_queue_entry_id: resolveDoctorQueueEntryId(row),
        source: 'appointments'
      };
      setSelectedPatient(patientData);
      handleTabChange('visit');
    }
  };

  const handleAppointmentActionClick = async (action, row, event) => {
    logger.info('[Dentist] handleAppointmentActionClick:', action, row);
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
            logger.warn('[Dentist] Cannot start visit without OnlineQueueEntry id', row);
            notify.error('Cannot start visit without a queue entry id');
            break;
          }
          const token = tokenManager.getAccessToken();
          const response = await fetch(`${API_V1_BASE}/doctor/queue/${queueEntryId}/start-visit`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            }
          });

          if (response.ok) {
            logger.info('[Dentist] Пациент вызван:', row.patient_fio);
            await loadDentistryAppointments(true);
          }
        } catch (error) {
          logger.error('[Dentist] Ошибка вызова пациента:', error);
        }
        break;
      case 'payment':
        logger.info('[Dentist] Открытие окна оплаты для:', row.patient_fio);
        notify.info(`Оплата для пациента: ${row.patient_fio}. Функция будет реализована позже.`);
        break;
      case 'print':
        logger.info('[Dentist] Печать талона для:', row.patient_fio);
        try {
          const printResult = await printPanelTicket(row, {
            specialtyName: 'Стоматология'
          });
          notify.success(printResult?.message || `Талон для ${row.patient_fio} отправлен на печать`);
        } catch (error) {
          logger.error('[Dentist] Ошибка печати талона:', error);
          notify.error(error.message || 'Не удалось отправить талон на печать');
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

          const patient = {
            id: row.id,
            appointment_id: row.appointment_id || null,
            visit_id: visitId,
            patient_name: row.patient_fio,
            phone: row.patient_phone,
            number: row.id,
            doctor_queue_entry_id: resolveDoctorQueueEntryId(row),
            source: 'appointments',
            status: 'in_cabinet'
          };
          logger.info('[Dentist] Завершение приёма для:', patient.patient_name);
          setSelectedPatient(patient);
          handleTabChange('visit');
        } catch (error) {
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

  const authHeader = useCallback(() => ({
    Authorization: `Bearer ${tokenManager.getAccessToken()}`
  }), []);

  const loadPatients = useCallback(async () => {
    try {
      const derivedPatients = buildPatientsFromAppointments(appointmentsTableDataRef.current);
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
      );

      if (refreshedPatients.length > 0) {
        setPatients(refreshedPatients);
      }
    } catch (e) {
      logger.error('Ошибка загрузки пациентов:', e);
    }
  }, [loadDentistryAppointments]);

  const loadTreatmentPlans = useCallback(async () => {
    try {
      // TODO: Implement treatment plans endpoint
      // Phase 4+ cleanup: treatmentPlans state removed (dead UI).
      // const res = await fetch(`${API_V1_BASE}/dental/treatments?limit=100`, { headers: authHeader() });
      // if (res.ok) setTreatmentPlans(await res.json());
      logger.info('Treatment plans endpoint not implemented yet');
    } catch {



      // Игнорируем ошибки загрузки планов лечения
    }}, []);const loadProsthetics = useCallback(async () => {
    try {
      // TODO: Implement prosthetics endpoint
      // Phase 4+ cleanup: prosthetics state removed (dead UI).
      // const res = await fetch(`${API_V1_BASE}/dental/prosthetics?limit=100`, { headers: authHeader() });
      // if (res.ok) setProsthetics(await res.json());
      logger.info('Prosthetics endpoint not implemented yet');
    } catch {



      // Игнорируем ошибки загрузки протезирования
    }}, []);const loadData = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([
      loadPatients(),
      loadPatients()]
      );
    } catch (error) {
      logger.error('Ошибка загрузки данных:', error);
    } finally {
      setLoading(false);
    }
  }, [loadPatients]);

  useEffect(() => {
    loadData();
    loadServices();
  }, [loadData, loadServices]);

  useEffect(() => {
    const selectedPatientIdForProtocols =
      selectedPatient?.patient?.id || selectedPatient?.patient_id || selectedPatient?.id || null;

    if (!selectedPatientIdForProtocols) {
      return;
    }

    let cancelled = false;

    const hydrateDentistVisitProtocols = async () => {
      try {
        const backendProtocols = await loadDentistVisitProtocolsForPatient(selectedPatient);
        if (cancelled || backendProtocols.length === 0) {
          return;
        }

        setSavedVisitProtocols((prev) => mergeDentistVisitProtocolCards(prev, backendProtocols));
      } catch (error) {
        logger.warn('[Dentist] Не удалось синхронизировать историю протоколов из EMR v2', {
          patientId: selectedPatientIdForProtocols,
          error: error?.message || error,
        });
      }
    };

    hydrateDentistVisitProtocols();

    return () => {
      cancelled = true;
    };
  }, [loadDentistVisitProtocolsForPatient, selectedPatient]);

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
        const findMatchingAppointment = (appointments) => {
          if (!Array.isArray(appointments)) {
            return null;
          }

          return appointments.find((appointment) => {
            if (visitIdFromUrl && normalizeNumericId(appointment.visit_id) === visitIdFromUrl) {
              return true;
            }
            return patientIdFromUrl && appointment.patient_id === patientIdFromUrl;
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
            matchingAppointment.name ||
            'Пациент';

          const patientObj = {
            id: matchingAppointment.appointment_id || matchingAppointment.id || patientIdFromUrl || visitIdFromUrl,
            patient_id: matchingAppointment.patient_id || patientIdFromUrl || matchingAppointment.id,
            appointment_id: matchingAppointment.appointment_id || null,
            visit_id: visitIdFromUrl || normalizeNumericId(matchingAppointment.visit_id) || null,
            patient_name: patientName,
            patient_fio: patientName,
            phone: matchingAppointment.patient_phone || matchingAppointment.phone || '',
            source: matchingAppointment.source || 'appointments',
            specialty: matchingAppointment.specialty || 'dental'
          };

          setSelectedPatient(patientObj);
          handleTabChange(patientObj.visit_id ? 'visit' : 'patients');
          logger.info('[Dentist] Загружен пациент из URL:', patientObj.patient_name);
          return;
        }

        if (visitIdFromUrl || patientIdFromUrl) {
          const fallbackLabel = patientIdFromUrl
            ? `Пациент #${patientIdFromUrl}`
            : `Визит #${visitIdFromUrl}`;

          const patientObj = {
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
          if (!dentistFallbackLoggedKeys.has(fallbackLogKey)) {
            dentistFallbackLoggedKeys.add(fallbackLogKey);
            logger.info('[Dentist] Пациент из URL не найден в очереди, использую безопасный URL-fallback:', patientObj.patient_name);
          }
        }
      } catch (error) {
        logger.error('[Dentist] Не удалось загрузить пациента из URL:', error);
      }
    };

    loadPatientFromUrl();
  }, [location.search, patientIdFromUrl, visitIdFromUrl, appointmentsTableData, loadDentistryAppointments]); // eslint-disable-line react-hooks/exhaustive-deps

  // Обработчики
  const handlePatientSelect = (patient) => {
    const normalizedPatient = {
      ...patient,
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    };
    setSelectedPatient(normalizedPatient);

    if (normalizedPatient.visit_id) {
      handleTabChange('visit');
      return;
    }

    notify.info('У пациента нет активного визита. Откройте вкладку «Пациенты» для поиска.');
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
  const CRITICAL_ICD10_CODES = useRef({
    'K04': 'Заболевания пульпы и периапикальных тканей (пульпит, периодонтит)',
    'K10': 'Заболевания челюстей (остеомиелит, абсцесс, киста)',
  }).current;

  const getCriticalDiagnosisWarning = useCallback(
    (icd10Code) => {
      if (!icd10Code || typeof icd10Code !== 'string') return null;
      const code = icd10Code.trim().toUpperCase();
      // Match by prefix (e.g. "K04" matches "K04.0", "K04.9", "K049")
      for (const [prefix, label] of Object.entries(CRITICAL_ICD10_CODES)) {
        if (code.startsWith(prefix)) {
          return { code: prefix, label, fullCode: code };
        }
      }
      return null;
    },
    [CRITICAL_ICD10_CODES]
  );

  const handleCompleteVisit = async () => {
    if (!selectedPatient) {
      notify.error('Не выбран пациент для завершения приёма');
      return;
    }

    const queueEntryId = resolveDoctorQueueEntryId(selectedPatient);
    if (queueEntryId === null) {
      logger.error('[Dentistry] handleCompleteVisit: нет queueEntryId', { selectedPatient });
      notify.error('Невозможно завершить приём без ID записи в очереди');
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
        title: `Критический диагноз: ${criticalWarning.label} (${criticalWarning.code})`,
        message:
          `Код МКБ-10 ${criticalWarning.fullCode} соответствует критическому стоматологическому диагнозу: ` +
          `"${criticalWarning.label}". Подтвердите, что диагноз установлен корректно. ` +
          'Ошибочный диагноз может привести к ненужному хирургическому вмешательству, ' +
          'госпитализации или назначению IV антибиотиков.',
        description:
          'После завершения приёма EMR будет сохранена с этим диагнозом. ' +
          'Изменение диагноза после подписания возможно только через поправку (amend).',
        confirmLabel: 'Подтверждаю диагноз',
        cancelLabel: 'Отмена — проверить диагноз',
        intent: 'danger',
      };
    } else {
      confirmOptions = {
        title: 'Завершить приём?',
        message: 'Приём будет сохранён. Убедитесь, что диагноз, план лечения и протокол заполнены.',
        description: 'После завершения изменения возможны только через поправку EMR.',
        confirmLabel: 'Завершить приём',
        cancelLabel: 'Отмена',
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
      notify.success('Приём завершён успешно');

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
          notify.success(`Вызван следующий пациент №${next.entry.number}`);
        }
      } catch (err) {
        logger.warn('[Dentistry] callNextWaiting(dentistry): failed', err);
        // Не блокируем UI: визит уже завершён, просто информируем
      }
    } catch (error) {
      logger.error('[Dentistry] handleCompleteVisit: error', error);
      notify.error(
        error?.message || 'Не удалось завершить приём. Проверьте соединение и попробуйте снова.'
      );
    } finally {
      logger.info('[Dentistry] handleCompleteVisit: finish');
      setLoading(false);
    }
  };























  const handleExamination = (patient) => {
    const patientId = resolvePatientId(patient);
    setSelectedPatient({
      ...patient,
      patient_id: patientId,
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    });
    setExaminationForm({ ...examinationForm, patient_id: patientId });
    setShowExaminationForm(true);
  };



  const handleDiagnosis = (patient) => {
    setSelectedPatient({
      ...patient,
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    });
    setShowDiagnosisForm(true);
  };

  const handleVisitProtocol = async (patient) => {
    const visitId = patient?.visit_id || await ensureCanonicalVisitId(patient);
    if (!visitId) {
      notify.error('Для протокола визита нужен канонический visit_id. Откройте пациента из вкладки "Записи".');
      return;
    }

    const backendProtocol = await loadDentistVisitProtocolByVisitId(visitId, patient);
    setSelectedPatient({
      ...patient,
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient),
      visit_id: visitId,
      visitData: backendProtocol?.visitData || patient?.visitData || null,
      source: backendProtocol?.source || patient?.source || 'appointments',
    });
    setShowVisitProtocol(true);
  };

  const handlePhotoArchive = (patient) => {
    setSelectedPatient({
      ...patient,
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    });
    setShowPhotoArchive(true);
  };

  const handleProtocolTemplates = () => {
    setShowProtocolTemplates(true);
  };

  const buildVisitProtocolDraftFromTemplate = useCallback((template) => {
    if (!template) {
      return null;
    }

    const mapPhotoList = (type) => (
      Array.isArray(template.photos)
        ? template.photos.filter((photo) => photo?.type === type).map((photo, index) => ({
          id: `${type}-${index}-${Date.now()}`,
          url: '',
          filename: photo.description || `${type} photo ${index + 1}`,
          size: 0,
          type,
          uploadedAt: new Date().toISOString(),
          description: photo.description || '',
        }))
        : []
    );

    return {
      chiefComplaint: template.description || template.name || '',
      historyOfPresentIllness: template.description || '',
      procedures: Array.isArray(template.steps)
        ? template.steps.map((step, index) => ({
          name: typeof step === 'string' ? step : step?.name || `Шаг ${index + 1}`,
          teeth: '',
          notes: '',
          duration: typeof step === 'object' && step !== null ? step.duration || 0 : 0,
        }))
        : [],
      materials: Array.isArray(template.materials)
        ? template.materials.map((material) => ({
          name: material?.name || '',
          quantity: material?.quantity || '',
          notes: material?.required ? 'Обязательный материал' : '',
        }))
        : [],
      anesthesia: Array.isArray(template.anesthesia)
        ? template.anesthesia.map((anesthesia) => ({
          drug: anesthesia?.drug || '',
          dose: anesthesia?.dose || '',
          method: anesthesia?.method || '',
          required: Boolean(anesthesia?.required),
        }))
        : [],
      photos: {
        before: mapPhotoList('before'),
        during: mapPhotoList('during'),
        after: mapPhotoList('after'),
      },
      radiographs: [],
      prescriptions: Array.isArray(template.prescriptions)
        ? template.prescriptions.map((prescription) => ({
          medication: prescription?.medication || '',
          dosage: prescription?.dosage || '',
          instructions: prescription?.instructions || '',
          required: Boolean(prescription?.required),
        }))
        : [],
      recommendations: template.aftercare || '',
      nextVisit: { date: '', time: '', purpose: '' },
    };
  }, []);

  const handleProtocolTemplateSelect = useCallback((template) => {
    const templateName = template?.name || 'Шаблон протокола';
    const currentPatientName = resolvePatientName(selectedPatient);
    const draft = {
      patient_id: selectedPatient?.patient_id || selectedPatient?.id || null,
      patient_name: currentPatientName || `Шаблон: ${templateName}`,
      patient_fio: currentPatientName || `Шаблон: ${templateName}`,
      visit_id: selectedPatient?.visit_id || null,
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
  }, [buildVisitProtocolDraftFromTemplate, resolvePatientName, selectedPatient]);

  const handleReports = () => {
    setShowReports(true);
  };

  const persistVisitProtocol = useCallback(async (patient, visitData) => {
    if (!patient?.visit_id) {
      return;
    }

    const patientId = patient?.patient?.id || patient?.patient_id || patient?.id || null;
    const patientName = patient?.patient_name || patient?.patient_fio || patient?.name || 'Пациент';
    const localRecord = buildDentistVisitProtocolCard(patient, visitData, {
      source: 'local_cache',
    });

    try {
      const payload = buildDentistVisitProtocolSaveRequest(patient, visitData, {
        isDraft: true,
        rowVersion: 0,
      });
      logger.info('[Dentist] Сохраняю протокол визита в EMR v2', {
        visitId: patient.visit_id,
        patientId,
      });

      const response = await apiClient.post(`/v2/emr/${patient.visit_id}`, payload);
      const backendRecord = mapDentistVisitProtocolFromEmr(response.data, patient) || localRecord;

      setSavedVisitProtocols((prev) => upsertDentistVisitProtocol(prev, backendRecord));
      return backendRecord;
    } catch (error) {
      logger.warn('[Dentist] Не удалось сохранить протокол визита в EMR v2, сохраняю локальный кеш', {
        visitId: patient.visit_id,
        patientName,
        error: error?.message || error,
      });

      setSavedVisitProtocols((prev) => upsertDentistVisitProtocol(prev, localRecord));
      return localRecord;
    }
  }, []);

  const reopenVisitProtocol = useCallback(async (protocolRecord) => {
    const backendProtocol = await loadDentistVisitProtocolByVisitId(protocolRecord?.visit_id, protocolRecord);

    if (!backendProtocol && !protocolRecord?.visitData) {
      notify.error('Не удалось открыть протокол визита: данные не найдены.');
      return;
    }

    const selectedProtocol = backendProtocol || protocolRecord;
    setSelectedPatient({
      id: selectedProtocol.patient_id || protocolRecord?.patient_id || null,
      patient_id: selectedProtocol.patient_id || protocolRecord?.patient_id || null,
      patient_name: selectedProtocol.patient_name || protocolRecord?.patient_name || 'Пациент',
      patient_fio: selectedProtocol.patient_name || protocolRecord?.patient_name || 'Пациент',
      visit_id: selectedProtocol.visit_id || protocolRecord?.visit_id || null,
      visitData: selectedProtocol.visitData || protocolRecord?.visitData || null,
      source: selectedProtocol.source || protocolRecord?.source || 'reports',
    });
    setShowVisitProtocol(true);
  }, [loadDentistVisitProtocolByVisitId, setSelectedPatient]);

  const handleDentalChart = (patient) => {
    setSelectedPatient({
      ...patient,
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    });
    setDentalChartData(patient.dentalChart || null);
    setShowDentalChart(true);
  };

  const handleTreatmentPlanner = async (patient) => {
    const visitId = patient?.visit_id || await ensureCanonicalVisitId(patient);
    if (!visitId) {
      notify.error('План лечения требует канонический visit_id. Откройте пациента из вкладки "Записи".');
      return;
    }

    setSelectedPatient({
      ...patient,
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient),
      visit_id: visitId
    });
    setShowTreatmentPlanner(true);
  };

  // Обработчики отправки форм
  const handleExaminationSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_V1_BASE}/dental/examinations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify(examinationForm)
      });
      if (res.ok) {
        setShowExaminationForm(false);
        setExaminationForm({
          patient_id: '', examination_date: '', oral_hygiene: '', caries_status: '',
          periodontal_status: '', occlusion: '', missing_teeth: '', dental_plaque: '',
          gingival_bleeding: '', diagnosis: '', recommendations: ''
        });
        loadDentistryAppointments(true);
      }
    } catch (e) {
      logger.error('Ошибка сохранения осмотра:', e);
    }
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
    const todayString = new Date().toDateString();
    const todayAppointmentsCount = appointmentsTableData.filter((apt) => {
      if (!apt.appointment_date) {
        return false;
      }
      return new Date(apt.appointment_date).toDateString() === todayString;
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
      label: 'Всего',
      value: appointmentsTableData.length,
      variant: 'info'
    },
    {
      key: 'waiting',
      label: 'Ожидают',
      value: countAppointmentsByStatuses(appointmentsTableData, DENTISTRY_WAITING_STATUSES),
      variant: 'warning'
    },
    {
      key: 'called',
      label: 'Вызваны',
      value: countAppointmentsByStatuses(appointmentsTableData, DENTISTRY_CALLED_STATUSES),
      variant: 'primary'
    },
    {
      key: 'completed',
      label: 'Приняты',
      value: countAppointmentsByStatuses(appointmentsTableData, DENTISTRY_COMPLETED_STATUSES),
      variant: 'success'
    }
  ], [appointmentsTableData]);

  // Вкладки
  // Рендер дашборда
  const renderDashboard = () =>
    <DentalDashboardTab
      appointments={appointmentsTableData}
      patients={patients}
      onGoToAppointments={() => handleTabChange('appointments')}
      onGoToPatients={() => handleTabChange('patients')}
    />;
  const renderPatients = () =>
    <DentalPatientsTab
      patients={patients}
      onSelectPatient={handlePatientSelect}
      onDentalChart={handleDentalChart}
    />;
  const renderAppointments = () =>
  <div className="dental-appointments-root">
      <Card padding="lg" className="dental-appointments-card">
        <div className="dental-appointments-header">
          <h3 className="dental-appointments-title">
            <Calendar className="dental-icon-20 dental-text-success dental-mr-8" />
            Записи к стоматологу
          </h3>
          <AppointmentSummaryBar
            ariaLabel="Сводка записей стоматолога"
            items={appointmentSummaryItems}
            onRefresh={loadDentistryAppointments}
            refreshDisabled={appointmentsLoading}
            BadgeComponent={Badge}
            ButtonComponent={Button}
            buttonProps={{ variant: 'secondary', size: 'sm' }}
          />
        </div>

        <EnhancedAppointmentsTable
        data={appointmentsTableData}
        loading={appointmentsLoading}
        theme="light"
        language="ru"
        view="doctor"
        selectedRows={new Set()}
        outerBorder={false}
        services={services}
        showCheckboxes={false}
        onRowClick={handleAppointmentRowClick}
        onActionClick={handleAppointmentActionClick} />

      </Card>
    </div>;


  // Рендер осмотров
  const renderExaminations = () =>
  <div className="dental-flex-col dental-gap-24">
      <Card padding="lg">
        <h3 className="dental-text-primary">Объективные осмотры</h3>
        <p className="dental-text-desc dental-text-secondary">
          Выберите пациента для проведения или просмотра объективного осмотра
        </p>

        <div className="dental-grid-auto-fill-250">
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label="Открыть осмотр пациента"
          className="dental-card-btn"
          onClick={() => handleExamination(patient)}
          onKeyDown={(event) => handleCardKeyDown(event, () => handleExamination(patient))}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}>

              <div className="dental-flex dental-gap-12">
                <div className="dental-icon-bg dental-icon-bg-success dental-icon-bg-full">
                  <span className="dental-text-value dental-text-white">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="dental-text-primary">{patient.name}</p>
                  <p className="dental-text-desc dental-text-secondary">Провести осмотр</p>
                </div>
              </div>
            </div>
        )}
        </div>
      </Card>
    </div>;


  // Рендер диагнозов
  const renderDiagnoses = () =>
  <div className="dental-flex-col dental-gap-24">
      <Card padding="lg">
        <h3 className="dental-text-primary">Диагнозы и назначения</h3>
        <p className="dental-text-desc dental-text-secondary">
          Выберите пациента для постановки диагнозов и назначений
        </p>

        <div className="dental-grid-auto-fill-250">
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label="Открыть диагноз пациента"
          className="dental-card-btn"
          onClick={() => handleDiagnosis(patient)}
          onKeyDown={(event) => handleCardKeyDown(event, () => handleDiagnosis(patient))}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e) => {
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
                  <p className="dental-text-desc dental-text-secondary">Поставить диагноз</p>
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
          patient={selectedPatient}
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
        <Card padding="lg">
          <h3 className="dental-text-primary">Протоколы визитов</h3>
          <p className="dental-text-desc dental-text-secondary">
            Выберите пациента из очереди или выберите из списка для создания протокола визита
          </p>

          <div className="dental-grid-auto-fill-250">
            {patients.map((patient) =>
            <div
              key={patient.id}
              role="button"
              tabIndex={0}
              aria-label="Открыть протокол визита"
              className="dental-card-btn"
              onClick={() => handleVisitProtocol(patient)}
              onKeyDown={(event) => handleCardKeyDown(event, () => handleVisitProtocol(patient))}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e) => {
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
                    <p className="dental-text-desc dental-text-secondary">Создать протокол</p>
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
      <Card padding="lg">
        <h3 className="dental-text-primary">Фото и рентген архив</h3>
        <p className="dental-text-desc dental-text-secondary">
          Выберите пациента для просмотра и управления фото и рентгеновскими снимками
        </p>

        <div className="dental-grid-auto-fill-250">
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label="Открыть фотоархив пациента"
          className="dental-card-btn"
          onClick={() => handlePhotoArchive(patient)}
          onKeyDown={(event) => handleCardKeyDown(event, () => handlePhotoArchive(patient))}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e) => {
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
                  <p className="dental-text-desc dental-text-secondary">Открыть архив</p>
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
      onApplyTemplate={() => notify.info('Шаблоны будут реализованы в следующей версии')}
    />;
  const renderReports = () =>
    <DentalReportsTab
      savedVisitProtocols={savedVisitProtocols}
      onReopenProtocol={reopenVisitProtocol}
      patients={patients}
      diagnoses={[]}
    />;
  const renderDentalChart = () =>
  <div className="dental-flex-col dental-gap-24">
      <Card padding="lg">
        <h3 className="dental-text-primary">Схемы зубов</h3>
        <p className="dental-text-desc dental-text-secondary">
          Выберите пациента для просмотра и редактирования схемы зубов
        </p>

        <div className="dental-grid-auto-fill-250">
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label="Открыть схему зубов пациента"
          className="dental-card-btn"
          onClick={() => handleDentalChart(patient)}
          onKeyDown={(event) => handleCardKeyDown(event, () => handleDentalChart(patient))}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e) => {
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
                  <p className="dental-text-desc dental-text-secondary">Открыть схему</p>
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
      <Card padding="lg">
        <h3 className="dental-text-primary">AI Помощник</h3>
        <AIAssistant
        specialty="dentistry"
        onSuggestionSelect={(type, suggestion) => {
          logger.info('[Dentistry] AI suggestion:', { type, suggestion });
          if (type === 'icd10') {
            notify.success('Код МКБ-10 добавлен из AI предложения');
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
            specialistId={user?.doctor_id || user?.specialist_id || ''}
            specialty="dentistry"
            onPatientSelect={handlePatientSelect}
            onStartVisit={(appointment) => {
              setSelectedPatient(appointment);
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

  const selectedPatientId = selectedPatient?.patient?.id || selectedPatient?.patient_id || selectedPatient?.id || null;
  const selectedPatientDisplayName =
    selectedPatient?.patient_name || selectedPatient?.patient_fio || selectedPatient?.name || 'Пациент';

  return (
    <div className="dentist-panel dental-text-primary">
      {renderContent()}

      {/* Модальные окна */}
      {showPatientCard && selectedPatient &&
      <PatientCard
        patient={selectedPatient}
        onSave={(updatedPatient) => {
          logger.info('Сохранение пациента:', updatedPatient);
          setShowPatientCard(false);
        }}
        onClose={() => setShowPatientCard(false)} />

      }

      {showExaminationForm && selectedPatient &&
      <ExaminationForm
        patientId={selectedPatientId}
        initialData={selectedPatient.examinationData}
        onSave={(examinationData) => {
          logger.info('Сохранение осмотра:', examinationData);
          setShowExaminationForm(false);
        }}
        onClose={() => setShowExaminationForm(false)} />

      }

      {showDiagnosisForm && selectedPatient &&
      <DiagnosisForm
        patientId={selectedPatientId}
        patientName={selectedPatientDisplayName}
        initialData={selectedPatient.diagnosisData}
        onSave={(diagnosisData) => {
          logger.info('Сохранение диагнозов:', diagnosisData);
          setShowDiagnosisForm(false);
        }}
        onClose={() => setShowDiagnosisForm(false)} />

      }

      {showVisitProtocol && (selectedPatient || protocolTemplateDraft) &&
      <VisitProtocol
        patientId={(selectedPatient || protocolTemplateDraft)?.patient_id || selectedPatientId}
        patientName={(selectedPatient || protocolTemplateDraft)?.patient_name || selectedPatientDisplayName}
        visitId={(selectedPatient || protocolTemplateDraft)?.visit_id || selectedPatient?.visit_id}
        initialData={(selectedPatient || protocolTemplateDraft)?.visitData || selectedPatient?.visitData}
        onSave={async (visitData) => {
          logger.info('Сохранение протокола визита:', visitData);
          await persistVisitProtocol(selectedPatient || protocolTemplateDraft, visitData);
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
        patientId={selectedPatientId}
        patientName={selectedPatientDisplayName}
        initialData={selectedPatient.photoArchive}
        onSave={(archiveData) => {
          logger.info('Сохранение фото архива:', archiveData);
          setShowPhotoArchive(false);
        }}
        onClose={() => setShowPhotoArchive(false)} />

      }

      {showProtocolTemplates &&
      <ProtocolTemplates
        onSelectTemplate={handleProtocolTemplateSelect}
        onClose={() => setShowProtocolTemplates(false)} />

      }

      {showReports &&
      <Suspense
        fallback={
          <Card role="status" aria-live="polite" className="dental-lazy-fallback">
            Загрузка отчетов...
          </Card>
        }>
        <LazyReportsAndAnalytics
        patientId={selectedPatient?.id}
        doctorId={user?.id}
        clinicId={user?.clinic_id}
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
                Схема зубов: {selectedPatientDisplayName}
              </h2>
              <button
              onClick={() => setShowDentalChart(false)}
              aria-label={`Закрыть схему зубов пациента ${selectedPatientDisplayName}`}
              className="dental-text-desc dental-text-secondary"
              onMouseEnter={(e) => {
                e.target.style.color = 'var(--mac-text-primary)';
                e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e) => {
                e.target.style.color = 'var(--mac-text-secondary)';
                e.target.style.backgroundColor = 'transparent';
              }}>

                <XCircle className="dental-icon-20" />
              </button>
            </div>
            <TeethChart
            patientId={selectedPatientId}
            initialData={dentalChartData}
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
                План лечения: {selectedPatientDisplayName}
              </h2>
              <button
              onClick={() => setShowTreatmentPlanner(false)}
              aria-label={`Закрыть план лечения пациента ${selectedPatientDisplayName}`}
              className="dental-text-desc dental-text-secondary"
              onMouseEnter={(e) => {
                e.target.style.color = 'var(--mac-text-primary)';
                e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e) => {
                e.target.style.color = 'var(--mac-text-secondary)';
                e.target.style.backgroundColor = 'transparent';
              }}>

                <XCircle className="dental-icon-20" />
              </button>
            </div>
            <TreatmentPlanner
            patientId={selectedPatientId}
            visitId={selectedPatient.visit_id}
            teethData={dentalChartData || {}}
            onUpdate={(plan) => {
              logger.info('План лечения обновлен:', plan);
            }} />

          </div>
        </div>
      }

      {/* Форма осмотра */}
      {showExaminationForm && selectedPatient &&
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg w-full max-w-4xl h-full max-h-[90vh] overflow-auto">
            <div className="p-6 border-b">
              <h2 className="text-xl font-semibold">
                Новый стоматологический осмотр — {selectedPatientDisplayName}
              </h2>
            </div>
            <div className="p-6">
              <form onSubmit={handleExaminationSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Дата осмотра *</label>
                    <Input
                    type="date"
                    aria-label="Дата осмотра"
                    value={examinationForm.examination_date}
                    onChange={(e) => setExaminationForm({ ...examinationForm, examination_date: e.target.value })}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Гигиена полости рта</label>
                    <select
                    value={examinationForm.oral_hygiene}
                    onChange={(e) => setExaminationForm({ ...examinationForm, oral_hygiene: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">

                      <option value="">Выберите</option>
                      <option value="excellent">Отличная</option>
                      <option value="good">Хорошая</option>
                      <option value="fair">Удовлетворительная</option>
                      <option value="poor">Плохая</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Статус кариеса</label>
                    <select
                    value={examinationForm.caries_status}
                    onChange={(e) => setExaminationForm({ ...examinationForm, caries_status: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">

                      <option value="">Выберите</option>
                      <option value="none">Нет кариеса</option>
                      <option value="initial">Начальный</option>
                      <option value="superficial">Поверхностный</option>
                      <option value="medium">Средний</option>
                      <option value="deep">Глубокий</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Статус пародонта</label>
                    <select
                    value={examinationForm.periodontal_status}
                    onChange={(e) => setExaminationForm({ ...examinationForm, periodontal_status: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">

                      <option value="">Выберите</option>
                      <option value="healthy">Здоровый</option>
                      <option value="gingivitis">Гингивит</option>
                      <option value="periodontitis">Пародонтит</option>
                      <option value="advanced">Тяжелый</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Прикус</label>
                    <select
                    value={examinationForm.occlusion}
                    onChange={(e) => setExaminationForm({ ...examinationForm, occlusion: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">

                      <option value="">Выберите</option>
                      <option value="normal">Нормальный</option>
                      <option value="open_bite">Открытый</option>
                      <option value="deep_bite">Глубокий</option>
                      <option value="cross_bite">Перекрестный</option>
                      <option value="crowding">Скученность</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Отсутствующие зубы</label>
                    <Input
                    type="text"
                    aria-label="Отсутствующие зубы"
                    value={examinationForm.missing_teeth}
                    onChange={(e) => setExaminationForm({ ...examinationForm, missing_teeth: e.target.value })}
                    placeholder="Номера отсутствующих зубов"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Зубной налет</label>
                    <select
                    value={examinationForm.dental_plaque}
                    onChange={(e) => setExaminationForm({ ...examinationForm, dental_plaque: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">

                      <option value="">Выберите</option>
                      <option value="none">Нет</option>
                      <option value="minimal">Минимальный</option>
                      <option value="moderate">Умеренный</option>
                      <option value="heavy">Тяжелый</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Кровоточивость десен</label>
                    <select
                    value={examinationForm.gingival_bleeding}
                    onChange={(e) => setExaminationForm({ ...examinationForm, gingival_bleeding: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">

                      <option value="">Выберите</option>
                      <option value="none">Нет</option>
                      <option value="mild">Легкая</option>
                      <option value="moderate">Умеренная</option>
                      <option value="severe">Тяжелая</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Диагноз</label>
                  <textarea
                  aria-label="Диагноз осмотра"
                  value={examinationForm.diagnosis}
                  onChange={(e) => setExaminationForm({ ...examinationForm, diagnosis: e.target.value })}
                  placeholder="Стоматологический диагноз"
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Рекомендации</label>
                  <textarea
                  aria-label="Рекомендации по осмотру"
                  value={examinationForm.recommendations}
                  onChange={(e) => setExaminationForm({ ...examinationForm, recommendations: e.target.value })}
                  placeholder="Рекомендации по лечению и уходу"
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                </div>

                <div className="flex gap-2">
                  <Button type="submit" className="flex items-center gap-2">
                    <Save className="h-4 w-4" />
                    Сохранить осмотр
                  </Button>
                  <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowExaminationForm(false)}>

                    Отмена
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      }

      {/* Phase 4+ cleanup: treatment + prosthetic forms removed (dead UI) */}

      {/* Модальное окно для работы с зубом */}
      {toothModalOpen && selectedTooth &&
      <ToothModal
        open={toothModalOpen}
        onClose={() => {
          setToothModalOpen(false);
          setSelectedTooth(null);
        }}
        toothNumber={selectedTooth.number}
        toothData={selectedTooth.data}
        onSave={(toothNumber, data) => {
          logger.info('Сохранение данных зуба:', toothNumber, data);
          // Обновляем данные зубной карты
          setDentalChartData((prev) => ({
            ...prev,
            [toothNumber]: data
          }));
          setToothModalOpen(false);
        }}
        patientId={selectedPatient?.id}
        visitId={selectedPatient?.visit_id} />

      }

      {/* DentalPriceManager Modal */}
      {showPriceManager && selectedServiceForPrice &&
      <DentalPriceManager
        visitId={selectedPatient?.visit_id}
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
        patient={scheduleNextModal.patient}
        theme={{ isDark, getColor, getSpacing, getFontSize }}
        specialtyFilter="dentistry" />

      }
      {/* X-13: AIChatWidget removed — AiTab in sidebar provides the same functionality */}

      <RoleNotificationCenter userRole="dentist" />

      {/* C-1 (UX audit): portal-mounted ConfirmDialog */}
      {confirmDialog}

      {/* C-2 (UX audit): session timeout warning dialog */}
      {sessionWarning && (
        <SessionWarningModal
          visible={!!sessionWarning}
          onDismiss={() => setSessionWarning(null)}
          onExtend={() => notify.info('Продлеваем сессию...')}
        />
      )}
    </div>);

};

export default DentistPanelUnified;
