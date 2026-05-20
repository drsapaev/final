import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
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
import { MacOSButton, MacOSCard, MacOSBadge, MacOSInput, MacOSTextarea, MacOSSelect, MacOSEmptyState } from '../components/ui/macos';
import { useTheme } from '../contexts/ThemeContext';
import DoctorServiceSelector from '../components/doctor/DoctorServiceSelector';
import AIAssistant from '../components/ai/AIAssistant';
import ServiceChecklist from '../components/ServiceChecklist';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import EditPatientModal from '../components/common/EditPatientModal';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
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
const dermatologyAppointmentsSummaryStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  gap: 'var(--mac-spacing-2)',
  flexWrap: 'wrap',
  minWidth: 0
};
const dermatologyRefreshButtonStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--mac-spacing-2)',
  flexShrink: 0
};
const dermatologyRequestCache = {
  appointments: { promise: null, data: null, lastAttemptAt: 0 },
  services: { promise: null, data: null, lastAttemptAt: 0 },
  skinExaminations: { promise: null, data: null, lastAttemptAt: 0 },
  cosmeticProcedures: { promise: null, data: null, lastAttemptAt: 0 }
};

function countAppointmentsByStatuses(appointments, statuses) {
  return appointments.filter((appointment) => statuses.includes(appointment.status)).length;
}

function getRecentDermatologyCache(cacheEntry, fallbackValue) {
  if (cacheEntry.lastAttemptAt && Date.now() - cacheEntry.lastAttemptAt < DERMATOLOGY_REQUEST_COOLDOWN_MS) {
    return cacheEntry.data ?? fallbackValue;
  }
  return null;
}

