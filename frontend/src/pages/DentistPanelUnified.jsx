import { lazy, Suspense, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useLocation } from 'react-router-dom';
// P-009 fix: shared doctor panel state hook
import { useDoctorPanelState } from '../hooks/useDoctorPanelState';
import { useTheme } from '../contexts/ThemeContext';
import { Button, Badge, Card } from '../components/ui/macos';
import AppointmentSummaryBar from '../components/doctor/AppointmentSummaryBar';
import auth from '../stores/auth.js';
import { apiClient } from '../api/client';
import AIAssistant from '../components/ai/AIAssistant';
import TeethChart from '../components/dental/TeethChart';
import ToothModal from '../components/dental/ToothModal';
import TreatmentPlanner from '../components/dental/TreatmentPlanner';
import PatientCard from '../components/dental/PatientCard';
import DentalPriceManager from '../components/dental/DentalPriceManager';
import ExaminationForm from '../components/dental/ExaminationForm';
import DiagnosisForm from '../components/dental/DiagnosisForm';
import VisitProtocol from '../components/dental/VisitProtocol';
import PhotoArchive from '../components/dental/PhotoArchive';
import ProtocolTemplates from '../components/dental/ProtocolTemplates';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
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
  Stethoscope as Tooth,
  Smile,
  BarChart3,
  Users,
  DollarSign,
  Scissors,
  Save,
  Building } from
'lucide-react';
import AIChatWidget from '../components/ai/AIChatWidget';
import '../styles/animations.css';
import { getApiBaseUrl } from '../api/runtime';
import { resolveCanonicalVisitId } from '../utils/canonicalVisit';
import { printPanelTicket } from '../services/panelPrint';
import notify from '../services/notify';
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

const LazyReportsAndAnalytics = lazy(() => import('../components/dental/ReportsAndAnalytics'));

const API_V1_BASE = getApiBaseUrl();
const DENTISTRY_WAITING_STATUSES = ['waiting', 'confirmed', 'pending'];
const DENTISTRY_CALLED_STATUSES = ['called', 'in_progress'];
const DENTISTRY_COMPLETED_STATUSES = ['completed', 'done'];
const DENTISTRY_LAZY_FALLBACK_STYLE = {
  margin: 'var(--mac-spacing-4)',
  padding: 'var(--mac-spacing-4)',
  color: 'var(--mac-text-secondary)',
  textAlign: 'center'
};
const dentistryAppointmentsHeaderStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  gap: 'var(--mac-spacing-4)',
  marginBottom: 'var(--mac-spacing-4)',
  flexWrap: 'wrap'
};
const dentistryAppointmentsTitleStyle = {
  fontSize: 'var(--mac-font-size-lg)',
  fontWeight: 'var(--mac-font-weight-medium)',
  display: 'flex',
  alignItems: 'center',
  color: 'var(--mac-text-primary)',
  margin: 0,
  minWidth: 'min(100%, 260px)'
};
let dentistAppointmentsCache = null;
let dentistAppointmentsLoadPromise = null;
let dentistServicesCache = null;
let dentistServicesLoadPromise = null;
const dentistVisitProtocolsCache = new Map();
const dentistVisitProtocolsLoadPromises = new Map();
const dentistFallbackLoggedKeys = new Set();

function countAppointmentsByStatuses(appointments, statuses) {
  return appointments.filter((appointment) => statuses.includes(appointment.status)).length;
}

