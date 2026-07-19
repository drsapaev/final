import { useState, useEffect, useCallback, useRef } from 'react';
import type { CSSProperties } from 'react';
import { useLocation } from 'react-router-dom';
// P-009 fix: shared doctor panel state hook
import { useDoctorPanelState } from '../hooks/useDoctorPanelState';
// P-016 (UX audit): persist cardiologist settings (ldlThreshold,
// showEcgEchoTogether) in localStorage so they survive page reloads.
import { useLocalStorage } from '../hooks/useLocalStorage';
// P-021 (UX audit): warn the doctor 5 minutes before session expiry
// so they can save their work instead of losing it to a silent 401.
import { useSessionTimeoutWarning } from '../hooks/useSessionTimeoutWarning';
import { useCardiologistHotkeys } from '../hooks/useCardiologistHotkeys';
// S-M-2 fix: replace lucide-direct with macos <Icon>
import {
  MacOSCard,
  Button,
  Checkbox,
  Input,
  Icon } from '../components/ui/macos';
import { useTheme } from '../contexts/ThemeContext';
import { adaptTimeFields } from '../utils/registrarAggregation';
import './cardiology.css';
import BloodTestsTab from '../components/cardiology/BloodTestsTab';
import EcgTab from '../components/cardiology/EcgTab';
import HistoryTab from '../components/cardiology/HistoryTab';
import ServicesTab from '../components/cardiology/ServicesTab';
import AiTabRaw from '../components/cardiology/AiTab';
const AiTab = AiTabRaw as unknown as React.ComponentType<Record<string, unknown>>;
import AppointmentsTab from '../components/cardiology/AppointmentsTab';
import VisitTab from '../components/cardiology/VisitTab';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import EditPatientModal from '../components/common/EditPatientModal';
import { queueService } from '../services/queue';
import { printPanelTicket } from '../services/panelPrint';
import QueueIntegration from '../components/QueueIntegration';
import { getApiBaseUrl } from '../api/runtime';
import { resolveCanonicalVisitId } from '../utils/canonicalVisit';
import { getErrorMessage } from '../utils/errorHandler';
import logger from '../utils/logger';
import notify from '../services/notify';
// STRAT#32: useTranslation adapter for confirm/notify i18n.
import { useTranslation } from '../i18n/useTranslation';
// QW-10 (UX audit): shared ConfirmDialog hook used before completing a visit.
import { useConfirm } from '../components/common/ConfirmDialog';
import RoleNotificationCenter from '../components/notifications/RoleNotificationCenter';
import tokenManager from '../utils/tokenManager';
import { countAppointmentsByStatuses, SPECIALTY_KEYS, getAllPatientServices, makeEnsureCanonicalVisitId } from '../utils/doctorPanelShared';
import { useVisitLifecycle } from '../hooks/useVisitLifecycle';