function normalizeNumericId(value) {
  const parsed = parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

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
    appointment_id: appointment.appointment_id || appointment.id || null,
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
  const navigate = useNavigate();

  // Синхронизация активной вкладки с URL
  const getActiveTabFromURL = useCallback(() => {
    const params = new URLSearchParams(location.search);
    const visitIdParam = params.get('visitId') || params.get('visit_id');

    // Deep-link по visitId должен сразу открывать прием.
    if (visitIdParam) {
      return params.get('tab') || 'visit';
    }
    // Deep-link по patientId требует выбора канонического визита из очереди
    if (params.get('patientId')) {
      return 'appointments';
    }
    return params.get('tab') || 'appointments';
  }, [location.search]);

  // Получаем patientId из URL для автоматической загрузки пациента
  const getPatientIdFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search);
    return params.get('patientId') ? parseInt(params.get('patientId'), 10) : null;
  }, [location.search]);

  const getVisitIdFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search);
    const visitIdParam = params.get('visitId') || params.get('visit_id');
    if (!visitIdParam) {
      return null;
    }

    const parsed = parseInt(visitIdParam, 10);
    return Number.isFinite(parsed) ? parsed : null;
  }, [location.search]);

  const [activeTab, setActiveTab] = useState(() => getActiveTabFromURL());
  const [selectedPatient, setSelectedPatient] = useState(null);

  // Синхронизация URL с активной вкладкой
  useEffect(() => {
    const urlTab = getActiveTabFromURL();
    if (urlTab !== activeTab) {
      setActiveTab(urlTab);
    }
  }, [activeTab, getActiveTabFromURL]);

  // Функция для изменения активной вкладки с обновлением URL
  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    const params = new URLSearchParams(location.search);
    params.set('tab', tabId);
    navigate({ pathname: location.pathname, search: params.toString() }, { replace: true });
  };
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
  const [doctorPrice, setDoctorPrice] = useState('');

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

        let allAppointments = [];
        if (queuesResponse.ok) {
          const queuesData = await queuesResponse.json();

          // Собираем записи из очередей
          if (queuesData && queuesData.queues && Array.isArray(queuesData.queues)) {
            queuesData.queues.forEach((queue) => {
              if (queue.entries) {
                queue.entries.forEach((entry) => {
                  allAppointments.push({
                    id: entry.id,
                    appointment_id: entry.appointment_id || entry.id,
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
                    payment_status: entry.payment_status || 'pending',
                    doctor: entry.doctor_name || 'Врач',
                    specialty: queue.specialty,
                    created_at: entry.created_at,
                    appointment_date: entry.created_at ? entry.created_at.split('T')[0] : today,
                    appointment_time: entry.visit_time || '09:00',
                    status: entry.status || 'waiting',
                    cost: entry.cost || 0,
                    visit_id: entry.visit_id || null
                  });
                });
              }
            });
          }
        }

        // 2. Получаем актуальный payment_status из БД через all-appointments
        try {
          const appointmentsResponse = await fetch(`${API_V1_BASE}/registrar/all-appointments?date_from=${today}&date_to=${today}&limit=500`, {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          });

          if (appointmentsResponse.ok) {
            const appointmentsDBResponse = await appointmentsResponse.json();
            const appointmentsDBData = appointmentsDBResponse.data || appointmentsDBResponse || []; // ✅ ИСПРАВЛЕНО: Извлекаем data из ответа
            logger.info('[Dermatology] Получены appointments из БД:', appointmentsDBData.length);

            // Создаем карту id -> payment_status
            const appointmentMetaMap = new Map();
            appointmentsDBData.forEach((apt) => {
              const appointmentMeta = {
                payment_status: apt.payment_status || 'pending',
                payment_type: apt.payment_type || null,
                visit_id: apt.visit_id || null,
                appointment_id: apt.appointment_id || (apt.source === 'appointments' ? apt.id : null)
              };
              if (apt.id) {
                appointmentMetaMap.set(apt.id, appointmentMeta);
              }
              if (apt.patient_id && apt.appointment_date) {
                const key = `${apt.patient_id}_${apt.appointment_date}`;
                appointmentMetaMap.set(key, appointmentMeta);
              }
            });

            // Обновляем payment_status в наших записях
            allAppointments = allAppointments.map((apt) => {
              let appointmentMeta = appointmentMetaMap.get(apt.appointment_id || apt.id);
              if (!appointmentMeta && apt.patient_id && apt.appointment_date) {
                const key = `${apt.patient_id}_${apt.appointment_date}`;
                appointmentMeta = appointmentMetaMap.get(key);
              }
              return {
                ...apt,
                appointment_id: appointmentMeta?.appointment_id || apt.appointment_id,
                visit_id: appointmentMeta?.visit_id || apt.visit_id || null,
                payment_status: appointmentMeta?.payment_status || apt.payment_status || 'pending',
                payment_type: appointmentMeta?.payment_type || apt.payment_type || null
              };
            });

            logger.info('[Dermatology] Обновлены payment_status для', allAppointments.length, 'записей');
          }
        } catch (err) {
          logger.warn('[Dermatology] Не удалось загрузить payment_status из БД:', err);
        }

        // Фильтруем только дерматологические записи
        const appointmentsData = allAppointments.filter((apt) =>
        apt.specialty === 'derma' || apt.specialty === 'dermatology'
        );

        // Добавляем информацию о всех услугах пациента
        const enrichedAppointmentsData = appointmentsData.map((apt) => {
          const allPatientServices = getAllPatientServices(apt.patient_id, allAppointments);
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
  }, [getAllPatientServices]);

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

  const ensureCanonicalVisitId = useCallback(async (row) => {
    const appointmentId = row?.appointment_id || row?.id;
    const visitId = row?.visit_id || await resolveCanonicalVisitId(appointmentId);

    if (visitId) {
      setAppointments((prev) => prev.map((appointment) =>
        appointment.id === row.id ? { ...appointment, visit_id: visitId } : appointment
      ));
    }

    return visitId;
  }, []);

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
        id: row.appointment_id || row.id,
        appointment_id: row.appointment_id || row.id,
        visit_id: normalizeNumericId(visitId),
        patient_id: row.patient_id,
        patient_name: row.patient_fio,
        phone: row.patient_phone,
        number: row.id,
        source: 'appointments',
        status: row.status || 'waiting',
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
          const token = tokenManager.getAccessToken();
          const response = await fetch(`${API_V1_BASE}/registrar/queue/${row.id}/start-visit`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            }
          });

          if (response.ok) {
            logger.info('[Dermatology] Пациент вызван:', row.patient_fio);
            setAppointments((prev) => prev.map((a) =>
            a.id === row.id ? { ...a, status: 'called' } : a
            ));
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
            id: row.appointment_id || row.id,
            appointment_id: row.appointment_id || row.id,
            visit_id: normalizeNumericId(visitId),
            patient_id: row.patient_id,
            patient_name: row.patient_fio,
            phone: row.patient_phone,
            number: row.id,
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
      const patientIdFromUrl = getPatientIdFromUrl();
      const visitIdFromUrl = getVisitIdFromUrl();
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
  }, [location.search, getPatientIdFromUrl, getVisitIdFromUrl, selectedPatient?.patient_id, selectedPatient?.visit_id, currentAppointment?.visit_id, appointments, loadDermatologyAppointments]);

  useEffect(() => {
    const appointmentId =
      currentAppointment?.appointment_id ||
      (currentAppointment?.source !== 'url' ? currentAppointment?.id : null);
    if (!appointmentId) {
      setEmr(null);
      setPrescription(null);
      return;
    }

    let isMounted = true;

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

        const normalizedStatusVisitId = normalizeNumericId(statusData.visit_id);
        const normalizedCurrentVisitId = normalizeNumericId(currentAppointment?.visit_id);
        if (normalizedStatusVisitId && normalizedStatusVisitId !== normalizedCurrentVisitId) {
          setCurrentAppointment((prev) => prev ? { ...prev, visit_id: normalizedStatusVisitId } : prev);
        }

        const normalizedAppointmentStatus = statusData.appointment?.status || statusData.status || null;
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
      const appointmentId = currentAppointment?.appointment_id || currentAppointment?.id;
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
    const entryId = selectedPatient?.id || currentAppointment?.id;
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
        logger.info('[Dermatology] callNextWaiting(derma): start');
        const next = await queueService.callNextWaiting('derma');
        logger.info('[Dermatology] callNextWaiting(derma): result', next);
        if (next?.success) {
            notify.success(`Вызван следующий пациент №${next.entry.number}`);
        }
      } catch (err) {
        logger.warn('[Dermatology] callNextWaiting(derma): failed', err);
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

  const pageStyle = {
    padding: '20px',
    maxWidth: '1400px',
    margin: '0 auto',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    background: 'var(--mac-bg-primary)',
    minHeight: '100vh',
    color: 'var(--mac-text-primary)'
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
    <div style={{
      ...pageStyle,
      padding: '0',
      boxSizing: 'border-box',
      overflow: 'hidden',
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

      <div style={{ padding: '0px' }}> {/* Убираем padding, так как он уже есть в main контейнере */}


        {/* Контент вкладок */}
        <div>
          {/* Записи дерматолога */}
          {activeTab === 'appointments' &&
          <div style={{
            width: '100%',
            maxWidth: 'none',
            display: 'flex',
            flexDirection: 'column',
            gap: '24px'
          }}>
              <MacOSCard style={{
              padding: '24px',
              width: '100%',
              maxWidth: '100%',
              minWidth: 0,
              boxSizing: 'border-box',
              overflow: 'hidden'
            }}>
                <div style={dermatologyAppointmentsHeaderStyle}>
                  <h3 style={dermatologyAppointmentsTitleStyle}>
                    <Calendar size={20} style={{ marginRight: '8px', color: 'var(--mac-green-500)' }} />
                    Записи к дерматологу
                  </h3>
                  <div style={dermatologyAppointmentsSummaryStyle} role="list" aria-label="Сводка записей дерматолога">
                    {appointmentSummaryItems.map((item) => (
                      <MacOSBadge
                      key={item.key}
                      role="listitem"
                      variant={item.variant}
                      aria-label={`${item.label}: ${item.value}`}>
                        {item.label}: {item.value}
                      </MacOSBadge>
                    ))}
                    <MacOSButton
                    variant="outline"
                    onClick={loadDermatologyAppointments}
                    disabled={appointmentsLoading}
                    style={dermatologyRefreshButtonStyle}>

                      <RefreshCw size={16} />
                      Обновить
                    </MacOSButton>
                  </div>
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <MacOSCard style={{ padding: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <h3 style={{
                  fontSize: '18px',
                  fontWeight: '600',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                  display: 'flex',
                  alignItems: 'center',
                  marginBottom: '20px'
                }}>
                    <User size={20} style={{ marginRight: '8px', color: 'var(--mac-green-500)' }} />
                    Дерматологические пациенты
                  </h3>
                  <MacOSBadge variant="info">Всего: {patients.length} пациентов</MacOSBadge>
                </div>

                {loading ?
              <div style={{ textAlign: 'center', padding: '32px' }}>
                    <RefreshCw size={32} style={{ margin: '0 auto 16px', color: 'var(--mac-text-secondary)', animation: 'spin 1s linear infinite' }} />
                    <p style={{ color: 'var(--mac-text-secondary)', fontSize: '14px' }}>Загрузка пациентов...</p>
                  </div> :

              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                    {patients.map((patient) =>
                <div key={patient.id} style={{
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-lg)',
                  padding: '24px',
                  backgroundColor: 'var(--mac-bg-primary)',
                  transition: 'box-shadow var(--mac-duration-normal) var(--mac-ease)'
                }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
                              <h4 style={{
                          fontSize: '16px',
                          fontWeight: '600',
                          color: 'var(--mac-text-primary)',
                          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
                          margin: 0
                        }}>
                                {patient.last_name} {patient.first_name} {patient.middle_name}
                              </h4>
                              <MacOSBadge variant="success" style={{ marginLeft: '12px' }}>Дерматология</MacOSBadge>
                            </div>
                            <div style={{
                        fontSize: '13px',
                        color: 'var(--mac-text-secondary)',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '12px'
                      }}>
                              <div style={{ display: 'flex', alignItems: 'center' }}>
                                <Phone size={18} style={{ marginRight: '8px', color: 'var(--mac-accent)' }} />
                                {patient.phone}
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center' }}>
                                <Calendar size={14} style={{ marginRight: '8px' }} />
                                {patient.birth_date}
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center' }}>
                                <User size={14} style={{ marginRight: '8px' }} />
                                ID: {patient.id}
                              </div>
                            </div>
                          </div>
                          <div style={{ display: 'flex', gap: '16px' }}>
                            <MacOSButton
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
                        style={{ fontSize: '13px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}>

                              <Activity size={16} />
                              Осмотр
                            </MacOSButton>
                            <MacOSButton
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
                        style={{ fontSize: '13px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}>

                              <Sparkles size={16} />
                              Процедура
                            </MacOSButton>
                            <MacOSButton
                        variant="outline"
                        onClick={() => setSelectedPatient(patient)}
                        style={{ fontSize: '13px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}>

                              <User size={16} />
                              Просмотр
                            </MacOSButton>
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
          {activeTab === 'visit' && currentAppointment &&
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <MacOSCard style={{ padding: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <h3 style={{
                  fontSize: '18px',
                  fontWeight: '600',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                  display: 'flex',
                  alignItems: 'center',
                  margin: 0
                }}>
                    <Stethoscope size={20} style={{ marginRight: '8px', color: 'var(--mac-orange-500)' }} />
                    Прием пациента: {currentAppointment.patient_name || 'Не указано'}
                  </h3>
                  <MacOSBadge variant="info">
                    Статус: {currentAppointment.status}
                  </MacOSBadge>
                </div>

                {/* Временная шкала приема */}
                <VisitTimeline
                appointment={currentAppointment}
                emr={emr}
                prescription={prescription} />


                {/* EMR система */}
                <div style={{ marginTop: '24px' }}>
                  <h4 style={{
                  fontSize: '16px',
                  fontWeight: '600',
                  marginBottom: '16px',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                  display: 'flex',
                  alignItems: 'center'
                }}>
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
                    <h4 style={{
                  fontSize: '16px',
                  fontWeight: '600',
                  marginBottom: '16px',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                  display: 'flex',
                  alignItems: 'center'
                }}>
                      <TestTube size={20} style={{ marginRight: '8px', color: 'var(--mac-green-500)' }} />
                      Рецепт
                    </h4>
                    <PrescriptionSystem
                  appointment={currentAppointment}
                  emr={emr}
                  prescription={prescription}
                  onSave={savePrescription}
                  onPrint={printPrescription} />

                  </div>
              }

                {/* Кнопка завершения приема */}
                {emr && !emr.is_draft &&
              <div style={{ marginTop: '24px', textAlign: 'center' }}>
                    <MacOSButton
                  onClick={handleSaveVisit}
                  disabled={loading}
                  style={{
                    backgroundColor: 'var(--mac-green-500)',
                    color: 'white',
                    fontSize: '16px',
                    padding: '12px 32px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    margin: '0 auto'
                  }}>

                      {loading ?
                  <RefreshCw size={20} className="animate-spin" /> :

                  <CheckCircle size={20} />
                  }
                      {loading ? 'Завершение...' : 'Завершить прием'}
                    </MacOSButton>
                  </div>
              }
              </MacOSCard>
            </div>
          }

          {/* Прием пациента - простая версия */}
          {activeTab === 'visit' && selectedPatient && !currentAppointment &&
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* Информация о пациенте */}
              <MacOSCard style={{ padding: '24px' }}>
                <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '20px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                display: 'flex',
                alignItems: 'center'
              }}>
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
                      <div style={{ display: 'flex', alignItems: 'center' }}>
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
              <MacOSCard style={{ padding: '24px' }}>
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
                    <MacOSTextarea
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
                      <MacOSInput
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
                      <MacOSInput
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
                    <MacOSTextarea
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
            <MacOSCard style={{ padding: '24px' }}>
                  <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '20px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                display: 'flex',
                alignItems: 'center'
              }}>
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
            <MacOSCard style={{ padding: '24px' }}>
                  <h3 className="text-lg font-medium mb-4 flex items-center">
                    <TestTube size={20} className="mr-2 text-green-600" />
                    Рецепт
                  </h3>
                  <PrescriptionSystem
                appointment={currentAppointment}
                emr={emr}
                prescription={prescription}
                onSave={savePrescription} />

                </MacOSCard>
            }

              {/* Действия */}
              <MacOSCard style={{ padding: '24px' }}>
                <div className="flex justify-end space-x-3">
                  <MacOSButton
                  variant="outline"
                  onClick={() => {
                    setSelectedPatient(null);
                    handleTabChange('queue');
                  }}>

                    Отменить
                  </MacOSButton>
                  <MacOSButton
                  onClick={handleSaveVisit}
                  disabled={loading || !visitData.complaint && !emr}>

                    {loading ?
                  <RefreshCw size={16} className="animate-spin mr-2" /> :

                  <Save size={16} className="mr-2" />
                  }
                    {loading ? 'Завершение...' : 'Завершить прием'}
                  </MacOSButton>
                </div>
              </MacOSCard>
            </div>
          }

          {/* Фото до/после */}
          {activeTab === 'photos' && (currentAppointment || selectedPatient) &&
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <MacOSCard style={{ padding: '24px' }}>
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

              <MacOSCard style={{ padding: '24px' }}>
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

              <MacOSCard style={{ padding: '24px' }}>
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
              <MacOSButton variant="outline" onClick={() => handleTabChange('queue')} style={{ marginTop: '16px' }}>
                    Перейти к очереди
                  </MacOSButton>
              } />

            </MacOSCard>
          }

          {/* Осмотр кожи */}
          {activeTab === 'skin' &&
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <MacOSCard style={{ padding: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{
                  fontSize: '18px',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
                }}>
                    <Activity size={20} style={{ marginRight: '8px', color: 'var(--mac-green-500)' }} />
                    Осмотры кожи
                  </h3>
                  <MacOSButton onClick={openSkinExaminationForm}>
                    <Plus size={16} style={{ marginRight: '6px' }} />
                    Новый осмотр
                  </MacOSButton>
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
                          <MacOSBadge variant="info">{exam.examination_date}</MacOSBadge>
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
            <MacOSCard style={{ padding: '24px' }}>
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
                        <MacOSInput
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
                        <MacOSSelect
                      value={skinExamination.skin_type}
                      onChange={(e) => setSkinExamination({ ...skinExamination, skin_type: e.target.value })}
                      required>

                          <option value="">Выберите тип кожи</option>
                          <option value="normal">Нормальная</option>
                          <option value="dry">Сухая</option>
                          <option value="oily">Жирная</option>
                          <option value="combination">Комбинированная</option>
                          <option value="sensitive">Чувствительная</option>
                        </MacOSSelect>
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
                        <MacOSInput
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
                        <MacOSInput
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
                      <MacOSInput
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
                      <MacOSTextarea
                    value={skinExamination.treatment_plan}
                    onChange={(e) => setSkinExamination({ ...skinExamination, treatment_plan: e.target.value })}
                    rows={4}
                    placeholder="План лечения и рекомендации" />

                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                      <MacOSButton
                    type="button"
                    variant="outline"
                    onClick={() => setShowSkinForm(false)}>

                        Отмена
                      </MacOSButton>
                      <MacOSButton type="submit">
                        <Save size={16} style={{ marginRight: '6px' }} />
                        Сохранить осмотр
                      </MacOSButton>
                    </div>
                  </form>
                </MacOSCard>
            }
            </div>
          }

          {/* Косметология */}
          {activeTab === 'cosmetic' &&
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <MacOSCard style={{ padding: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{
                  fontSize: '18px',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
                }}>
                    <Sparkles size={20} style={{ marginRight: '8px', color: 'var(--mac-pink-500)' }} />
                    Косметические процедуры
                  </h3>
                  <MacOSButton onClick={openCosmeticProcedureForm}>
                    <Plus size={16} style={{ marginRight: '6px' }} />
                    Новая процедура
                  </MacOSButton>
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
                          <MacOSBadge variant="info">{procedure.procedure_date}</MacOSBadge>
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
            <MacOSCard style={{ padding: '24px' }}>
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
                        <MacOSInput
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
                        <MacOSSelect
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
                        </MacOSSelect>
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
                        <MacOSInput
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
                        <MacOSInput
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
                      <MacOSTextarea
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
                      <MacOSTextarea
                    value={cosmeticProcedure.follow_up}
                    onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, follow_up: e.target.value })}
                    rows={3}
                    placeholder="Рекомендации по уходу после процедуры" />

                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                      <MacOSButton
                    type="button"
                    variant="outline"
                    onClick={() => setShowCosmeticForm(false)}>

                        Отмена
                      </MacOSButton>
                      <MacOSButton type="submit">
                        <Save size={16} style={{ marginRight: '6px' }} />
                        Сохранить процедуру
                      </MacOSButton>
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
              <MacOSCard style={{ padding: '24px' }}>
                <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>
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


                    <div style={{ marginTop: '16px' }}>
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
                          <MacOSInput
                          type="text"
                          value={doctorPrice}
                          onChange={(e) => setDoctorPrice(e.target.value)}
                          placeholder="Например: 50000"
                          inputMode="numeric"
                          style={{ paddingLeft: '40px' }} />

                        </div>
                        <MacOSButton
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
                        title="Изменить цену процедуры">

                          <DollarSign size={16} />
                        </MacOSButton>
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
                      <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      height: '40px',
                      padding: '0 12px',
                      border: '2px dashed var(--mac-border)',
                      borderRadius: '8px',
                      backgroundColor: 'var(--mac-bg-secondary)'
                    }}>
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
              <MacOSCard style={{ padding: '24px' }}>
                <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>
                  <Calendar size={20} style={{ marginRight: '8px', color: 'var(--mac-text-secondary)' }} />
                  История приемов и процедур
                </h3>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '24px' }}>
                  {/* История осмотров кожи */}
                  <div>
                    <h4 style={{
                    fontWeight: '600',
                    fontSize: '14px',
                    marginBottom: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    color: 'var(--mac-text-primary)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
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
                            <MacOSBadge variant="info">{exam.examination_date}</MacOSBadge>
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
                    <h4 style={{
                    fontWeight: '600',
                    fontSize: '14px',
                    marginBottom: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    color: 'var(--mac-text-primary)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
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
                            <MacOSBadge variant="info">{procedure.procedure_date}</MacOSBadge>
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