function normalizeNumericId(value) {
  const parsed = parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

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
    defaultTab: 'appointments',
    visitDeepLinkTab: 'visits',
    patientDeepLinkTab: 'appointments',
  });

  const handleCardKeyDown = useCallback((event, action) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  }, []);
  const [patients, setPatients] = useState([]);
  const [treatmentPlans, setTreatmentPlans] = useState([]);
  const [prosthetics, setProsthetics] = useState([]);
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
  const [showTreatmentForm, setShowTreatmentForm] = useState(false);
  const [showProstheticForm, setShowProstheticForm] = useState(false);
  const [dentalChartData, setDentalChartData] = useState(null);

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

  const [treatmentForm, setTreatmentForm] = useState({
    patient_id: '',
    treatment_date: '',
    treatment_type: '',
    teeth_involved: '',
    procedure_description: '',
    materials_used: '',
    anesthesia: '',
    complications: '',
    follow_up_date: '',
    cost: ''
  });

  const [prostheticForm, setProstheticForm] = useState({
    patient_id: '',
    prosthetic_date: '',
    prosthetic_type: '',
    teeth_replaced: '',
    material: '',
    shade: '',
    fit_quality: '',
    patient_satisfaction: '',
    warranty_period: '',
    cost: ''
  });

  // Refs

  // Используем централизованную систему темизации
  const {
    isDark,
    getColor,
    getSpacing,
    getFontSize
  } = useTheme();

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
  const getAllPatientServices = useCallback((patientId, allAppointments) => {
    const patientServices = new Set();
    const patientServiceCodes = new Set();

    allAppointments.forEach((appointment) => {
      if (appointment.patient_id === patientId) {
        if (appointment.services && Array.isArray(appointment.services)) {
          appointment.services.forEach((service) => patientServices.add(service));
        }
        if (appointment.service_codes && Array.isArray(appointment.service_codes)) {
          appointment.service_codes.forEach((code) => patientServiceCodes.add(code));
        }
      }
    });

    return {
      services: Array.from(patientServices),
      service_codes: Array.from(patientServiceCodes)
    };
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
          let allAppointments = [];
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
          let appointmentsData = allAppointments.filter((apt) =>
            isDentistrySpecialty(apt.specialty)
          );

          // Добавляем информацию о всех услугах пациента в каждую запись
          const enrichedAppointmentsData = appointmentsData.map((apt) => {
            const allPatientServices = getAllPatientServices(apt.patient_id, allAppointments);
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
  }, [getAllPatientServices]);

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

  const ensureCanonicalVisitId = useCallback(async (row) => {
    const appointmentId = row?.appointment_id || null;
    const visitId = row?.visit_id || (appointmentId ? await resolveCanonicalVisitId(appointmentId) : null);

    if (visitId) {
      setAppointmentsTableData((prev) => prev.map((appointment) =>
        appointment.id === row.id ? { ...appointment, visit_id: visitId } : appointment
      ));
    }

    return visitId;
  }, []);

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
      handleTabChange('examinations');
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
          handleTabChange('examinations');
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
      // const res = await fetch(`${API_V1_BASE}/dental/treatments?limit=100`, { headers: authHeader() });
      // if (res.ok) setTreatmentPlans(await res.json());
      setTreatmentPlans([]);
      logger.info('Treatment plans endpoint not implemented yet');
    } catch {



      // Игнорируем ошибки загрузки планов лечения
    }}, []);const loadProsthetics = useCallback(async () => {
    try {
      // TODO: Implement prosthetics endpoint
      // const res = await fetch(`${API_V1_BASE}/dental/prosthetics?limit=100`, { headers: authHeader() });
      // if (res.ok) setProsthetics(await res.json());
      setProsthetics([]);
      logger.info('Prosthetics endpoint not implemented yet');
    } catch {



      // Игнорируем ошибки загрузки протезирования
    }}, []);const loadData = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([
      loadPatients(),
      loadTreatmentPlans(),
      loadProsthetics()]
      );
    } catch (error) {
      logger.error('Ошибка загрузки данных:', error);
    } finally {
      setLoading(false);
    }
  }, [loadPatients, loadProsthetics, loadTreatmentPlans]);

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
          handleTabChange(patientObj.visit_id ? 'visits' : 'appointments');
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
          handleTabChange(visitIdFromUrl ? 'visits' : 'appointments');
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
      handleTabChange('visits');
      return;
    }

    notify.info('Выберите визит с каноническим visit_id во вкладке "Записи".');
    handleTabChange('appointments');
  };

  // Сохранение EMR






































  // Завершение визита


























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

  const handleTreatment = (patient) => {
    const patientId = resolvePatientId(patient);
    setSelectedPatient({
      ...patient,
      patient_id: patientId,
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    });
    setTreatmentForm({ ...treatmentForm, patient_id: patientId });
    setShowTreatmentForm(true);
  };

  const handleProsthetic = (patient) => {
    const patientId = resolvePatientId(patient);
    setSelectedPatient({
      ...patient,
      patient_id: patientId,
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    });
    setProstheticForm({ ...prostheticForm, patient_id: patientId });
    setShowProstheticForm(true);
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
  }, [loadDentistVisitProtocolByVisitId]);

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

  const handleTreatmentSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_V1_BASE}/dental/treatments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify(treatmentForm)
      });
      if (res.ok) {
        setShowTreatmentForm(false);
        setTreatmentForm({
          patient_id: '', treatment_date: '', treatment_type: '', teeth_involved: '',
          procedure_description: '', materials_used: '', anesthesia: '', complications: '',
          follow_up_date: '', cost: ''
        });
        loadTreatmentPlans();
      }
    } catch (e) {
      logger.error('Ошибка сохранения лечения:', e);
    }
  };

  const handleProstheticSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_V1_BASE}/dental/prosthetics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify(prostheticForm)
      });
      if (res.ok) {
        setShowProstheticForm(false);
        setProstheticForm({
          patient_id: '', prosthetic_date: '', prosthetic_type: '', teeth_replaced: '',
          material: '', shade: '', fit_quality: '', patient_satisfaction: '',
          warranty_period: '', cost: ''
        });
        loadProsthetics();
      }
    } catch (e) {
      logger.error('Ошибка сохранения протеза:', e);
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

    const activePlansFromState = treatmentPlans.filter((plan) => plan.status === 'active').length;
    const activePlansDerived = appointmentsTableData.filter((apt) => apt.status === 'in_progress' || apt.status === 'waiting').length;
    const activeTreatmentPlansCount = activePlansFromState || activePlansDerived;

    const completedProstheticsFromState = prosthetics.filter((prosthetic) => prosthetic.status === 'completed').length;
    const completedProstheticsDerived = appointmentsTableData.filter((apt) => apt.status === 'completed').length;
    const completedProstheticsCount = completedProstheticsFromState || completedProstheticsDerived;

    return {
      totalPatients: patients.length,
      todayAppointments: todayAppointmentsCount,
      activeTreatmentPlans: activeTreatmentPlansCount,
      completedProsthetics: completedProstheticsCount
    };
  }, [appointmentsTableData, patients, prosthetics, treatmentPlans]);

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
  <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      {/* Статистические карточки */}
      <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
      gap: '24px'
    }}>
        <div style={{
        background: 'var(--mac-bg-primary)',
        borderRadius: 'var(--mac-radius-xl)',
        padding: '24px',
        boxShadow: 'var(--mac-shadow-sm)',
        border: '1px solid var(--mac-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        transition: 'all var(--mac-duration-normal) var(--mac-ease)',
        cursor: 'default'
      }}>
          <div>
            <p style={{
            fontSize: 'var(--mac-font-size-xs)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-secondary)',
            marginBottom: '4px'
          }}>Всего пациентов</p>
            <p style={{
            fontSize: 'var(--mac-font-size-3xl)',
            fontWeight: 'var(--mac-font-weight-bold)',
            color: 'var(--mac-text-primary)'
          }}>{stats.totalPatients}</p>
            <p style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-success)',
            marginTop: '4px'
          }}>+12% за месяц</p>
          </div>
          <div style={{
          width: '56px',
          height: '56px',
          background: 'var(--mac-accent-blue)',
          borderRadius: 'var(--mac-radius-xl)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: 'var(--mac-shadow-lg)'
        }}>
            <Users style={{ height: '28px', width: '28px', color: 'white' }} />
          </div>
        </div>

        <div style={{
        background: 'var(--mac-bg-primary)',
        borderRadius: 'var(--mac-radius-xl)',
        padding: '24px',
        boxShadow: 'var(--mac-shadow-sm)',
        border: '1px solid var(--mac-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        transition: 'all var(--mac-duration-normal) var(--mac-ease)',
        cursor: 'default'
      }}>
          <div>
            <p style={{
            fontSize: 'var(--mac-font-size-xs)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-secondary)',
            marginBottom: '4px'
          }}>Записей сегодня</p>
            <p style={{
            fontSize: 'var(--mac-font-size-3xl)',
            fontWeight: 'var(--mac-font-weight-bold)',
            color: 'var(--mac-text-primary)'
          }}>{stats.todayAppointments}</p>
            <p style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-accent-blue)',
            marginTop: '4px'
          }}>8 из 12 слотов</p>
          </div>
          <div style={{
          width: '56px',
          height: '56px',
          background: 'var(--mac-success)',
          borderRadius: 'var(--mac-radius-xl)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: 'var(--mac-shadow-lg)'
        }}>
            <Calendar style={{ height: '28px', width: '28px', color: 'white' }} />
          </div>
        </div>

        <div style={{
        background: 'var(--mac-bg-primary)',
        borderRadius: 'var(--mac-radius-xl)',
        padding: '24px',
        boxShadow: 'var(--mac-shadow-sm)',
        border: '1px solid var(--mac-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        transition: 'all var(--mac-duration-normal) var(--mac-ease)',
        cursor: 'default'
      }}>
          <div>
            <p style={{
            fontSize: 'var(--mac-font-size-xs)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-secondary)',
            marginBottom: '4px'
          }}>Активные планы</p>
            <p style={{
            fontSize: 'var(--mac-font-size-3xl)',
            fontWeight: 'var(--mac-font-weight-bold)',
            color: 'var(--mac-text-primary)'
          }}>{stats.activeTreatmentPlans}</p>
            <p style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-accent-purple)',
            marginTop: '4px'
          }}>+8% к прошлому месяцу</p>
          </div>
          <div style={{
          width: '56px',
          height: '56px',
          background: 'var(--mac-accent-purple)',
          borderRadius: 'var(--mac-radius-xl)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: 'var(--mac-shadow-lg)'
        }}>
            <FileText style={{ height: '28px', width: '28px', color: 'white' }} />
          </div>
        </div>

        <div style={{
        background: 'var(--mac-bg-primary)',
        borderRadius: 'var(--mac-radius-xl)',
        padding: '24px',
        boxShadow: 'var(--mac-shadow-sm)',
        border: '1px solid var(--mac-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        transition: 'all var(--mac-duration-normal) var(--mac-ease)',
        cursor: 'default'
      }}>
          <div>
            <p style={{
            fontSize: 'var(--mac-font-size-xs)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-secondary)',
            marginBottom: '4px'
          }}>Протезы</p>
            <p style={{
            fontSize: 'var(--mac-font-size-3xl)',
            fontWeight: 'var(--mac-font-weight-bold)',
            color: 'var(--mac-text-primary)'
          }}>{stats.completedProsthetics}</p>
            <p style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-warning)',
            marginTop: '4px'
          }}>+15% к прошлому месяцу</p>
          </div>
          <div style={{
          width: '56px',
          height: '56px',
          background: 'var(--mac-warning)',
          borderRadius: 'var(--mac-radius-xl)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: 'var(--mac-shadow-lg)'
        }}>
            <Smile style={{ height: '28px', width: '28px', color: 'white' }} />
          </div>
        </div>
      </div>

      {/* Быстрые действия */}
      <div style={{
      background: 'var(--mac-bg-primary)',
      borderRadius: 'var(--mac-radius-xl)',
      padding: '24px',
      boxShadow: 'var(--mac-shadow-sm)',
      border: '1px solid var(--mac-border)'
    }}>
        <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '24px'
      }}>
          <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          color: 'var(--mac-text-primary)'
        }}>Быстрые действия</h3>
        </div>
        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '24px'
      }}>
          <Button
          onClick={() => handleTabChange('patients')}
          variant="primary"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '16px 24px',
            borderRadius: 'var(--mac-radius-lg)',
            boxShadow: 'var(--mac-shadow-sm)',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            background: 'var(--mac-accent-blue)',
            color: 'white',
            fontWeight: 'var(--mac-font-weight-medium)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.boxShadow = 'var(--mac-shadow-md)';
            e.currentTarget.style.transform = 'translateY(-2px)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
            e.currentTarget.style.transform = 'translateY(0)';
          }}>

            <Plus style={{ height: '20px', width: '20px' }} />
            <span style={{ fontWeight: 'var(--mac-font-weight-medium)' }}>Новый пациент</span>
          </Button>
          <Button
          onClick={() => handleTabChange('appointments')}
          variant="outline"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '16px 24px',
            borderRadius: 'var(--mac-radius-lg)',
            boxShadow: 'var(--mac-shadow-sm)',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            border: '1px solid var(--mac-border)',
            fontWeight: 'var(--mac-font-weight-medium)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.boxShadow = 'var(--mac-shadow-md)';
            e.currentTarget.style.transform = 'translateY(-2px)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
            e.currentTarget.style.transform = 'translateY(0)';
          }}>

            <Calendar style={{ height: '20px', width: '20px' }} />
            <span style={{ fontWeight: 'var(--mac-font-weight-medium)' }}>Записать на прием</span>
          </Button>
          <Button
          onClick={() => handleTabChange('dental-chart')}
          variant="outline"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '16px 24px',
            borderRadius: 'var(--mac-radius-lg)',
            boxShadow: 'var(--mac-shadow-sm)',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            border: '1px solid var(--mac-border)',
            fontWeight: 'var(--mac-font-weight-medium)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.boxShadow = 'var(--mac-shadow-md)';
            e.currentTarget.style.transform = 'translateY(-2px)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
            e.currentTarget.style.transform = 'translateY(0)';
          }}>

            <Tooth style={{ height: '20px', width: '20px' }} />
            <span style={{ fontWeight: 'var(--mac-font-weight-medium)' }}>Схема зубов</span>
          </Button>
        </div>
      </div>

      {/* Последние записи */}
      <div style={{
      background: 'var(--mac-bg-primary)',
      borderRadius: 'var(--mac-radius-xl)',
      padding: '24px',
      boxShadow: 'var(--mac-shadow-sm)',
      border: '1px solid var(--mac-border)'
    }}>
        <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '24px'
      }}>
          <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          color: 'var(--mac-text-primary)'
        }}>Последние записи</h3>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {appointmentsTableData.slice(0, 5).map((appointment) =>
        <div
          key={appointment.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '24px',
            background: 'var(--mac-bg-secondary)',
            borderRadius: 'var(--mac-radius-lg)',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            cursor: 'default'
          }}>

              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{
              width: '40px',
              height: '40px',
              background: 'var(--mac-accent-blue)',
              borderRadius: 'var(--mac-radius-lg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: 'var(--mac-shadow-sm)'
            }}>
                  <span style={{
                color: 'white',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-bold)'
              }}>
                    {appointment.patientName?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>{appointment.patientName}</p>
                  <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>{appointment.date} {appointment.time}</p>
                </div>
              </div>
              <div style={{
            padding: '4px 12px',
            borderRadius: 'var(--mac-radius-full)',
            fontSize: 'var(--mac-font-size-xs)',
            fontWeight: 'var(--mac-font-weight-medium)',
            background: appointment.status === 'confirmed' ? 'var(--mac-success-bg)' : 'var(--mac-warning-bg)',
            color: appointment.status === 'confirmed' ? 'var(--mac-success)' : 'var(--mac-warning)'
          }}>
                {appointment.status}
              </div>
            </div>
        )}
        </div>
      </div>
    </div>;


  // Рендер пациентов
  const renderPatients = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Поиск и фильтры */}
      <Card padding="lg">
        <div style={{ display: 'flex', flexDirection: 'row', gap: '16px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <div style={{ position: 'relative' }}>
              <Search style={{
              position: 'absolute',
              left: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              height: '16px',
              width: '16px',
              color: 'var(--mac-text-tertiary)'
            }} />
              <input
              type="text"
              placeholder="Поиск пациентов..."
              aria-label="Search dentist patients"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                paddingLeft: '40px',
                paddingRight: '16px',
                paddingTop: '8px',
                paddingBottom: '8px',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-lg)',
                fontSize: 'var(--mac-font-size-base)',
                fontFamily: 'inherit',
                backgroundColor: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                transition: 'all var(--mac-duration-fast) var(--mac-ease)'
              }}
              onFocus={(e) => {
                e.target.style.outline = 'var(--mac-focus-ring)';
                e.target.style.outlineOffset = '2px';
                e.target.style.borderColor = 'var(--mac-accent-blue)';
              }}
              onBlur={(e) => {
                e.target.style.outline = 'none';
                e.target.style.borderColor = 'var(--mac-border)';
              }} />

            </div>
          </div>
          <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          style={{
            padding: '8px 16px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            fontSize: 'var(--mac-font-size-base)',
            fontFamily: 'inherit',
            backgroundColor: 'var(--mac-bg-primary)',
            color: 'var(--mac-text-primary)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-fast) var(--mac-ease)'
          }}
          onFocus={(e) => {
            e.target.style.outline = 'var(--mac-focus-ring)';
            e.target.style.outlineOffset = '2px';
            e.target.style.borderColor = 'var(--mac-accent-blue)';
          }}
          onBlur={(e) => {
            e.target.style.outline = 'none';
            e.target.style.borderColor = 'var(--mac-border)';
          }}>

            <option value="all">Все статусы</option>
            <option value="active">Активные</option>
            <option value="inactive">Неактивные</option>
          </select>
        </div>
      </Card>

      {/* Список пациентов */}
      <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
      gap: '24px'
    }}>
        {filteredPatients.map((patient) =>
      <Card
        key={patient.id}
        padding="lg"
        style={{
          transition: 'all var(--mac-duration-normal) var(--mac-ease)',
          cursor: 'pointer'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.boxShadow = 'var(--mac-shadow-lg)';
          e.currentTarget.style.transform = 'translateY(-2px)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
          e.currentTarget.style.transform = 'translateY(0)';
        }}>

            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
              width: '48px',
              height: '48px',
              background: 'var(--mac-accent-blue)',
              borderRadius: 'var(--mac-radius-full)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                  <span style={{
                color: 'white',
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <h3 style={{
                fontWeight: 'var(--mac-font-weight-semibold)',
                fontSize: 'var(--mac-font-size-lg)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>{patient.name}</h3>
                  <p style={{
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-sm)'
              }}>{patient.phone}</p>
                </div>
              </div>
              <Badge variant={patient.status === 'active' ? 'success' : 'warning'}>
                {patient.status}
              </Badge>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
              <p style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-secondary)'
          }}>
                <strong style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>Возраст:</strong> {patient.age} лет
              </p>
              <p style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-secondary)'
          }}>
                <strong style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>Последний визит:</strong> {patient.lastVisit || 'Не было'}
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
              <Button
            size="sm"
            onClick={() => handlePatientSelect(patient)}
            style={{ gridColumn: 'span 2', marginBottom: '8px' }}>

                <Edit style={{ height: '16px', width: '16px', marginRight: '4px' }} />
                Карточка пациента
              </Button>
              <Button
            size="sm"
            variant="outline"
            type="button"
            aria-label={`Open examination for ${patient.name || patient.id}`}
            onClick={() => handleExamination(patient)}
            title="Осмотр"
            style={{ padding: '8px' }}>

                <Eye aria-hidden="true" style={{ height: '16px', width: '16px' }} />
              </Button>
              <Button
            size="sm"
            variant="outline"
            type="button"
            aria-label={`Open diagnoses for ${patient.name || patient.id}`}
            onClick={() => handleDiagnosis(patient)}
            title="Диагнозы"
            style={{ padding: '8px' }}>

                <Stethoscope aria-hidden="true" style={{ height: '16px', width: '16px' }} />
              </Button>
              <Button
            size="sm"
            variant="outline"
            type="button"
            aria-label={`Open visit protocol for ${patient.name || patient.id}`}
            onClick={() => handleVisitProtocol(patient)}
            title="Протокол визита"
            style={{ padding: '8px' }}>

                <FileText aria-hidden="true" style={{ height: '16px', width: '16px' }} />
              </Button>
              <Button
            size="sm"
            variant="outline"
            type="button"
            aria-label={`Open dental chart for ${patient.name || patient.id}`}
            onClick={() => handleDentalChart(patient)}
            title="Схема зубов"
            style={{ padding: '8px' }}>

                <Tooth aria-hidden="true" style={{ height: '16px', width: '16px' }} />
              </Button>
              <Button
            size="sm"
            variant="outline"
            type="button"
            aria-label={`Open treatment for ${patient.name || patient.id}`}
            onClick={() => handleTreatment(patient)}
            title="Лечение"
            style={{ padding: '8px' }}>

                <Scissors aria-hidden="true" style={{ height: '16px', width: '16px' }} />
              </Button>
              <Button
            size="sm"
            variant="outline"
            type="button"
            aria-label={`Open prosthetics for ${patient.name || patient.id}`}
            onClick={() => handleProsthetic(patient)}
            title="Протезирование"
            style={{ padding: '8px' }}>

                <Smile aria-hidden="true" style={{ height: '16px', width: '16px' }} />
              </Button>
            </div>
          </Card>
      )}
      </div>
    </div>;


  // Рендер записей
  const renderAppointments = () =>
  <div style={{
    width: '100%',
    maxWidth: 'none',
    display: 'flex',
    flexDirection: 'column',
    gap: '24px'
  }}>
      <Card padding="lg" style={{
      width: '100%',
      maxWidth: '100%',
      minWidth: 0,
      boxSizing: 'border-box',
      overflow: 'hidden'
    }}>
        <div style={dentistryAppointmentsHeaderStyle}>
          <h3 style={dentistryAppointmentsTitleStyle}>
            <Calendar size={20} style={{ marginRight: '8px', color: 'var(--mac-success)' }} />
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
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)',
        marginBottom: '16px',
        color: 'var(--mac-text-primary)'
      }}>Объективные осмотры</h3>
        <p style={{
        color: 'var(--mac-text-secondary)',
        marginBottom: '16px',
        fontSize: 'var(--mac-font-size-base)'
      }}>
          Выберите пациента для проведения или просмотра объективного осмотра
        </p>

        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
        gap: '16px'
      }}>
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label={`Open examination for ${resolvePatientName(patient)}`}
          style={{
            padding: '24px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}
          onClick={() => handleExamination(patient)}
          onKeyDown={(event) => handleCardKeyDown(event, () => handleExamination(patient))}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
              width: '32px',
              height: '32px',
              background: 'var(--mac-success)',
              borderRadius: 'var(--mac-radius-full)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                  <span style={{
                color: 'white',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>{patient.name}</p>
                  <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>Провести осмотр</p>
                </div>
              </div>
            </div>
        )}
        </div>
      </Card>
    </div>;


  // Рендер диагнозов
  const renderDiagnoses = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)',
        marginBottom: '16px',
        color: 'var(--mac-text-primary)'
      }}>Диагнозы и назначения</h3>
        <p style={{
        color: 'var(--mac-text-secondary)',
        marginBottom: '16px',
        fontSize: 'var(--mac-font-size-base)'
      }}>
          Выберите пациента для постановки диагнозов и назначений
        </p>

        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
        gap: '16px'
      }}>
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label={`Open diagnosis for ${resolvePatientName(patient)}`}
          style={{
            padding: '24px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}
          onClick={() => handleDiagnosis(patient)}
          onKeyDown={(event) => handleCardKeyDown(event, () => handleDiagnosis(patient))}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
              width: '32px',
              height: '32px',
              background: 'var(--mac-accent-blue)',
              borderRadius: 'var(--mac-radius-full)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                  <span style={{
                color: 'white',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>{patient.name}</p>
                  <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>Поставить диагноз</p>
                </div>
              </div>
            </div>
        )}
        </div>
      </Card>
    </div>;


  // Рендер протоколов визитов
  const renderVisits = () => {
    // Если выбран пациент из очереди - показываем EMR
    if (selectedPatient) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <Card padding="lg">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <h3 style={{
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <Stethoscope size={20} />
                Прием пациента: {selectedPatient.patient_name || selectedPatient.name || `№${selectedPatient.number}`}
              </h3>
              <Button
                variant="outline"
                onClick={() => {
                  setSelectedPatient(null);
                  handleTabChange('queue');
                }}>

                Вернуться в очередь
              </Button>
            </div>

            {/* EMR System */}
            <EMRContainerV2
              visitId={selectedPatient.visit_id}
              patientId={selectedPatient.patient?.id || selectedPatient.patient_id || selectedPatient.id}
              specialty="dentistry" />

          </Card>
        </div>);

    }

    // Иначе показываем список пациентов для выбора протокола
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <Card padding="lg">
          <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            marginBottom: '16px',
            color: 'var(--mac-text-primary)'
          }}>Протоколы визитов</h3>
          <p style={{
            color: 'var(--mac-text-secondary)',
            marginBottom: '16px',
            fontSize: 'var(--mac-font-size-base)'
          }}>
            Выберите пациента из очереди или выберите из списка для создания протокола визита
          </p>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
            gap: '16px'
          }}>
            {patients.map((patient) =>
            <div
              key={patient.id}
              role="button"
              tabIndex={0}
              aria-label={`Open visit protocol for ${resolvePatientName(patient)}`}
              style={{
                padding: '24px',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-lg)',
                cursor: 'pointer',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
              onClick={() => handleVisitProtocol(patient)}
              onKeyDown={(event) => handleCardKeyDown(event, () => handleVisitProtocol(patient))}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{
                  width: '32px',
                  height: '32px',
                  background: 'var(--mac-accent-purple)',
                  borderRadius: 'var(--mac-radius-full)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                    <span style={{
                    color: 'white',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)'
                  }}>
                      {patient.name?.charAt(0)}
                    </span>
                  </div>
                  <div>
                    <p style={{
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)'
                  }}>{patient.name}</p>
                    <p style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)'
                  }}>Создать протокол</p>
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
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)',
        marginBottom: '16px',
        color: 'var(--mac-text-primary)'
      }}>Фото и рентген архив</h3>
        <p style={{
        color: 'var(--mac-text-secondary)',
        marginBottom: '16px',
        fontSize: 'var(--mac-font-size-base)'
      }}>
          Выберите пациента для просмотра и управления фото и рентгеновскими снимками
        </p>

        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
        gap: '16px'
      }}>
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label={`Open photo archive for ${resolvePatientName(patient)}`}
          style={{
            padding: '24px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}
          onClick={() => handlePhotoArchive(patient)}
          onKeyDown={(event) => handleCardKeyDown(event, () => handlePhotoArchive(patient))}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
              width: '32px',
              height: '32px',
              background: 'var(--mac-warning)',
              borderRadius: 'var(--mac-radius-full)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                  <span style={{
                color: 'white',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>{patient.name}</p>
                  <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>Открыть архив</p>
                </div>
              </div>
            </div>
        )}
        </div>
      </Card>
    </div>;


  // Рендер шаблонов
  const renderTemplates = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '16px'
      }}>
          <div>
            <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            marginBottom: '4px'
          }}>Шаблоны протоколов</h3>
            <p style={{
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
              Стандартные протоколы для быстрого создания протоколов визитов
            </p>
          </div>
          <Button
          onClick={handleProtocolTemplates}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>

            <FileText style={{ height: '16px', width: '16px' }} />
            Управление шаблонами
          </Button>
        </div>

        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: '16px'
      }}>
          <div
          style={{
            padding: '16px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            cursor: 'default',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}>

            <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            marginBottom: '12px'
          }}>
              <div style={{
              width: '40px',
              height: '40px',
              background: 'var(--mac-accent-blue-bg)',
              borderRadius: 'var(--mac-radius-lg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                <Scissors style={{ height: '20px', width: '20px', color: 'var(--mac-accent-blue)' }} />
              </div>
              <div>
                <h4 style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>Лечение кариеса</h4>
                <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>60 мин</p>
              </div>
            </div>
            <p style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)',
            marginBottom: '12px'
          }}>
              Стандартный протокол лечения кариеса с анестезией и пломбированием
            </p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Button size="sm" style={{ flex: 1 }} onClick={handleProtocolTemplates} type="button">
                Использовать
              </Button>
              <Button
                size="sm"
                variant="outline"
                type="button"
                title="Edit caries treatment template"
                aria-label="Edit caries treatment template">
                <Edit aria-hidden="true" style={{ height: '16px', width: '16px' }} />
              </Button>
            </div>
          </div>

          <div
          style={{
            padding: '16px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            cursor: 'default',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}>

            <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            marginBottom: '12px'
          }}>
              <div style={{
              width: '40px',
              height: '40px',
              background: 'var(--mac-danger-bg)',
              borderRadius: 'var(--mac-radius-lg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                <Scissors style={{ height: '20px', width: '20px', color: 'var(--mac-danger)' }} />
              </div>
              <div>
                <h4 style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>Эндодонтическое лечение</h4>
                <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>120 мин</p>
              </div>
            </div>
            <p style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)',
            marginBottom: '12px'
          }}>
              Протокол лечения корневых каналов с инструментальной обработкой
            </p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Button size="sm" style={{ flex: 1 }} onClick={handleProtocolTemplates} type="button">
                Использовать
              </Button>
              <Button
                size="sm"
                variant="outline"
                type="button"
                title="Edit endodontic treatment template"
                aria-label="Edit endodontic treatment template">
                <Edit aria-hidden="true" style={{ height: '16px', width: '16px' }} />
              </Button>
            </div>
          </div>

          <div
          style={{
            padding: '16px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            cursor: 'default',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}>

            <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            marginBottom: '12px'
          }}>
              <div style={{
              width: '40px',
              height: '40px',
              background: 'var(--mac-success-bg)',
              borderRadius: 'var(--mac-radius-lg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                <Scissors style={{ height: '20px', width: '20px', color: 'var(--mac-success)' }} />
              </div>
              <div>
                <h4 style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>Профессиональная гигиена</h4>
                <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>75 мин</p>
              </div>
            </div>
            <p style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)',
            marginBottom: '12px'
          }}>
              Протокол профессиональной гигиены полости рта
            </p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Button size="sm" style={{ flex: 1 }} onClick={handleProtocolTemplates} type="button">
                Использовать
              </Button>
              <Button
                size="sm"
                variant="outline"
                type="button"
                title="Edit professional hygiene template"
                aria-label="Edit professional hygiene template">
                <Edit aria-hidden="true" style={{ height: '16px', width: '16px' }} />
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </div>;


  // Рендер отчетов
  const renderReports = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {savedVisitProtocols.length > 0 &&
      <Card padding="lg">
          <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '16px'
        }}>
            <div>
              <h3 style={{
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              marginBottom: '4px'
            }}>Сохранённые протоколы визитов</h3>
              <p style={{
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)'
            }}>
                Последние протоколы доступны для повторного открытия без ручной пересборки
              </p>
            </div>
          </div>

          <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: '16px'
        }}>
            {savedVisitProtocols.map((protocol) =>
          <div
            key={protocol.visit_id}
            style={{
              padding: '16px',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-lg)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px'
            }}>
                <div>
                  <div style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>{protocol.patient_name}</div>
                  <div style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>
                    Визит #{protocol.visit_id} • {new Date(protocol.saved_at).toLocaleString('ru-RU')}
                  </div>
                </div>
                <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)',
              minHeight: '36px'
            }}>
                  {protocol.visitData?.chiefComplaint || 'Жалоба не указана'}
                </div>
                <Button
                onClick={() => reopenVisitProtocol(protocol)}
                style={{
                  alignSelf: 'flex-start'
                }}>
                  Открыть протокол
                </Button>
              </div>
          )}
          </div>
        </Card>
      }

      <Card padding="lg">
        <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '16px'
      }}>
          <div>
            <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            marginBottom: '4px'
          }}>Отчеты и аналитика</h3>
            <p style={{
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
              Статистика по пациентам, врачам, процедурам и клинике
            </p>
          </div>
          <Button
          onClick={handleReports}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>

            <BarChart3 style={{ height: '16px', width: '16px' }} />
            Открыть отчеты
          </Button>
        </div>

        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
        gap: '16px'
      }}>
          <div
          role="button"
          tabIndex={0}
          style={{
            padding: '16px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}
          onClick={handleReports}
          onKeyDown={(event) => handleCardKeyDown(event, handleReports)}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}>

            <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            marginBottom: '12px'
          }}>
              <div style={{
              width: '40px',
              height: '40px',
              background: 'var(--mac-accent-blue-bg)',
              borderRadius: 'var(--mac-radius-lg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                <BarChart3 style={{ height: '20px', width: '20px', color: 'var(--mac-accent-blue)' }} />
              </div>
              <div>
                <h4 style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>Общий обзор</h4>
                <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>Основные показатели</p>
              </div>
            </div>
            <p style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)'
          }}>
              Общая статистика по всем направлениям деятельности
            </p>
          </div>

          <div
          role="button"
          tabIndex={0}
          style={{
            padding: '16px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}
          onClick={handleReports}
          onKeyDown={(event) => handleCardKeyDown(event, handleReports)}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}>

            <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            marginBottom: '12px'
          }}>
              <div style={{
              width: '40px',
              height: '40px',
              background: 'var(--mac-success-bg)',
              borderRadius: 'var(--mac-radius-lg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                <Users style={{ height: '20px', width: '20px', color: 'var(--mac-success)' }} />
              </div>
              <div>
                <h4 style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>По пациентам</h4>
                <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>Демография и активность</p>
              </div>
            </div>
            <p style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)'
          }}>
              Анализ пациентской базы и их активности
            </p>
          </div>

          <div
          role="button"
          tabIndex={0}
          style={{
            padding: '16px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}
          onClick={handleReports}
          onKeyDown={(event) => handleCardKeyDown(event, handleReports)}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}>

            <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            marginBottom: '12px'
          }}>
              <div style={{
              width: '40px',
              height: '40px',
              background: 'var(--mac-accent-purple-bg)',
              borderRadius: 'var(--mac-radius-lg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                <Stethoscope style={{ height: '20px', width: '20px', color: 'var(--mac-accent-purple)' }} />
              </div>
              <div>
                <h4 style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>По врачам</h4>
                <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>Производительность</p>
              </div>
            </div>
            <p style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)'
          }}>
              Статистика работы врачей и их специализаций
            </p>
          </div>

          <div
          role="button"
          tabIndex={0}
          style={{
            padding: '16px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}
          onClick={handleReports}
          onKeyDown={(event) => handleCardKeyDown(event, handleReports)}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}>

            <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            marginBottom: '12px'
          }}>
              <div style={{
              width: '40px',
              height: '40px',
              background: 'var(--mac-warning-bg)',
              borderRadius: 'var(--mac-radius-lg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                <Building style={{ height: '20px', width: '20px', color: 'var(--mac-warning)' }} />
              </div>
              <div>
                <h4 style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>По клинике</h4>
                <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>Оборудование и загруженность</p>
              </div>
            </div>
            <p style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)'
          }}>
              Анализ работы клиники и состояния оборудования
            </p>
          </div>
        </div>
      </Card>
    </div>;


  // Рендер схем зубов
  const renderDentalChart = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)',
        marginBottom: '16px',
        color: 'var(--mac-text-primary)'
      }}>Схемы зубов</h3>
        <p style={{
        color: 'var(--mac-text-secondary)',
        marginBottom: '16px',
        fontSize: 'var(--mac-font-size-base)'
      }}>
          Выберите пациента для просмотра и редактирования схемы зубов
        </p>

        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
        gap: '16px'
      }}>
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label={`Open dental chart for ${resolvePatientName(patient)}`}
          style={{
            padding: '24px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}
          onClick={() => handleDentalChart(patient)}
          onKeyDown={(event) => handleCardKeyDown(event, () => handleDentalChart(patient))}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
              width: '32px',
              height: '32px',
              background: 'var(--mac-accent-blue)',
              borderRadius: 'var(--mac-radius-full)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                  <span style={{
                color: 'white',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>{patient.name}</p>
                  <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>Открыть схему</p>
                </div>
              </div>
            </div>
        )}
        </div>
      </Card>
    </div>;


  // Рендер планов лечения
  const renderTreatmentPlans = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)',
        marginBottom: '16px',
        color: 'var(--mac-text-primary)'
      }}>Планы лечения</h3>
        <p style={{
        color: 'var(--mac-text-secondary)',
        marginBottom: '16px',
        fontSize: 'var(--mac-font-size-base)'
      }}>
          Выберите пациента для создания или редактирования плана лечения
        </p>

        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
        gap: '16px'
      }}>
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label={`Open treatment planner for ${resolvePatientName(patient)}`}
          style={{
            padding: '24px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}
          onClick={() => handleTreatmentPlanner(patient)}
          onKeyDown={(event) => handleCardKeyDown(event, () => handleTreatmentPlanner(patient))}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
              width: '32px',
              height: '32px',
              background: 'var(--mac-success)',
              borderRadius: 'var(--mac-radius-full)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                  <span style={{
                color: 'white',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>{patient.name}</p>
                  <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>Открыть план</p>
                </div>
              </div>
            </div>
        )}
        </div>
      </Card>
    </div>;


  // Рендер протезирования
  const renderProsthetics = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)',
        marginBottom: '16px',
        color: 'var(--mac-text-primary)'
      }}>Протезирование</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {prosthetics.map((prosthetic) =>
        <div
          key={prosthetic.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px',
            background: 'var(--mac-bg-secondary)',
            borderRadius: 'var(--mac-radius-lg)',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}>

              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{
              width: '40px',
              height: '40px',
              background: 'var(--mac-warning)',
              borderRadius: 'var(--mac-radius-full)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
                  <Smile style={{ height: '20px', width: '20px', color: 'white' }} />
                </div>
                <div>
                  <p style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)'
              }}>{prosthetic.patientName}</p>
                  <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>{prosthetic.type}</p>
                </div>
              </div>
              <Badge variant={prosthetic.status === 'completed' ? 'success' : 'warning'}>
                {prosthetic.status}
              </Badge>
            </div>
        )}
        </div>
      </Card>
    </div>;


  // Рендер AI помощника
  const renderAIAssistant = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)',
        marginBottom: '16px',
        color: 'var(--mac-text-primary)'
      }}>AI Помощник</h3>
        <AIAssistant
        context="dental"
        onSuggestion={(suggestion) => {
          logger.info('AI предложение:', suggestion);
        }} />

      </Card>
    </div>;


  // Рендер контента
  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return renderDashboard();
      case 'queue':
        return (
          <QueueIntegration
            specialistId={user?.doctor_id || user?.specialist_id || ''}
            specialty="dentistry"
            onPatientSelect={handlePatientSelect}
            onStartVisit={(appointment) => {
              setSelectedPatient(appointment);
              handleTabChange('visits');
            }} />);


      case 'patients':
        return renderPatients();
      case 'appointments':
        return renderAppointments();
      case 'examinations':
        return renderExaminations();
      case 'diagnoses':
        return renderDiagnoses();
      case 'visits':
        return renderVisits();
      case 'photos':
        return renderPhotos();
      case 'templates':
        return renderTemplates();
      case 'reports':
        return renderReports();
      case 'dental-chart':
        return renderDentalChart();
      case 'treatment-plans':
        return renderTreatmentPlans();
      case 'prosthetics':
        return renderProsthetics();
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
      <div style={{ padding: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div style={{
            height: '32px',
            background: 'var(--mac-bg-secondary)',
            borderRadius: 'var(--mac-radius-md)',
            width: '25%',
            animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
          }}></div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '24px'
          }}>
            {[...Array(4)].map((_, i) =>
            <div key={i} style={{
              height: '96px',
              background: 'var(--mac-bg-secondary)',
              borderRadius: 'var(--mac-radius-md)',
              animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
            }}></div>
            )}
          </div>
        </div>
      </div>);

  }

  const selectedPatientId = selectedPatient?.patient?.id || selectedPatient?.patient_id || selectedPatient?.id || null;
  const selectedPatientDisplayName =
    selectedPatient?.patient_name || selectedPatient?.patient_fio || selectedPatient?.name || 'Пациент';

  return (
    <div className="dentist-panel" style={{
      padding: '0px', // Убираем padding, так как он уже есть в main контейнере
      boxSizing: 'border-box',
      width: '100%',
      position: 'relative',
      zIndex: 1,
      display: 'block',
      maxWidth: '100%',
      margin: 0,
      minHeight: '100vh',
      background: 'var(--mac-gradient-window)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
      color: 'var(--mac-text-primary)',
      transition: 'background var(--mac-duration-normal) var(--mac-ease)'
    }}>
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
          <Card role="status" aria-live="polite" style={DENTISTRY_LAZY_FALLBACK_STYLE}>
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
      <div style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50
      }}>
          <div style={{
          background: 'var(--mac-bg-primary)',
          borderRadius: 'var(--mac-radius-xl)',
          padding: '24px',
          width: '100%',
          maxWidth: '1152px',
          height: '100%',
          maxHeight: '90vh',
          overflow: 'auto',
          boxShadow: 'var(--mac-shadow-xl)',
          border: '1px solid var(--mac-border)'
        }}>
            <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '16px'
          }}>
              <h2 style={{
              fontSize: 'var(--mac-font-size-xl)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)'
            }}>
                Схема зубов: {selectedPatientDisplayName}
              </h2>
              <button
              onClick={() => setShowDentalChart(false)}
              aria-label={`Закрыть схему зубов пациента ${selectedPatientDisplayName}`}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--mac-text-secondary)',
                cursor: 'pointer',
                transition: 'all var(--mac-duration-fast) var(--mac-ease)',
                padding: '4px',
                borderRadius: 'var(--mac-radius-sm)'
              }}
              onMouseEnter={(e) => {
                e.target.style.color = 'var(--mac-text-primary)';
                e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e) => {
                e.target.style.color = 'var(--mac-text-secondary)';
                e.target.style.backgroundColor = 'transparent';
              }}>

                <XCircle style={{ height: '24px', width: '24px' }} />
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
      <div style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50
      }}>
          <div style={{
          background: 'var(--mac-bg-primary)',
          borderRadius: 'var(--mac-radius-xl)',
          padding: '24px',
          width: '100%',
          maxWidth: '1152px',
          height: '100%',
          maxHeight: '90vh',
          overflow: 'auto',
          boxShadow: 'var(--mac-shadow-xl)',
          border: '1px solid var(--mac-border)'
        }}>
            <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '16px'
          }}>
              <h2 style={{
              fontSize: 'var(--mac-font-size-xl)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)'
            }}>
                План лечения: {selectedPatientDisplayName}
              </h2>
              <button
              onClick={() => setShowTreatmentPlanner(false)}
              aria-label={`Закрыть план лечения пациента ${selectedPatientDisplayName}`}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--mac-text-secondary)',
                cursor: 'pointer',
                transition: 'all var(--mac-duration-fast) var(--mac-ease)',
                padding: '4px',
                borderRadius: 'var(--mac-radius-sm)'
              }}
              onMouseEnter={(e) => {
                e.target.style.color = 'var(--mac-text-primary)';
                e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e) => {
                e.target.style.color = 'var(--mac-text-secondary)';
                e.target.style.backgroundColor = 'transparent';
              }}>

                <XCircle style={{ height: '24px', width: '24px' }} />
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
                    <input
                    type="date"
                    aria-label="Examination date"
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
                    <input
                    type="text"
                    aria-label="Missing teeth"
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
                  aria-label="Examination diagnosis"
                  value={examinationForm.diagnosis}
                  onChange={(e) => setExaminationForm({ ...examinationForm, diagnosis: e.target.value })}
                  placeholder="Стоматологический диагноз"
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Рекомендации</label>
                  <textarea
                  aria-label="Examination recommendations"
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

      {/* Форма лечения */}
      {showTreatmentForm && selectedPatient &&
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg w-full max-w-4xl h-full max-h-[90vh] overflow-auto">
            <div className="p-6 border-b">
              <h2 className="text-xl font-semibold">
                Новый план лечения — {selectedPatientDisplayName}
              </h2>
            </div>
            <div className="p-6">
              <form onSubmit={handleTreatmentSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Дата лечения *</label>
                    <input
                    type="date"
                    aria-label="Treatment date"
                    value={treatmentForm.treatment_date}
                    onChange={(e) => setTreatmentForm({ ...treatmentForm, treatment_date: e.target.value })}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Тип лечения *</label>
                    <select
                    value={treatmentForm.treatment_type}
                    onChange={(e) => setTreatmentForm({ ...treatmentForm, treatment_type: e.target.value })}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">

                      <option value="">Выберите тип</option>
                      <option value="filling">Пломбирование</option>
                      <option value="root_canal">Каналы</option>
                      <option value="extraction">Удаление</option>
                      <option value="cleaning">Чистка</option>
                      <option value="whitening">Отбеливание</option>
                      <option value="orthodontics">Ортодонтия</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Вовлеченные зубы</label>
                    <input
                    type="text"
                    aria-label="Treatment teeth involved"
                    value={treatmentForm.teeth_involved}
                    onChange={(e) => setTreatmentForm({ ...treatmentForm, teeth_involved: e.target.value })}
                    placeholder="Номера зубов"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Стоимость</label>
                    <input
                    type="number"
                    aria-label="Treatment cost"
                    value={treatmentForm.cost}
                    onChange={(e) => setTreatmentForm({ ...treatmentForm, cost: e.target.value })}
                    placeholder="Сумма"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Описание процедуры</label>
                  <textarea
                  aria-label="Treatment procedure description"
                  value={treatmentForm.procedure_description}
                  onChange={(e) => setTreatmentForm({ ...treatmentForm, procedure_description: e.target.value })}
                  placeholder="Подробное описание"
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Материалы</label>
                    <input
                    type="text"
                    aria-label="Treatment materials used"
                    value={treatmentForm.materials_used}
                    onChange={(e) => setTreatmentForm({ ...treatmentForm, materials_used: e.target.value })}
                    placeholder="Названия материалов"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Анестезия</label>
                    <select
                    value={treatmentForm.anesthesia}
                    onChange={(e) => setTreatmentForm({ ...treatmentForm, anesthesia: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">

                      <option value="">Выберите</option>
                      <option value="none">Не требуется</option>
                      <option value="local">Местная</option>
                      <option value="sedation">Седация</option>
                      <option value="general">Общая</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Осложнения</label>
                    <input
                    type="text"
                    aria-label="Treatment complications"
                    value={treatmentForm.complications}
                    onChange={(e) => setTreatmentForm({ ...treatmentForm, complications: e.target.value })}
                    placeholder="Описание осложнений"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Дата контроля</label>
                    <input
                    type="date"
                    aria-label="Treatment follow-up date"
                    value={treatmentForm.follow_up_date}
                    onChange={(e) => setTreatmentForm({ ...treatmentForm, follow_up_date: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                  </div>
                </div>

                <div className="flex gap-2">
                  <Button type="submit" className="flex items-center gap-2">
                    <Save className="h-4 w-4" />
                    Сохранить лечение
                  </Button>
                  <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    // Открываем менеджер цен для указания итоговой стоимости
                    setSelectedServiceForPrice({
                      id: 1, // ID услуги - в реальном приложении получать из формы
                      name: treatmentForm.procedure_type || 'Стоматологическое лечение',
                      price: Number(treatmentForm.cost) || 50000
                    });
                    setShowPriceManager(true);
                  }}
                  className="flex items-center gap-2">

                    <DollarSign className="h-4 w-4" />
                    Указать цену
                  </Button>
                  <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowTreatmentForm(false)}>

                    Отмена
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      }

      {/* Форма протезирования */}
      {showProstheticForm && selectedPatient &&
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg w-full max-w-4xl h-full max-h-[90vh] overflow-auto">
            <div className="p-6 border-b">
              <h2 className="text-xl font-semibold">
                Новый протез — {selectedPatientDisplayName}
              </h2>
            </div>
            <div className="p-6">
              <form onSubmit={handleProstheticSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Дата протезирования *</label>
                    <input
                    type="date"
                    aria-label="Prosthetic date"
                    value={prostheticForm.prosthetic_date}
                    onChange={(e) => setProstheticForm({ ...prostheticForm, prosthetic_date: e.target.value })}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Тип протеза *</label>
                    <select
                    value={prostheticForm.prosthetic_type}
                    onChange={(e) => setProstheticForm({ ...prostheticForm, prosthetic_type: e.target.value })}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">

                      <option value="">Выберите тип</option>
                      <option value="crown">Коронка</option>
                      <option value="bridge">Мост</option>
                      <option value="implant">Имплант</option>
                      <option value="partial_denture">Частичный протез</option>
                      <option value="full_denture">Полный протез</option>
                      <option value="veneer">Винир</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Заменяемые зубы</label>
                    <input
                    type="text"
                    aria-label="Prosthetic teeth replaced"
                    value={prostheticForm.teeth_replaced}
                    onChange={(e) => setProstheticForm({ ...prostheticForm, teeth_replaced: e.target.value })}
                    placeholder="Номера зубов"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Материал</label>
                    <select
                    value={prostheticForm.material}
                    onChange={(e) => setProstheticForm({ ...prostheticForm, material: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">

                      <option value="">Выберите материал</option>
                      <option value="porcelain">Фарфор</option>
                      <option value="metal">Металл</option>
                      <option value="ceramic">Керамика</option>
                      <option value="composite">Композит</option>
                      <option value="zirconia">Диоксид циркония</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Оттенок</label>
                    <input
                    type="text"
                    aria-label="Prosthetic shade"
                    value={prostheticForm.shade}
                    onChange={(e) => setProstheticForm({ ...prostheticForm, shade: e.target.value })}
                    placeholder="A1, B2, C3 и т.д."
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Стоимость</label>
                    <input
                    type="number"
                    aria-label="Prosthetic cost"
                    value={prostheticForm.cost}
                    onChange={(e) => setProstheticForm({ ...prostheticForm, cost: e.target.value })}
                    placeholder="Сумма"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Качество посадки</label>
                    <select
                    value={prostheticForm.fit_quality}
                    onChange={(e) => setProstheticForm({ ...prostheticForm, fit_quality: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">

                      <option value="">Выберите</option>
                      <option value="excellent">Отличная</option>
                      <option value="good">Хорошая</option>
                      <option value="fair">Удовлетворительная</option>
                      <option value="poor">Плохая</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Удовлетворенность пациента</label>
                    <select
                    value={prostheticForm.patient_satisfaction}
                    onChange={(e) => setProstheticForm({ ...prostheticForm, patient_satisfaction: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">

                      <option value="">Выберите</option>
                      <option value="very_satisfied">Очень доволен</option>
                      <option value="satisfied">Доволен</option>
                      <option value="neutral">Нейтрально</option>
                      <option value="dissatisfied">Не доволен</option>
                      <option value="very_dissatisfied">Очень не доволен</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Гарантийный период</label>
                  <input
                  type="text"
                  aria-label="Prosthetic warranty period"
                  value={prostheticForm.warranty_period}
                  onChange={(e) => setProstheticForm({ ...prostheticForm, warranty_period: e.target.value })}
                  placeholder="Например: 2 года"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

                </div>

                <div className="flex gap-2">
                  <Button type="submit" className="flex items-center gap-2">
                    <Save className="h-4 w-4" />
                    Сохранить протез
                  </Button>
                  <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowProstheticForm(false)}>

                    Отмена
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      }

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

      {/* AI Chat Widget */}
      <AIChatWidget
        contextType="general"
        specialty="dentistry"
        useWebSocket={false}
        position="bottom-right" />

      <RoleNotificationCenter userRole="dentist" />
    </div>);

};

export default DentistPanelUnified;
