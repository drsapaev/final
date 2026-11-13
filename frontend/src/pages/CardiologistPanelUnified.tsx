import { createElement, lazy, Suspense, useState, useEffect, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
// P-009 fix: shared doctor panel state hook
import { useDoctorPanelState } from '../hooks/useDoctorPanelState';
// P-016 (UX audit): persist cardiologist settings (ldlThreshold) in
// localStorage so they survive page reloads. Cardioplan slice 5: the
// unused ECG/Echo layout toggle and the floating settings menu are gone.
import { useLocalStorage } from '../hooks/useLocalStorage';
// P-021 (UX audit): warn the doctor 5 minutes before session expiry
// so they can save their work instead of losing it to a silent 401.
import { useSessionTimeoutWarning } from '../hooks/useSessionTimeoutWarning';
import { useCardiologistHotkeys } from '../hooks/useCardiologistHotkeys';
// S-M-2 (история, ОТМЕНЕО Track 3-2): macos-Icon обёртка → lucide refs (§3.3)
import { Card, Button } from '../components/ui/macos';
import { useTheme } from '../contexts/ThemeContext';
import { adaptTimeFields } from '../utils/registrarAggregation';
import './cardiology.css';
import BloodTestsTab from '../components/cardiology/BloodTestsTab';
// CARDIO-FE-001 (audit 3886 round 20): dedicated manual ECG entry form.
// The old flow reused <BloodTestsTab showFormOpen /> for the ECG add
// action, rendering blood-test inputs and POSTing null ECG measurements.
import ManualEcgForm from '../components/cardiology/ManualEcgForm';
import HistoryTab from '../components/cardiology/HistoryTab';
import ServicesTab from '../components/cardiology/ServicesTab';
import AiTab from '../components/cardiology/AiTab';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import { queueService } from '../services/queue';
import { printPanelTicket } from '../services/panelPrint';
import apiClient from '../api/client';
import CardiologyQueueTab, { type CardiologyQueueEntry } from '../components/cardiology/CardiologyQueueTab';
import PatientSearch, { type PatientSearchResult } from '../components/cardiology/PatientSearch';
import { getApiBaseUrl } from '../api/runtime';
import { resolveCanonicalVisitId } from '../utils/canonicalVisit';
import { getErrorMessage } from '../utils/errorHandler';
import logger from '../utils/logger';
import notify from '../services/notify';
// STRAT#32: useTranslation adapter for confirm/notify i18n.
import { useTranslation } from '../i18n/useTranslation';
// QW-10 (UX audit): shared ConfirmDialog hook used before completing a visit.
import { useConfirm } from '../components/common/ConfirmDialog';
import tokenManager from '../utils/tokenManager';
import { countAppointmentsByStatuses, SPECIALTY_KEYS, getAllPatientServices, makeEnsureCanonicalVisitId } from '../utils/doctorPanelShared';
import { openPatientFilePreview } from '../utils/patientFilePreview';
import { selectEntriesForSpecialist } from '../utils/cardiologyQueue';
import { useVisitLifecycle } from '../hooks/useVisitLifecycle';
import { emrTextValue } from '../components/emr-v2/emrCompletion';


const AppointmentsTab = lazy(() => import('../components/cardiology/AppointmentsTab'));
const loadVisitTab = () => import('../components/cardiology/VisitTab');
const VisitTab = lazy(loadVisitTab);
const EcgTab = lazy(() => import('../components/cardiology/EcgTab'));
const EditPatientModal = lazy(() => import('../components/common/EditPatientModal'));

function preloadVisitTab(): void {
  void loadVisitTab().catch(() => undefined);
}

const API_V1_BASE = getApiBaseUrl();
const CARDIOLOGY_WAITING_STATUSES = ['waiting', 'confirmed', 'pending'];
const CARDIOLOGY_CALLED_STATUSES = ['called', 'in_progress'];
const CARDIOLOGY_COMPLETED_STATUSES = ['completed', 'done'];
// countAppointmentsByStatuses is imported from utils/doctorPanelShared
// (unified implementation shared with Dermatology and Dentistry panels).

/**
 * Loose shape for the doctor-panel `selectedPatient` state object.
 *
 * The shared `useDoctorPanelState` hook keeps `selectedPatient` typed as
 * `null` (its useState is declared without an explicit generic, and the
 * runtime payload is built ad-hoc from API/queue rows). Until the hook
 * ships a proper type, the panels cast its return through this alias.
 */
type SelectedPatient = {
  id?: string | number | null;
  appointment_id?: string | number | null;
  visit_id?: string | number | null;
  patient_id?: string | number | null;
  patient_name?: string;
  patient_fio?: string;
  phone?: string;
  number?: string | number | null;
  doctor_queue_entry_id?: string | number | null;
  queue_entry_id?: string | number | null;
  source?: string;
  status?: string | null;
  payment_status?: string | null;
  discount_mode?: string;
  specialty?: string;
  patient?: { id?: string | number; full_name?: string; name?: string; [k: string]: unknown } | null;
  [k: string]: unknown;
};

type DoctorPanelState = {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  handleTabChange: (tab: string) => void;
  patientIdFromUrl: number | null;
  visitIdFromUrl: number | null;
  selectedPatient: SelectedPatient | null;
  setSelectedPatient: React.Dispatch<React.SetStateAction<SelectedPatient | null>>;
};

function resolveDoctorQueueEntryId(row: Record<string, unknown> | null | undefined): string | number | null {
  const explicitQueueEntryId = row?.doctor_queue_entry_id ?? row?.queue_entry_id ?? null;
  if (explicitQueueEntryId !== null && explicitQueueEntryId !== undefined) {
    return explicitQueueEntryId as string | number;
  }

  return null;
}

/**
 * Унифицированная панель кардиолога
 * Объединяет: очередь + специализированные функции + AI + ЭКГ/ЭхоКГ
 */
const MacOSCardiologistPanelUnified = (): React.JSX.Element | null => {
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
  }) as DoctorPanelState;

  // DOCFLOW-FE-002 (audit 3886): the LATEST selected patient must be
  // reachable from a ref so a completion flow that started for patient A can
  // re-verify the selection identity after every async boundary (confirm
  // dialog, network) before the irreversible POST and the clinical UI reset.
  const selectedPatientRef = useRef(selectedPatient);
  selectedPatientRef.current = selectedPatient;
  // CARDVISIT-FE-001 (audit 3886 round 24): one navigation-intent epoch for
  // every entry path that resolves a canonical visit id before selecting
  // the patient (appointment row click, view_emr action, complete action).
  // The latest intent wins: a delayed canonical-visit lookup for patient A
  // cannot switch the selected patient, EMR and active tab after the
  // doctor already moved to patient B.
  // RETRO-3963-01 (post-merge review 3968): the epoch is now the single
  // invalidation point for EVERY authoritative selection — not only the
  // three appointment-derived paths but also patient-search picks, queue
  // start/open-visit, URL deep-link hydration, completion deselect and the
  // explicit cancel — plus unmount, so no late async resolution can steal
  // a newer clinical context.
  const navigationEpochRef = useRef(0);
  // RETRO-3963-01: leaving the panel invalidates every in-flight navigation
  // ticket — a resolution that lands after unmount must be a no-op.
  useEffect(() => () => { navigationEpochRef.current += 1; }, []);
  const [selectedServices, setSelectedServices] = useState<unknown[]>([]);
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
  const confirm = confirmRaw;
  // STRAT#32: useTranslation adapter for confirm/notify i18n.
  const { t: tI18n } = useTranslation();
  const tI18nRef = useRef(tI18n);
  tI18nRef.current = tI18n;
  const [scheduleNextModal, setScheduleNextModal] = useState<{ open: boolean; patient: SelectedPatient | Record<string, unknown> | null }>({ open: false, patient: null });
  const [editPatientModal, setEditPatientModal] = useState<{ open: boolean; patient: SelectedPatient | Record<string, unknown> | null; loading: boolean }>({ open: false, patient: null, loading: false });
  // CARDPAT-FE-003 (audit 3886 round 24): request-generation guard for the
  // edit-patient modal. Every handleEditPatient run takes a ticket; a late
  // fetch for row A may not overwrite a newer edit (row B) or reopen a
  // modal the doctor already closed.
  const editPatientEpochRef = useRef(0);
  const closeEditPatientModal = useCallback(() => {
    editPatientEpochRef.current += 1;
    setEditPatientModal({ open: false, patient: null, loading: false });
  }, []);
  // P-016 (UX audit): settings persist in localStorage across reloads.
  // Cardioplan slice 5: only the LDL threshold remains — it is the single
  // setting actually consumed by the panel (blood-tab critical values).
  // The unused "show ECG and Echo together" toggle and the floating
  // settings menu were removed with this slice; stale stored keys are
  // simply ignored.
  const [settings, setSettings] = useLocalStorage('cardio.settings', {
    ldlThreshold: 100,
  });
  const [emr, setEmr] = useState<Record<string, unknown> | null>(null);

  // Ref для отслеживания предыдущего пациента для очистки EMR
  const prevSelectedPatientRef = useRef<string | number | null>(null);

  // Состояния для таблицы записей
  const [appointments, setAppointments] = useState<Record<string, unknown>[]>([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [appointmentsError, setAppointmentsError] = useState(false);
  const currentDoctorIdRef = useRef<number | null>(null);
  const [services, setServices] = useState({} as Record<string, unknown>); // ✅ Добавлено: состояние для услуг

  // P-021 (UX audit): session timeout warning state. When the JWT is
  // about to expire, we show a dialog so the doctor can save their work.
  const [sessionWarning, setSessionWarning] = useState<{ active: boolean; expiresAt?: number } | null>(null); // { expiresAt } | null

  useSessionTimeoutWarning({
    onWarning: (expiresAt) => setSessionWarning({ active: true, expiresAt: expiresAt ? Number(expiresAt) : undefined }),
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
  } as Record<string, unknown>);

  const [showForm, setShowForm] = useState({ open: false, type: 'blood' } as Record<string, unknown>);
  const [ecgResults, setEcgResults] = useState<Record<string, unknown>[]>([]);
  const [bloodTests, setBloodTests] = useState<Record<string, unknown>[]>([]);
  const [patientFiles, setPatientFiles] = useState<Record<string, unknown>[]>([]);
  // Cardioplan slice 4: the doctor-owned visit history ("записи") of the
  // currently selected patient, rendered alongside the medical history.
  const [visitHistory, setVisitHistory] = useState<Record<string, unknown>[]>([]);
  const [historyFilter, setHistoryFilter] = useState('all');
  const [authRefreshTick, setAuthRefreshTick] = useState(0);
  const filesAccessDeniedRef = useRef(false);
  // CARDIO-FE-002 (audit 3886 round 20): request-generation guard for the
  // four cross-patient data stores below (ecgResults, bloodTests,
  // patientFiles, visitHistory). Every loadPatientData run takes a
  // generation ticket; a store may only be written while that run is still
  // the latest one. A late response for patient A can therefore never
  // overwrite the visible panels of patient B after a selection change.
  const patientDataEpochRef = useRef(0);

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
  useVisitLifecycle(
    currentVisitId as unknown as string | number,
    currentPatientId as unknown as string | number,
    {
      invalidateCacheOnChange: true,
      onCleanup: () => {
        // Reset local EMR state so stale data does not bleed into the
        // next visit's view. loadEMR will be re-invoked by the existing
        // useEffect when selectedPatient changes.
        setEmr(null);
      },
    });

  const getEmptyBloodTestForm = useCallback((overrides: Record<string, unknown> = {}) => ({
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

  const normalizeOptionalNumber = (value: unknown) => {
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
  const isLdlCritical = useCallback((rawValue: number | string | undefined) => {
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
    (fieldName: string, rawValue: unknown): { valid?: boolean; message?: string } | undefined => {
      const range = (FIELD_RANGES as Record<string, { min: number; max: number; unit: string; label: string }>)[fieldName];
      if (!range) return undefined;
      const parsed = Number(rawValue);
      if (!Number.isFinite(parsed) || rawValue === '' || rawValue === null || rawValue === undefined) {
        return undefined;
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
      return { valid: true, message: undefined };
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
    (icd10Code: unknown) => {
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

  // Canonical Doctor.id of the authenticated doctor (cached per mount).
  // Cardioplan slice 4: also used to scope the visit-history query — the
  // backend allows doctor roles to list only their own visits.
  const resolveCurrentDoctorId = useCallback(async (): Promise<number> => {
    if (currentDoctorIdRef.current !== null) return currentDoctorIdRef.current;

    const { data: profile } = await apiClient.get<{ doctor?: { id?: unknown } }>('/doctor/my-info');
    const doctorId = Number(profile?.doctor?.id);
    if (!Number.isInteger(doctorId) || doctorId <= 0) {
      throw new Error('Current doctor profile has no canonical Doctor.id');
    }

    currentDoctorIdRef.current = doctorId;
    return doctorId;
  }, []);

  // ✅ Функция загрузки данных пациента (объявлена до использования)
  const loadPatientData = useCallback(async () => {
    const { patientId, visitId } = getSelectedPatientContext();
    if (!patientId) {
      // Invalidate any in-flight load for a previous patient context.
      patientDataEpochRef.current += 1;
      setVisitHistory([]);
      return;
    }

    const epoch = ++patientDataEpochRef.current;
    const isStale = () => epoch !== patientDataEpochRef.current;

    try {
      const token = tokenManager.getAccessToken();

      // Загружаем ЭКГ пациента
      const ecgResponse = await fetch(`${API_V1_BASE}/cardio/ecg?patient_id=${patientId}&limit=10`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (ecgResponse.ok) {
        const ecgData = await ecgResponse.json();
        if (isStale()) return; // CARDIO-FE-002: late cross-patient response
        setEcgResults(Array.isArray(ecgData) ? ecgData : []);
      }

      // Загружаем анализы крови пациента
      const bloodResponse = await fetch(`${API_V1_BASE}/cardio/blood-tests?patient_id=${patientId}&limit=10`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (bloodResponse.ok) {
        const bloodData = await bloodResponse.json();
        if (isStale()) return; // CARDIO-FE-002: late cross-patient response
        setBloodTests(Array.isArray(bloodData) ? bloodData : []);
      }

      const fileEndpoints = [
        `${API_V1_BASE}/files?patient_id=${patientId}&page=1&size=50`,
      ];

      if (visitId) {
        fileEndpoints.push(`${API_V1_BASE}/files?visit_id=${visitId}&page=1&size=50`);
      }

      if (filesAccessDeniedRef.current) {
        if (isStale()) return;
        setPatientFiles([]);
        return;
      }

      const mergedFiles = new Map<unknown, Record<string, unknown>>();
      for (const endpoint of fileEndpoints) {
        const fileResponse = await fetch(endpoint, {
          headers: { 'Authorization': `Bearer ${token}` },
        });

        if (isStale()) return; // CARDIO-FE-002: late cross-patient response

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
        if (isStale()) return; // CARDIO-FE-002: late cross-patient response
        const files: unknown[] = Array.isArray(fileData?.files) ? fileData.files : [];
        files.forEach((file) => {
          const fileRecord = file as Record<string, unknown>;
          if (fileRecord?.id != null) {
            mergedFiles.set(fileRecord.id, fileRecord);
          }
        });
      }

      if (isStale()) return; // CARDIO-FE-002: late cross-patient response
      setPatientFiles(Array.from(mergedFiles.values()));

      // Cardioplan slice 4: doctor-owned visit history ("записи") of the same
      // patient. The backend requires doctor roles to pass their canonical
      // Doctor.id and rejects foreign doctor_id values, so the panel only
      // ever renders visits the authenticated doctor owns.
      try {
        const historyDoctorId = await resolveCurrentDoctorId();
        if (isStale()) return; // CARDIO-FE-002: late cross-patient response
        const { data: visitsData } = await apiClient.get('/visits/visits', {
          params: { patient_id: patientId, doctor_id: historyDoctorId, limit: 50 },
        });
        if (isStale()) return; // CARDIO-FE-002: late cross-patient response
        setVisitHistory(Array.isArray(visitsData) ? visitsData : []);
      } catch (visitErr) {
        if (isStale()) return;
        logger.warn('[Cardiology] Failed to load doctor-owned visit history', visitErr);
        setVisitHistory([]);
      }
    } catch (error: unknown) {
      if (epoch === patientDataEpochRef.current) {
        notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_patient_data_update_failed')));
      }
    }
  }, [getSelectedPatientContext, resolveCurrentDoctorId]);

  // ✅ Очистка EMR и visitData при смене пациента
  useEffect(() => {
    if (selectedPatient) {
      const currentPatientId = (selectedPatient.patient_id ?? selectedPatient.id ?? selectedPatient.appointment_id) as string | number | null | undefined;
      const previousPatientId = prevSelectedPatientRef.current;

      // Если это новый пациент (не просто обновление того же)
      if (previousPatientId !== null && previousPatientId !== currentPatientId) {
        // Очищаем EMR и visitData при смене пациента
        setEmr(null);
        setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
        // CARDIO-FE-002 (audit 3886 round 20): a selection change must also
        // invalidate any in-flight loads for the PREVIOUS patient and clear
        // the four cross-patient data stores, so no late A response can land
        // in B's panels while B's own loads are still in flight.
        patientDataEpochRef.current += 1;
        setEcgResults([]);
        setBloodTests([]);
        setPatientFiles([]);
        setVisitHistory([]);
        // RETRO-3941-01 (post-merge review of PR 3941): an open manual ECG
        // form belongs to the patient it was opened for — close it on owner
        // change so no typed A measurements can be submitted under B. The
        // mount below is additionally keyed by patient+visit identity.
        setShowForm((prev) => (prev.open && prev.type === 'ecg'
          ? { open: false, type: 'ecg' }
          : prev));
      }

      // Сохраняем ID текущего пациента
      prevSelectedPatientRef.current = currentPatientId ?? null;

      // Загружаем данные пациента
      loadPatientData();
    } else {
      // Если пациента нет, очищаем всё
      prevSelectedPatientRef.current = null;
      patientDataEpochRef.current += 1;
      setEmr(null);
      setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
      setEcgResults([]);
      setBloodTests([]);
      setPatientFiles([]);
      setVisitHistory([]);
      setHistoryFilter('all');
      // RETRO-3941-01: clearing the selection is an owner change too — an
      // open ECG form must not survive it.
      setShowForm((prev) => (prev.open && prev.type === 'ecg'
        ? { open: false, type: 'ecg' }
        : prev));
    }
  }, [selectedPatient, loadPatientData, authRefreshTick]);

  // CARDIO-FE-002 (audit 3886 round 20): on unmount the pending loads must
  // become stale so their late resolutions never touch panel state.
  useEffect(() => () => {
    patientDataEpochRef.current += 1;
  }, []);

  // Отслеживаем изменения URL для синхронизации активной вкладки
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const tabParam = params.get('tab');
    if (tabParam && tabParam !== activeTab) {
      setActiveTab(tabParam);
    }
  }, [location.search, activeTab, setActiveTab]);

  useEffect(() => {
    if (visitIdFromUrl) preloadVisitTab();
  }, [visitIdFromUrl]);

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
          const servicesData = data?.services_by_group || {};
          setServices(servicesData as Record<string, unknown>);
        }
      } catch (error: unknown) {
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


    // RETRO-3963-01 (review 3968 + independent re-review): URL deep-link
    // hydration must never override a newer human selection. Two guards:
    // (1) the navigation epoch — a newer intent took a ticket while this
    // fetch was in flight; and (2) the live committed selection — if the
    // doctor already selected a DIFFERENT patient, the deep link is stale
    // and must bail WITHOUT merging its identity over the new selection
    // (the merge previously could produce a hybrid record: patient P2's
    // appointment context carrying patient P1's patient_id). Capturing
    // the epoch alone was insufficient: the hydration effect re-fires on
    // every selection change, so it could share the ticket of the very
    // navigation that triggered it.
    const epoch = navigationEpochRef.current;
    const liveSelectionIsOtherPatient = (): boolean => {
      const live = selectedPatientRef.current;
      const livePatientId = live?.patient?.id || live?.patient_id || null;
      return livePatientId !== null && String(livePatientId) !== String(patientIdFromUrl);
    };
    // RETRO-3969-01 (post-merge review of the 3969–3996 window): the
    // VISIT dimension of the same steal scenario. This effect re-fires
    // on every selection change, so a committed same-patient /
    // different-visit selection (the doctor row-clicked P1 at V_row
    // while the URL still carries ?patientId=P1&visitId=V1) reached the
    // merge, which stamped the stale URL visit over the doctor's chosen
    // one and hijacked the tab. The dermatology panel guards this exact
    // class (selectionContradictsUrl: patient AND visit) and this
    // panel's own URL-appointment sync bails on a visit mismatch — the
    // patient-identity hydration must not be the one surface without
    // it. A visitless live selection (search pick) is NOT a conflict:
    // the deep link still supplies the visit for it.
    const liveSelectionContradictsVisit = (): boolean => {
      const live = selectedPatientRef.current;
      const liveVisitId = live?.visit_id ?? null;
      const urlVisitId = visitIdFromUrl ?? null;
      return urlVisitId !== null && liveVisitId !== null && String(liveVisitId) !== String(urlVisitId);
    };

    try {
      const token = tokenManager.getAccessToken();
      if (!token) return;

      if (liveSelectionIsOtherPatient() || liveSelectionContradictsVisit()) return;

      const patientResponse = await fetch(`${API_V1_BASE}/patients/${patientIdFromUrl}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (epoch !== navigationEpochRef.current) return;
      if (liveSelectionIsOtherPatient() || liveSelectionContradictsVisit()) return;

      if (!patientResponse.ok) {
        return;
      }

      const patientData = await patientResponse.json();
      if (epoch !== navigationEpochRef.current) return;
      if (liveSelectionIsOtherPatient() || liveSelectionContradictsVisit()) return;
      const patientName = `${patientData?.last_name || ''} ${patientData?.first_name || ''} ${patientData?.middle_name || ''}`.trim();

      setSelectedPatient((prev: SelectedPatient | null) => ({
        ...(prev || {}),
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
    } catch (error: unknown) {
      // RETRO-3969-02 (P3 hygiene, ledger comment 3 inventory): the failure
      // path owns the same epoch/live-selection guard as every async
      // boundary above — a hydration fetch that failed AFTER the operator
      // moved on must not toast a stale failure (sibling of the fixed
      // loadEMR catch).
      if (epoch !== navigationEpochRef.current) return;
      if (liveSelectionIsOtherPatient() || liveSelectionContradictsVisit()) return;
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
    (row: Record<string, unknown>) => makeEnsureCanonicalVisitId(setAppointments, resolveCanonicalVisitId)(row),
    []
  );

  useEffect(() => {
    // P-009: patientIdFromUrl / visitIdFromUrl come from useDoctorPanelState
    if ((!patientIdFromUrl && !visitIdFromUrl) || appointments.length === 0) {
      return;
    }

    const matchingAppointment = appointments.find((appointment: Record<string, unknown>) => {
      if (visitIdFromUrl && appointment.visit_id === visitIdFromUrl) {
        return true;
      }
      return Boolean(patientIdFromUrl) && appointment.patient_id === patientIdFromUrl;
    });
    if (!matchingAppointment) {
      return;
    }

    setSelectedPatient((prev: SelectedPatient | null) => {
      const prevPatientId = prev?.patient?.id || prev?.patient_id || null;
      const prevVisitId = prev?.visit_id || null;
      if (patientIdFromUrl && prevPatientId && prevPatientId !== patientIdFromUrl) {
        return prev;
      }
      if (visitIdFromUrl && prevVisitId && prevVisitId !== visitIdFromUrl) {
        return prev;
      }

      const nextAppointmentId = (matchingAppointment.appointment_id as string | number | null | undefined) || prev?.appointment_id || null;
      const nextVisitId = (matchingAppointment.visit_id as string | number | null | undefined) || visitIdFromUrl || prev?.visit_id || null;
      const nextPatientName = (matchingAppointment.patient_fio as string | undefined) || prev?.patient_name || prev?.patient_fio || '';
      const nextPatient: SelectedPatient = {
        ...(prev || {}),
        id: nextAppointmentId || prev?.id || patientIdFromUrl,
        appointment_id: nextAppointmentId,
        visit_id: nextVisitId,
        patient_id: patientIdFromUrl,
        patient_name: nextPatientName,
        patient_fio: nextPatientName,
        phone: (matchingAppointment.patient_phone as string | undefined) || prev?.phone || '',
        number: nextAppointmentId || prev?.number || patientIdFromUrl,
        source: 'appointments',
        status: (matchingAppointment.status as string | null) ?? null,
        payment_status: (matchingAppointment.payment_status as string | null) ?? null,
        discount_mode: (matchingAppointment.discount_mode as string | undefined) || prev?.discount_mode,
        specialty: (matchingAppointment.specialty as string | undefined) || prev?.specialty || 'cardiology'
      };

      const didChange =
        prev?.appointment_id !== nextPatient.appointment_id ||
        prev?.visit_id !== nextPatient.visit_id ||
        prev?.status !== nextPatient.status ||
        prev?.payment_status !== nextPatient.payment_status ||
        prev?.source !== nextPatient.source;

      // RETRO-3963-01 (independent re-review): this effect is synchronous
      // and prev-guarded — it merges compatible appointment context and
      // never switches the selection's patient identity. It must NOT touch
      // the navigation epoch: a bump here (previously inside this updater,
      // also a render-phase side effect that violated updater purity) let
      // a background queueUpdated status refresh cancel an in-flight human
      // click — the doctor's click silently did nothing. Human navigation
      // wins over this background sync simply by committing later (its
      // post-await rechecks still pass because no ticket was taken).
      return didChange ? nextPatient : prev;
    });
  }, [appointments, patientIdFromUrl, visitIdFromUrl, setSelectedPatient]);

  // Функция для получения всех услуг пациента из всех записей
  const getAllPatientServicesCb = useCallback((patientId: string | number | null | undefined, allAppointments: Record<string, unknown>[]) => {
    return getAllPatientServices(patientId, allAppointments);
  }, []);

  // Загрузка записей текущего кардиолога по каноническому Doctor.id.
  // CARDAPPT-FE-001 (audit 3886 round 24): sequence guard — every load takes
  // a generation ticket; a stale snapshot (poll, event, or refresh response
  // that resolves after a newer one) can no longer overwrite the newer
  // appointments state, error flag or loading flag.
  const appointmentsEpochRef = useRef(0);
  const loadMacOSCardiologyAppointments = useCallback(async (_silent?: boolean) => {
    const epoch = ++appointmentsEpochRef.current;
    setAppointmentsLoading(true);
    setAppointmentsError(false);
    try {
      const currentDoctorId = await resolveCurrentDoctorId();
      const { data } = await apiClient.get('/registrar/queues/today');
      if (epoch !== appointmentsEpochRef.current) return;
      const selectedEntries = selectEntriesForSpecialist(data, currentDoctorId);
      const seenIds = new Set<string>();
      const appointmentsData: Record<string, unknown>[] = [];

      selectedEntries.forEach(({ queue, entry }) => {
        const appointmentId = entry.appointment_id || null;
        const doctorQueueEntryId = resolveDoctorQueueEntryId(entry);
        const recordKey = `${entry.patient_id}_${entry.canonical_record_id || entry.id}_${queue.specialty}`;
        if (seenIds.has(recordKey)) return;
        seenIds.add(recordKey);

        const patientEntry = entry.patient as Record<string, unknown> | undefined;
        appointmentsData.push({
          id: entry.id,
          appointment_id: appointmentId,
          visit_id: entry.visit_id || null,
          patient_id: entry.patient_id,
          patient_fio: entry.patient_name || `${patientEntry?.first_name || ''} ${patientEntry?.last_name || ''}`.trim(),
          patient_phone: entry.phone || '',
          patient_birth_year: entry.patient_birth_year || '',
          address: entry.address || '',
          visit_type:
            entry.discount_mode === 'repeat' ? tI18nRef.current('cardio.cardio_panel_visit_type_repeat') :
            entry.discount_mode === 'benefit' ? tI18nRef.current('cardio.cardio_panel_visit_type_benefit') :
            entry.discount_mode === 'all_free' ? 'All Free' :
            tI18nRef.current('cardio.cardio_panel_visit_type_paid'),
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
          doctor: queue.specialist_name || tI18nRef.current('cardio.cardio_panel_doctor_fallback'),
          specialty: queue.specialty,
          ...adaptTimeFields(entry, data),
          status: entry.status ?? null,
          cost: entry.cost || 0,
        });
      });

        // Добавляем информацию о всех услугах пациента в каждую запись
      const enrichedAppointmentsData = appointmentsData.map((apt) => {
        const allPatientServices = getAllPatientServicesCb(
          apt.patient_id as string | number | null | undefined,
          appointmentsData,
        );
        return {
          ...apt,
          all_patient_services: (allPatientServices as { services?: unknown[]; service_codes?: unknown[] }).services,
          all_patient_service_codes: (allPatientServices as { services?: unknown[]; service_codes?: unknown[] }).service_codes,
        };
      });

      setAppointments(enrichedAppointmentsData);
    } catch {
      if (epoch === appointmentsEpochRef.current) setAppointmentsError(true);
    } finally {
      if (epoch === appointmentsEpochRef.current) setAppointmentsLoading(false);
    }
  }, [getAllPatientServicesCb, resolveCurrentDoctorId]);

  // CARDAPPT-FE-001: one coalesced refresh per queueUpdated burst — a
  // debounced single reload (the 500 ms delay gives the backend time to
  // settle statuses) that replaces any pending timer instead of stacking
  // an immediate call plus an uncancellable delayed one.
  const appointmentsRefreshTimerRef = useRef<number | null>(null);
  const scheduleAppointmentsRefresh = useCallback(() => {
    if (appointmentsRefreshTimerRef.current !== null) {
      window.clearTimeout(appointmentsRefreshTimerRef.current);
    }
    appointmentsRefreshTimerRef.current = window.setTimeout(() => {
      appointmentsRefreshTimerRef.current = null;
      loadMacOSCardiologyAppointments();
    }, 500);
  }, [loadMacOSCardiologyAppointments]);

  // Загружаем записи при переключении на вкладку
  useEffect(() => {
    if (activeTab === 'patients' || activeTab === 'appointments' || shouldHydrateAppointmentContext) {
      loadMacOSCardiologyAppointments();
    }

    // Слушаем глобальные события обновления очереди
    // CARDAPPT-FE-001: coalesced — every queueUpdated event (including
    // visitCompleted / nextPatientCalled) schedules exactly ONE debounced
    // refresh while the appointments context is active. The epoch guard in
    // the loader drops out-of-order snapshots; the cleanup cancels a
    // pending timer on tab switch or unmount.
    const handleQueueUpdate = () => {
      if (activeTab === 'patients' || activeTab === 'appointments' || shouldHydrateAppointmentContext) {
        scheduleAppointmentsRefresh();
      }
    };
    window.addEventListener('queueUpdated', handleQueueUpdate);

    return () => {
      window.removeEventListener('queueUpdated', handleQueueUpdate);
      if (appointmentsRefreshTimerRef.current !== null) {
        window.clearTimeout(appointmentsRefreshTimerRef.current);
        appointmentsRefreshTimerRef.current = null;
      }
    };
  }, [activeTab, loadMacOSCardiologyAppointments, scheduleAppointmentsRefresh, shouldHydrateAppointmentContext]);

  // Функция для получения данных пациента по ID
  // CARDPAT-FE-001 (audit 3886 round 24): the numeric threshold (IDs at or
  // above 1000) «demo patient» shortcut is removed. Backend patient IDs are
  // unbounded integers and the backend is the only authority on whether a
  // patient exists (REG-FE-036 precedent): a legal patient must actually be
  // fetched, and a 404 or a network failure is an explicit backend answer,
  // never a silent demo classification.
  const fetchPatientData = useCallback(async (patientId: string | number) => {
    const token = tokenManager.getAccessToken();
    if (!token) return null;

    try {
      const response = await fetch(`${API_V1_BASE}/patients/${patientId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        return await response.json();
      }
    } catch (error: unknown) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_patient_data_load_failed')));
    }
    return null;
  }, []);

  // Функция для преобразования данных пациента из формата API в формат PatientModal
  // CARDPAT-FE-002 (audit 3886 round 24): emits the FLAT edit contract that
  // EditPatientModal → AppointmentWizardV2 actually reads in edit mode
  // (patient_fio / patient_birth_date / patient_birth_year / patient_id).
  // The previous camelCase-only shape (firstName/lastName/birthDate) was
  // never read by the modal or the wizard, so a fully hydrated patient
  // opened the edit form with a blank FIO and birth date and an unchanged
  // save was blocked by FIO validation. Backend GET /patients/{id} stays
  // the SSOT; nothing is invented here.
  const transformPatientData = useCallback((apiPatient: Record<string, unknown> | null) => {
    if (!apiPatient) return null;

    const fio = [apiPatient.last_name, apiPatient.first_name, apiPatient.middle_name]
      .map((part) => String(part ?? '').trim())
      .filter(Boolean)
      .join(' ');
    const birthDate = apiPatient.birth_date ? String(apiPatient.birth_date) : '';

    return {
      id: apiPatient.id,
      patient_id: apiPatient.id,
      patient_fio: fio,
      patient_birth_date: birthDate,
      patient_birth_year: birthDate ? Number.parseInt(birthDate.slice(0, 4), 10) || null : null,
      phone: apiPatient.phone || '',
      address: apiPatient.address || '',
      gender: apiPatient.sex === 'M' ? 'male' : apiPatient.sex === 'F' ? 'female' : '',
      sex: apiPatient.sex ?? '',
      email: apiPatient.email || '',
      passport: apiPatient.doc_number || ''
    };
  }, []);

  // Функция для создания частичного объекта пациента из данных row (для QR-пациентов)
  // УПРОЩЕНО: Не нормализуем ФИО здесь - это делает backend (Single Source of Truth)
  // Просто преобразуем данные для отображения
  const createPartialPatientFromRow = useCallback((row: Record<string, unknown>) => {
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
  const handleEditPatient = useCallback(async (row: Record<string, unknown>) => {
    // CARDPAT-FE-003: this run's ticket. A newer edit intent or a modal
    // close bumps the epoch and invalidates every pending resolution below.
    const epoch = ++editPatientEpochRef.current;

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
      const apiPatient = await fetchPatientData(row.patient_id as string | number);
      if (epoch !== editPatientEpochRef.current) return;

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

    } catch (error: unknown) {
      if (epoch !== editPatientEpochRef.current) return;
      const partialPatient = createPartialPatientFromRow(row);
      setEditPatientModal({ open: true, patient: partialPatient, loading: false });
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_patient_card_load_failed')));
    }
  }, [fetchPatientData, transformPatientData, createPartialPatientFromRow]);

  // Обработчики для таблицы записей
  const handleAppointmentRowClick = async (row: Record<string, unknown>) => {
    // Можно открыть детали записи или переключиться на прием
    if (row.patient_fio) {
      preloadVisitTab();
      // CARDVISIT-FE-001: this click's navigation ticket.
      const epoch = ++navigationEpochRef.current;
      const appointmentId = row.appointment_id || null;
      const visitId = await ensureCanonicalVisitId(row);
      if (epoch !== navigationEpochRef.current) return;
      if (!visitId) {
        notify.error(tI18n('cardio.no_visit_id'));
        return;
      }

      const patientData: SelectedPatient = {
        id: row.id as string | number | undefined,
        appointment_id: (appointmentId as string | number | null) ?? null,
        visit_id: visitId,
        patient_id: row.patient_id as string | number | undefined,
        patient_name: row.patient_fio as string,
        phone: row.patient_phone as string | undefined,
        number: row.id as string | number | undefined,
        doctor_queue_entry_id: resolveDoctorQueueEntryId(row),
        source: 'appointments',
        status: (row.status as string | null) ?? null,
        payment_status: (row.payment_status as string | null) ?? null,
        discount_mode: row.discount_mode as string | undefined,
        specialty: (row.specialty as string) || 'cardiology'
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

      // RETRO-3963-01: loadEMR is another async boundary — the tab switch
      // belongs to this click only if no newer selection happened meanwhile.
      if (epoch !== navigationEpochRef.current) return;
      goToTab('visit');
    }
  };

  // C-3 fix: cancel appointment with confirm dialog + backend call.
  // Previously the 'cancel' action was a no-op stub — the button rendered
  // but did nothing, leaving the doctor with no feedback.
  const handleCancelAppointment = async (row: Record<string, unknown> | null) => {
    const ok = await confirm({
      title: tI18n('cardio.cancel_appointment_title'),
      message: tI18n('cardio.cancel_appointment_message', { name: ((row?.patient_fio || row?.patient_name || '') as string).trim() }),
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
    } catch (error: unknown) {
      logger.error('[Cardiology] Ошибка отмены записи:', error);
      notify.error(getErrorMessage(error) || tI18n('cardio.cardio_panel_appointment_cancel_failed'));
    } finally {
      setLoading(false);
    }
  };

  const handleAppointmentActionClick = async (action: string, row: Record<string, unknown>) => {
    // Note: `event` here is the legacy `window.event` global — preserved
    // for runtime parity. Guard with optional chaining so strict mode is
    // satisfied without changing runtime behavior.
    (event as Event | undefined)?.stopPropagation?.();

    switch (action) {
      case 'view':
        await handleAppointmentRowClick(row);
        break;
      case 'view_emr':{
          preloadVisitTab();
          // Просмотр EMR для завершённой записи
          // CARDVISIT-FE-001: this action's navigation ticket.
          const epoch = ++navigationEpochRef.current;
          const appointmentId = row.appointment_id || null;
          const visitId = await ensureCanonicalVisitId(row);
          if (epoch !== navigationEpochRef.current) break;
          if (!visitId) {
            notify.error(tI18n('cardio.emr_no_visit_id'));
            break;
          }

          // Создаем объект пациента
          const patientData: SelectedPatient = {
            id: row.id as string | number | undefined,
            appointment_id: (appointmentId as string | number | null) ?? null,
            visit_id: visitId,
            patient_id: row.patient_id as string | number | undefined,
            patient_name: row.patient_fio as string,
            phone: row.patient_phone as string | undefined,
            number: row.id as string | number | undefined,
            doctor_queue_entry_id: resolveDoctorQueueEntryId(row),
            source: 'appointments',
            status: (row.status as string | null) ?? null,
            payment_status: (row.payment_status as string | null) ?? null,
            discount_mode: row.discount_mode as string | undefined,
            specialty: (row.specialty as string) || 'cardiology'
          };

          setSelectedPatient(patientData);

          // Загружаем EMR
          await loadEMR(visitId);

          // RETRO-3963-01: recheck after the EMR fetch — a newer selection
          // must keep its own tab.
          if (epoch !== navigationEpochRef.current) break;
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
            notify.success(tI18n('cardio.cardio_panel_patient_called', { name: row.patient_fio as string }));
          }
        } catch (error: unknown) {
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
          notify.success(printResult?.message || tI18n('cardio.cardio_panel_ticket_printed', { name: row.patient_fio as string }));
        } catch (error: unknown) {
          notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_ticket_print_failed')));
        }
        break;
      case 'complete':{
          preloadVisitTab();
          // Завершить приём
          // CARDVISIT-FE-001: this action's navigation ticket.
          const epoch = ++navigationEpochRef.current;
          try {
            const visitId = await ensureCanonicalVisitId(row);
            if (epoch !== navigationEpochRef.current) break;
            if (!visitId) {
              notify.error(tI18n('cardio.no_visit_id_for_complete'));
              break;
            }
            // Переходим на вкладку визита для завершения
            const patient: SelectedPatient = {
              id: row.id as string | number | undefined,
              appointment_id: (row.appointment_id as string | number | null) ?? null,
              visit_id: visitId,
              patient_id: row.patient_id as string | number | undefined,
              patient_name: row.patient_fio as string,
              phone: row.patient_phone as string | undefined,
              number: row.id as string | number | undefined,
              doctor_queue_entry_id: resolveDoctorQueueEntryId(row),
              source: 'appointments',
              status: 'in_cabinet',
              payment_status: (row.payment_status as string | null) ?? null,
              discount_mode: row.discount_mode as string | undefined,
              specialty: (row.specialty as string) || 'cardiology'
            };

            setSelectedPatient(patient);

            // Загружаем EMR если есть
            await loadEMR(patient.visit_id);

            // RETRO-3963-01: recheck after the EMR fetch — a newer selection
            // must keep its own tab.
            if (epoch !== navigationEpochRef.current) break;
            // Переходим на вкладку visit для завершения
            goToTab('visit');
          } catch (error: unknown) {
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

  // Обработка сохранения визита
  const handleSaveVisit = async (savedEMRData: Record<string, unknown>) => {
    if (!selectedPatient) return;

    // DOCFLOW-FE-002 (audit 3886): snapshot the queue-entry/patient identity
    // BEFORE the async confirm boundary so the completion can be re-verified
    // against the live selection after the dialog resolves.
    const completionIdentity = {
      queueEntryId: resolveDoctorQueueEntryId(selectedPatient),
      patientId: selectedPatient.patient?.id ?? selectedPatient.patient_id ?? selectedPatient.id ?? null,
    };
    if (completionIdentity.queueEntryId === null) {
      notify.error(tI18n('cardio.no_queue_id_for_visit'));
      return;
    }

    const complaint = emrTextValue(savedEMRData.complaints);
    const diagnosis = emrTextValue(savedEMRData.diagnosis);
    const legacyDiagnosis = savedEMRData.diagnosis && typeof savedEMRData.diagnosis === 'object'
      ? savedEMRData.diagnosis as Record<string, unknown>
      : null;
    const icd10 = emrTextValue(savedEMRData.icd10_code) || emrTextValue(legacyDiagnosis?.icd10_code);
    const notes = emrTextValue(savedEMRData.notes);

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
    const hasDiagnosis = Boolean(diagnosis.trim());
    const hasComplaint = Boolean(complaint.trim());
    const missingCritical = !hasDiagnosis || !hasComplaint;
    const criticalWarning = getCriticalDiagnosisWarning(icd10);

    let confirmOptions: Record<string, unknown>;
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

    // DOCFLOW-FE-002 (audit 3886): the confirm dialog is an async boundary —
    // the selection may have changed while it was pending. Bind the
    // completion to the snapshotted queue-entry/patient identity and abort
    // (no POST, no UI reset) when the panel has moved to another patient;
    // otherwise a stale handler could complete A and wipe B's state
    // (dermatology's isSameDermatologyVisit recheck is the repo reference).
    const currentSelection = selectedPatientRef.current;
    if (
      String(resolveDoctorQueueEntryId(currentSelection)) !== String(completionIdentity.queueEntryId) ||
      String(currentSelection?.patient?.id ?? currentSelection?.patient_id ?? currentSelection?.id ?? null) !== String(completionIdentity.patientId)
    ) {
      logger.warn('[Cardiology] Selection changed during completion confirmation — aborting stale completion');
      return;
    }

    try {
      setLoading(true);

      const visitPayload = {
        patient_id: completionIdentity.patientId,
        complaint,
        diagnosis,
        icd10,
        services: selectedServices,
        notes,
      };
      // DOCFLOW-FE-001 (audit 3886): only a confirmed `success: true` DTO
      // completes the visit in the UI. An ambiguous (unreadable 2xx) or
      // rejected response keeps the clinical state intact; the ambiguous
      // branch additionally reconciles the visible queue with the canonical
      // server snapshot instead of blindly retrying.
      const completionAck = await queueService.completeVisit(completionIdentity.queueEntryId, visitPayload);
      if (completionAck?.success !== true) {
        const ackMessage = (completionAck as { message?: unknown } | undefined)?.message;
        notify.error(
          (typeof ackMessage === 'string' && ackMessage) || tI18n('cardio.cardio_panel_action_failed')
        );
        if ((completionAck as { unknown?: unknown } | undefined)?.unknown === true) {
          // Ambiguous outcome — refresh the visible queue from the server.
          void loadMacOSCardiologyAppointments(true);
        }
        return;
      }

      // DOCFLOW-FE-004 (post-merge review of PR 3902, P1): the completion
      // POST is itself an async boundary — the selection may have moved to
      // another patient while the request was in flight (row click, deep
      // link, Escape). The completion belongs to the CAPTURED identity: a
      // stale ack must not wipe the newer patient's state, must not switch
      // the tab, and must not auto-call the next queue entry over the
      // newer context (dermatology's DERMACOMPLETE-FE-002 recheck is the
      // repo reference).
      const postCompletionSelection = selectedPatientRef.current;
      if (
        String(resolveDoctorQueueEntryId(postCompletionSelection)) !== String(completionIdentity.queueEntryId) ||
        String(postCompletionSelection?.patient?.id ?? postCompletionSelection?.patient_id ?? postCompletionSelection?.id ?? null) !== String(completionIdentity.patientId)
      ) {
        logger.warn('[Cardiology] Stale completion response ignored for a changed selection — the newer patient\'s state is preserved');
        return;
      }
      notify.success(tI18n('cardio.visit_completed'));

      // Очищаем форму и возвращаемся в очередь
      // RETRO-3963-01: completion deselect is an authoritative selection
      // change — invalidate in-flight navigation tickets.
      navigationEpochRef.current += 1;
      setSelectedPatient(null);
      setSelectedServices([]);
      setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
      setActiveTab('queue');

      // Автоматически вызвать следующего пациента для кардиолога
      try {
        const next = await queueService.callNextWaiting(SPECIALTY_KEYS.CARDIOLOGY);
        if (next?.success && next.entry) {
          notify.success(tI18n('cardio.cardio_panel_next_patient_called', { number: (next.entry as Record<string, unknown>).number }));
        }
      } catch (err) {
        notify.warning(getErrorMessage(
          err,
          tI18n('cardio.cardio_panel_next_patient_call_failed')
        ));
      }

    } catch (error: unknown) {
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
  const loadEMR = async (visitId: string | number | null | undefined) => {
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

    // RETRO-3963-01 (review 3968 + independent re-review): the fetched EMR
    // belongs to the navigation intent that requested it. If the doctor
    // switched the selected patient while this fetch was in flight, a late
    // setEmr would display the previous patient's record under the new
    // selection — every post-await branch rechecks the ticket, including
    // the catch block (no error toast for a patient the doctor left).
    const epoch = navigationEpochRef.current;
    try {
      const response = await fetch(`${API_V1_BASE}/v2/emr/${visitId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });
      if (epoch !== navigationEpochRef.current) return null;

      if (response.ok) {
        const emrData = await response.json();
        if (epoch !== navigationEpochRef.current) return null;
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
      if (epoch !== navigationEpochRef.current) return null;
      logger.warn('[Cardiology] loadEMR: client error', { visitId, status: response.status, errorPayload });
      notify.error(getErrorMessage(errorPayload, tI18n('cardio.cardio_panel_emr_load_failed')));
      setEmr(null);
      return null;
    } catch (error: unknown) {
      // AbortError happens when the parent component aborted the fetch
      // (e.g. visitId changed) — not a user-facing error.
      if ((error as Error)?.name === 'AbortError') {
        logger.info('[Cardiology] loadEMR: aborted', { visitId });
        return null;
      }
      // RETRO-3963-01 (independent re-review): a stale fetch that fails
      // must not toast an error for a patient the doctor is no longer
      // viewing.
      if (epoch !== navigationEpochRef.current) return null;
      logger.error('[Cardiology] loadEMR: network error', { visitId, error: getErrorMessage(error) || error });
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_emr_load_failed')));
      return null;
    }
  };

  // Сохранение EMR
  // (P-019 useEffect was moved above the isDemoMode early return
  //  to satisfy the rules-of-hooks lint rule — see the effect that calls
  //  loadEMR(visitId) on selectedPatient/authRefreshTick changes above
  //  handleSaveVisit.)































































































  // Обработка завершения приема через EMR
  const handleCompleteVisitFromEMR = async (savedEMRData: Record<string, unknown>) => {
    if (!selectedPatient) return;

    try {
      await handleSaveVisit(savedEMRData);
    } catch (error: unknown) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_complete_visit_emr_failed')));
    }
  };

  const handleEMRCompletionBlocked = () => {
    notify.error(tI18n('cardio.cardio_panel_complete_visit_emr_failed'));
  };

  // Обработка анализов крови
  const handleBloodTestSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
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
      interpretation: String(bloodTestForm.interpretation ?? '').trim() || null
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
    } catch (error: unknown) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_blood_test_save_failed')));
    }
  };


  const getHistoryTimestampValue = (value: unknown) => {
    if (!value) {
      return 0;
    }

    const parsed = new Date(value as string | number | Date);
    return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime();
  };

  const formatFileSize = (size: number | unknown) => {
    if (!size && size !== 0) {
      return '—';
    }

    const numericSize = Number(size);
    if (!Number.isFinite(numericSize)) {
      return '—';
    }

    if (numericSize < 1024) {
      return `${numericSize} B`;
    }

    if (numericSize < 1024 * 1024) {
      return `${(numericSize / 1024).toFixed(1)} KB`;
    }

    return `${(numericSize / (1024 * 1024)).toFixed(1)} MB`;
  };

  const canPreviewAttachment = (file: Record<string, unknown> | null | undefined) => {
    const mimeType = String(file?.mime_type || file?.type || '').toLowerCase();
    return mimeType.startsWith('image/') || mimeType.startsWith('text/') || mimeType === 'application/pdf';
  };

  const downloadPatientFile = async (file: Record<string, unknown> | null | undefined) => {
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
      link.download = (file.title as string) || (file.original_filename as string) || (file.filename as string) || `file-${file.id}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error: unknown) {
      notify.error(getErrorMessage(error, tI18n('cardio.cardio_panel_download_failed')));
    }
  };

  const previewPatientFile = (file: Record<string, unknown> | null | undefined): void => {
    if (!file?.id) {
      return;
    }

    // CARDHIST-FE-001 (audit 3886): delegate to the honest preview
    // transport — the browsing context is reserved synchronously inside
    // the click gesture, opener isolation is preserved by severing the
    // opener before navigation, and a successful open is never reported
    // as blocked (the old code treated the `noopener` null return —
    // which happens on SUCCESS — as a popup block).
    void openPatientFilePreview({
      apiBase: API_V1_BASE,
      fileId: file.id as string | number,
      getAccessToken: () => tokenManager.getAccessToken(),
      onNotifyError: (message) => notify.error(message),
      messages: {
        previewUnavailable: tI18n('cardio.cardio_panel_preview_unavailable_short'),
        previewBlocked: tI18n('cardio.cardio_panel_preview_blocked_short'),
        openFailed: tI18n('cardio.cardio_panel_open_file_failed'),
      },
    });
  };

  const historyEntries = [
    ...bloodTests.map((test) => ({
      id: `blood-${test.id}`,
      kind: 'labs',
      title: tI18n('cardio.cardio_panel_blood_test_title', { date: test.test_date || '—' }),
      subtitle: tI18n('cardio.cardio_panel_blood_test_subtitle', { total: test.cholesterol_total || '—', ldl: test.cholesterol_ldl || '—', glucose: test.glucose || '—' }),
      timestamp: (test.test_date || test.created_at || test.updated_at) as string | number | Date | null,
      badgeVariant: 'secondary',
      meta: (test.interpretation as string | null | undefined) || tI18n('cardio.cardio_panel_blood_test_meta', { id: test.id }),
    })),
    ...ecgResults.map((result) => ({
      id: `ecg-${result.id || result.ecg_date}`,
      kind: 'ecg',
      title: tI18n('cardio.cardio_panel_ecg_title', { date: result.ecg_date || '—' }),
      subtitle: tI18n('cardio.cardio_panel_ecg_subtitle', { rhythm: result.rhythm || '—', heart_rate: result.heart_rate || '—' }),
      timestamp: (result.ecg_date || result.created_at || result.updated_at) as string | number | Date | null,
      badgeVariant: 'success',
      meta: (result.source as string | null | undefined) || tI18n('cardio.cardio_panel_ecg_meta', { id: result.id || '—' }),
    })),
    ...visitHistory.map((visit) => {
      const when = (visit.finished_at || visit.started_at || visit.planned_date || visit.created_at) as string | null | undefined;
      const doctorName = (visit.doctor_name as string | null | undefined) || tI18n('cardio.cardio_panel_doctor_fallback');
      return {
        id: `visit-${visit.id}`,
        kind: 'visits',
        title: tI18n('cardio.cardio_panel_visit_history_title', { date: when || '—' }),
        subtitle: doctorName,
        timestamp: (when || null) as string | number | Date | null,
        badgeVariant: 'primary',
        meta: null,
      };
    }),
    ...patientFiles.map((file) => {
      const fileLabel = (file.title || file.original_filename || file.filename || file.name || tI18n('cardio.cardio_panel_file_label', { id: file.id })) as string;
      const tags = Array.isArray(file.tags) && file.tags.length > 0 ? (file.tags as unknown[]).join(', ') : '';
      const fileType = (file.file_type || file.mime_type || file.type || 'attachment') as string;

      return {
        id: `file-${file.id}`,
        kind: 'attachments',
        title: fileLabel,
        subtitle: `${fileType}${tags ? ` • ${tags}` : ''}`,
        timestamp: (file.created_at || file.updated_at || file.uploaded_at) as string | number | Date | null,
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
    { value: 'visits', label: tI18n('cardio.cardio_panel_filter_visits'), count: visitHistory.length },
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

  // Cardioplan slice 4: picking a patient from the search results selects
  // them for the whole panel (visit history + medical history). No visit or
  // queue context is attached — visits are opened from the queue screen, so
  // this selection only feeds history views and read-only context.
  const handlePatientSearchPick = (patient: PatientSearchResult) => {
    // RETRO-3963-01 (review 3968): picking a patient from search is an
    // authoritative selection. It must invalidate any appointment-path
    // navigation ticket still awaiting ensureCanonicalVisitId/loadEMR,
    // otherwise that late resolution would steal this selection.
    navigationEpochRef.current += 1;
    setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
    setSelectedPatient({
      id: patient.id,
      patient_id: patient.id,
      visit_id: null,
      patient_name: patient.full_name,
      phone: patient.phone || '',
      number: patient.id,
      source: 'patient_search',
      status: null,
      specialty: 'cardiology',
    });
  };

  const handleDoctorQueueStartVisit = (entry: CardiologyQueueEntry, result: { patient_id?: number | null; visit_id?: number | null }) => {
    // RETRO-3963-01 (review 3968): starting a visit from the queue is an
    // authoritative selection — same invalidation contract as the
    // appointment paths, or a late appointment resolution could steal it.
    navigationEpochRef.current += 1;
    preloadVisitTab();
    setEmr(null);
    setSelectedPatient({
      id: entry.id,
      patient_id: result.patient_id,
      visit_id: result.visit_id,
      patient_name: entry.patient_name || '',
      phone: entry.phone || '',
      number: entry.number ?? entry.id,
      doctor_queue_entry_id: entry.id,
      source: 'doctor_queue',
      status: 'in_progress',
      specialty: 'cardiology',
    });
    // Synchronous path: no await between the epoch invalidation above and
    // this tab switch, so no post-await recheck is needed. If an await is
    // ever inserted here, take a ticket (++navigationEpochRef) at entry and
    // recheck after each await (RETRO-3963-01 protocol).
    goToTab('visit');
  };

  const handleDoctorQueueOpenVisit = async (entry: CardiologyQueueEntry, completed: boolean) => {
    if (entry.patient_id == null || entry.visit_id == null) return;

    // RETRO-3963-01 (review 3968): this open-visit selection owns the
    // navigation intent from entry to the final goToTab — a late EMR fetch
    // or appointment resolution must not steal the tab afterwards.
    const epoch = ++navigationEpochRef.current;
    preloadVisitTab();
    setSelectedPatient({
      id: entry.id,
      patient_id: entry.patient_id,
      visit_id: entry.visit_id,
      patient_name: entry.patient_name || '',
      phone: entry.phone || '',
      number: entry.number ?? entry.id,
      doctor_queue_entry_id: entry.id,
      source: 'doctor_queue',
      status: completed ? 'completed' : entry.status,
      specialty: 'cardiology',
    });

    if (completed) {
      await loadEMR(entry.visit_id);
    } else {
      setEmr(null);
    }
    // RETRO-3963-01: recheck after the EMR fetch — a newer selection must
    // keep its own tab.
    if (epoch !== navigationEpochRef.current) return;
    goToTab('visit');
  };

  // Keep this dynamic JSX slot as `any`; narrowing its inferred result to a
  // ReactNode currently makes the legacy parent fail strict child checking.
  const cardiologyQueuePanel: any = activeTab === 'queue'
    ? createElement(CardiologyQueueTab, {
      onStartVisit: handleDoctorQueueStartVisit,
      onOpenVisit: (entry, completed) => { void handleDoctorQueueOpenVisit(entry, completed); },
    })
    : null;

  const tabLoadingFallback = (
    <Card role="status" aria-live="polite" className="cardio-card-fullwidth">
      {tI18n('common.loading')}
    </Card>
  );

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
            <Suspense fallback={tabLoadingFallback}>
              <PatientSearch
                onPick={handlePatientSearchPick}
                selectedPatientId={(selectedPatient?.patient_id ?? selectedPatient?.id ?? null) as string | number | null}
              />
              <AppointmentsTab
                appointments={appointments}
                appointmentsLoading={appointmentsLoading}
                appointmentsError={appointmentsError}
                appointmentSummaryItems={appointmentSummaryItems}
                onRefresh={loadMacOSCardiologyAppointments}
                onRowClick={(row) => { void handleAppointmentRowClick(row as Record<string, unknown>); }}
                onActionClick={(action, row) => { void handleAppointmentActionClick(action, row as Record<string, unknown>); }}
                services={services}
                isDark={isDark}
              />
            </Suspense>
          }

          {/* The queue screen reads only the authenticated doctor's own queue. */}
          {cardiologyQueuePanel}

          {/* Приём пациента — R-15: extracted to VisitTab component */}
          {activeTab === 'visit' &&
            <Suspense fallback={tabLoadingFallback}>
              <VisitTab
                selectedPatient={selectedPatient as unknown as {
                  patient_name?: string;
                  patient?: { full_name?: string; id?: number };
                  patient_id?: number;
                  number?: string | number;
                  phone?: string;
                  visit_id?: number | string;
                  status?: string | null;
                } | null}
                emr={emr}
                loading={loading}
                onCancel={() => {
                  // RETRO-3963-01: explicit close invalidates every in-flight
                  // navigation ticket — a late appointment/EMR resolution
                  // must not resurrect a closed visit screen.
                  navigationEpochRef.current += 1;
                  setSelectedPatient(null);
                  setActiveTab('queue');
                }}
                onComplete={handleCompleteVisitFromEMR}
                onCompletionBlocked={handleEMRCompletionBlocked}
                onGoToAppointments={() => goToTab('patients')}
                getColor={getColor}
                getFontSize={getFontSize}
              />
            </Suspense>
          }

          {/* ЭКГ — R-15: extracted to EcgTab component */}
          {activeTab === 'ecg' &&
            <Suspense fallback={tabLoadingFallback}>
              <EcgTab
                selectedPatient={selectedPatient}
                onAddEcg={() => setShowForm({ open: true, type: 'ecg' })}
                onDataUpdate={loadPatientData}
                getSpacing={getSpacing}
              />
            </Suspense>
          }

          {/* CARDIO-FE-001 (audit 3886 round 20): dedicated manual ECG form.
              The old flow reused <BloodTestsTab showFormOpen /> here, which
              rendered blood-test inputs and POSTed null ECG parameters. */}
          {/* RETRO-3941-01: keyed by the canonical patient+visit identity so
              a selection switch can never reuse the previous patient's
              local form state under the new patient's props. */}
          {showForm.open && showForm.type === 'ecg' && (
            <ManualEcgForm
              key={`manual-ecg-${((selectedPatient?.patient?.id || selectedPatient?.patient_id) ?? 'none')}-${(selectedPatient?.visit_id ?? 'none')}`}
              patientId={((selectedPatient?.patient?.id || selectedPatient?.patient_id) as string | number | null | undefined) ?? null}
              visitId={(selectedPatient?.visit_id ?? null) as string | number | null}
              onCancel={() => setShowForm({ open: false })}
              onSaved={() => {
                setShowForm({ open: false });
                loadPatientData();
              }}
            />
          )}

          {/* Анализы крови — R-15: extracted to BloodTestsTab component */}
          {activeTab === 'blood' &&
            <BloodTestsTab
              bloodTests={bloodTests}
              bloodTestForm={bloodTestForm}
              setBloodTestForm={setBloodTestForm}
              showFormOpen={Boolean(showForm.open) && showForm.type === 'blood'}
              onNewTest={openBloodTestForm}
              onCancelForm={() => setShowForm({ open: false, type: 'blood' })}
              onSubmit={handleBloodTestSubmit}
              getEmptyBloodTestForm={getEmptyBloodTestForm}
              getFieldRangeWarning={getFieldRangeWarning}
              isLdlCritical={isLdlCritical}
              settings={settings}
              onLdlThresholdChange={(value: number) => setSettings({ ...settings, ldlThreshold: value })}
              getColor={getColor}
              getFontSize={getFontSize}
              getSpacing={getSpacing}
            />
          }

          {/* AI Помощник — R-15: extracted to AiTab component.
              Cardioplan slice 4: read-only — no apply button, no success
              notify; suggestions are applied inside the EMR editor. */}
          {activeTab === 'ai' &&
            <AiTab />
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
          patient={scheduleNextModal.patient ?? undefined}
          theme={{ isDark, getColor, getSpacing, getFontSize }}
          specialtyFilter="cardiology" />

        }

        {/* Модальное окно редактирования пациента */}
        {editPatientModal.open &&
        <Suspense fallback={
          <div className="cardio-modal-overlay" role="status" aria-live="polite">
            <div className="cardio-modal-card">{tI18n('common.loading')}</div>
          </div>
        }>
          <EditPatientModal
            isOpen={editPatientModal.open}
            onClose={closeEditPatientModal}
            patient={editPatientModal.patient ?? undefined}
            onSave={async () => {
              await loadMacOSCardiologyAppointments();
              closeEditPatientModal();
            }}
            loading={editPatientModal.loading}
            theme={{ isDark, getColor, getSpacing, getFontSize }} />
        </Suspense>

        }

        {/* QW-10 (UX audit): portal-mounted ConfirmDialog used before completing a visit */}
        {confirmDialog}

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

      {/* X-13: AIChatWidget removed — AiTab in sidebar provides the same functionality */}

      </div>
    </div>);

};

export default MacOSCardiologistPanelUnified;
