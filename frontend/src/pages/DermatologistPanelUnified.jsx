import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
// P-009 fix: shared doctor panel state hook
import { useDoctorPanelState } from '../hooks/useDoctorPanelState';
import {
  Activity,
  FileText,
  User,
  Save,
  RefreshCw,
  CheckCircle,
  Stethoscope,
  Calendar,
  Phone,
  Plus,
  TestTube,
  Scissors,
  Sparkles,
  DollarSign } from
'lucide-react';
import {
  Button, MacOSCard, Badge, Input, Textarea, Select, MacOSEmptyState,
} from '../components/ui/macos';
import { useTheme } from '../contexts/ThemeContext';
import './dermatology.css';
import AppointmentSummaryBar from '../components/doctor/AppointmentSummaryBar';
import DoctorServiceSelector from '../components/doctor/DoctorServiceSelector';
import AIAssistant from '../components/ai/AIAssistant';
import ServiceChecklist from '../components/ServiceChecklist';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import EditPatientModal from '../components/common/EditPatientModal';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import QueueIntegration from '../components/QueueIntegration';
import { EMRContainerV2 } from '../components/emr-v2/EMRContainerV2';
import PhotoUploader from '../components/dermatology/PhotoUploader';
import PhotoComparison from '../components/dermatology/PhotoComparison';
import ProcedureTemplates from '../components/dermatology/ProcedureTemplates';
import SkinAnalysis from '../components/dermatology/SkinAnalysis';
import PriceOverrideManager from '../components/dermatology/PriceOverrideManager';
import PrescriptionSystem from '../components/PrescriptionSystem';
import VisitTimeline from '../components/VisitTimeline';
import { printPanelTicket } from '../services/panelPrint';
import { queueService } from '../services/queue';
import { printService } from '../services/print';
import AIChatWidget from '../components/ai/AIChatWidget';
import { getApiBaseUrl } from '../api/runtime';
import { resolveCanonicalVisitId } from '../utils/canonicalVisit';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
import notify from '../services/notify';
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