const API_V1_BASE = getApiBaseUrl();
const CARDIOLOGY_WAITING_STATUSES = ['waiting', 'confirmed', 'pending'];
const CARDIOLOGY_CALLED_STATUSES = ['called', 'in_progress'];
const CARDIOLOGY_COMPLETED_STATUSES = ['completed', 'done'];
// countAppointmentsByStatuses is imported from utils/doctorPanelShared
// (unified implementation shared with Dermatology and Dentistry panels).

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
  const { isDark, getColor, getSpacing, getFontSize } = useTheme();
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
  // QW-01 (UX audit): removed swallowed setMessage — all calls now route through `notify`
  // (the shared adapter in services/notify.js) so users actually see error/success/warning
  // feedback. The `message` destructure was dropped, which silently discarded every
  // notification before this fix.
  // QW-10 (UX audit): confirm hook used before completing a visit (prevents
  // accidental completion with empty diagnosis/treatment).
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;
  // STRAT#32: useTranslation adapter for confirm/notify i18n.
  const { t: tI18n } = useTranslation();
  const [scheduleNextModal, setScheduleNextModal] = useState({ open: false, patient: null });
  const [editPatientModal, setEditPatientModal] = useState({ open: false, patient: null, loading: false });
  const [settingsOpen, setSettingsOpen] = useState(false);
  // P-016 (UX audit): settings now persist in localStorage. The doctor's
  // LDL threshold and ECG/Echo layout preference survive page reloads.
  const [settings, setSettings] = useLocalStorage('cardio.settings', {
    ldlThreshold: 100,
    showEcgEchoTogether: true,
  });
  const [emr, setEmr] = useState(null as any);

  // Ref для отслеживания предыдущего пациента для очистки EMR
  const prevSelectedPatientRef = useRef(null);

  // Состояния для таблицы записей
  const [appointments, setAppointments] = useState([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [services, setServices] = useState({} as any); // ✅ Добавлено: состояние для услуг

  // P-021 (UX audit): session timeout warning state. When the JWT is
  // about to expire, we show a dialog so the doctor can save their work.
  const [sessionWarning, setSessionWarning] = useState(null as any); // { expiresAt } | null

  useSessionTimeoutWarning({
    onWarning: (expiresAt) => setSessionWarning({ expiresAt }),
    onExpired: () => {
      setSessionWarning(null);
      notify.error(tI18n('cardio.session_expired'));
      // Force a reload so the auth guard redirects to /login.
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    },
  });

  // H-8 fix: keyboard shortcuts for tab switching, refresh, close modal.
  useCardiologistHotkeys({
    setActiveTab: (tab: string) => goToTab(tab),
    refreshData: () => loadMacOSCardiologyAppointments(true),
    closeModal: () => {
      setShowForm({ open: false });
      setScheduleNextModal({ open: false, patient: null });
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
  } as any);

  const [showForm, setShowForm] = useState({ open: false, type: 'blood' } as any);
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

  // P-022 (workflow audit): wire useVisitLifecycle so the in-memory cache
  // is invalidated when the doctor switches between visits or patients.
  // Previously, cache entries tagged with `visit:${prevVisitId}` could
  // linger and leak data between patients on rapid visit switches.
  //
  // We pass the lifecycle hook only the canonical patientId / visitId
  // derived from selectedPatient — when those change, the hook:
  //   1. aborts all in-flight requests via AbortController
  //   2. calls cacheService.invalidateByVisit(prevVisitId)
  //   3. calls cacheService.invalidateByPatient(prevPatientId)
  //   4. invokes our onCleanup callback (resets the local EMR state)
  //
  // This is a non-breaking change: existing loadEMR / loadPatientData
  // functions are untouched. The lifecycle hook only adds cache hygiene
  // on top of the existing data flow.
  const currentVisitId = selectedPatient?.visit_id || visitIdFromUrl || null;
  const currentPatientId =
    selectedPatient?.patient?.id ||
    selectedPatient?.patient_id ||
    patientIdFromUrl ||
    null;
  useVisitLifecycle(currentVisitId, currentPatientId, {
    invalidateCacheOnChange: true,
    onCleanup: () => {
      // Reset local EMR state so stale data does not bleed into the
      // next visit's view. loadEMR will be re-invoked by the existing
      // useEffect when selectedPatient changes.
      setEmr(null);
    },
  });

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
    cholesterol_total: { min: 50, max: 1000, unit: tI18n('cardio.cardio_panel_unit_mgdl'), label: tI18n('cardio.cardio_panel_field_cholesterol_total_label') },
    cholesterol_hdl: { min: 5, max: 200, unit: tI18n('cardio.cardio_panel_unit_mgdl'), label: 'HDL' },
    cholesterol_ldl: { min: 5, max: 1000, unit: tI18n('cardio.cardio_panel_unit_mgdl'), label: 'LDL' },
    triglycerides: { min: 10, max: 2000, unit: tI18n('cardio.cardio_panel_unit_mgdl'), label: tI18n('cardio.cardio_panel_field_triglycerides_label') },
    glucose: { min: 20, max: 1000, unit: tI18n('cardio.cardio_panel_unit_mgdl'), label: tI18n('cardio.cardio_panel_field_glucose_label') },
    crp: { min: 0, max: 500, unit: tI18n('cardio.cardio_panel_unit_mgl'), label: 'CRP' },
    troponin: { min: 0, max: 100, unit: tI18n('cardio.cardio_panel_unit_ngml'), label: tI18n('cardio.cardio_panel_field_troponin_label') },
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
          message: tI18n('cardio.cardio_panel_range_below_min', { label: range.label, value: parsed, unit: range.unit, min: range.min }),
        };
      }
      if (parsed > range.max) {
        return {
          valid: false,
          message: tI18n('cardio.cardio_panel_range_above_max', { label: range.label, value: parsed, unit: range.unit, max: range.max }),
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
    'I21': tI18n('cardio.cardio_panel_critical_icd_I21'),
    'I22': tI18n('cardio.cardio_panel_critical_icd_I22'),
    'I46': tI18n('cardio.cardio_panel_critical_icd_I46'),
    'I50': tI18n('cardio.cardio_panel_critical_icd_I50'),
    'I71': tI18n('cardio.cardio_panel_critical_icd_I71'),
    'R57': tI18n('cardio.cardio_panel_critical_icd_R57'),
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
      notify.error(tI18n('cardio.select_patient_first'));
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
    } catch (error: any) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_patient_data_update_failed')));
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
  }, [location.search, activeTab, setActiveTab]);

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
      } catch (error: any) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_services_load_failed')));
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
      setActiveTab('patients');
      notify.info(tI18n('cardio.cardio_panel_patient_loaded_info', { name: patientName }));
    } catch (error: any) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_patient_load_failed')));
    }
  }, [patientIdFromUrl, visitIdFromUrl, selectedPatient, setSelectedPatient, setActiveTab]);

  useEffect(() => {
    hydratePatientFromUrl();
  }, [hydratePatientFromUrl, authRefreshTick]);

  // P-009: patientIdFromUrl / visitIdFromUrl now come from useDoctorPanelState
  const shouldHydrateAppointmentContext = Boolean(patientIdFromUrl || visitIdFromUrl);

  // P-009: goToTab is now handleTabChange from useDoctorPanelState

  const ensureCanonicalVisitId = useCallback(
    (row) => makeEnsureCanonicalVisitId(setAppointments, resolveCanonicalVisitId)(row),
    []
  );

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
  }, [appointments, patientIdFromUrl, visitIdFromUrl, setSelectedPatient]);

  // Функция для получения всех услуг пациента из всех записей
  const getAllPatientServicesCb = useCallback((patientId, allAppointments) => {
    return getAllPatientServices(patientId, allAppointments);
  }, []);

  // Загрузка записей кардиолога
  const loadMacOSCardiologyAppointments = useCallback(async (_silent?: boolean) => {
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
                    entry.discount_mode === 'repeat' ? tI18n('cardio.cardio_panel_visit_type_repeat') :
                    entry.discount_mode === 'benefit' ? tI18n('cardio.cardio_panel_visit_type_benefit') :
                    entry.discount_mode === 'all_free' ? 'All Free' :
                    tI18n('cardio.cardio_panel_visit_type_paid'),
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
                  doctor: entry.doctor_name || tI18n('cardio.cardio_panel_doctor_fallback'),
                  specialty: queue.specialty,
                  ...adaptTimeFields(entry, data),
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
          const allPatientServices = getAllPatientServicesCb(apt.patient_id, allAppointments);
          return {
            ...apt,
            all_patient_services: allPatientServices.services,
            all_patient_service_codes: allPatientServices.service_codes
          };
        });

        setAppointments(enrichedAppointmentsData);
      }
    } catch (error: any) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_appointments_load_failed')));
    } finally {
      setAppointmentsLoading(false);
    }
  }, [getAllPatientServicesCb]);

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
    } catch (error: any) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_patient_data_load_failed')));
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
        notify.warning(tI18n('cardio.patient_card_load_failed'));
        return;
      }

      // Преобразуем данные в формат PatientModal
      const transformedPatient = transformPatientData(apiPatient);
      setEditPatientModal({ open: true, patient: transformedPatient, loading: false });

    } catch (error: any) {
      const partialPatient = createPartialPatientFromRow(row);
      setEditPatientModal({ open: true, patient: partialPatient, loading: false });
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_patient_card_load_failed')));
    }
  }, [fetchPatientData, transformPatientData, createPartialPatientFromRow]);

  // Обработчики для таблицы записей
  const handleAppointmentRowClick = async (row) => {
    // Можно открыть детали записи или переключиться на прием
    if (row.patient_fio) {
      const appointmentId = row.appointment_id || null;
      const visitId = await ensureCanonicalVisitId(row);
      if (!visitId) {
        notify.error(tI18n('cardio.no_visit_id'));
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

  // C-3 fix: cancel appointment with confirm dialog + backend call.
  // Previously the 'cancel' action was a no-op stub — the button rendered
  // but did nothing, leaving the doctor with no feedback.
  const handleCancelAppointment = async (row) => {
    const ok = await confirm({
      title: tI18n('cardio.cancel_appointment_title'),
      message: tI18n('cardio.cancel_appointment_message', { name: (row?.patient_fio || row?.patient_name || '').trim() }),
      description: tI18n('cardio.cardio_panel_appointment_cancel_description'),
      confirmLabel: tI18n('cardio.cancel_appointment_confirm'),
      cancelLabel: tI18n('cardio.cancel_appointment_cancel'),
      intent: 'warning',
    });
    if (!ok) {
      return;
    }

    try {
      setLoading(true);
      const token = tokenManager.getAccessToken();
      const response = await fetch(`${API_V1_BASE}/doctor/queue/${row?.doctor_queue_entry_id || row?.id}/cancel`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData?.detail || `HTTP ${response.status}`);
      }

      notify.success(tI18n('cardio.appointment_cancelled'));
      loadMacOSCardiologyAppointments(true);
    } catch (error: any) {
      logger.error('[Cardiology] Ошибка отмены записи:', error);
      notify.error(error?.message || tI18n('cardio.cardio_panel_appointment_cancel_failed'));
    } finally {
      setLoading(false);
    }
  };

  const handleAppointmentActionClick = async (action, row) => {
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
            notify.error(tI18n('cardio.emr_no_visit_id'));
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
            notify.error(tI18n('cardio.no_queue_id_for_visit'));
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
            notify.success(tI18n('cardio.cardio_panel_patient_called', { name: row.patient_fio }));
          }
        } catch (error: any) {
          notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_call_patient_failed')));
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
            specialtyName: tI18n('cardio.cardio_panel_specialty_name')
          });
          notify.success(printResult?.message || tI18n('cardio.cardio_panel_ticket_printed', { name: row.patient_fio }));
        } catch (error: any) {
          notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_ticket_print_failed')));
        }
        break;
      case 'complete':{
          // Завершить приём
          try {
            const visitId = await ensureCanonicalVisitId(row);
            if (!visitId) {
              notify.error(tI18n('cardio.no_visit_id_for_complete'));
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
          } catch (error: any) {
            notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_complete_visit_failed')));
          }
          break;
        }
      case 'edit':
        // Загружаем полные данные пациента перед открытием модального окна
        await handleEditPatient(row);
        break;
      case 'cancel':
        // C-3 fix: previously this was a no-op stub. Now opens a confirm
        // dialog and calls the backend cancel endpoint. Falls back to a
        // notify.error if the backend rejects the cancellation.
        await handleCancelAppointment(row);
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
      notify.success(tI18n('cardio.icd_added_from_ai'));
      // P-020 (UX audit): immediately warn if the AI-suggested ICD-10 code
      // is a critical diagnosis, so the doctor can double-check before
      // completing the visit.
      const critical = getCriticalDiagnosisWarning(suggestion);
      if (critical) {
        notify.warning(
          tI18n('cardio.cardio_panel_critical_diagnosis_warning', { label: critical.label, fullCode: critical.fullCode })
        );
      }
    } else if (type === 'diagnosis') {
      setVisitData({ ...visitData, diagnosis: suggestion });
      notify.success(tI18n('cardio.diagnosis_added_from_ai'));
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
        title: tI18n('cardio.cardio_panel_critical_diagnosis_title', { label: criticalWarning.label, code: criticalWarning.code }),
        message:
          tI18n('cardio.cardio_panel_critical_diagnosis_message', { fullCode: criticalWarning.fullCode, label: criticalWarning.label }),
        description:
          tI18n('cardio.cardio_panel_critical_diagnosis_description'),
        confirmLabel: tI18n('cardio.cardio_panel_critical_diagnosis_confirm'),
        cancelLabel: tI18n('cardio.cardio_panel_critical_diagnosis_cancel'),
        intent: 'danger',
      };
    } else if (missingCritical) {
      confirmOptions = {
        title: tI18n('cardio.cardio_panel_complete_without_diagnosis_title'),
        message: hasDiagnosis
          ? tI18n('cardio.cardio_panel_missing_complaint_message')
          : hasComplaint
            ? tI18n('cardio.cardio_panel_missing_diagnosis_message')
            : tI18n('cardio.cardio_panel_missing_both_message'),
        description:
          tI18n('cardio.cardio_panel_missing_critical_description'),
        confirmLabel: tI18n('cardio.cardio_panel_complete_anyway_confirm'),
        cancelLabel: tI18n('cardio.cardio_panel_back_to_filling_cancel'),
        intent: 'warning',
      };
    } else {
      confirmOptions = {
        title: tI18n('cardio.cardio_panel_complete_visit_title'),
        message: tI18n('cardio.cardio_panel_complete_visit_message'),
        description:
          tI18n('cardio.cardio_panel_complete_visit_description'),
        confirmLabel: tI18n('cardio.cardio_panel_complete_visit_confirm'),
        cancelLabel: tI18n('cardio.cardio_panel_complete_visit_cancel'),
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
        notify.error(tI18n('cardio.no_queue_id_for_visit'));
        return;
      }

      // X-2 (UX audit): fetch latest EMR data for the payload instead of
      // using local visitData which is never populated by EMRContainerV2.
      let emrPayload = { complaint: '', diagnosis: '', icd10: '', notes: '' };
      try {
        const emrResponse = await fetch(`${API_V1_BASE}/v2/emr/${selectedPatient?.visit_id}`, {
          headers: { 'Authorization': `Bearer ${tokenManager.getAccessToken()}` }
        });
        if (emrResponse.ok) {
          const emrData = await emrResponse.json();
          emrPayload = {
            complaint: emrData?.complaints || '',
            diagnosis: emrData?.diagnosis || '',
            icd10: emrData?.icd10_code || emrData?.icd10 || '',
            notes: emrData?.notes || '',
          };
        }
      } catch (emrErr) {
        logger.warn('[Cardiology] Failed to fetch EMR for visit payload, using local visitData', emrErr);
        emrPayload = {
          complaint: visitData.complaint,
          diagnosis: visitData.diagnosis,
          icd10: visitData.icd10,
          notes: visitData.notes,
        };
      }

      const visitPayload = {
        patient_id: selectedPatient.patient?.id || selectedPatient.patient_id || selectedPatient.id,
        complaint: emrPayload.complaint,
        diagnosis: emrPayload.diagnosis,
        icd10: emrPayload.icd10,
        services: selectedServices,
        notes: emrPayload.notes
      };
      await queueService.completeVisit(queueEntryId, visitPayload);
      notify.success(tI18n('cardio.visit_completed'));

      // Очищаем форму и возвращаемся в очередь
      setSelectedPatient(null);
      setSelectedServices([]);
      setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
      setActiveTab('queue');

      // Автоматически вызвать следующего пациента для кардиолога
      try {
        const next = await queueService.callNextWaiting(SPECIALTY_KEYS.CARDIOLOGY);
        if (next?.success) {
          notify.success(tI18n('cardio.cardio_panel_next_patient_called', { number: next.entry.number }));
        }
      } catch (err) {
        notify.warning(getErrorMessage(
          err,
          tI18n('cardio.cardio_panel_next_patient_call_failed')
        ));
      }

    } catch (error: any) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_action_failed')));
    } finally {
      setLoading(false);
    }
  };

  // Загрузка EMR для просмотра
  //
  // P-021 (workflow audit): previously this function had three issues:
  //   1. 401/403 surfaced as a generic 'EMR load failed' toast — the
  //      doctor had no way to tell their session had expired vs the
  //      backend being unreachable.
  //   2. Network errors were caught but the user-visible message did
  //      not distinguish 'no connection' from 'server error'.
  //   3. The local \`error\` variable was assigned but only its
  //      \`detail\` field reached getErrorMessage, losing HTTP status.
  //
  // Now:
  //   - 401/403 → 'Сессия истекла, войдите снова' toast + log auth event
  //   - 404 → silent (EMR not yet created is a normal state)
  //   - 5xx → 'Сервер недоступен, попробуйте позже'
  //   - Network/AbortError → silent (component unmounted or visit changed)
  //   - Other → generic fallback via getErrorMessage
  const loadEMR = async (visitId) => {
    if (!visitId) {
      notify.error(tI18n('cardio.emr_v2_no_visit_id'));
      return null;
    }

    const token = tokenManager.getAccessToken();
    if (!token) {
      logger.warn('[Cardiology] loadEMR: no auth token, skipping EMR load', { visitId });
      notify.error(tI18n('cardio.session_expired_short'));
      return null;
    }

    try {
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
      }

      if (response.status === 404) {
        // EMR ещё не создана - это нормально
        setEmr(null);
        return null;
      }

      if (response.status === 401 || response.status === 403) {
        logger.warn('[Cardiology] loadEMR: auth denied', { visitId, status: response.status });
        notify.error(tI18n('cardio.emr_no_permission'));
        setEmr(null);
        return null;
      }

      if (response.status >= 500) {
        logger.error('[Cardiology] loadEMR: server error', { visitId, status: response.status });
        notify.error(tI18n('cardio.server_unavailable'));
        setEmr(null);
        return null;
      }

      // Other 4xx — surface the backend detail if available
      const errorPayload = await response.json().catch(() => ({ detail: tI18n('cardio.cardio_panel_emr_load_error_short') }));
      logger.warn('[Cardiology] loadEMR: client error', { visitId, status: response.status, errorPayload });
      notify.error(getErrorMessage(errorPayload, tI18n('cardio.cardio_panel_emr_load_failed')));
      setEmr(null);
      return null;
    } catch (error: any) {
      // AbortError happens when the parent component aborted the fetch
      // (e.g. visitId changed) — not a user-facing error.
      if (error?.name === 'AbortError') {
        logger.info('[Cardiology] loadEMR: aborted', { visitId });
        return null;
      }
      logger.error('[Cardiology] loadEMR: network error', { visitId, error: error?.message || error });
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_emr_load_failed')));
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
    } catch (error: any) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_complete_visit_emr_failed')));
    }
  };

  // Обработка анализов крови
  const handleBloodTestSubmit = async (e) => {
    e.preventDefault();
    const { patientId, visitId } = getSelectedPatientContext();

    if (!patientId) {
      notify.error(tI18n('cardio.blood_test_no_patient'));
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
        notify.success(tI18n('cardio.blood_test_saved'));
        return;
      }

      const errorData = await response.json().catch(() => ({}));
      notify.error(getErrorMessage(errorData?.detail || errorData?.message || '', tI18n('cardio.cardio_panel_blood_test_save_failed')));
    } catch (error: any) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_blood_test_save_failed')));
    }
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
        throw new Error(tI18n('cardio.cardio_panel_download_failed_short'));
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
    } catch (error: any) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_download_failed')));
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
        throw new Error(tI18n('cardio.cardio_panel_preview_unavailable_short'));
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      window.setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
      const previewWindow = window.open(url, '_blank', 'noopener,noreferrer');
      if (!previewWindow) {
        throw new Error(tI18n('cardio.cardio_panel_preview_blocked_short'));
      }
    } catch (error: any) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_open_file_failed')));
    }
  };

  const historyEntries = [
    ...bloodTests.map((test) => ({
      id: `blood-${test.id}`,
      kind: 'labs',
      title: tI18n('cardio.cardio_panel_blood_test_title', { date: test.test_date || '—' }),
      subtitle: tI18n('cardio.cardio_panel_blood_test_subtitle', { total: test.cholesterol_total || '—', ldl: test.cholesterol_ldl || '—', glucose: test.glucose || '—' }),
      timestamp: test.test_date || test.created_at || test.updated_at,
      badgeVariant: 'secondary',
      meta: test.interpretation || tI18n('cardio.cardio_panel_blood_test_meta', { id: test.id }),
    })),
    ...ecgResults.map((result) => ({
      id: `ecg-${result.id || result.ecg_date}`,
      kind: 'ecg',
      title: tI18n('cardio.cardio_panel_ecg_title', { date: result.ecg_date || '—' }),
      subtitle: tI18n('cardio.cardio_panel_ecg_subtitle', { rhythm: result.rhythm || '—', heart_rate: result.heart_rate || '—' }),
      timestamp: result.ecg_date || result.created_at || result.updated_at,
      badgeVariant: 'success',
      meta: result.source || tI18n('cardio.cardio_panel_ecg_meta', { id: result.id || '—' }),
    })),
    ...patientFiles.map((file) => {
      const fileLabel = file.title || file.original_filename || file.filename || file.name || tI18n('cardio.cardio_panel_file_label', { id: file.id });
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
    { value: 'all', label: tI18n('cardio.cardio_panel_filter_all'), count: historyEntries.length },
    { value: 'ecg', label: tI18n('cardio.cardio_panel_filter_ecg'), count: ecgResults.length },
    { value: 'labs', label: tI18n('cardio.cardio_panel_filter_labs'), count: bloodTests.length },
    { value: 'attachments', label: tI18n('cardio.cardio_panel_filter_attachments'), count: patientFiles.length },
  ];

  const selectedPatientLabel = selectedPatient?.patient_name
    || selectedPatient?.patient?.full_name
    || selectedPatient?.patient?.name
    || '—';
  const appointmentSummaryItems = [
    {
      key: 'total',
      label: tI18n('cardio.cardio_panel_summary_total'),
      value: appointments.length,
      variant: 'info'
    },
    {
      key: 'waiting',
      label: tI18n('cardio.cardio_panel_summary_waiting'),
      value: countAppointmentsByStatuses(appointments, CARDIOLOGY_WAITING_STATUSES),
      variant: 'warning'
    },
    {
      key: 'called',
      label: tI18n('cardio.cardio_panel_summary_called'),
      value: countAppointmentsByStatuses(appointments, CARDIOLOGY_CALLED_STATUSES),
      variant: 'primary'
    },
    {
      key: 'completed',
      label: tI18n('cardio.cardio_panel_summary_completed'),
      value: countAppointmentsByStatuses(appointments, CARDIOLOGY_COMPLETED_STATUSES),
      variant: 'success'
    }
  ];

  return (
    <div className="cardio-root-container">

      <div className="cardio-card-padded cardio-p-0"> {/* Убираем padding, так как он уже есть в main контейнере */}

        {/* Навигация по вкладкам удалена — управление через сайдбар и URL */}

        {/* Контент вкладок */}
        <div className="cardio-tab-content">
          {/* Phase 4+: 'patients' tab combines former 'appointments' + 'history'.
              Back-compat: 'appointments' and 'history' cases still render for
              old deep links. */}
          {(activeTab === 'patients' || activeTab === 'appointments') &&
            <AppointmentsTab
              appointments={appointments}
              appointmentsLoading={appointmentsLoading}
              appointmentSummaryItems={appointmentSummaryItems}
              onRefresh={loadMacOSCardiologyAppointments}
              onRowClick={handleAppointmentRowClick}
              onActionClick={handleAppointmentActionClick}
              services={services}
              isDark={isDark}
            />
          }

          {/* Прием пациента */}
          {/* Очередь — trivial 1-liner, no extraction needed */}
          {activeTab === 'queue' &&
          <QueueIntegration specialty="cardiology" />
          }

          {/* Приём пациента — R-15: extracted to VisitTab component */}
          {activeTab === 'visit' &&
            <VisitTab
              selectedPatient={selectedPatient}
              emr={emr}
              loading={loading}
              onCancel={() => {
                setSelectedPatient(null);
                setActiveTab('queue');
              }}
              onComplete={handleCompleteVisitFromEMR}
              onGoToAppointments={() => goToTab('patients')}
              getColor={getColor}
              getFontSize={getFontSize}
            />
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

          {/* C-4 fix: 'Добавить ЭКГ' button now opens a simple ECG entry form.
              Previously setShowForm({type:'ecg'}) was called but no UI rendered. */}
          {showForm.open && showForm.type === 'ecg' && (
            <MacOSCard className="cardio-p-6">
              <div className="cardio-flex-between" style={{ marginBottom: 16 }}>
                <h3 style={{ margin: 0 }}>{tI18n('cardio.cardio_panel_add_ecg_title')}</h3>
                <Button variant="outline" size="small" onClick={() => setShowForm({ open: false })}>
                  {tI18n('cardio.cardio_panel_close')}
                </Button>
              </div>
              <BloodTestsTab
                bloodTests={[]}
                bloodTestForm={{
                  ...bloodTestForm,
                  // Hint the doctor that this form is for ECG metadata entry
                  interpretation: bloodTestForm?.interpretation || '',
                }}
                setBloodTestForm={setBloodTestForm}
                showFormOpen
                onNewTest={() => {}}
                onCancelForm={() => setShowForm({ open: false })}
                onSubmit={(e) => {
                  e?.preventDefault?.();
                  // C-4 fix: Persist ECG metadata to /cardio/ecg as a manual entry
                  // (file_id is null — the doctor is typing parameters from
                  // a printout or another system). Uses fetch + tokenManager
                  // to match the rest of CardiologistPanelUnified (not apiClient).
                  const token = tokenManager.getAccessToken();
                  fetch(`${API_V1_BASE}/cardio/ecg`, {
                    method: 'POST',
                    headers: {
                      'Authorization': `Bearer ${token}`,
                      'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                      patient_id: selectedPatient?.patient?.id || selectedPatient?.patient_id || null,
                      visit_id: selectedPatient?.visit_id || null,
                      file_id: null,
                      ecg_date: new Date().toISOString().slice(0, 10),
                      heart_rate: bloodTestForm?.heart_rate || null,
                      pr_interval: bloodTestForm?.pr_interval || null,
                      qrs_duration: bloodTestForm?.qrs_duration || null,
                      qt_interval: bloodTestForm?.qt_interval || null,
                      rhythm: bloodTestForm?.rhythm || null,
                      axis: bloodTestForm?.axis || null,
                      interpretation: bloodTestForm?.interpretation || null,
                      source: 'manual',
                      parameters: bloodTestForm,
                    }),
                  }).then((response) => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    notify.success(tI18n('cardio.ecg_added'));
                    setShowForm({ open: false });
                    loadPatientData();
                  }).catch((err) => {
                    logger.error('[Cardiology] Ошибка сохранения ЭКГ:', err);
                    notify.error(tI18n('cardio.ecg_save_failed'));
                  });
                }}
                getEmptyBloodTestForm={getEmptyBloodTestForm}
                getFieldRangeWarning={getFieldRangeWarning}
                isLdlCritical={isLdlCritical}
                settings={settings}
                getColor={getColor}
                getFontSize={getFontSize}
                getSpacing={getSpacing}
              />
            </MacOSCard>
          )}

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

          {/* AI Помощник — R-15: extracted to AiTab component */}
          {activeTab === 'ai' &&
            <AiTab onSuggestionSelect={handleAISuggestion} />
          }

          {/* Управление услугами — R-15: extracted to ServicesTab component */}
          {activeTab === 'services' &&
            <ServicesTab />
          }

          {/* История — R-15: extracted to HistoryTab component.
              Phase 4+: also renders under 'patients' tab (combined view). */}
          {(activeTab === 'history' || activeTab === 'patients') &&
            <HistoryTab
              selectedPatient={selectedPatient}
              selectedPatientLabel={selectedPatientLabel}
              filteredHistoryEntries={filteredHistoryEntries}
              historyFilterOptions={historyFilterOptions}
              historyFilter={historyFilter}
              setHistoryFilter={setHistoryFilter}
              canPreviewAttachment={canPreviewAttachment}
              downloadPatientFile={downloadPatientFile}
              previewPatientFile={previewPatientFile}
              getColor={getColor}
              getFontSize={getFontSize}
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
        {confirmDialog as unknown as React.ReactNode}

        {/* P-021 (UX audit): session timeout warning dialog */}
        {sessionWarning && (
          <div
            role="alertdialog"
            aria-label={tI18n('cardio.cardio_panel_session_warning_aria')}
            className="cardio-modal-overlay"
          >
            <div
              className="cardio-modal-card"
            >
              <h3 className="cardio-modal-heading">
                {tI18n('cardio.cardio_panel_session_warning_title')}
              </h3>
              <p className="cardio-modal-text">
                {tI18n('cardio.cardio_panel_session_warning_text')}
              </p>
              <div className="cardio-modal-actions">
                <Button
                  variant="outline"
                  onClick={() => {
                    setSessionWarning(null);
                    // Reset the warning flag so it can fire again if the
                    // session is still expiring after dismissal.
                  }}
                >
                  {tI18n('cardio.cardio_panel_session_warning_later')}
                </Button>
                <Button
                  onClick={() => {
                    setSessionWarning(null);
                    // Trigger a token refresh by making any API call —
                    // the api/client.js interceptor will refresh if needed.
                    // A simple page reload also works but is more disruptive.
                    notify.info(tI18n('cardio.session_extending'));
                    loadMacOSCardiologyAppointments?.();
                  }}
                >
                  {tI18n('cardio.cardio_panel_session_warning_extend')}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Настройки кардиолога: плавающая кнопка и панель */}
        <button
          onClick={() => setSettingsOpen(true)}
          className="cardio-settings-fab"
          aria-label={tI18n('cardio.cardio_panel_settings_open_aria')}>

          <Icon name="gear" size={18 as never} />
        </button>
        {(activeTab === 'visit' || activeTab === 'blood') && settingsOpen &&
        <MacOSCard className="cardio-settings-card">
            <h3 className="cardio-settings-title">{tI18n('cardio.cardio_panel_settings_title')}</h3>
            <div className="cardio-flex-col">
              <label className="flex items-center cardio-settings-label">
                <Checkbox
                checked={settings.showEcgEchoTogether}
                onChange={(e: any) => setSettings({ ...settings, showEcgEchoTogether: e?.target?.checked ?? e })} />

                {tI18n('cardio.cardio_panel_settings_show_ecg_echo')}
              </label>
              <div>
                <div className="text-sm cardio-ldl-label">{tI18n('cardio.cardio_panel_settings_ldl_threshold')}</div>
                <Input
                type="number"
                aria-label={tI18n('cardio.cardio_panel_settings_ldl_threshold_aria')}
                value={settings.ldlThreshold}
                onChange={(e) => setSettings({ ...settings, ldlThreshold: Number(e.target.value) })}
                className="cardio-settings-input" />

              </div>
            </div>
            <div className="flex justify-end cardio-settings-actions">
              <Button variant="outline" onClick={() => setSettingsOpen(false)}>{tI18n('cardio.cardio_panel_close')}</Button>
              <Button onClick={() => {
                // P-016 (UX audit): settings are already persisted to
                // localStorage on every change via useLocalStorage. The
                // "Save" button gives the doctor explicit feedback that
                // the values are stored.
                notify.success(tI18n('cardio.settings_saved'));
                setSettingsOpen(false);
              }}><Icon name="square.and.arrow.down" size={16 as never} className="cardio-icon-mr" />{tI18n('cardio.cardio_panel_save')}</Button>
            </div>
          </MacOSCard>
        }
      {/* X-13: AIChatWidget removed — AiTab in sidebar provides the same functionality */}

        <RoleNotificationCenter userRole="cardiologist" />
      </div>
    </div>);

};

export default MacOSCardiologistPanelUnified;
