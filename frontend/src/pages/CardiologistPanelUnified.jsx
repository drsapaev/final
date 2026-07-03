import { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
// P-009 fix: shared doctor panel state hook
import { useDoctorPanelState } from '../hooks/useDoctorPanelState';
// P-016 (UX audit): persist cardiologist settings (ldlThreshold,
// showEcgEchoTogether) in localStorage so they survive page reloads.
import { useLocalStorage } from '../hooks/useLocalStorage';
// P-021 (UX audit): warn the doctor 5 minutes before session expiry
// so they can save their work instead of losing it to a silent 401.
import { useSessionTimeoutWarning } from '../hooks/useSessionTimeoutWarning';
import {
  FileText,
  User,
  Settings,
  Save,
  RefreshCw,
  Calendar,
  Phone,
  Plus,
  TestTube } from
'lucide-react';
import {
  MacOSCard,
  Button,
  Badge,
  Skeleton,
  MacOSEmptyState,
  Textarea,
  Checkbox,
} from '../components/ui/macos';
import { useTheme } from '../contexts/ThemeContext';
import './cardiology.css';
import AppointmentSummaryBar from '../components/doctor/AppointmentSummaryBar';
import DoctorServiceSelector from '../components/doctor/DoctorServiceSelector';
import AIAssistant from '../components/ai/AIAssistant';
import BloodTestsTab from '../components/cardiology/BloodTestsTab';
import EcgTab from '../components/cardiology/EcgTab';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import EditPatientModal from '../components/common/EditPatientModal';
import { queueService } from '../services/queue';
import { printPanelTicket } from '../services/panelPrint';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import QueueIntegration from '../components/QueueIntegration';
import { getApiBaseUrl } from '../api/runtime';
import { EMRContainerV2 } from '../components/emr-v2/EMRContainerV2';
import AIChatWidget from '../components/ai/AIChatWidget';
import { resolveCanonicalVisitId } from '../utils/canonicalVisit';
import { getErrorMessage } from '../utils/errorHandler';
import logger from '../utils/logger';
import notify from '../services/notify';
// QW-10 (UX audit): shared ConfirmDialog hook used before completing a visit.
import { useConfirm } from '../components/common/ConfirmDialog';
import RoleNotificationCenter from '../components/notifications/RoleNotificationCenter';
import tokenManager from '../utils/tokenManager';

const API_V1_BASE = getApiBaseUrl();
const CARDIOLOGY_WAITING_STATUSES = ['waiting', 'confirmed', 'pending'];
const CARDIOLOGY_CALLED_STATUSES = ['called', 'in_progress'];
const CARDIOLOGY_COMPLETED_STATUSES = ['completed', 'done'];
function countAppointmentsByStatuses(appointments, statuses) {
  return appointments.filter((appointment) => statuses.includes(appointment.status)).length;
}

function resolveDoctorQueueEntryId(row) {
  const explicitQueueEntryId = row?.doctor_queue_entry_id ?? row?.queue_entry_id ?? null;
  if (explicitQueueEntryId !== null && explicitQueueEntryId !== undefined) {
    return explicitQueueEntryId;
  }

  return null;
}

/**
 * Унифицированная панель кардиолога
 * Объединяет: очередь + специализированные функции + AI + ЭКГ/ЭхоКГ
 */
const MacOSCardiologistPanelUnified = () => {
  // Всегда вызываем хуки первыми
  const { isDark, getColor, getSpacing, getFontSize, getShadow } = useTheme();
  const location = useLocation();
  // P-009: navigate removed — useDoctorPanelState handles tab URL sync

  // P-009 fix: use shared useDoctorPanelState hook for tab/URL/patient state.
  const {
    activeTab,
    setActiveTab,
    handleTabChange: goToTab,
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
  // QW-01 (UX audit): removed swallowed setMessage — all calls now route through `notify`
  // (the shared adapter in services/notify.js) so users actually see error/success/warning
  // feedback. The `message` destructure was dropped, which silently discarded every
  // notification before this fix.
  // QW-10 (UX audit): confirm hook used before completing a visit (prevents
  // accidental completion with empty diagnosis/treatment).
  const [confirm, confirmDialog] = useConfirm();
  const [scheduleNextModal, setScheduleNextModal] = useState({ open: false, patient: null });
  const [editPatientModal, setEditPatientModal] = useState({ open: false, patient: null, loading: false });
  const [settingsOpen, setSettingsOpen] = useState(false);
  // P-016 (UX audit): settings now persist in localStorage. The doctor's
  // LDL threshold and ECG/Echo layout preference survive page reloads.
  const [settings, setSettings] = useLocalStorage('cardio.settings', {
    ldlThreshold: 100,
    showEcgEchoTogether: true,
  });
  const [emr, setEmr] = useState(null);

  // Ref для отслеживания предыдущего пациента для очистки EMR
  const prevSelectedPatientRef = useRef(null);

  // Состояния для таблицы записей
  const [appointments, setAppointments] = useState([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [services, setServices] = useState({}); // ✅ Добавлено: состояние для услуг

  // P-021 (UX audit): session timeout warning state. When the JWT is
  // about to expire, we show a dialog so the doctor can save their work.
  const [sessionWarning, setSessionWarning] = useState(null); // { expiresAt } | null

  useSessionTimeoutWarning({
    onWarning: (expiresAt) => setSessionWarning({ expiresAt }),
    onExpired: () => {
      setSessionWarning(null);
      notify.error('Сессия истекла. Пожалуйста, войдите снова.');
      // Force a reload so the auth guard redirects to /login.
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    },
  });

  // Специализированные данные кардиолога
  const [bloodTestForm, setBloodTestForm] = useState({
    patient_id: '',
    test_date: '',
    cholesterol_total: '',
    cholesterol_hdl: '',
    cholesterol_ldl: '',
    triglycerides: '',
    glucose: '',
    crp: '',
    troponin: '',
    interpretation: ''
  });

  const [showForm, setShowForm] = useState({ open: false, type: 'blood' });
  const [ecgResults, setEcgResults] = useState([]);
  const [bloodTests, setBloodTests] = useState([]);
  const [patientFiles, setPatientFiles] = useState([]);
  const [historyFilter, setHistoryFilter] = useState('all');
  const [authRefreshTick, setAuthRefreshTick] = useState(0);
  const filesAccessDeniedRef = useRef(false);

  const getSelectedPatientContext = useCallback(() => {
    const patientId = selectedPatient?.patient?.id || selectedPatient?.patient_id || null;
    const visitId = selectedPatient?.visit_id || null;
    return { patientId, visitId };
  }, [selectedPatient]);

  const getEmptyBloodTestForm = useCallback((overrides = {}) => ({
    patient_id: '',
    test_date: '',
    cholesterol_total: '',
    cholesterol_hdl: '',
    cholesterol_ldl: '',
    triglycerides: '',
    glucose: '',
    crp: '',
    troponin: '',
    interpretation: '',
    ...overrides
  }), []);

  const normalizeOptionalNumber = (value) => {
    if (value === '' || value === null || value === undefined) {
      return null;
    }

    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  // R-17 / P-011 (UX audit): surface critical LDL values to the cardiologist.
  // The `settings.ldlThreshold` (default 100 мг/дл) was previously declared
  // in the floating settings popover but never actually used anywhere in
  // the code. ESC guidelines flag LDL ≥ 190 мг/дл as very-high-risk, but the
  // doctor may want a different threshold depending on patient context —
  // that's why the threshold is configurable. We use it to paint the LDL
  // value red wherever it appears: in the entry form, in the average-LDL
  // stat card, and in the blood-test history list.
  const isLdlCritical = useCallback((rawValue) => {
    const parsed = typeof rawValue === 'number' ? rawValue : Number(rawValue);
    if (!Number.isFinite(parsed)) {
      return false;
    }
    const threshold = Number(settings?.ldlThreshold);
    return Number.isFinite(threshold) && threshold > 0 && parsed > threshold;
  }, [settings?.ldlThreshold]);

  // P-023 (UX audit): range validation for blood-test fields. Returns
  // { valid, message } so the form can paint the field red and show an
  // inline hint when the entered value is physiologically impossible
  // (e.g. negative cholesterol, heart rate > 250). Ranges are based on
  // standard clinical reference intervals in mg/dL (matching R-12 unification).
  // LDL uses the configurable settings.ldlThreshold as its upper "critical"
  // marker; the hard physiological ceiling is 1000 mg/dL.
  const FIELD_RANGES = useRef({
    cholesterol_total: { min: 50, max: 1000, unit: 'мг/дл', label: 'Общий холестерин' },
    cholesterol_hdl: { min: 5, max: 200, unit: 'мг/дл', label: 'HDL' },
    cholesterol_ldl: { min: 5, max: 1000, unit: 'мг/дл', label: 'LDL' },
    triglycerides: { min: 10, max: 2000, unit: 'мг/дл', label: 'Триглицериды' },
    glucose: { min: 20, max: 1000, unit: 'мг/дл', label: 'Глюкоза' },
    crp: { min: 0, max: 500, unit: 'мг/л', label: 'CRP' },
    troponin: { min: 0, max: 100, unit: 'нг/мл', label: 'Тропонин' },
  }).current;

  const getFieldRangeWarning = useCallback(
    (fieldName, rawValue) => {
      const range = FIELD_RANGES[fieldName];
      if (!range) return null;
      const parsed = Number(rawValue);
      if (!Number.isFinite(parsed) || rawValue === '' || rawValue === null || rawValue === undefined) {
        return null;
      }
      if (parsed < range.min) {
        return {
          valid: false,
          message: `${range.label} ${parsed} ${range.unit} ниже физиологического минимума (${range.min}). Проверьте значение.`,
        };
      }
      if (parsed > range.max) {
        return {
          valid: false,
          message: `${range.label} ${parsed} ${range.unit} превышает физиологический максимум (${range.max}). Проверьте значение.`,
        };
      }
      return { valid: true, message: null };
    },
    [FIELD_RANGES]
  );

  // P-020 (UX audit): critical ICD-10 codes that require secondary
  // confirmation before the visit can be completed. These are diagnoses
  // with high clinical stakes — an erroneous entry could trigger
  // unnecessary thrombolysis, coronary angiography, or aggressive
  // therapy. The doctor must explicitly confirm when one of these codes
  // is present.
  const CRITICAL_ICD10_CODES = useRef({
    'I21': 'Острый инфаркт миокарда',
    'I22': 'Повторный инфаркт миокарда',
    'I46': 'Остановка сердца',
    'I50': 'Сердечная недостаточность',
    'I71': 'Аневризма и расслоение аорты',
    'R57': 'Шок (включая кардиогенный)',
  }).current;

  const getCriticalDiagnosisWarning = useCallback(
    (icd10Code) => {
      if (!icd10Code || typeof icd10Code !== 'string') return null;
      const code = icd10Code.trim().toUpperCase();
      // Match by prefix (e.g. "I21" matches "I21.0", "I21.9", "I219")
      for (const [prefix, label] of Object.entries(CRITICAL_ICD10_CODES)) {
        if (code.startsWith(prefix)) {
          return { code: prefix, label, fullCode: code };
        }
      }
      return null;
    },
    [CRITICAL_ICD10_CODES]
  );

  const openBloodTestForm = () => {
    const { patientId } = getSelectedPatientContext();
    if (!patientId) {
      notify.error('Сначала выберите пациента или визит кардиолога');
      return;
    }

    setBloodTestForm(getEmptyBloodTestForm({
      patient_id: String(patientId),
      test_date: new Date().toISOString().split('T')[0]
    }));
    setShowForm({ open: true, type: 'blood' });
  };

  // ✅ Функция загрузки данных пациента (объявлена до использования)
  const loadPatientData = useCallback(async () => {
    const { patientId, visitId } = getSelectedPatientContext();
    if (!patientId) return;

    try {
      const token = tokenManager.getAccessToken();

      // Загружаем ЭКГ пациента
      const ecgResponse = await fetch(`${API_V1_BASE}/cardio/ecg?patient_id=${patientId}&limit=10`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (ecgResponse.ok) {
        const ecgData = await ecgResponse.json();
        setEcgResults(ecgData);
      }

      // Загружаем анализы крови пациента
      const bloodResponse = await fetch(`${API_V1_BASE}/cardio/blood-tests?patient_id=${patientId}&limit=10`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (bloodResponse.ok) {
        const bloodData = await bloodResponse.json();
        setBloodTests(bloodData);
      }

      const fileEndpoints = [
        `${API_V1_BASE}/files?patient_id=${patientId}&page=1&size=50`,
      ];

      if (visitId) {
        fileEndpoints.push(`${API_V1_BASE}/files?visit_id=${visitId}&page=1&size=50`);
      }

      if (filesAccessDeniedRef.current) {
        setPatientFiles([]);
        return;
      }

      const mergedFiles = new Map();
      for (const endpoint of fileEndpoints) {
        const fileResponse = await fetch(endpoint, {
          headers: { 'Authorization': `Bearer ${token}` },
        });

        if (!fileResponse.ok) {
          if (fileResponse.status === 403) {
            filesAccessDeniedRef.current = true;
            logger.info('[FIX:FILES] Skipping file fetches after permission denied', {
              patientId,
              visitId,
              endpoint
            });
            break;
          }
          continue;
        }

        const fileData = await fileResponse.json();
        const files = Array.isArray(fileData?.files) ? fileData.files : [];
        files.forEach((file) => {
          if (file?.id != null) {
            mergedFiles.set(file.id, file);
          }
        });
      }

      setPatientFiles(Array.from(mergedFiles.values()));
    } catch (error) {
      notify.error(getErrorMessage(error, 'Не удалось обновить данные пациента. Проверьте соединение и попробуйте снова.'));
    }
  }, [getSelectedPatientContext]);

  // ✅ Очистка EMR и visitData при смене пациента
  useEffect(() => {
    if (selectedPatient) {
      const currentPatientId = selectedPatient.patient_id || selectedPatient.id || selectedPatient.appointment_id;
      const previousPatientId = prevSelectedPatientRef.current;

      // Если это новый пациент (не просто обновление того же)
      if (previousPatientId !== null && previousPatientId !== currentPatientId) {
        // Очищаем EMR и visitData при смене пациента
        setEmr(null);
        setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
      }

      // Сохраняем ID текущего пациента
      prevSelectedPatientRef.current = currentPatientId;

      // Загружаем данные пациента
      loadPatientData();
    } else {
      // Если пациента нет, очищаем всё
      prevSelectedPatientRef.current = null;
      setEmr(null);
      setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
      setEcgResults([]);
      setBloodTests([]);
      setPatientFiles([]);
      setHistoryFilter('all');
    }
  }, [selectedPatient, loadPatientData, authRefreshTick]);

  // Отслеживаем изменения URL для синхронизации активной вкладки
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const tabParam = params.get('tab');
    if (tabParam && tabParam !== activeTab) {
      setActiveTab(tabParam);
    }
  }, [location.search, activeTab]);

  useEffect(() => {
    const handleAuthLikeRefresh = () => {
      setAuthRefreshTick((prev) => prev + 1);
    };

    window.addEventListener('authStateChanged', handleAuthLikeRefresh);
    window.addEventListener('storage', handleAuthLikeRefresh);

    return () => {
      window.removeEventListener('authStateChanged', handleAuthLikeRefresh);
      window.removeEventListener('storage', handleAuthLikeRefresh);
    };
  }, []);

  // ✅ Загрузка услуг при монтировании
  useEffect(() => {
    const loadServices = async () => {
      try {
        const token = tokenManager.getAccessToken();
        if (!token) return;

        const response = await fetch(`${API_V1_BASE}/registrar/services`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
          const data = await response.json();
          const servicesData = data.services_by_group || {};
          setServices(servicesData);
        }
      } catch (error) {
      notify.error(getErrorMessage(error, 'Не удалось загрузить список услуг. Проверьте соединение и попробуйте снова.'));
      }
    };

    loadServices();
  }, []);

  const hydratePatientFromUrl = useCallback(async () => {
    // P-009: patientIdFromUrl / visitIdFromUrl come from useDoctorPanelState
    if (!patientIdFromUrl) return;

    const selectedPatientId = selectedPatient?.patient?.id || selectedPatient?.patient_id || null;
    const selectedVisitId = selectedPatient?.visit_id || null;
    if (
      selectedPatientId === patientIdFromUrl &&
      (!visitIdFromUrl || selectedVisitId === visitIdFromUrl)
    ) {
      return;
    }

    try {
      const token = tokenManager.getAccessToken();
      if (!token) return;

      const patientResponse = await fetch(`${API_V1_BASE}/patients/${patientIdFromUrl}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!patientResponse.ok) {
        return;
      }

      const patientData = await patientResponse.json();
      const patientName = `${patientData.last_name || ''} ${patientData.first_name || ''} ${patientData.middle_name || ''}`.trim();

      setSelectedPatient((prev) => ({
        ...prev,
        id: prev?.id || patientData.id,
        patient_id: patientData.id,
        patient_name: patientName,
        patient_fio: patientName,
        phone: patientData.phone || prev?.phone || '',
        visit_id: visitIdFromUrl || prev?.visit_id || null,
        source: prev?.source || 'search',
        specialty: prev?.specialty || 'cardiology'
      }));
      setActiveTab('appointments');
      notify.info(`Загружен пациент: ${patientName}. Выберите визит с каноническим visit_id.`);
    } catch (error) {
      notify.error(getErrorMessage(error, 'Не удалось загрузить пациента. Проверьте соединение и попробуйте снова.'));
    }
  }, [patientIdFromUrl, visitIdFromUrl, selectedPatient]);

  useEffect(() => {
    hydratePatientFromUrl();
  }, [hydratePatientFromUrl, authRefreshTick]);

  // P-009: patientIdFromUrl / visitIdFromUrl now come from useDoctorPanelState
  const shouldHydrateAppointmentContext = Boolean(patientIdFromUrl || visitIdFromUrl);

  // P-009: goToTab is now handleTabChange from useDoctorPanelState

  const ensureCanonicalVisitId = useCallback(async (row) => {
    const appointmentId = row?.appointment_id || null;
    const visitId = row?.visit_id || (appointmentId ? await resolveCanonicalVisitId(appointmentId) : null);

    if (visitId) {
      setAppointments((prev) => prev.map((appointment) =>
        appointment.id === row.id ? { ...appointment, visit_id: visitId } : appointment
      ));
    }

    return visitId;
  }, []);

  useEffect(() => {
    // P-009: patientIdFromUrl / visitIdFromUrl come from useDoctorPanelState
    if ((!patientIdFromUrl && !visitIdFromUrl) || appointments.length === 0) {
      return;
    }

    const matchingAppointment = appointments.find((appointment) => {
      if (visitIdFromUrl && appointment.visit_id === visitIdFromUrl) {
        return true;
      }
      return patientIdFromUrl && appointment.patient_id === patientIdFromUrl;
    });
    if (!matchingAppointment) {
      return;
    }

    setSelectedPatient((prev) => {
      const prevPatientId = prev?.patient?.id || prev?.patient_id || null;
      const prevVisitId = prev?.visit_id || null;
      if (patientIdFromUrl && prevPatientId && prevPatientId !== patientIdFromUrl) {
        return prev;
      }
      if (visitIdFromUrl && prevVisitId && prevVisitId !== visitIdFromUrl) {
        return prev;
      }

      const nextAppointmentId = matchingAppointment.appointment_id || prev?.appointment_id || null;
      const nextVisitId = matchingAppointment.visit_id || visitIdFromUrl || prev?.visit_id || null;
      const nextPatientName = matchingAppointment.patient_fio || prev?.patient_name || prev?.patient_fio || '';
      const nextPatient = {
        ...prev,
        id: nextAppointmentId || prev?.id || patientIdFromUrl,
        appointment_id: nextAppointmentId,
        visit_id: nextVisitId,
        patient_id: patientIdFromUrl,
        patient_name: nextPatientName,
        patient_fio: nextPatientName,
        phone: matchingAppointment.patient_phone || prev?.phone || '',
        number: nextAppointmentId || prev?.number || patientIdFromUrl,
        source: 'appointments',
        status: matchingAppointment.status ?? null,
        payment_status: matchingAppointment.payment_status ?? null,
        discount_mode: matchingAppointment.discount_mode || prev?.discount_mode,
        specialty: matchingAppointment.specialty || prev?.specialty || 'cardiology'
      };

      const didChange =
        prev?.appointment_id !== nextPatient.appointment_id ||
        prev?.visit_id !== nextPatient.visit_id ||
        prev?.status !== nextPatient.status ||
        prev?.payment_status !== nextPatient.payment_status ||
        prev?.source !== nextPatient.source;

      return didChange ? nextPatient : prev;
    });
  }, [appointments, patientIdFromUrl, visitIdFromUrl]);

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

  // Загрузка записей кардиолога
  const loadMacOSCardiologyAppointments = useCallback(async () => {
    setAppointmentsLoading(true);
    try {
      const token = tokenManager.getAccessToken();
      if (!token) {
        setAppointmentsLoading(false);
        return;
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
        const seenIds = new Set(); // Для отслеживания уже добавленных записей

        if (data && data.queues && Array.isArray(data.queues)) {
          data.queues.forEach((queue) => {
            if (queue.entries) {
              queue.entries.forEach((entry) => {
                const appointmentId = entry.appointment_id || null;
                const doctorQueueEntryId = resolveDoctorQueueEntryId(entry);
                const recordKey = `${entry.patient_id}_${entry.canonical_record_id || entry.id}_${queue.specialty}`;

                // Пропускаем дубликаты (один и тот же пациент с одним и тем же appointment_id в одной специальности)
                if (seenIds.has(recordKey)) {
                  return;
                }
                seenIds.add(recordKey);

                allAppointments.push({
                  id: entry.id,
                  appointment_id: appointmentId,
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

        // ✅ Фильтруем только кардиологические записи, исключая ЭКГ
        const appointmentsData = allAppointments.filter((apt) => {
          // Исключаем записи из очереди ЭКГ
          if (apt.specialty === 'echokg' || apt.specialty === 'ecg') {
            return false;
          }

          // Проверяем по specialty
          const isCardiology = apt.specialty === 'cardio' || apt.specialty === 'cardiology';

          // ✅ Проверяем по кодам услуг: исключаем записи, которые содержат только ЭКГ
          const serviceCodes = apt.service_codes || apt.services || [];
          const hasOnlyECG = serviceCodes.length > 0 && serviceCodes.every((code) => {
            const codeStr = String(code).toUpperCase();
            return codeStr.includes('ECG') || codeStr.includes('ЭКГ') || codeStr === 'ECG';
          });

          // Если запись содержит только ЭКГ, исключаем её
          if (hasOnlyECG) {
            return false;
          }

          // ✅ Проверяем, содержит ли запись консультацию кардиолога (не только ЭКГ)
          const hasCardiologyConsultation = serviceCodes.some((code) => {
            const codeStr = String(code).toUpperCase();
            // Коды кардиологии: K01, K02, CARD_, CONSULTATION.CARDIOLOGY и т.д., но не ECG
            return (codeStr.startsWith('K') || codeStr.startsWith('CARD_') || codeStr.includes('CONSULT')) &&
            !codeStr.includes('ECG') && !codeStr.includes('ЭКГ');
          });

          // Если есть консультация кардиолога и specialty правильный, включаем
          return isCardiology && (hasCardiologyConsultation || serviceCodes.length === 0);
        });

        // Добавляем информацию о всех услугах пациента в каждую запись
        const enrichedAppointmentsData = appointmentsData.map((apt) => {
          const allPatientServices = getAllPatientServices(apt.patient_id, allAppointments);
          return {
            ...apt,
            all_patient_services: allPatientServices.services,
            all_patient_service_codes: allPatientServices.service_codes
          };
        });

        setAppointments(enrichedAppointmentsData);
      }
    } catch (error) {
      notify.error(getErrorMessage(error, 'Не удалось загрузить записи кардиолога. Проверьте соединение и попробуйте снова.'));
    } finally {
      setAppointmentsLoading(false);
    }
  }, [getAllPatientServices]);

  // Загружаем записи при переключении на вкладку
  useEffect(() => {
    if (activeTab === 'appointments' || shouldHydrateAppointmentContext) {
      loadMacOSCardiologyAppointments();
    }

    // Слушаем глобальные события обновления очереди
    const handleQueueUpdate = (event) => {
      const { action } = event.detail || {};

      // Автоматически обновляем список appointments после завершения приёма
      if (action === 'visitCompleted' || action === 'nextPatientCalled') {
        if (activeTab === 'appointments' || shouldHydrateAppointmentContext) {
          loadMacOSCardiologyAppointments();
        }
      }

      // Обновляем при любых изменениях, если открыта вкладка appointments
      if (activeTab === 'appointments' || shouldHydrateAppointmentContext) {
        // Небольшая задержка, чтобы дать бэкенду время обновить статусы
        setTimeout(() => {
          loadMacOSCardiologyAppointments();
        }, 500);
      }
    };
    window.addEventListener('queueUpdated', handleQueueUpdate);

    return () => {
      window.removeEventListener('queueUpdated', handleQueueUpdate);
    };
  }, [activeTab, loadMacOSCardiologyAppointments, shouldHydrateAppointmentContext]);

  // Функция для получения данных пациента по ID
  const fetchPatientData = useCallback(async (patientId) => {
    // Проверяем, является ли это демо-пациентом (ID >= 1000)
    if (patientId >= 1000) {
      return null;
    }

    const token = tokenManager.getAccessToken();
    if (!token) return null;

    try {
      const response = await fetch(`${API_V1_BASE}/patients/${patientId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      notify.error(getErrorMessage(error, 'Не удалось загрузить данные пациента. Проверьте соединение и попробуйте снова.'));
    }
    return null;
  }, []);

  // Функция для преобразования данных пациента из формата API в формат PatientModal
  const transformPatientData = useCallback((apiPatient) => {
    if (!apiPatient) return null;

    return {
      id: apiPatient.id,
      firstName: apiPatient.first_name || '',
      lastName: apiPatient.last_name || '',
      middleName: apiPatient.middle_name || '',
      email: apiPatient.email || '',
      phone: apiPatient.phone || '',
      birthDate: apiPatient.birth_date || '',
      gender: apiPatient.sex === 'M' ? 'male' : apiPatient.sex === 'F' ? 'female' : '',
      address: apiPatient.address || '',
      passport: apiPatient.doc_number || '',
      insuranceNumber: '', // Это поле может отсутствовать в API
      emergencyContact: '', // Это поле может отсутствовать в API
      emergencyPhone: '', // Это поле может отсутствовать в API
      bloodType: '', // Это поле может отсутствовать в API
      allergies: '', // Это поле может отсутствовать в API
      chronicDiseases: '', // Это поле может отсутствовать в API
      notes: '' // Это поле может отсутствовать в API
    };
  }, []);

  // Функция для создания частичного объекта пациента из данных row (для QR-пациентов)
  // УПРОЩЕНО: Не нормализуем ФИО здесь - это делает backend (Single Source of Truth)
  // Просто преобразуем данные для отображения
  const createPartialPatientFromRow = useCallback((row) => {
    return {
      // Используем полное ФИО как есть, без нормализации
      fullName: row.patient_fio || '',
      firstName: '', // Будет заполнено через API при необходимости
      lastName: '', // Будет заполнено через API при необходимости
      middleName: '', // Будет заполнено через API при необходимости
      phone: row.patient_phone || '',
      address: row.address || '',
      birthDate: row.patient_birth_year ? `${row.patient_birth_year}-01-01` : ''
    };
  }, []);

  // Обработчик редактирования пациента
  const handleEditPatient = useCallback(async (row) => {
    // Если нет patient_id (QR-пациент), используем частичные данные из row
    if (!row.patient_id) {
      const partialPatient = createPartialPatientFromRow(row);
      setEditPatientModal({ open: true, patient: partialPatient, loading: false });
      return;
    }

    try {
      // Показываем индикатор загрузки
      setEditPatientModal({ open: true, patient: null, loading: true });

      // Загружаем полные данные пациента
      const apiPatient = await fetchPatientData(row.patient_id);

      if (!apiPatient) {
        // Если не удалось загрузить, используем данные из row (частичные)
        const partialPatient = createPartialPatientFromRow(row);
        setEditPatientModal({ open: true, patient: partialPatient, loading: false });
        notify.warning('Не удалось загрузить карточку пациента, показаны данные из очереди');
        return;
      }

      // Преобразуем данные в формат PatientModal
      const transformedPatient = transformPatientData(apiPatient);
      setEditPatientModal({ open: true, patient: transformedPatient, loading: false });

    } catch (error) {
      const partialPatient = createPartialPatientFromRow(row);
      setEditPatientModal({ open: true, patient: partialPatient, loading: false });
      notify.error(getErrorMessage(error, 'Не удалось загрузить карточку пациента. Проверьте соединение и попробуйте снова.'));
    }
  }, [fetchPatientData, transformPatientData, createPartialPatientFromRow]);

  // Обработчики для таблицы записей
  const handleAppointmentRowClick = async (row) => {
    // Можно открыть детали записи или переключиться на прием
    if (row.patient_fio) {
      const appointmentId = row.appointment_id || null;
      const visitId = await ensureCanonicalVisitId(row);
      if (!visitId) {
        notify.error('Не удалось определить канонический visit_id для пациента');
        return;
      }

      const patientData = {
        id: row.id,
        appointment_id: appointmentId,
        visit_id: visitId,
        patient_id: row.patient_id,
        patient_name: row.patient_fio,
        phone: row.patient_phone,
        number: row.id,
        doctor_queue_entry_id: resolveDoctorQueueEntryId(row),
        source: 'appointments',
        status: row.status ?? null,
        payment_status: row.payment_status ?? null,
        discount_mode: row.discount_mode,
        specialty: row.specialty || 'cardiology'
      };
      setSelectedPatient(patientData);

      // Если запись завершена - загружаем EMR для просмотра
      const isCompleted = row.status === 'served' || row.status === 'completed' || row.status === 'done';
      if (isCompleted) {
        await loadEMR(visitId);
      } else {
        // Для незавершённых записей очищаем EMR
        setEmr(null);
      }

      goToTab('visit');
    }
  };

  const handleAppointmentActionClick = async (action, row, event) => {
    event.stopPropagation();

    switch (action) {
      case 'view':
        await handleAppointmentRowClick(row);
        break;
      case 'view_emr':{
          // Просмотр EMR для завершённой записи
          const appointmentId = row.appointment_id || null;
          const visitId = await ensureCanonicalVisitId(row);
          if (!visitId) {
            notify.error('Не удалось открыть EMR без канонического visit_id');
            break;
          }

          // Создаем объект пациента
          const patientData = {
            id: row.id,
            appointment_id: appointmentId,
            visit_id: visitId,
            patient_id: row.patient_id,
            patient_name: row.patient_fio,
            phone: row.patient_phone,
            number: row.id,
            doctor_queue_entry_id: resolveDoctorQueueEntryId(row),
            source: 'appointments',
            status: row.status ?? null,
            payment_status: row.payment_status ?? null,
            discount_mode: row.discount_mode,
            specialty: row.specialty || 'cardiology'
          };

          setSelectedPatient(patientData);

          // Загружаем EMR
          await loadEMR(visitId);

          // Переходим на вкладку visit
          goToTab('visit');
          break;
        }
      case 'call':
        // Вызвать пациента
        try {
          const queueEntryId = resolveDoctorQueueEntryId(row);
          if (queueEntryId === null) {
            logger.warn('[Cardiology] Cannot start visit without OnlineQueueEntry id', row);
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
            await loadMacOSCardiologyAppointments();
            notify.success(`Пациент ${row.patient_fio} вызван`);
          }
        } catch (error) {
          notify.error(getErrorMessage(error, 'Не удалось вызвать пациента. Проверьте соединение и попробуйте снова.'));
        }
        break;
      case 'payment':
        // QW-05 (UX audit): removed dead "functionality will be added later" stub.
        // The `payment` action is disabled for doctor view at the table level
        // (canPay = !isDoctorView && backendCanPay), so we should never arrive
        // here in production. If we do, log the event for debugging rather than
        // surfacing a "feature not implemented" toast to the doctor — that
        // breaks Nielsen heuristic #2 (match between system and real world).
        logger.info('[Cardiology] payment action invoked (disabled for doctor view)', row);
        break;
      case 'print':
        try {
          const printResult = await printPanelTicket(row, {
            specialtyName: 'Кардиология'
          });
          notify.success(printResult?.message || `Талон для ${row.patient_fio} отправлен на печать`);
        } catch (error) {
          notify.error(getErrorMessage(error, 'Не удалось отправить талон на печать'));
        }
        break;
      case 'complete':{
          // Завершить приём
          try {
            const visitId = await ensureCanonicalVisitId(row);
            if (!visitId) {
              notify.error('Не удалось завершить приём без канонического visit_id');
              break;
            }
            // Переходим на вкладку визита для завершения
            const patient = {
              id: row.id,
              appointment_id: row.appointment_id || null,
              visit_id: visitId,
              patient_id: row.patient_id,
              patient_name: row.patient_fio,
              phone: row.patient_phone,
              number: row.id,
              doctor_queue_entry_id: resolveDoctorQueueEntryId(row),
              source: 'appointments',
              status: 'in_cabinet',
              payment_status: row.payment_status,
              discount_mode: row.discount_mode,
              specialty: row.specialty || 'cardiology'
            };

            setSelectedPatient(patient);

            // Загружаем EMR если есть
            await loadEMR(patient.visit_id);

            // Переходим на вкладку visit для завершения
            goToTab('visit');
          } catch (error) {
            notify.error(getErrorMessage(error, 'Не удалось завершить приём. Проверьте соединение и попробуйте снова.'));
          }
          break;
        }
      case 'edit':
        // Загружаем полные данные пациента перед открытием модального окна
        await handleEditPatient(row);
        break;
      case 'cancel':
        // Логика отмены записи
        break;
      case 'schedule_next':
        // Назначить следующий визит
        setScheduleNextModal({ open: true, patient: row });
        break;
      default:
        break;
    }
  };

  // P-019 (UX audit): load EMR when a patient is selected so the audit
  // badge on the visit tab can show status, version, last-modified, and
  // signed-by. Previously EMR was only loaded when the doctor clicked a
  // specific action (call/complete/view_emr), not on initial patient
  // selection — so the doctor had no visibility into who last touched
  // the record.
  // MUST be above the isDemoMode early return to satisfy the
  // rules-of-hooks lint rule (no conditional hook calls).
  useEffect(() => {
    const { visitId } = getSelectedPatientContext();
    if (visitId && selectedPatient) {
      loadEMR(visitId);
    }
  }, [selectedPatient, authRefreshTick]); // eslint-disable-line react-hooks/exhaustive-deps

  // Проверяем демо-режим после всех хуков
  const isDemoMode = window.location.pathname.includes('/medilab-demo');

  // В демо-режиме не рендерим компонент
  if (isDemoMode) {
    return null;
  }

  // Обработка AI предложений
  const handleAISuggestion = (type, suggestion) => {
    if (type === 'icd10') {
      setVisitData({ ...visitData, icd10: suggestion });
      notify.success('Код МКБ-10 добавлен из AI предложения');
      // P-020 (UX audit): immediately warn if the AI-suggested ICD-10 code
      // is a critical diagnosis, so the doctor can double-check before
      // completing the visit.
      const critical = getCriticalDiagnosisWarning(suggestion);
      if (critical) {
        notify.warning(
          `Критический диагноз: ${critical.label} (${critical.fullCode}). ` +
          'Потребуется подтверждение при завершении приёма.'
        );
      }
    } else if (type === 'diagnosis') {
      setVisitData({ ...visitData, diagnosis: suggestion });
      notify.success('Диагноз добавлен из AI предложения');
    }
  };

  // Обработка сохранения визита
  const handleSaveVisit = async () => {
    if (!selectedPatient) return;

    // QW-10 (UX audit): confirm before completing the visit. completeVisit is
    // an irreversible action that closes the encounter and auto-calls the next
    // patient. Without a confirm, a doctor could accidentally complete a visit
    // with an empty diagnosis or treatment, leaving the EMR incomplete. We
    // surface a stronger warning (intent='warning') when critical fields are
    // empty, and a normal confirmation otherwise.
    //
    // P-020 (UX audit): if the ICD-10 code matches a critical diagnosis
    // (I21 acute MI, I46 cardiac arrest, I50 heart failure, I71 aortic
    // dissection, R57 shock), we show the strongest warning (intent='danger')
    // and require explicit confirmation. This prevents accidental entry of
    // a life-threatening diagnosis that could trigger aggressive therapy.
    const hasDiagnosis = Boolean(visitData?.diagnosis?.trim());
    const hasComplaint = Boolean(visitData?.complaint?.trim());
    const missingCritical = !hasDiagnosis || !hasComplaint;
    const criticalWarning = getCriticalDiagnosisWarning(visitData?.icd10);

    let confirmOptions;
    if (criticalWarning) {
      confirmOptions = {
        title: `Критический диагноз: ${criticalWarning.label} (${criticalWarning.code})`,
        message:
          `Код МКБ-10 ${criticalWarning.fullCode} соответствует критическому диагнозу: ` +
          `"${criticalWarning.label}". Подтвердите, что диагноз установлен корректно. ` +
          `Ошибочный диагноз может привести к ненужному агрессивному лечению ` +
          `(тромболизис, коронарография, интенсивная терапия).`,
        description:
          'После завершения приёма EMR будет сохранена с этим диагнозом. ' +
          'Изменение диагноза после подписания возможно только через поправку (amend).',
        confirmLabel: 'Подтверждаю диагноз',
        cancelLabel: 'Отмена — проверить диагноз',
        intent: 'danger',
      };
    } else if (missingCritical) {
      confirmOptions = {
        title: 'Завершить приём без диагноза?',
        message: hasDiagnosis
          ? 'Не заполнена жалоба пациента.'
          : hasComplaint
            ? 'Не заполнен диагноз. Рекомендуется указать диагноз перед завершением приёма.'
            : 'Не заполнены жалоба и диагноз. Рекомендуется заполнить их перед завершением.',
        description:
          'После завершения приёма EMR будет сохранена в текущем состоянии. ' +
          'Дополнить карту можно будет через поправку (amend).',
        confirmLabel: 'Завершить всё равно',
        cancelLabel: 'Вернуться к заполнению',
        intent: 'warning',
      };
    } else {
      confirmOptions = {
        title: 'Завершить приём?',
        message: 'Приём будет сохранён, и система автоматически вызовет следующего пациента.',
        description:
          'Перед завершением убедитесь, что диагноз, лечение и рекомендации заполнены корректно. ' +
          'После подписания EMR изменения возможны только через поправку.',
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
      const queueEntryId = resolveDoctorQueueEntryId(selectedPatient);
      if (queueEntryId === null) {
        notify.error('Cannot complete visit without a queue entry id');
        return;
      }

      const visitPayload = {
        patient_id: selectedPatient.patient?.id || selectedPatient.patient_id || selectedPatient.id,
        complaint: visitData.complaint,
        diagnosis: visitData.diagnosis,
        icd10: visitData.icd10,
        services: selectedServices,
        notes: visitData.notes
      };
      await queueService.completeVisit(queueEntryId, visitPayload);
      notify.success('Прием завершен успешно');

      // Очищаем форму и возвращаемся в очередь
      setSelectedPatient(null);
      setSelectedServices([]);
      setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
      setActiveTab('queue');

      // Автоматически вызвать следующего пациента для кардиолога
      try {
        const next = await queueService.callNextWaiting('cardiology');
        if (next?.success) {
          notify.success(`Вызван следующий пациент №${next.entry.number}`);
        }
      } catch (err) {
        notify.warning(getErrorMessage(
          err,
          'Следующий пациент не вызван автоматически. Проверьте соединение и попробуйте снова.'
        ));
      }

    } catch (error) {
      notify.error(getErrorMessage(error, 'Не удалось завершить действие. Проверьте соединение и попробуйте снова.'));
    } finally {
      setLoading(false);
    }
  };

  // Загрузка EMR для просмотра
  const loadEMR = async (visitId) => {
    try {
      const token = tokenManager.getAccessToken();
      if (!visitId) {
        notify.error('Не указан visit_id для EMR v2');
        return null;
      }

      const response = await fetch(`${API_V1_BASE}/v2/emr/${visitId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const emrData = await response.json();
        setEmr(emrData);
        return emrData;
      } else if (response.status === 404) {
        // EMR ещё не создана - это нормально
        setEmr(null);
        return null;
      } else {
        const error = await response.json().catch(() => ({ detail: 'Ошибка при загрузке EMR' }));
      notify.error(getErrorMessage(error, 'Не удалось загрузить EMR. Проверьте соединение и попробуйте снова.'));
        return null;
      }
    } catch (error) {
      notify.error(getErrorMessage(error, 'Не удалось загрузить EMR. Проверьте соединение и попробуйте снова.'));
      return null;
    }
  };

  // Сохранение EMR
  // (P-019 useEffect was moved above the isDemoMode early return
  //  to satisfy the rules-of-hooks lint rule. See line ~1049.)































































































  // Обработка завершения приема через EMR
  const handleCompleteVisitFromEMR = async () => {
    if (!selectedPatient) return;

    try {
      await handleSaveVisit();
    } catch (error) {
      notify.error(getErrorMessage(error, 'Не удалось завершить приём через EMR. Проверьте соединение и попробуйте снова.'));
    }
  };

  // Обработка анализов крови
  const handleBloodTestSubmit = async (e) => {
    e.preventDefault();
    const { patientId, visitId } = getSelectedPatientContext();

    if (!patientId) {
      notify.error('Нельзя сохранить анализ без выбранного пациента');
      return;
    }

    const payload = {
      patient_id: patientId,
      visit_id: visitId || undefined,
      test_date: bloodTestForm.test_date,
      cholesterol_total: normalizeOptionalNumber(bloodTestForm.cholesterol_total),
      cholesterol_hdl: normalizeOptionalNumber(bloodTestForm.cholesterol_hdl),
      cholesterol_ldl: normalizeOptionalNumber(bloodTestForm.cholesterol_ldl),
      triglycerides: normalizeOptionalNumber(bloodTestForm.triglycerides),
      glucose: normalizeOptionalNumber(bloodTestForm.glucose),
      crp: normalizeOptionalNumber(bloodTestForm.crp),
      troponin: normalizeOptionalNumber(bloodTestForm.troponin),
      interpretation: bloodTestForm.interpretation?.trim() || null
    };

    try {
      const response = await fetch(`${API_V1_BASE}/cardio/blood-tests`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        setShowForm({ open: false, type: 'blood' });
        setBloodTestForm(getEmptyBloodTestForm());
        await loadPatientData();
        notify.success('Анализ крови сохранен успешно');
        return;
      }

      const errorData = await response.json().catch(() => ({}));
      notify.error(getErrorMessage(errorData?.detail || errorData?.message || '', 'Не удалось сохранить анализ. Проверьте соединение и попробуйте снова.'));
    } catch (error) {
      notify.error(getErrorMessage(error, 'Не удалось сохранить анализ. Проверьте соединение и попробуйте снова.'));
    }
  };

  // Используем дизайн-систему вместо инлайновых стилей
  const pageStyle = {
    padding: getSpacing('lg'),
    width: '100%',
    minHeight: 'calc(100vh - 60px)',
    background: getColor('background'),
    color: getColor('text'),
    overflow: 'visible'
  };

  const formatHistoryTimestamp = (value) => {
    if (!value) {
      return '—';
    }

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return String(value);
    }

    return parsed.toLocaleString('ru-RU');
  };

  const getHistoryTimestampValue = (value) => {
    if (!value) {
      return 0;
    }

    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime();
  };

  const formatFileSize = (size) => {
    if (!size && size !== 0) {
      return '—';
    }

    if (size < 1024) {
      return `${size} B`;
    }

    if (size < 1024 * 1024) {
      return `${(size / 1024).toFixed(1)} KB`;
    }

    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  };

  const canPreviewAttachment = (file) => {
    const mimeType = String(file?.mime_type || file?.type || '').toLowerCase();
    return mimeType.startsWith('image/') || mimeType.startsWith('text/') || mimeType === 'application/pdf';
  };

  const downloadPatientFile = async (file) => {
    if (!file?.id) {
      return;
    }

    try {
      const token = tokenManager.getAccessToken();
      const response = await fetch(`${API_V1_BASE}/files/${file.id}/download`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!response.ok) {
        throw new Error('Не удалось скачать файл');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = file.title || file.original_filename || file.filename || `file-${file.id}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      notify.error(getErrorMessage(error, 'Не удалось скачать файл. Проверьте соединение и попробуйте снова.'));
    }
  };

  const previewPatientFile = async (file) => {
    if (!file?.id) {
      return;
    }

    try {
      const token = tokenManager.getAccessToken();
      const response = await fetch(`${API_V1_BASE}/files/${file.id}/preview`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!response.ok) {
        throw new Error('Предпросмотр недоступен');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      window.setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
      const previewWindow = window.open(url, '_blank', 'noopener,noreferrer');
      if (!previewWindow) {
        throw new Error('Браузер заблокировал окно предпросмотра');
      }
    } catch (error) {
      notify.error(getErrorMessage(error, 'Не удалось открыть файл. Проверьте соединение и попробуйте снова.'));
    }
  };

  const historyEntries = [
    ...bloodTests.map((test) => ({
      id: `blood-${test.id}`,
      kind: 'labs',
      title: `Анализ крови — ${test.test_date || '—'}`,
      subtitle: `Хол: ${test.cholesterol_total || '—'}; LDL: ${test.cholesterol_ldl || '—'}; Глюкоза: ${test.glucose || '—'}`,
      timestamp: test.test_date || test.created_at || test.updated_at,
      badgeVariant: 'secondary',
      meta: test.interpretation || `Тест #${test.id}`,
    })),
    ...ecgResults.map((result) => ({
      id: `ecg-${result.id || result.ecg_date}`,
      kind: 'ecg',
      title: `ЭКГ — ${result.ecg_date || '—'}`,
      subtitle: `Ритм: ${result.rhythm || '—'}, ЧСС: ${result.heart_rate || '—'}`,
      timestamp: result.ecg_date || result.created_at || result.updated_at,
      badgeVariant: 'success',
      meta: result.source || `Запись #${result.id || '—'}`,
    })),
    ...patientFiles.map((file) => {
      const fileLabel = file.title || file.original_filename || file.filename || file.name || `Файл #${file.id}`;
      const tags = Array.isArray(file.tags) && file.tags.length > 0 ? file.tags.join(', ') : '';
      const fileType = file.file_type || file.mime_type || file.type || 'attachment';

      return {
        id: `file-${file.id}`,
        kind: 'attachments',
        title: fileLabel,
        subtitle: `${fileType}${tags ? ` • ${tags}` : ''}`,
        timestamp: file.created_at || file.updated_at || file.uploaded_at,
        badgeVariant: 'info',
        meta: formatFileSize(file.file_size),
        file,
      };
    }),
  ].sort((left, right) => getHistoryTimestampValue(right.timestamp) - getHistoryTimestampValue(left.timestamp));

  const filteredHistoryEntries = historyFilter === 'all'
    ? historyEntries
    : historyEntries.filter((entry) => entry.kind === historyFilter);

  const historyFilterOptions = [
    { value: 'all', label: 'Все', count: historyEntries.length },
    { value: 'ecg', label: 'ЭКГ', count: ecgResults.length },
    { value: 'labs', label: 'Анализы', count: bloodTests.length },
    { value: 'attachments', label: 'Вложения', count: patientFiles.length },
  ];

  const selectedPatientLabel = selectedPatient?.patient_name
    || selectedPatient?.patient?.full_name
    || selectedPatient?.patient?.name
    || '—';
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
      value: countAppointmentsByStatuses(appointments, CARDIOLOGY_WAITING_STATUSES),
      variant: 'warning'
    },
    {
      key: 'called',
      label: 'Вызваны',
      value: countAppointmentsByStatuses(appointments, CARDIOLOGY_CALLED_STATUSES),
      variant: 'primary'
    },
    {
      key: 'completed',
      label: 'Приняты',
      value: countAppointmentsByStatuses(appointments, CARDIOLOGY_COMPLETED_STATUSES),
      variant: 'success'
    }
  ];

  return (
    <div className="cardio-root-container" style={{ ...pageStyle }}>

      <div className="cardio-card-padded" style={{ padding: 0 }}> {/* Убираем padding, так как он уже есть в main контейнере */}

        {/* Навигация по вкладкам удалена — управление через сайдбар и URL */}

        {/* Контент вкладок */}
        <div style={{
          width: '100%',
          maxWidth: 'none',
          overflow: 'visible',
          boxSizing: 'border-box',
          position: 'relative',
          zIndex: 1,
          display: 'block',
          gap: getSpacing('lg')
        }}>
          {/* Записи кардиолога */}
          {activeTab === 'appointments' &&
          <div style={{
            width: '100%',
            maxWidth: 'none',
            display: 'flex',
            flexDirection: 'column',
            gap: getSpacing('xl')
          }}>
              <MacOSCard className="cardio-card-fullwidth">
                <div className="cardio-appointments-header">
                  <h3 className="cardio-appointments-title">
                    <Calendar size={20} className="cardio-icon-mr" style={{ marginRight: '12px', color: 'var(--mac-accent)' }} />
                    Записи к кардиологу
                  </h3>
                  <AppointmentSummaryBar
                    ariaLabel="Сводка записей кардиолога"
                    items={appointmentSummaryItems}
                    onRefresh={loadMacOSCardiologyAppointments}
                    refreshDisabled={appointmentsLoading}
                    buttonProps={{ variant: 'outline' }}
                  />
                </div>

                {appointmentsLoading ?
              <Skeleton type="table" count={5} /> :
              appointments.length === 0 ?
              <MacOSEmptyState
                type="calendar"
                title="Записи не найдены"
                description="В системе пока нет записей к кардиологу" /> :


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

              }
              </MacOSCard>
            </div>
          }

          {/* Прием пациента */}
          {activeTab === 'queue' &&
          <QueueIntegration specialty="cardiology" />
          }

          {activeTab === 'visit' && selectedPatient &&
          <div className="cardio-flex-col-visible" style={{ gap: '24px' }}>
              {/* Информация о пациенте */}
              <MacOSCard className="cardio-card-padded">
                <h3 className="cardio-section-heading">
                  <User size={20} className="cardio-icon-mr cardio-icon-blue" />
                  Пациент #{selectedPatient.number}
                </h3>

                <div className="cardio-grid-auto">
                  <div>
                    <label className="cardio-form-label-block">
                      ФИО пациента
                    </label>
                    <div className="cardio-patient-name cardio-patient-name-primary">{selectedPatient.patient_name}</div>
                  </div>

                  {selectedPatient.phone &&
                <div>
                      <label className="cardio-form-label-block">
                        Телефон
                      </label>
                      <div style={{
                    display: 'flex',
                    alignItems: 'center'
                  }}>
                        <Phone size={16} style={{
                      marginRight: '6px',
                      color: 'var(--mac-text-secondary)'
                    }} />
                        <span className="cardio-patient-name cardio-patient-name-primary">{selectedPatient.phone}</span>
                      </div>
                    </div>
                }
                </div>

                {/* P-019 (UX audit): EMR audit badge — show status, version,
                    last-modified date, and who signed/amended the record.
                    Previously this info was hidden inside the EMR container's
                    toggle-only history panel; now the cardiologist sees it at
                    a glance on the visit tab. */}
                {emr && (
                  <div className="cardio-emr-audit-badge" style={{
                    marginTop: '12px',
                    padding: '8px 12px',
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    gap: '12px',
                    fontSize: getFontSize('sm'),
                    color: getColor('textSecondary'),
                    background: emr.status === 'signed' ? 'var(--mac-success-bg, #f0fdf4)' : 'var(--mac-surface-secondary, #f8fafc)',
                    border: `1px solid ${emr.status === 'signed' ? 'var(--mac-success-border, #bbf7d0)' : getColor('border')}`,
                    borderRadius: '8px',
                  }}>
                    <span style={{ fontWeight: '600', color: getColor('text') }}>
                      EMR #{emr.id ?? '—'}
                    </span>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontWeight: '600',
                      fontSize: '11px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                      background: emr.status === 'signed' ? '#16a34a' : emr.status === 'amended' ? '#ca8a04' : '#6b7280',
                      color: '#ffffff',
                    }}>
                      {emr.status || 'draft'}
                    </span>
                    {emr.version != null && (
                      <span title="Версия EMR">v{emr.version}</span>
                    )}
                    {emr.updated_at && (
                      <span title="Последнее изменение">
                        изм. {new Date(emr.updated_at).toLocaleDateString('ru-RU', {
                          day: '2-digit', month: '2-digit', year: 'numeric',
                          hour: '2-digit', minute: '2-digit',
                        })}
                      </span>
                    )}
                    {emr.signed_at && (
                      <span title="Подписана">
                        подписана {new Date(emr.signed_at).toLocaleDateString('ru-RU', {
                          day: '2-digit', month: '2-digit', year: 'numeric',
                        })}
                      </span>
                    )}
                    {emr.signed_by != null && emr.signed_by > 0 && (
                      <span title="Кем подписана">
                        врач #{emr.signed_by}
                      </span>
                    )}
                  </div>
                )}
              </MacOSCard>


              {/* Электронная медицинская карта */}
              <MacOSCard className="cardio-card-padded">
                <h3 className="cardio-section-heading">
                  <FileText size={20} className="cardio-icon-mr cardio-icon-blue" />
                  Электронная медицинская карта
                </h3>
                <EMRContainerV2
                visitId={selectedPatient?.visit_id}
                patientId={selectedPatient?.patient?.id || selectedPatient?.patient_id}
                specialty="cardiology" />

              </MacOSCard>

              {/* Действия */}
              <MacOSCard className="cardio-card-padded">
                <div className="flex justify-end" style={{ gap: '12px' }}>
                  <Button
                  variant="outline"
                  onClick={() => {
                    setSelectedPatient(null);
                    setActiveTab('queue');
                  }}>

                    Отменить
                  </Button>
                  <Button
                  onClick={handleCompleteVisitFromEMR}
                  disabled={loading}>

                    {loading ?
                  <RefreshCw size={16} className="cardio-icon-mr" /> :

                  <Save size={16} className="cardio-icon-mr" />
                  }
                    Завершить прием
                  </Button>
                </div>
              </MacOSCard>
            </div>
          }

          {/* ЭКГ */}
          {activeTab === 'visit' && !selectedPatient &&
          <MacOSCard className="cardio-empty-state" style={{ padding: "48px" }}>
              <MacOSEmptyState
              icon={Calendar}
              title="Выберите визит"
              description="Откройте прием из очереди или списка записей, либо используйте ссылку с visitId."
              action={
              <Button variant="outline" onClick={() => goToTab('appointments')} style={{ marginTop: '16px' }}>
                    Перейти к записям
                  </Button>
              } />
            </MacOSCard>
          }

          {/* ЭКГ — R-15: extracted to EcgTab component */}
          {activeTab === 'ecg' &&
            <EcgTab
              selectedPatient={selectedPatient}
              onAddEcg={() => setShowForm({ open: true, type: 'ecg' })}
              onDataUpdate={loadPatientData}
              getSpacing={getSpacing}
            />
          }

          {/* Анализы крови — R-15: extracted to BloodTestsTab component */}
          {activeTab === 'blood' &&
            <BloodTestsTab
              bloodTests={bloodTests}
              bloodTestForm={bloodTestForm}
              setBloodTestForm={setBloodTestForm}
              showFormOpen={showForm.open && showForm.type === 'blood'}
              onNewTest={openBloodTestForm}
              onCancelForm={() => setShowForm({ open: false, type: 'blood' })}
              onSubmit={handleBloodTestSubmit}
              getEmptyBloodTestForm={getEmptyBloodTestForm}
              getFieldRangeWarning={getFieldRangeWarning}
              isLdlCritical={isLdlCritical}
              settings={settings}
              getColor={getColor}
              getFontSize={getFontSize}
              getSpacing={getSpacing}
            />
          }

          {/* AI Помощник */}
          {activeTab === 'ai' &&
          <div className="cardio-w-full-visible">
              <AIAssistant
              specialty="cardiology"
              onSuggestionSelect={handleAISuggestion} />

            </div>
          }

          {/* Управление услугами */}
          {activeTab === 'services' &&
          <div className="cardio-w-full-visible">
              <DoctorServiceSelector
              specialty="cardiology"
              selectedServices={[]}
              canEditPrices={false} />

            </div>
          }

          {/* История и вложения */}
          {activeTab === 'history' &&
          <div style={{
            width: '100%',
            maxWidth: 'none',
            overflow: 'visible',
            display: 'flex',
            flexDirection: 'column',
            gap: getSpacing('xl')
          }}>
              {!selectedPatient ?
            <MacOSCard style={{
              padding: getSpacing('xl'),
              textAlign: 'center'
            }}>
                  <Calendar size={48} style={{
                margin: '0 auto 16px',
                color: getColor('textSecondary')
              }} />
                  <h3 style={{
                fontSize: getFontSize('lg'),
                fontWeight: '500',
                marginBottom: getSpacing('sm'),
                color: getColor('text')
              }}>История</h3>
                  <p className="cardio-text-secondary">Выберите пациента в очереди или из записей</p>
                </MacOSCard> :

            <>
                  <MacOSCard className="cardio-card-padded">
                    <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  gap: getSpacing('md'),
                  flexWrap: 'wrap',
                  marginBottom: getSpacing('lg')
                }}>
                      <div>
                        <h3 style={{
                      fontSize: getFontSize('lg'),
                      fontWeight: '500',
                      marginBottom: getSpacing('xs'),
                      color: getColor('text')
                    }}>Хронология записей пациента</h3>
                        <p className="cardio-text-secondary">
                          {selectedPatientLabel}
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        onClick={loadPatientData}
                        className="cardio-flex" style={{ gap: "8px" }}>
                        <RefreshCw size={16} />
                        Обновить
                      </Button>
                    </div>

                    <div style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: getSpacing('sm'),
                  marginBottom: getSpacing('lg')
                }}>
                      {historyFilterOptions.map((option) => (
                        <Button
                          key={option.value}
                          variant={historyFilter === option.value ? 'primary' : 'outline'}
                          onClick={() => setHistoryFilter(option.value)}
                          className="cardio-flex" style={{ gap: "8px" }}>
                          {option.label}
                          <Badge variant="info">{option.count}</Badge>
                        </Button>
                      ))}
                    </div>

                    <div className="cardio-flex-col">
                      {filteredHistoryEntries.length === 0 && (
                        <MacOSEmptyState
                          type="calendar"
                          title="История пуста"
                          description="Для выбранного фильтра пока нет записей" />
                      )}

                      {filteredHistoryEntries.map((entry) => (
                        <div
                          key={entry.id}
                          style={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: getSpacing('md'),
                            padding: getSpacing('md'),
                            border: `1px solid ${getColor('border')}`,
                            backgroundColor: getColor('surface'),
                            borderRadius: '12px'
                          }}>
                          <div style={{
                            width: '10px',
                            height: '10px',
                            borderRadius: '50%',
                            backgroundColor: entry.badgeVariant === 'success'
                              ? getColor('success', 500)
                              : entry.badgeVariant === 'secondary'
                                ? getColor('secondary', 500)
                                : getColor('primary', 500),
                            marginTop: getSpacing('sm')
                          }} />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              gap: getSpacing('sm'),
                              flexWrap: 'wrap'
                            }}>
                              <div style={{
                                fontSize: getFontSize('base'),
                                fontWeight: '500',
                                color: getColor('text')
                              }}>{entry.title}</div>
                              <Badge variant={entry.badgeVariant}>
                                {entry.kind === 'attachments'
                                  ? 'Вложение'
                                  : entry.kind === 'ecg'
                                    ? 'ЭКГ'
                                    : 'Анализ'}
                              </Badge>
                            </div>
                            <div style={{
                              fontSize: getFontSize('sm'),
                              color: getColor('textSecondary'),
                              marginTop: getSpacing('xs')
                            }}>
                              {entry.subtitle}
                            </div>
                            <div style={{
                              fontSize: getFontSize('sm'),
                              color: getColor('textSecondary'),
                              marginTop: getSpacing('xs'),
                              display: 'flex',
                              gap: getSpacing('md'),
                              flexWrap: 'wrap'
                            }}>
                              <span>{formatHistoryTimestamp(entry.timestamp)}</span>
                              <span>{entry.meta}</span>
                            </div>

                            {entry.kind === 'attachments' && entry.file && (
                              <div style={{
                                marginTop: getSpacing('md'),
                                display: 'flex',
                                gap: getSpacing('sm'),
                                flexWrap: 'wrap'
                              }}>
                                {canPreviewAttachment(entry.file) && (
                                  <Button
                                    variant="outline"
                                    onClick={() => previewPatientFile(entry.file)}>
                                    Просмотр
                                  </Button>
                                )}
                                <Button
                                  variant="outline"
                                  onClick={() => downloadPatientFile(entry.file)}>
                                  Скачать
                                </Button>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </MacOSCard>

                  <MacOSCard className="cardio-card-padded">
                    <h3 style={{
                  fontSize: getFontSize('lg'),
                  fontWeight: '500',
                  marginBottom: getSpacing('lg'),
                  color: getColor('text')
                }}>Сводка по пациенту</h3>
                    <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: getSpacing('lg')
                }}>
                      <div className="cardio-input-container"
                  style={{
                    border: `1px solid ${getColor('border')}`,
                    backgroundColor: getColor('surface')
                  }}>
                        <div className="cardio-stat-label-sm cardio-text-secondary">Количество ЭКГ</div>
                        <div className="cardio-stat-value cardio-stat-value-default">{ecgResults.length}</div>
                      </div>
                      <div className="cardio-input-container"
                  style={{
                    border: `1px solid ${getColor('border')}`,
                    backgroundColor: getColor('surface')
                  }}>
                        <div className="cardio-stat-label-sm cardio-text-secondary">Количество анализов</div>
                        <div className="cardio-stat-value cardio-stat-value-default">{bloodTests.length}</div>
                      </div>
                      <div className="cardio-input-container"
                  style={{
                    border: `1px solid ${getColor('border')}`,
                    backgroundColor: getColor('surface')
                  }}>
                        <div className="cardio-stat-label-sm cardio-text-secondary">Вложения</div>
                        <div className="cardio-stat-value cardio-stat-value-default">{patientFiles.length}</div>
                      </div>
                      <div className="cardio-input-container"
                  style={{
                    border: `1px solid ${getColor('border')}`,
                    backgroundColor: getColor('surface')
                  }}>
                        <div className="cardio-stat-label-sm cardio-text-secondary">Выбранный пациент</div>
                        <div className="cardio-stat-value cardio-stat-value-default">{selectedPatientLabel}</div>
                      </div>
                    </div>
                  </MacOSCard>
                </>
            }
            </div>
          }
        </div>

        {/* Модальное окно Schedule Next */}
        {scheduleNextModal.open &&
        <ScheduleNextModal
          isOpen={scheduleNextModal.open}
          onClose={() => setScheduleNextModal({ open: false, patient: null })}
          patient={scheduleNextModal.patient}
          theme={{ isDark, getColor, getSpacing, getFontSize }}
          specialtyFilter="cardiology" />

        }

        {/* Модальное окно редактирования пациента */}
        {editPatientModal.open &&
        <EditPatientModal
          isOpen={editPatientModal.open}
          onClose={() => setEditPatientModal({ open: false, patient: null, loading: false })}
          patient={editPatientModal.patient}
          onSave={async () => {
            await loadMacOSCardiologyAppointments();
            setEditPatientModal({ open: false, patient: null, loading: false });
          }}
          loading={editPatientModal.loading}
          theme={{ isDark, getColor, getSpacing, getFontSize }} />

        }

        {/* QW-10 (UX audit): portal-mounted ConfirmDialog used before completing a visit */}
        {confirmDialog}

        {/* P-021 (UX audit): session timeout warning dialog */}
        {sessionWarning && (
          <div
            role="alertdialog"
            aria-label="Предупреждение об истечении сессии"
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'rgba(0,0,0,0.5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 10000,
            }}
          >
            <div
              style={{
                background: getColor('surface'),
                border: `1px solid ${getColor('border')}`,
                borderRadius: '12px',
                padding: '24px',
                maxWidth: '420px',
                width: '90%',
                boxShadow: getShadow('xl'),
              }}
            >
              <h3 style={{ margin: '0 0 12px 0', fontSize: getFontSize('lg'), color: getColor('text') }}>
                Сессия скоро истечёт
              </h3>
              <p style={{ margin: '0 0 16px 0', fontSize: getFontSize('base'), color: getColor('textSecondary'), lineHeight: 1.5 }}>
                Ваша сессия истекает. Несохранённые данные (жалобы, диагноз, лечение)
                могут быть потеряны. Сохраните текущий приём или продлите сессию.
              </p>
              <div style={{ display: 'flex', gap: getSpacing('sm'), justifyContent: 'flex-end' }}>
                <Button
                  variant="outline"
                  onClick={() => {
                    setSessionWarning(null);
                    // Reset the warning flag so it can fire again if the
                    // session is still expiring after dismissal.
                  }}
                >
                  Позже
                </Button>
                <Button
                  onClick={() => {
                    setSessionWarning(null);
                    // Trigger a token refresh by making any API call —
                    // the api/client.js interceptor will refresh if needed.
                    // A simple page reload also works but is more disruptive.
                    notify.info('Продлеваем сессию...');
                    loadMacOSCardiologyAppointments?.();
                  }}
                >
                  Продлить сессию
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Настройки кардиолога: плавающая кнопка и панель */}
        <button
          onClick={() => setSettingsOpen(true)}
          style={{
            position: 'fixed',
            right: 16,
            bottom: 16,
            background: getColor('surface'),
            border: `1px solid ${getColor('border')}`,
            borderRadius: '9999px',
            padding: getSpacing('md'),
            boxShadow: getShadow('lg')
          }}
          aria-label="Открыть настройки">

          <Settings size={18} />
        </button>
        {settingsOpen &&
        <MacOSCard style={{
          padding: '24px',
          position: 'fixed',
          right: 16,
          bottom: 80,
          width: 360,
          backgroundColor: getColor('surface'),
          border: `1px solid ${getColor('border')}`,
          boxShadow: getShadow('xl')
        }}>
            <h3 style={{
            fontSize: getFontSize('lg'),
            fontWeight: '500',
            marginBottom: getSpacing('md'),
            color: getColor('text')
          }}>Настройки кардиолога</h3>
            <div className="cardio-flex-col">
              <label className="flex items-center" style={{
              gap: '8px',
              color: 'var(--mac-text-primary)',
              fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
            }}>
                <Checkbox
                checked={settings.showEcgEchoTogether}
                onChange={(e) => setSettings({ ...settings, showEcgEchoTogether: e.target.checked })} />

                Показывать ЭКГ и ЭхоКГ вместе
              </label>
              <div>
                <div className="text-sm" style={{
                color: getColor('textSecondary'),
                marginBottom: getSpacing('xs')
              }}>Порог LDL (мг/дл)</div>
                <input
                type="number"
                aria-label="LDL threshold"
                value={settings.ldlThreshold}
                onChange={(e) => setSettings({ ...settings, ldlThreshold: Number(e.target.value) })}
                style={{
                  width: '100%',
                  padding: `${getSpacing('sm')} ${getSpacing('md')}`,
                  border: `1px solid ${getColor('border')}`,
                  borderRadius: '6px',
                  backgroundColor: getColor('surface'),
                  color: getColor('text'),
                  fontSize: getFontSize('base'),
                  outline: 'none'
                }} />

              </div>
            </div>
            <div className="flex justify-end" style={{
            gap: getSpacing('sm'),
            marginTop: getSpacing('lg')
          }}>
              <Button variant="outline" onClick={() => setSettingsOpen(false)}>Закрыть</Button>
              <Button onClick={() => {
                // P-016 (UX audit): settings are already persisted to
                // localStorage on every change via useLocalStorage. The
                // "Save" button gives the doctor explicit feedback that
                // the values are stored.
                notify.success('Настройки сохранены');
                setSettingsOpen(false);
              }}><Save size={16} className="cardio-icon-mr" />Сохранить</Button>
            </div>
          </MacOSCard>
        }

        {/* AI Chat Widget */}
        <AIChatWidget
          contextType="general"
          specialty="cardiology"
          useWebSocket={false}
          position="bottom-right" />

        <RoleNotificationCenter userRole="cardiologist" />
      </div>
    </div>);

};

export default MacOSCardiologistPanelUnified;