function buildDermatologyPatientFromAppointment(appointment) {
  if (!appointment) {
    return null;
  }

  const patientId = appointment.patient_id || appointment.id || null;
  if (!patientId) {
    return null;
  }

  const patientName =
    appointment.patient_fio || appointment.patient_name || appointment.name || 'Пациент';
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

function buildPatientsFromAppointments(appointments) {
  const patientsById = new Map();

  appointments.forEach((appointment) => {
    const patient = buildDermatologyPatientFromAppointment(appointment);
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
    defaultTab: 'appointments',
    visitDeepLinkTab: 'visit',
    patientDeepLinkTab: 'appointments',
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
  const photoData = useMemo(() => [], []);

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

  // Состояние для PriceOverrideManager
  const [showPriceOverride, setShowPriceOverride] = useState(false);
  const [selectedServiceForPriceOverride, setSelectedServiceForPriceOverride] = useState(null);

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
        const response = await fetch(`${API_V1_BASE}/registrar/services`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
          const data = await response.json();
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
        setPatients(buildPatientsFromAppointments(cachedAppointments));
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
        const today = new Date().toISOString().split('T')[0];
        // 1. Получаем очереди для информации об услугах
        const queuesResponse = await fetch(`${API_V1_BASE}/registrar/queues/today`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        const allAppointments = [];
        if (queuesResponse.ok) {
          const queuesData = await queuesResponse.json();

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
                    appointment_date: entry.created_at ? entry.created_at.split('T')[0] : today,
                    appointment_time: entry.visit_time || '',
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
        setPatients(buildPatientsFromAppointments(enrichedAppointmentsData));
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
      buildDermatologyPatientFromAppointment(row) ||
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
            logger.info('[Dermatology] Пациент вызван:', row.patient_fio);
            await loadDermatologyAppointments();
          }
        } catch (error) {
          logger.error('[Dermatology] Ошибка вызова пациента:', error);
        }
        break;
      case 'payment':
        logger.info('[Dermatology] Открытие окна оплаты для:', row.patient_fio);
        notify.info(`Оплата для пациента: ${row.patient_fio}. Функция будет реализована позже.`);
        break;
      case 'print':
        logger.info('[Dermatology] Печать талона для:', row.patient_fio);
        try {
          const printResult = await printPanelTicket(row, {
            specialtyName: 'Дерматология'
          });
          notify.success(printResult?.message || `Талон для ${row.patient_fio} отправлен на печать`);
        } catch (error) {
          logger.error('[Dermatology] Ошибка печати талона:', error);
          notify.error(error.message || 'Не удалось отправить талон на печать');
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
        const response = await fetch(`${API_V1_BASE}/derma/examinations?limit=100`, {
          headers: authHeader()
        });
        if (response.ok) {
          const data = await response.json();
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
        const response = await fetch(`${API_V1_BASE}/derma/procedures?limit=100`, {
          headers: authHeader()
        });
        if (response.ok) {
          const data = await response.json();
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

      const skinResponse = await fetch(`${API_V1_BASE}/derma/examinations?patient_id=${patientId}&limit=10`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (skinResponse.ok) {
        const skinData = await skinResponse.json();
        setSkinExaminations(Array.isArray(skinData) ? skinData : []);
      }

      const cosmeticResponse = await fetch(`${API_V1_BASE}/derma/procedures?patient_id=${patientId}&limit=10`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (cosmeticResponse.ok) {
        const cosmeticData = await cosmeticResponse.json();
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
          const patientObj = buildDermatologyPatientFromAppointment(appointment);
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
          notify.info(`Загружен пациент: ${patientObj.patient_name}. Выберите визит с каноническим visit_id.`);
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
            ? `Пациент #${fallbackPatientId}`
            : `Визит #${visitIdFromUrl}`;
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
          setActiveTab('appointments');
          notify.info(
            visitIdFromUrl
              ? 'Не удалось найти визит в очереди дерматологии. Выберите запись вручную.'
              : 'Пациент не найден в очереди дерматологии. Выберите запись вручную.'
          );
        }
      } catch (error) {
        logger.error('[Dermatology] Не удалось загрузить пациента из URL:', error);
        notify.error('Не удалось загрузить пациента');
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
        const response = await fetch(`/api/v1/appointments/${appointmentId}/status`, {
          headers: {
            Authorization: `Bearer ${tokenManager.getAccessToken()}`
          }
        });

        if (!response.ok) {
          return;
        }

        const statusData = await response.json();
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
        notify.error('Не удалось определить запись для сохранения рецепта');
        return;
      }
      const response = await fetch(`${API_V1_BASE}/appointments/${appointmentId}/prescription`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify(prescriptionData)
      });

      if (response.ok) {
        const savedPrescription = await response.json();
        setPrescription(savedPrescription);
        notify.success('Рецепт сохранен успешно!');
      } else {
        const error = await response.json();
        notify.error(error.detail || 'Ошибка при сохранении рецепта');
      }
    } catch (error) {
      logger.error('DermatologistPanel: Save prescription error:', error);
      notify.error('Ошибка при сохранении рецепта');
    }
  };

  const printPrescription = async (prescriptionData) => {
    const patientFullName =
      selectedPatient?.patient_name ||
      currentAppointment?.patient_fio ||
      currentAppointment?.patient_name ||
      selectedPatient?.name ||
      'Пациент';

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
        throw new Error(result.error || 'Ошибка при печати рецепта');
      }

      notify.success(result.data?.message || 'Рецепт отправлен в печать');
      logger.info('[Dermatology] Prescription print success', {
        patientId: payload.patient.id,
        visitId: currentAppointment?.visit_id || null,
        printer: result.data?.printer || null,
        jobId: result.data?.job_id || null
      });
    } catch (error) {
      logger.error('[Dermatology] Prescription print error:', error);
      notify.error(error.message || 'Ошибка при печати рецепта');
      throw error;
    }
  };

  // УДАЛЕНО: старая функция completeVisit заменена на унифицированную handleSaveVisit

  // Обработка AI предложений
  const handleAISuggestion = (type, suggestion) => {
    if (type === 'icd10') {
      setVisitData({ ...visitData, icd10: suggestion });
        notify.success('Код МКБ-10 добавлен из AI предложения');
    } else if (type === 'diagnosis') {
      setVisitData({ ...visitData, diagnosis: suggestion });
        notify.success('Диагноз добавлен из AI предложения');
    }
  };

  // Унифицированная обработка сохранения визита
  const handleSaveVisit = async () => {
    // Определяем ID записи: приоритет selectedPatient, потом currentAppointment
    const entryId = resolveDoctorQueueEntryId(selectedPatient) ?? resolveDoctorQueueEntryId(currentAppointment);
    if (!entryId) {
      logger.error('[Dermатology] handleSaveVisit: нет entryId');
      notify.error('Не выбран пациент для завершения приема');
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

      const visitPayload = {
        patient_id: patientId,
        complaint: visitData.complaint,
        diagnosis: visitData.diagnosis,
        icd10: visitData.icd10,
        services: selectedServices,
        notes: visitData.notes
      };

      logger.info('[Dermatology] handleSaveVisit: payload', visitPayload);
      await queueService.completeVisit(entryId, visitPayload);
      logger.info('[Dermatology] handleSaveVisit: completeVisit OK');

      notify.success('Прием завершен успешно');

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
            notify.success(`Вызван следующий пациент №${next.entry.number}`);
        }
      } catch (err) {
        logger.warn('[Dermatology] callNextWaiting(dermatology): failed', err);
      }

    } catch (error) {
      logger.error('[Dermatology] handleSaveVisit: error', error);
      notify.error(error.message || 'Ошибка при завершении приема');
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

      const response = await fetch(`${API_V1_BASE}/derma/examinations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
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
        notify.success('Осмотр кожи сохранен успешно');
      } else {
        const detail = await response.text();
        logger.error('[Dermatology] Ошибка ответа при сохранении осмотра', { status: response.status, detail });
        notify.error('Ошибка сохранения осмотра кожи');
      }
    } catch (error) {
      logger.error('Ошибка сохранения осмотра:', error);
      notify.error('Ошибка сохранения осмотра кожи');
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

      const response = await fetch(`${API_V1_BASE}/derma/procedures`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
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
        notify.success('Косметическая процедура сохранена успешно');
      } else {
        const detail = await response.text();
        logger.error('[Dermatology] Ошибка ответа при сохранении процедуры', { status: response.status, detail });
        notify.error('Ошибка сохранения косметической процедуры');
      }
    } catch (error) {
      logger.error('Ошибка сохранения процедуры:', error);
      notify.error('Ошибка сохранения косметической процедуры');
    }
  };

  if (isDemoMode) {
    logger.info('DermatologistPanelUnified: Skipping render in demo mode');
    return null;
  }

  const appointmentSummaryItems = [
    {
      key: 'total',
      label: 'Всего',
      value: appointments.length,
      variant: 'info'
    },
    {
      key: 'waiting',
      label: 'Ожидают',
      value: countAppointmentsByStatuses(appointments, DERMATOLOGY_WAITING_STATUSES),
      variant: 'warning'
    },
    {
      key: 'called',
      label: 'Вызваны',
      value: countAppointmentsByStatuses(appointments, DERMATOLOGY_CALLED_STATUSES),
      variant: 'primary'
    },
    {
      key: 'completed',
      label: 'Приняты',
      value: countAppointmentsByStatuses(appointments, DERMATOLOGY_COMPLETED_STATUSES),
      variant: 'success'
    }
  ];

  return (
    <div className="derma-page-root">

      <div className="derma-p-0"> {/* Убираем padding, так как он уже есть в main контейнере */}


        {/* Контент вкладок */}
        <div>
          {/* Записи дерматолога */}
          {activeTab === 'appointments' &&
          <div className="derma-flex-col-24 derma-w-full derma-max-w-none">
              <MacOSCard className="derma-card-w-full">
                <div style={dermatologyAppointmentsHeaderStyle}>
                  <h3 style={dermatologyAppointmentsTitleStyle}>
                    <Calendar size={20} className="derma-icon-mr-green" />
                    Записи к дерматологу
                  </h3>
                  <AppointmentSummaryBar
                    ariaLabel="Сводка записей дерматолога"
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
                    <User size={20} className="derma-icon-mr-green" />
                    Дерматологические пациенты
                  </h3>
                  <Badge variant="info">Всего: {patients.length} пациентов</Badge>
                </div>

                {loading ?
              <div className="derma-loading-state">
                    <RefreshCw size={32} className="derma-loading-icon" />
                    <p className="derma-p-14-secondary">Загрузка пациентов...</p>
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
                              <Badge variant="success" className="derma-ml-12">Дерматология</Badge>
                            </div>
                            <div className="derma-patient-info-list">
                              <div className="derma-flex-center">
                                <Phone size={18} className="derma-icon-mr derma-text-accent" />
                                {patient.phone}
                              </div>
                              <div className="derma-flex-center">
                                <Calendar size={14} className="derma-icon-mr" />
                                {patient.birth_date}
                              </div>
                              <div className="derma-flex-center">
                                <User size={14} className="derma-icon-mr" />
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

                              <Activity size={16} />
                              Осмотр
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

                              <Sparkles size={16} />
                              Процедура
                            </Button>
                            <Button
                        variant="outline"
                        onClick={() => setSelectedPatient(patient)}
                        className="derma-flex-center">

                              <User size={16} />
                              Просмотр
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <MacOSCard className="derma-p-8">
                <div className="derma-flex" style={{ alignItems: 'center' }}>
                  <h3 className="derma-flex" style={{ alignItems: 'center' }}>
                    <Stethoscope size={20} style={{ marginRight: '8px', color: 'var(--mac-orange-500)' }} />
                    Прием пациента: {currentAppointment.patient_name || 'Не указано'}
                  </h3>
                  <Badge variant="info">
                    Статус: {currentAppointment.status}
                  </Badge>
                </div>

                {/* Временная шкала приема */}
                <VisitTimeline
                appointment={currentAppointment}
                emr={emr}
                prescription={prescription} />


                {/* EMR система */}
                <div style={{ marginTop: '24px' }}>
                  <h4 className="derma-flex" style={{ alignItems: 'center' }}>
                    <FileText size={20} style={{ marginRight: '8px', color: 'var(--mac-blue-500)' }} />
                    Электронная медицинская карта
                  </h4>
                  <EMRContainerV2
                  visitId={currentAppointment?.visit_id}
                  patientId={currentAppointment?.patient_id}
                  specialty="dermatology" />

                </div>

                {/* Система рецептов */}
                {emr && !emr.is_draft &&
              <div style={{ marginTop: '24px' }}>
                    <h4 className="derma-flex" style={{ alignItems: 'center' }}>
                      <TestTube size={20} style={{ marginRight: '8px', color: 'var(--mac-green-500)' }} />
                      Рецепт
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
              <div style={{ marginTop: '24px', textAlign: 'center' }}>
                    <Button
                  onClick={handleSaveVisit}
                  disabled={loading}
                  className="derma-flex" style={{ alignItems: 'center' }}>

                      {loading ?
                  <RefreshCw size={20} className="animate-spin" /> :

                  <CheckCircle size={20} />
                  }
                      {loading ? 'Завершение...' : 'Завершить прием'}
                    </Button>
                  </div>
              }
              </MacOSCard>
            </div>
          }

          {/* Прием пациента - простая версия */}
          {activeTab === 'visit' && selectedPatient && !currentAppointment &&
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* Информация о пациенте */}
              <MacOSCard className="derma-p-8">
                <h3 className="derma-flex" style={{ alignItems: 'center' }}>
                  <User size={20} style={{ marginRight: '8px', color: 'var(--mac-blue-500)' }} />
                  Пациент #{selectedPatient.number}
                </h3>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                  <div>
                    <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: '500',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '6px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                      ФИО пациента
                    </label>
                    <div style={{
                    fontSize: '16px',
                    fontWeight: '600',
                    color: 'var(--mac-text-primary)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>{selectedPatient.patient_name}</div>
                  </div>

                  {selectedPatient.phone &&
                <div>
                      <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: '500',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '6px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                        Телефон
                      </label>
                      <div className="derma-flex" style={{ alignItems: 'center' }}>
                        <Phone size={16} style={{ marginRight: '8px', color: 'var(--mac-text-secondary)' }} />
                        <span style={{
                      fontSize: '16px',
                      fontWeight: '500',
                      color: 'var(--mac-text-primary)',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>{selectedPatient.phone}</span>
                      </div>
                    </div>
                }
                </div>
              </MacOSCard>

              {/* Жалобы и диагноз */}
              <MacOSCard className="derma-p-8">
                <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '20px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>📝 Жалобы и диагноз</h3>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  <div>
                    <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: '500',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '6px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                      Жалобы пациента
                    </label>
                    <Textarea
                    value={visitData.complaint}
                    onChange={(e) => setVisitData({ ...visitData, complaint: e.target.value })}
                    rows={4}
                    placeholder="Опишите жалобы пациента..." />

                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                    <div>
                      <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                        Диагноз
                      </label>
                      <Input
                      type="text"
                      value={visitData.diagnosis}
                      onChange={(e) => setVisitData({ ...visitData, diagnosis: e.target.value })}
                      placeholder="Диагноз" />

                    </div>

                    <div>
                      <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                        МКБ-10
                      </label>
                      <Input
                      type="text"
                      value={visitData.icd10}
                      onChange={(e) => setVisitData({ ...visitData, icd10: e.target.value })}
                      placeholder="L70.9" />

                    </div>
                  </div>

                  <div>
                    <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: '500',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '6px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                      Примечания
                    </label>
                    <Textarea
                    value={visitData.notes}
                    onChange={(e) => setVisitData({ ...visitData, notes: e.target.value })}
                    rows={3}
                    placeholder="Дополнительные примечания..." />

                  </div>
                </div>
              </MacOSCard>

              {/* Услуги визита */}
              <DoctorServiceSelector
              specialty="dermatology"
              selectedServices={selectedServices}
              onServicesChange={setSelectedServices}
              canEditPrices={true} />


              {/* EMR система */}
              {currentAppointment &&
            <MacOSCard className="derma-p-8">
                  <h3 className="derma-flex" style={{ alignItems: 'center' }}>
                    <FileText size={20} style={{ marginRight: '8px', color: 'var(--mac-blue-500)' }} />
                    Электронная медицинская карта
                  </h3>
                  <EMRContainerV2
                visitId={currentAppointment?.visit_id}
                patientId={currentAppointment?.patient_id}
                specialty="dermatology" />

                </MacOSCard>
            }

              {/* Система рецептов */}
              {currentAppointment && emr && !emr.is_draft &&
            <MacOSCard className="derma-p-8">
                  <h3 className="text-lg font-medium mb-4 flex items-center">
                    <TestTube size={20} className="mr-2 text-green-600" />
                    Рецепт
                  </h3>
                  <PrescriptionSystem
                appointment={currentAppointment}
                emr={emr}
                prescription={prescription}
                canCreatePrescription={canCreatePrescription}
                onSave={savePrescription} />

                </MacOSCard>
            }

              {/* Действия */}
              <MacOSCard className="derma-p-8">
                <div className="flex justify-end space-x-3">
                  <Button
                  variant="outline"
                  onClick={() => {
                    setSelectedPatient(null);
                    handleTabChange('queue');
                  }}>

                    Отменить
                  </Button>
                  <Button
                  onClick={handleSaveVisit}
                  disabled={loading || !visitData.complaint && !emr}>

                    {loading ?
                  <RefreshCw size={16} className="animate-spin mr-2" /> :

                  <Save size={16} className="mr-2" />
                  }
                    {loading ? 'Завершение...' : 'Завершить прием'}
                  </Button>
                </div>
              </MacOSCard>
            </div>
          }

          {/* Фото до/после */}
          {activeTab === 'visit' && !currentAppointment && !selectedPatient &&
          <MacOSCard style={{ padding: '48px' }}>
              <MacOSEmptyState
              icon={Calendar}
              title="Выберите визит"
              description="Откройте прием из очереди или списка записей, либо используйте ссылку с visitId."
              action={
              <Button variant="outline" onClick={() => handleTabChange('appointments')} className="derma-p-4" style={{ marginTop: '16px' }}>
                    Перейти к записям
                  </Button>
              } />
            </MacOSCard>
          }

          {activeTab === 'photos' && (currentAppointment || selectedPatient) &&
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <MacOSCard className="derma-p-8">
                <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '20px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>
                  Загрузить фото
                </h3>
                {/* Загрузчик фото с HEIC поддержкой */}
                <PhotoUploader
                visitId={currentAppointment?.visit_id}
                patientId={currentAppointment?.patient_id || selectedPatient?.patient_id || selectedPatient?.patient?.id}
                onDataUpdate={() => {
                  logger.info('Фото обновлены');
                  loadPatientData();
                }} />

              </MacOSCard>

              <MacOSCard className="derma-p-8">
                <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '20px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>
                  AI анализ кожи
                </h3>
                {/* AI анализ кожи */}
                <SkinAnalysis
                photos={photoData}
                visitId={currentAppointment?.visit_id}
                patientId={currentAppointment?.patient_id || selectedPatient?.patient_id || selectedPatient?.patient?.id}
                onAnalysisComplete={(result) => {
                  logger.info('AI анализ завершен:', result);
                }} />

              </MacOSCard>

              <MacOSCard className="derma-p-8">
                <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '20px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>
                  Сравнение «до» и «после»
                </h3>
                {/* Сравнение фото до и после */}
                <PhotoComparison
                photos={photoData}
                visitId={currentAppointment?.visit_id}
                patientId={currentAppointment?.patient_id || selectedPatient?.patient_id || selectedPatient?.patient?.id}
                onComparisonComplete={(result) => {
                  logger.info('Сравнение завершено:', result);
                }} />

              </MacOSCard>
            </div>
          }

          {activeTab === 'photos' && !currentAppointment && !selectedPatient &&
          <MacOSCard style={{ padding: '48px', textAlign: 'center' }}>
              <MacOSEmptyState
              type="image"
              title="Выберите пациента"
              description="Перейдите на вкладку 'Очередь' и выберите пациента для просмотра фото"
              action={
              <Button variant="outline" onClick={() => handleTabChange('queue')} className="derma-p-4" style={{ marginTop: '16px' }}>
                    Перейти к очереди
                  </Button>
              } />

            </MacOSCard>
          }

          {/* Осмотр кожи */}
          {activeTab === 'skin' &&
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <MacOSCard className="derma-p-8">
                <div className="derma-flex" style={{ alignItems: 'center' }}>
                  <h3 className="derma-flex" style={{ alignItems: 'center' }}>
                    <Activity size={20} style={{ marginRight: '8px', color: 'var(--mac-green-500)' }} />
                    Осмотры кожи
                  </h3>
                  <Button onClick={openSkinExaminationForm}>
                    <Plus size={16} style={{ marginRight: '6px' }} />
                    Новый осмотр
                  </Button>
                </div>

                {skinExaminations.length > 0 ?
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {skinExaminations.map((exam) =>
                <div key={exam.id} style={{
                  border: '1px solid var(--mac-border)',
                  borderRadius: '8px',
                  padding: '16px',
                  backgroundColor: 'var(--mac-bg-secondary)'
                }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                          <h4 style={{
                      fontWeight: '600',
                      fontSize: '16px',
                      color: 'var(--mac-text-primary)',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>Осмотр #{exam.id}</h4>
                          <Badge variant="info">{exam.examination_date}</Badge>
                        </div>
                        <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                    gap: '16px',
                    fontSize: '14px',
                    color: 'var(--mac-text-secondary)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                          <div>🧴 Тип кожи: {exam.skin_type}</div>
                          <div>📈 Состояние: {exam.skin_condition}</div>
                          <div>🎯 Поражения: {exam.lesions}</div>
                          <div>📍 Распространение: {exam.distribution}</div>
                        </div>
                        {exam.diagnosis &&
                  <div style={{
                    marginTop: '8px',
                    fontSize: '14px',
                    color: 'var(--mac-text-primary)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                            <strong>Диагноз:</strong> {exam.diagnosis}
                          </div>
                  }
                      </div>
                )}
                  </div> :

              <MacOSEmptyState
                type="doc"
                title="Нет данных осмотров кожи"
                description="Добавьте новый осмотр кожи для пациента" />

              }
              </MacOSCard>

              {/* Форма осмотра кожи */}
              {showSkinForm &&
            <MacOSCard className="derma-p-8">
                  <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '16px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>Новый осмотр кожи</h3>
                  <form onSubmit={handleSkinExaminationSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                      <div>
                        <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                          Дата осмотра *
                        </label>
                        <Input
                      type="date"
                      value={skinExamination.examination_date}
                      onChange={(e) => setSkinExamination({ ...skinExamination, examination_date: e.target.value })}
                      required />

                      </div>
                      <div>
                        <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                          Тип кожи *
                        </label>
                        <Select
                      value={skinExamination.skin_type}
                      onChange={(e) => setSkinExamination({ ...skinExamination, skin_type: e.target.value })}
                      required>

                          <option value="">Выберите тип кожи</option>
                          <option value="normal">Нормальная</option>
                          <option value="dry">Сухая</option>
                          <option value="oily">Жирная</option>
                          <option value="combination">Комбинированная</option>
                          <option value="sensitive">Чувствительная</option>
                        </Select>
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                      <div>
                        <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                          Состояние кожи
                        </label>
                        <Input
                      type="text"
                      value={skinExamination.skin_condition}
                      onChange={(e) => setSkinExamination({ ...skinExamination, skin_condition: e.target.value })}
                      placeholder="Хорошее, удовлетворительное, проблемное" />

                      </div>
                      <div>
                        <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                          Поражения
                        </label>
                        <Input
                      type="text"
                      value={skinExamination.lesions}
                      onChange={(e) => setSkinExamination({ ...skinExamination, lesions: e.target.value })}
                      placeholder="Акне, пигментация, родинки" />

                      </div>
                    </div>

                    <div>
                      <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: '500',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '6px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                        Диагноз
                      </label>
                      <Input
                    type="text"
                    value={skinExamination.diagnosis}
                    onChange={(e) => setSkinExamination({ ...skinExamination, diagnosis: e.target.value })}
                    placeholder="Диагноз" />

                    </div>

                    <div>
                      <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: '500',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '6px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                        План лечения
                      </label>
                      <Textarea
                    value={skinExamination.treatment_plan}
                    onChange={(e) => setSkinExamination({ ...skinExamination, treatment_plan: e.target.value })}
                    rows={4}
                    placeholder="План лечения и рекомендации" />

                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                      <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowSkinForm(false)}>

                        Отмена
                      </Button>
                      <Button type="submit">
                        <Save size={16} style={{ marginRight: '6px' }} />
                        Сохранить осмотр
                      </Button>
                    </div>
                  </form>
                </MacOSCard>
            }
            </div>
          }

          {/* Косметология */}
          {activeTab === 'cosmetic' &&
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <MacOSCard className="derma-p-8">
                <div className="derma-flex" style={{ alignItems: 'center' }}>
                  <h3 className="derma-flex" style={{ alignItems: 'center' }}>
                    <Sparkles size={20} style={{ marginRight: '8px', color: 'var(--mac-pink-500)' }} />
                    Косметические процедуры
                  </h3>
                  <Button onClick={openCosmeticProcedureForm}>
                    <Plus size={16} style={{ marginRight: '6px' }} />
                    Новая процедура
                  </Button>
                </div>

                {cosmeticProcedures.length > 0 ?
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {cosmeticProcedures.map((procedure) =>
                <div key={procedure.id} style={{
                  border: '1px solid var(--mac-border)',
                  borderRadius: '8px',
                  padding: '16px',
                  backgroundColor: 'var(--mac-bg-secondary)'
                }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                          <h4 style={{
                      fontWeight: '600',
                      fontSize: '16px',
                      color: 'var(--mac-text-primary)',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>Процедура #{procedure.id}</h4>
                          <Badge variant="info">{procedure.procedure_date}</Badge>
                        </div>
                        <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                    gap: '16px',
                    fontSize: '14px',
                    color: 'var(--mac-text-secondary)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                          <div>✨ Тип: {procedure.procedure_type}</div>
                          <div>📍 Область: {procedure.area_treated}</div>
                          <div>🧴 Продукты: {procedure.products_used}</div>
                        </div>
                        {procedure.results &&
                  <div style={{
                    marginTop: '8px',
                    fontSize: '14px',
                    color: 'var(--mac-text-primary)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                            <strong>Результаты:</strong> {procedure.results}
                          </div>
                  }
                      </div>
                )}
                  </div> :

              <MacOSEmptyState
                type="doc"
                title="Нет данных косметических процедур"
                description="Добавьте новую косметическую процедуру для пациента" />

              }
              </MacOSCard>

              {/* Форма косметической процедуры */}
              {showCosmeticForm &&
            <MacOSCard className="derma-p-8">
                  <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '16px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>Новая косметическая процедура</h3>
                  <form onSubmit={handleCosmeticProcedureSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                      <div>
                        <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                          Дата процедуры *
                        </label>
                        <Input
                      type="date"
                      value={cosmeticProcedure.procedure_date}
                      onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, procedure_date: e.target.value })}
                      required />

                      </div>
                      <div>
                        <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                          Тип процедуры *
                        </label>
                        <Select
                      value={cosmeticProcedure.procedure_type}
                      onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, procedure_type: e.target.value })}
                      required>

                          <option value="">Выберите процедуру</option>
                          <option value="cleaning">Чистка лица</option>
                          <option value="peeling">Пилинг</option>
                          <option value="botox">Ботокс</option>
                          <option value="filler">Филлеры</option>
                          <option value="laser">Лазерная терапия</option>
                          <option value="mesotherapy">Мезотерапия</option>
                        </Select>
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                      <div>
                        <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                          Область обработки
                        </label>
                        <Input
                      type="text"
                      value={cosmeticProcedure.area_treated}
                      onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, area_treated: e.target.value })}
                      placeholder="Лицо, шея, декольте" />

                      </div>
                      <div>
                        <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                          Использованные продукты
                        </label>
                        <Input
                      type="text"
                      value={cosmeticProcedure.products_used}
                      onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, products_used: e.target.value })}
                      placeholder="Названия препаратов" />

                      </div>
                    </div>

                    <div>
                      <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: '500',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '6px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                        Результаты
                      </label>
                      <Textarea
                    value={cosmeticProcedure.results}
                    onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, results: e.target.value })}
                    rows={4}
                    placeholder="Описание результатов процедуры" />

                    </div>

                    <div>
                      <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: '500',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '6px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                        Рекомендации по уходу
                      </label>
                      <Textarea
                    value={cosmeticProcedure.follow_up}
                    onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, follow_up: e.target.value })}
                    rows={3}
                    placeholder="Рекомендации по уходу после процедуры" />

                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                      <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowCosmeticForm(false)}>

                        Отмена
                      </Button>
                      <Button type="submit">
                        <Save size={16} style={{ marginRight: '6px' }} />
                        Сохранить процедуру
                      </Button>
                    </div>
                  </form>
                </MacOSCard>
            }
            </div>
          }

          {/* AI Помощник */}
          {activeTab === 'ai' &&
          <AIAssistant
            specialty="dermatology"
            onSuggestionSelect={handleAISuggestion} />

          }

          {/* Управление услугами */}
          {activeTab === 'services' &&
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <MacOSCard className="derma-p-8">
                <h3 className="derma-flex" style={{ alignItems: 'center' }}>
                  <Scissors size={20} style={{ marginRight: '8px', color: 'var(--mac-orange-600)' }} />
                  Услуги дерматологии и косметологии
                </h3>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div>
                    <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: '500',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '8px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                      Выбор услуг
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


                    <div className="derma-p-4" style={{ marginTop: '16px' }}>
                      <ServiceChecklist
                      value={selectedServices}
                      onChange={setSelectedServices}
                      department="derma" />

                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
                    <div>
                      <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '8px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                        Стоимость от врача (UZS)
                      </label>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <div style={{ position: 'relative', flex: '1' }}>
                          <DollarSign size={16} style={{
                          position: 'absolute',
                          left: '12px',
                          top: '50%',
                          transform: 'translateY(-50%)',
                          color: 'var(--mac-text-secondary)'
                        }} />
                          <Input
                          type="text"
                          value={doctorPrice}
                          onChange={(e) => setDoctorPrice(e.target.value)}
                          placeholder="Например: 50000"
                          inputMode="numeric"
                          style={{ paddingLeft: '40px' }} />

                        </div>
                        <Button
                        onClick={() => {
                          if (selectedServices.length > 0) {
                            setSelectedServiceForPriceOverride({
                              id: selectedServices[0].id || 1,
                              name: selectedServices[0].name || 'Выбранная услуга',
                              price: selectedServices[0].price || 50000
                            });
                            setShowPriceOverride(true);
                          } else {
                            notify.warning('Сначала выберите услугу');
                          }
                        }}
                        variant="primary"
                        aria-label="Изменить цену процедуры"
                        title="Изменить цену процедуры">

                          <DollarSign size={16} />
                        </Button>
                      </div>
                    </div>

                    <div>
                      <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '8px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                        Итого к оплате
                      </label>
                      <div className="derma-flex" style={{ alignItems: 'center' }}>
                        <span style={{
                        fontSize: '18px',
                        fontWeight: '600',
                        color: 'var(--mac-text-primary)',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                          {totalCost.toLocaleString()} UZS
                        </span>
                        <span style={{
                        marginLeft: '8px',
                        fontSize: '13px',
                        color: 'var(--mac-text-secondary)',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                          (услуги: {servicesSubtotal.toLocaleString()} UZS
                          {doctorPriceNum ? `, врач: ${doctorPriceNum.toLocaleString()} UZS` : ''})
                        </span>
                      </div>
                    </div>
                  </div>

                  <div style={{
                  backgroundColor: 'var(--mac-blue-50)',
                  padding: '16px',
                  borderRadius: '8px',
                  border: '1px solid var(--mac-blue-200)'
                }}>
                    <h4 style={{
                    fontWeight: '600',
                    fontSize: '14px',
                    color: 'var(--mac-blue-900)',
                    marginBottom: '8px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                      💡 Справочник цен
                    </h4>
                    <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: '8px',
                    fontSize: '13px',
                    color: 'var(--mac-blue-800)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                      <div>• Консультация: 50,000 UZS</div>
                      <div>• Биопсия: 150,000 UZS</div>
                      <div>• Чистка лица: 80,000 UZS</div>
                      <div>• Ботокс: 300,000 UZS</div>
                      <div>• Лазер: 250,000 UZS</div>
                      <div>• + стоимость от врача</div>
                    </div>
                  </div>
                </div>
              </MacOSCard>
            </div>
          }

          {/* История */}
          {activeTab === 'history' &&
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <MacOSCard className="derma-p-8">
                <h3 className="derma-flex" style={{ alignItems: 'center' }}>
                  <Calendar size={20} style={{ marginRight: '8px', color: 'var(--mac-text-secondary)' }} />
                  История приемов и процедур
                </h3>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '24px' }}>
                  {/* История осмотров кожи */}
                  <div>
                    <h4 className="derma-flex" style={{ alignItems: 'center' }}>
                      <Activity size={16} style={{ marginRight: '8px', color: 'var(--mac-green-600)' }} />
                      Осмотры кожи ({skinExaminations.length})
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '400px', overflowY: 'auto' }}>
                      {skinExaminations.map((exam) =>
                    <div key={exam.id} style={{
                      border: '1px solid var(--mac-border)',
                      borderRadius: '8px',
                      padding: '12px',
                      fontSize: '13px',
                      backgroundColor: 'var(--mac-bg-secondary)'
                    }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                            <span style={{
                          fontWeight: '600',
                          fontSize: '14px',
                          color: 'var(--mac-text-primary)',
                          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                        }}>#{exam.id}</span>
                            <Badge variant="info">{exam.examination_date}</Badge>
                          </div>
                          <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                        fontSize: '13px',
                        color: 'var(--mac-text-secondary)',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                            <div>🧴 {exam.skin_type} • {exam.skin_condition}</div>
                            <div>🎯 {exam.lesions}</div>
                            {exam.diagnosis && <div>📋 {exam.diagnosis}</div>}
                          </div>
                        </div>
                    )}
                    </div>
                  </div>

                  {/* История косметических процедур */}
                  <div>
                    <h4 className="derma-flex" style={{ alignItems: 'center' }}>
                      <Sparkles size={16} style={{ marginRight: '8px', color: 'var(--mac-pink-600)' }} />
                      Косметические процедуры ({cosmeticProcedures.length})
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '400px', overflowY: 'auto' }}>
                      {cosmeticProcedures.map((procedure) =>
                    <div key={procedure.id} style={{
                      border: '1px solid var(--mac-border)',
                      borderRadius: '8px',
                      padding: '12px',
                      fontSize: '13px',
                      backgroundColor: 'var(--mac-bg-secondary)'
                    }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                            <span style={{
                          fontWeight: '600',
                          fontSize: '14px',
                          color: 'var(--mac-text-primary)',
                          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                        }}>#{procedure.id}</span>
                            <Badge variant="info">{procedure.procedure_date}</Badge>
                          </div>
                          <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                        fontSize: '13px',
                        color: 'var(--mac-text-secondary)',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                            <div>✨ {procedure.procedure_type}</div>
                            <div>📍 {procedure.area_treated}</div>
                            {procedure.results && <div>📊 {procedure.results}</div>}
                            {procedure.total_cost &&
                        <div style={{
                          fontWeight: '600',
                          fontSize: '14px',
                          color: 'var(--mac-green-600)',
                          marginTop: '4px'
                        }}>
                                💰 {Number(procedure.total_cost).toLocaleString()} UZS
                              </div>
                        }
                          </div>
                        </div>
                    )}
                    </div>
                  </div>
                </div>

                {skinExaminations.length === 0 && cosmeticProcedures.length === 0 &&
              <MacOSEmptyState
                type="calendar"
                title="Нет данных о приемах и процедурах"
                description="История приемов и процедур будет отображаться здесь" />

              }
              </MacOSCard>
            </div>
          }
        </div>

        {/* PriceOverrideManager Modal */}
        {showPriceOverride && selectedServiceForPriceOverride &&
        <PriceOverrideManager
          visitId={selectedPatient?.visit_id}
          serviceId={selectedServiceForPriceOverride.id}
          serviceName={selectedServiceForPriceOverride.name}
          originalPrice={selectedServiceForPriceOverride.price}
          isOpen={showPriceOverride}
          onClose={() => {
            setShowPriceOverride(false);
            setSelectedServiceForPriceOverride(null);
          }}
          onPriceOverrideCreated={(override) => {
            logger.info('Price override created:', override);
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
        <AIChatWidget
          contextType="general"
          specialty="dermatology"
          useWebSocket={false}
          position="bottom-right" />

        <RoleNotificationCenter userRole="dermatologist" />
      </div>
    </div>);

};

export default DermatologistPanelUnified;
