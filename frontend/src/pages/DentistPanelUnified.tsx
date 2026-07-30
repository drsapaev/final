import { lazy, Suspense, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import './dentistry.css';
import { useLocation } from 'react-router-dom';
// P-009 fix: shared doctor panel state hook
import { useDoctorPanelState } from '../hooks/useDoctorPanelState';
import { useTheme } from '../contexts/ThemeContext';
import { adaptTimeFields } from '../utils/registrarAggregation';
import { getLocalDateString, parseRegistrarTimestamp } from '../utils/dateUtils';
import {
  Button, Badge, Card,
  Input } from '../components/ui/macos';
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
import ExaminationForm from '../components/dental/ExaminationForm';
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
  XCircle,
  Save } from
'lucide-react';
import '../styles/animations.css';
import { getApiBaseUrl } from '../api/runtime';
import { resolveCanonicalVisitId } from '../utils/canonicalVisit';
import { printPanelTicket } from '../services/panelPrint';
import notify from '../services/notify';
// STRAT#34: useTranslation adapter for confirm/notify i18n.
import { useTranslation } from '../i18n/useTranslation';
import type { Appointment } from '../types/domain/clinic';
import type { Patient } from '../types/domain/clinic';
import { useConfirm } from '../components/common/ConfirmDialog';
import { useSessionTimeoutWarning } from '../hooks/useSessionTimeoutWarning';
import { useDentalHotkeys } from '../hooks/useDentalHotkeys';
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
import { getErrorMessage } from '../utils/type-guards';

const LazyReportsAndAnalytics = lazy(() => import('../components/dental/ReportsAndAnalytics'));

/**
 * Loose shape for the doctor-panel `selectedPatient` state object.
 * The shared `useDoctorPanelState` hook keeps `selectedPatient` typed as
 * `null` (its useState is declared without an explicit generic, and the
 * runtime payload is built ad-hoc from API/queue rows). Until the hook
 * ships a proper type, the panel casts its return through this alias.
 */
type SelectedPatient = {
  id?: string | number | null;
  appointment_id?: string | number | null;
  visit_id?: string | number | null;
  patient_id?: string | number | null;
  patient_name?: string;
  patient_fio?: string;
  name?: string;
  phone?: string;
  number?: string | number | null;
  doctor_queue_entry_id?: string | number | null;
  queue_entry_id?: string | number | null;
  source?: string;
  status?: string | null;
  specialty?: string;
  patient?: { id?: string | number; full_name?: string; name?: string; [k: string]: unknown } | null;
  visitData?: Record<string, unknown> | null;
  examinationData?: Record<string, unknown> | null;
  diagnosisData?: Record<string, unknown> | null;
  photoArchive?: Record<string, unknown> | null;
  dentalChart?: Record<string, unknown> | null;
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

const API_V1_BASE = getApiBaseUrl();
const DENTISTRY_WAITING_STATUSES = ['waiting', 'confirmed', 'pending'];
const DENTISTRY_CALLED_STATUSES = ['called', 'in_progress'];
const DENTISTRY_COMPLETED_STATUSES = ['completed', 'done'];
let dentistAppointmentsCache: Appointment[] | null = null;
let dentistAppointmentsLoadPromise: Promise<Appointment[]> | null = null;
let dentistServicesCache: Record<string, unknown> | null = null;
let dentistServicesLoadPromise: Promise<Record<string, unknown> | null> | null = null;
const dentistVisitProtocolsCache = new Map<string, Record<string, unknown>[]>();
const dentistVisitProtocolsLoadPromises = new Map<string, Promise<Record<string, unknown>[]>>();
const dentistFallbackLoggedKeys = new Set<string>();

// audit/phase-1, BS-42: invalidation helper for the 7 module-level caches.
// Previously these caches were never invalidated on patient switch, so on
// rapid visit-to-visit navigation the panel showed the previous patient's
// appointments / services (PHI leak between patients on a shared workstation).
// `useVisitLifecycle` already aborts in-flight requests and clears the
// cacheService layer; this helper additionally clears the panel-local
// module-level singletons so the next render refetches from the backend.
function invalidateDentistPanelCaches() {
  dentistAppointmentsCache = null;
  dentistAppointmentsLoadPromise = null;
  dentistServicesCache = null;
  dentistServicesLoadPromise = null;
  dentistVisitProtocolsCache.clear();
  dentistVisitProtocolsLoadPromises.clear();
  // Note: dentistFallbackLoggedKeys intentionally retained — it only guards
  // against duplicate log noise, holds no PHI, and clearing it would resurface
  // log spam on the next visit to the same patient.
}

// countAppointmentsByStatuses and normalizeNumericId are imported from
// utils/doctorPanelShared (unified across Cardiology / Dermatology / Dentistry).

function resolveDoctorQueueEntryId(row: Record<string, unknown> | null | undefined): string | number | null {
  const explicitQueueEntryId = row?.doctor_queue_entry_id ?? row?.queue_entry_id ?? null;
  if (explicitQueueEntryId !== null && explicitQueueEntryId !== undefined) {
    return explicitQueueEntryId as string | number;
  }

  return null;
}

function buildPatientsFromAppointments(
  appointments: Appointment[] | null | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
): SelectedPatient[] {
  const patientsById = new Map<string | number, SelectedPatient>();

  (appointments ?? []).forEach((appointment: Appointment) => {
    const patientId = appointment.patient_id || appointment.id;
    if (!patientId || patientsById.has(patientId)) {
      return;
    }

    const patientName =
      appointment.patient_fio || appointment.patient_name || (appointment.name as string | undefined) || t('dental.dental_panel_patient_default');

    patientsById.set(patientId, {
      id: patientId,
      patient_id: patientId,
      appointment_id: (appointment.appointment_id as string | number | null | undefined) || null,
      visit_id: normalizeNumericId(appointment.visit_id),
      name: patientName,
      patient_name: patientName,
      patient_fio: patientName,
      phone: (appointment.patient_phone as string) || (appointment.phone as string) || '',
      specialty: (appointment.specialty as string) || 'dentistry',
      source: (appointment.source as string) || 'appointments',
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
  }) as DoctorPanelState;

  const handleCardKeyDown = useCallback((event: React.KeyboardEvent<HTMLElement>, action: () => void) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  }, []);
  const [patients, setPatients] = useState<SelectedPatient[]>([]);
  // Phase 4+ cleanup: treatmentPlans/prosthetics state removed (dead UI).
  const [loading, setLoading] = useState(true);
  // P-009: selectedPatient / setSelectedPatient now come from useDoctorPanelState
  const [savedVisitProtocols, setSavedVisitProtocols] = useState<Record<string, unknown>[]>(
    () => loadStoredDentistDocuments().visitProtocols
  );
  const [scheduleNextModal, setScheduleNextModal] = useState<{ open: boolean; patient: SelectedPatient | Record<string, unknown> | null }>({ open: false, patient: null });
  const [protocolTemplateDraft, setProtocolTemplateDraft] = useState<SelectedPatient | null>(null);

  // Состояния для таблицы записей
  const [appointmentsTableData, setAppointmentsTableData] = useState<Appointment[]>([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [services, setServices] = useState<Record<string, unknown>>({});
  const appointmentsTableDataRef = useRef<Appointment[]>([]);
  const appointmentsLoadPromiseRef = useRef<Promise<Appointment[]> | null>(null);
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
  const [dentalChartData, setDentalChartData] = useState<Record<string, unknown> | null>(null);

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
  // Состояние для DentalPriceManager
  const [showPriceManager, setShowPriceManager] = useState(false);
  const [selectedServiceForPrice, setSelectedServiceForPrice] = useState<{ id?: string | number; name?: string; price?: number; [key: string]: unknown } | null>(null);
  const [selectedTooth, setSelectedTooth] = useState<{ number: string | number; data: unknown } | string | number | null>(null);
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
    } catch (error: unknown) {
      logger.warn('[Dentist] Не удалось сохранить локальные протоколы визита:', error);
    }
  }, [savedVisitProtocols]);

  useEffect(() => {
    appointmentsTableDataRef.current = appointmentsTableData;
  }, [appointmentsTableData]);

  const loadDentistVisitProtocolsForPatient = useCallback(async (patient: SelectedPatient | Record<string, unknown> | null) => {
    const patientRecord = (patient ?? {}) as Record<string, unknown>;
    const nestedPatient = patientRecord.patient as { id?: string | number; [k: string]: unknown } | undefined;
    const patientId = nestedPatient?.id || patientRecord.patient_id || patientRecord.id || null;
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
      patientName: patientRecord.patient_name as string || patientRecord.patient_fio as string || patientRecord.name as string || 'Пациент',
    });

    const loadPromise = (async () => {
      try {
        const response = await apiClient.get(`/v2/emr/patient/${patientId}`, {
          params: { limit: 20 },
          silent: true,
        } as Record<string, unknown>);

        const summaries: Record<string, unknown>[] = Array.isArray(response.data) ? response.data : [];
        const records = await Promise.all(
          summaries.map(async (summary) => {
            try {
              const emrResponse = await apiClient.get(`/v2/emr/${summary.visit_id}`, {
                silent: true,
                validateStatus: (status: number) => status === 404 || (status >= 200 && status < 300),
              } as Record<string, unknown>);

              if (emrResponse.status === 404) {
                return null;
              }

              const protocolRecord = mapDentistVisitProtocolFromEmr(
                emrResponse.data,
                patient as Record<string, unknown> | null,
              );

              if (!protocolRecord) {
                return null;
              }

              return protocolRecord;
            } catch (error: unknown) {
              logger.warn('[Dentist] Не удалось загрузить EMR визита для протокола', {
                patientId,
                visitId: summary.visit_id,
                error: getErrorMessage(error) || error,
              });
              return null;
            }
          })
        );

        const filteredRecords = records.filter((r): r is Record<string, unknown> => Boolean(r));
        dentistVisitProtocolsCache.set(cacheKey, filteredRecords);
        return filteredRecords;
      } catch (error: unknown) {
        dentistVisitProtocolsCache.delete(cacheKey);
        throw error;
      } finally {
        dentistVisitProtocolsLoadPromises.delete(cacheKey);
      }
    })();

    dentistVisitProtocolsLoadPromises.set(cacheKey, loadPromise);
    return loadPromise;
  }, []);

  const loadDentistVisitProtocolByVisitId = useCallback(async (visitId: string | number | null | undefined, patient: SelectedPatient | Record<string, unknown> | null = null) => {
    if (!visitId) {
      return null;
    }

    try {
      const response = await apiClient.get(`/v2/emr/${visitId}`, {
        silent: true,
        validateStatus: (status: number) => status === 404 || (status >= 200 && status < 300),
      } as Record<string, unknown>);

      if (response.status === 404) {
        return null;
      }

      const protocolRecord = mapDentistVisitProtocolFromEmr(response.data, patient as Record<string, unknown> | null);
      if (!protocolRecord) {
        return null;
      }

      logger.info('[Dentist] Протокол визита загружен из EMR v2', {
        visitId,
        emrId: response.data?.id,
        status: response.data?.status,
      });

      return protocolRecord;
    } catch (error: unknown) {
      logger.warn('[Dentist] Не удалось загрузить протокол визита из EMR v2', {
        visitId,
        error: getErrorMessage(error) || error,
      });
      return null;
    }
  }, []);

  // Формы данных
  const [examinationForm, setExaminationForm] = useState<Record<string, string>>({
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
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;
  // STRAT#34: useTranslation adapter for confirm/notify i18n.
  const { t: tI18n } = useTranslation();
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
        const response = await apiClient.get('/registrar/services');
        if (response.status < 400) {
          const data = response.data;
          const servicesData = data.services_by_group || {};
          dentistServicesCache = servicesData;
          setServices(servicesData);
          logger.info('[Dentist] Услуги загружены:', Object.keys(servicesData).length, 'групп');
          return servicesData;
        }

        return null;
      } catch (error: unknown) {
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
  const getAllPatientServicesCb = useCallback((patientId: string | number | null | undefined, allAppointments: Appointment[] | null | undefined) => {
    return getAllPatientServices(patientId, allAppointments as unknown as Array<Record<string, unknown>> | null | undefined);
  }, []);

  // Загрузка записей стоматолога
  const loadDentistryAppointments = useCallback(async (forceRefresh = false): Promise<Appointment[]> => {
    if (!forceRefresh && dentistAppointmentsCache) {
      appointmentsTableDataRef.current = dentistAppointmentsCache;
      setAppointmentsTableData(dentistAppointmentsCache);
      setPatients((prev) => {
        const derivedPatients = buildPatientsFromAppointments(dentistAppointmentsCache, tI18n);
        return derivedPatients.length > 0 ? derivedPatients : prev;
      });
      return dentistAppointmentsCache;
    }

    if (appointmentsLoadPromiseRef.current || dentistAppointmentsLoadPromise) {
      return (appointmentsLoadPromiseRef.current || dentistAppointmentsLoadPromise) as Promise<Appointment[]>;
    }

    const loadPromise = (async (): Promise<Appointment[]> => {
      setAppointmentsLoading(true);
      try {
        const token = tokenManager.getAccessToken();
        if (!token) {
          logger.info('Нет токена аутентификации');
          return [];
        }

        // Загружаем ВСЕ очереди для получения полной картины услуг пациентов
        const response = await apiClient.get('/registrar/queues/today');

        if (response.status < 400) {
          const data = response.data as Record<string, unknown>;

          // Собираем ВСЕ записи из всех очередей для получения полной картины услуг
          const allAppointments: Appointment[] = [];
          if (data && data.queues && Array.isArray(data.queues)) {
            (data.queues as Record<string, unknown>[]).forEach((queue) => {
              const entries = queue?.entries as Record<string, unknown>[] | undefined;
              if (entries) {
                entries.forEach((entry) => {
                  const doctorQueueEntryId = resolveDoctorQueueEntryId(entry);
                  const patientObj = entry.patient as { first_name?: string; last_name?: string; [k: string]: unknown } | undefined;
                  const entryWithTimes = { ...entry, ...adaptTimeFields(entry, data) };
                  allAppointments.push({
                    id: entry.id as string | number,
                    appointment_id: (entry.appointment_id as string | number | null | undefined) || null,
                    visit_id: (entry.visit_id as string | number | null | undefined) || null,
                    patient_id: entry.patient_id as string | number,
                    patient_fio: (entry.patient_name as string) || `${patientObj?.first_name || ''} ${patientObj?.last_name || ''}`.trim(),
                    patient_phone: (entry.phone as string) || '',
                    patient_birth_year: (entry.patient_birth_year as number | undefined) || undefined,
                    address: (entry.address as string) || '',
                    visit_type:
                      entry.discount_mode === 'repeat' ? tI18n('dental.dental_panel_discount_repeat') :
                      entry.discount_mode === 'benefit' ? tI18n('dental.dental_panel_discount_benefit') :
                      entry.discount_mode === 'all_free' ? 'All Free' :
                      tI18n('dental.dental_panel_discount_paid'),
                    discount_mode: (entry.discount_mode as string) || 'none',
                    services: (entry.services as unknown as Appointment['services']) || [],
                    service_codes: (entry.service_codes as string[]) || [],
                    payment_type: (entry.payment_type as string) || null,
                    payment_status: (entry.payment_status as string | undefined) ?? null,
                    available_actions: (entry.available_actions as unknown[]) || [],
                    can_mark_paid: Boolean(entry.can_mark_paid),
                    can_start_visit: Boolean(entry.can_start_visit) && doctorQueueEntryId !== null,
                    can_print_ticket: Boolean(entry.can_print_ticket),
                    can_complete: Boolean(entry.can_complete) && doctorQueueEntryId !== null,
                    can_cancel: Boolean(entry.can_cancel),
                    queue_entry_id: (entry.queue_entry_id as string | number | null | undefined) ?? null,
                    doctor_queue_entry_id: doctorQueueEntryId,
                    canonical_record_id: (entry.canonical_record_id as string | number | undefined) || entry.id as string | number,
                    record_kind: entry.record_kind,
                    source_kind: entry.source_kind,
                    canonical_status: (entry.canonical_status as string | null | undefined) ?? null,
                    queue_status: (entry.queue_status as string | null | undefined) ?? null,
                    queue_position: entry.queue_position,
                    doctor: (entry.doctor_name as string) || tI18n('dental.dental_panel_doctor_default'),
                    specialty: queue.specialty as string,
                    ...entryWithTimes,
                    status: (entry.status as string | null | undefined) ?? null,
                    cost: (entry.cost as number) || 0
                  } as unknown as Appointment);
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
          const derivedPatients = buildPatientsFromAppointments(enrichedAppointmentsData, tI18n);
            return derivedPatients.length > 0 ? derivedPatients : prev;
          });
          return enrichedAppointmentsData;
        }

        logger.error('Ошибка загрузки очередей:', response.status);
        return [];
      } catch (error: unknown) {
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
  }, [getAllPatientServicesCb, tI18n]);

  // Загружаем записи при переключении на вкладку
  useEffect(() => {
    if (activeTab === 'appointments') {
      loadDentistryAppointments();
    }

    // Слушаем глобальные события обновления очереди
    const handleQueueUpdate = (event: Event) => {
      const customEvent = event as CustomEvent<unknown>;
      logger.info('[Dentist] Получено событие обновления очереди:', customEvent.detail);
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
    (row: Appointment | Record<string, unknown>) => makeEnsureCanonicalVisitId(setAppointmentsTableData as unknown as React.Dispatch<React.SetStateAction<unknown[]>>, resolveCanonicalVisitId)(row as Record<string, unknown>),
    []
  );

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
        doctor_queue_entry_id: resolveDoctorQueueEntryId(row as unknown as Record<string, unknown>),
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
          const queueEntryId = resolveDoctorQueueEntryId(row as unknown as Record<string, unknown>);
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
          const printResult = await printPanelTicket(row as unknown as Record<string, unknown>, {
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
            doctor_queue_entry_id: resolveDoctorQueueEntryId(row as unknown as Record<string, unknown>),
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

  const authHeader = useCallback(() => ({
    Authorization: `Bearer ${tokenManager.getAccessToken()}`
  }), []);

  const loadPatients = useCallback(async () => {
    try {
      const derivedPatients = buildPatientsFromAppointments(appointmentsTableDataRef.current, tI18n);
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
        tI18n,
      );

      if (refreshedPatients.length > 0) {
        setPatients(refreshedPatients);
      }
    } catch (e: unknown) {
      logger.error('Ошибка загрузки пациентов:', e);
    }
  }, [loadDentistryAppointments, tI18n]);

  const loadTreatmentPlans = useCallback(async () => {
    try {
      // PR-43 / Medium-24: stub cleaned up. Treatment plans endpoint not yet
      // implemented in backend. This function is kept as a no-op placeholder
      // so the UI hook wiring remains stable when the endpoint ships.
      logger.debug('Treatment plans endpoint pending backend implementation');
    } catch {



      // Игнорируем ошибки загрузки планов лечения
    }}, []);const loadProsthetics = useCallback(async () => {
    try {
      // PR-43 / Medium-24: stub cleaned up. Prosthetics endpoint not yet
      // implemented in backend. This function is kept as a no-op placeholder
      // so the UI hook wiring remains stable when the endpoint ships.
      logger.debug('Prosthetics endpoint pending backend implementation');
    } catch {



      // Игнорируем ошибки загрузки протезирования
    }}, []);const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // PR-35 / P0-14: Removed duplicate loadPatients() call — was calling
      // Promise.all([loadPatients(), loadPatients()]) which fetched the
      // patient list twice on every mount.
      await Promise.all([
        loadPatients(),
        loadServices(),
      ]);
    } catch (error: unknown) {
      logger.error('Ошибка загрузки данных:', error);
    } finally {
      setLoading(false);
    }
  }, [loadPatients, loadServices]);

  useEffect(() => {
    loadData();
  }, [loadData]);

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
      } catch (error: unknown) {
        logger.warn('[Dentist] Не удалось синхронизировать историю протоколов из EMR v2', {
          patientId: selectedPatientIdForProtocols,
          error: getErrorMessage(error) || error,
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
          if (!dentistFallbackLoggedKeys.has(fallbackLogKey)) {
            dentistFallbackLoggedKeys.add(fallbackLogKey);
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























  const handleExamination = (patient: SelectedPatient | Record<string, unknown> | null) => {
    const patientId = resolvePatientId(patient);
    setSelectedPatient({
      ...(patient as Record<string, unknown>),
      patient_id: patientId,
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    } as SelectedPatient);
    setExaminationForm({ ...examinationForm, patient_id: String(patientId ?? '') });
    setShowExaminationForm(true);
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

  const persistVisitProtocol = useCallback(async (patient: SelectedPatient | Record<string, unknown> | null, visitData: Record<string, unknown>) => {
    const patientRecord = (patient ?? {}) as Record<string, unknown>;
    if (!patientRecord.visit_id) {
      return;
    }

    const nestedPatient = patientRecord.patient as { id?: string | number; [k: string]: unknown } | undefined;
    const patientId = nestedPatient?.id || patientRecord.patient_id || patientRecord.id || null;
    const patientName = (patientRecord.patient_name as string) || (patientRecord.patient_fio as string) || (patientRecord.name as string) || tI18n('dental.dental_panel_patient_default');
    const localRecord = buildDentistVisitProtocolCard(patient, visitData, {
      source: 'local_cache',
    });

    try {
      const payload = buildDentistVisitProtocolSaveRequest(patient, visitData, {
        isDraft: true,
        rowVersion: 0,
      });
      logger.info('[Dentist] Сохраняю протокол визита в EMR v2', {
        visitId: patientRecord.visit_id,
        patientId,
      });

      const response = await apiClient.post(`/v2/emr/${patientRecord.visit_id}`, payload);
      const backendRecord = mapDentistVisitProtocolFromEmr(response.data, patient as Record<string, unknown> | null) || localRecord;

      setSavedVisitProtocols((prev) => upsertDentistVisitProtocol(prev, backendRecord));
      return backendRecord;
    } catch (error: unknown) {
      logger.warn('[Dentist] Не удалось сохранить протокол визита в EMR v2, сохраняю локальный кеш', {
        visitId: patientRecord.visit_id,
        patientName,
        error: getErrorMessage(error) || error,
      });

      setSavedVisitProtocols((prev) => upsertDentistVisitProtocol(prev, localRecord));
      return localRecord;
    }
  }, [tI18n]);

  const reopenVisitProtocol = useCallback(async (protocolRecord: Record<string, unknown> | null) => {
    const backendProtocol = await loadDentistVisitProtocolByVisitId(protocolRecord?.visit_id as string | number | null | undefined, protocolRecord);

    if (!backendProtocol && !protocolRecord?.visitData) {
      notify.error(tI18n('dental.protocol_not_found'));
      return;
    }

    const selectedProtocol = (backendProtocol || protocolRecord) as Record<string, unknown>;
    setSelectedPatient({
      id: (selectedProtocol.patient_id as string | number | null) || (protocolRecord?.patient_id as string | number | null) || null,
      patient_id: (selectedProtocol.patient_id as string | number | null) || (protocolRecord?.patient_id as string | number | null) || null,
      patient_name: (selectedProtocol.patient_name as string) || (protocolRecord?.patient_name as string) || tI18n('dental.dental_panel_patient_default'),
      patient_fio: (selectedProtocol.patient_name as string) || (protocolRecord?.patient_name as string) || tI18n('dental.dental_panel_patient_default'),
      visit_id: (selectedProtocol.visit_id as string | number | null) || (protocolRecord?.visit_id as string | number | null) || null,
      visitData: (selectedProtocol.visitData as Record<string, unknown> | null) || (protocolRecord?.visitData as Record<string, unknown> | null) || null,
      source: (selectedProtocol.source as string) || (protocolRecord?.source as string) || 'reports',
    } as SelectedPatient);
    setShowVisitProtocol(true);
  }, [loadDentistVisitProtocolByVisitId, setSelectedPatient, tI18n]);

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

  // Обработчики отправки форм
  const handleExaminationSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      const res = await apiClient.post('/dental/examinations', examinationForm);
      if (res.status < 400) {
        setShowExaminationForm(false);
        setExaminationForm({
          patient_id: '', examination_date: '', oral_hygiene: '', caries_status: '',
          periodontal_status: '', occlusion: '', missing_teeth: '', dental_plaque: '',
          gingival_bleeding: '', diagnosis: '', recommendations: ''
        });
        loadDentistryAppointments(true);
      }
    } catch (e: unknown) {
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


  // Рендер осмотров
  const renderExaminations = () =>
  <div className="dental-flex-col dental-gap-24">
      <Card padding="large">
        <h3 className="dental-text-primary">{tI18n('dental.dental_panel_examinations_title')}</h3>
        <p className="dental-text-desc dental-text-secondary">
          {tI18n('dental.dental_panel_examinations_subtitle')}
        </p>

        <div className="dental-grid-auto-fill-250">
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label={tI18n('dental.dental_panel_aria_examination')}
          className="dental-card-btn"
          onClick={() => handleExamination(patient)}
          onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleCardKeyDown(event, () => handleExamination(patient))}
          onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
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
                  <p className="dental-text-desc dental-text-secondary">{tI18n('dental.dental_panel_examination_action')}</p>
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
          patient={selectedPatient as unknown as Record<string, unknown>}
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

      {showExaminationForm && selectedPatient &&
      <ExaminationForm
        patientId={selectedPatientId}
        initialData={selectedPatient.examinationData}
        onSave={(examinationData: unknown) => {
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

      {/* Форма осмотра */}
      {showExaminationForm && selectedPatient &&
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg w-full max-w-4xl h-full max-h-[90vh] overflow-auto">
            <div className="p-6 border-b">
              <h2 className="text-xl font-semibold">
                {tI18n('dental.dental_panel_exam_form_title', { name: selectedPatientDisplayName })}
              </h2>
            </div>
            <div className="p-6">
              <form onSubmit={handleExaminationSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium var(--mac-text-primary) mb-2">{tI18n('dental.dental_panel_exam_label_date')}</label>
                    <Input
                    type="date"
                    aria-label={tI18n('dental.dental_panel_exam_aria_date')}
                    value={examinationForm.examination_date}
                    onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setExaminationForm({ ...examinationForm, examination_date: e.target.value })}
                    required
                    className="w-full px-3 py-2 border var(--mac-border) rounded-md  var(--mac-accent) " />

                  </div>
                  <div>
                    <label className="block text-sm font-medium var(--mac-text-primary) mb-2">{tI18n('dental.dental_panel_exam_label_hygiene')}</label>
                    <select
                    value={examinationForm.oral_hygiene}
                    onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setExaminationForm({ ...examinationForm, oral_hygiene: e.target.value })}
                    className="w-full px-3 py-2 border var(--mac-border) rounded-md  var(--mac-accent) ">

                      <option value="">{tI18n('dental.dental_panel_option_select')}</option>
                      <option value="excellent">{tI18n('dental.dental_panel_hygiene_excellent')}</option>
                      <option value="good">{tI18n('dental.dental_panel_hygiene_good')}</option>
                      <option value="fair">{tI18n('dental.dental_panel_hygiene_fair')}</option>
                      <option value="poor">{tI18n('dental.dental_panel_hygiene_poor')}</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium var(--mac-text-primary) mb-2">{tI18n('dental.dental_panel_exam_label_caries')}</label>
                    <select
                    value={examinationForm.caries_status}
                    onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setExaminationForm({ ...examinationForm, caries_status: e.target.value })}
                    className="w-full px-3 py-2 border var(--mac-border) rounded-md  var(--mac-accent) ">

                      <option value="">{tI18n('dental.dental_panel_option_select')}</option>
                      <option value="none">{tI18n('dental.dental_panel_caries_none')}</option>
                      <option value="initial">{tI18n('dental.dental_panel_caries_initial')}</option>
                      <option value="superficial">{tI18n('dental.dental_panel_caries_superficial')}</option>
                      <option value="medium">{tI18n('dental.dental_panel_caries_medium')}</option>
                      <option value="deep">{tI18n('dental.dental_panel_caries_deep')}</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium var(--mac-text-primary) mb-2">{tI18n('dental.dental_panel_exam_label_periodontal')}</label>
                    <select
                    value={examinationForm.periodontal_status}
                    onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setExaminationForm({ ...examinationForm, periodontal_status: e.target.value })}
                    className="w-full px-3 py-2 border var(--mac-border) rounded-md  var(--mac-accent) ">

                      <option value="">{tI18n('dental.dental_panel_option_select')}</option>
                      <option value="healthy">{tI18n('dental.dental_panel_periodontal_healthy')}</option>
                      <option value="gingivitis">{tI18n('dental.dental_panel_periodontal_gingivitis')}</option>
                      <option value="periodontitis">{tI18n('dental.dental_panel_periodontal_periodontitis')}</option>
                      <option value="advanced">{tI18n('dental.dental_panel_periodontal_advanced')}</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium var(--mac-text-primary) mb-2">{tI18n('dental.dental_panel_exam_label_occlusion')}</label>
                    <select
                    value={examinationForm.occlusion}
                    onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setExaminationForm({ ...examinationForm, occlusion: e.target.value })}
                    className="w-full px-3 py-2 border var(--mac-border) rounded-md  var(--mac-accent) ">

                      <option value="">{tI18n('dental.dental_panel_option_select')}</option>
                      <option value="normal">{tI18n('dental.dental_panel_occlusion_normal')}</option>
                      <option value="open_bite">{tI18n('dental.dental_panel_occlusion_open')}</option>
                      <option value="deep_bite">{tI18n('dental.dental_panel_occlusion_deep')}</option>
                      <option value="cross_bite">{tI18n('dental.dental_panel_occlusion_cross')}</option>
                      <option value="crowding">{tI18n('dental.dental_panel_occlusion_crowding')}</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium var(--mac-text-primary) mb-2">{tI18n('dental.dental_panel_exam_label_missing')}</label>
                    <Input
                    type="text"
                    aria-label={tI18n('dental.dental_panel_exam_aria_missing')}
                    value={examinationForm.missing_teeth}
                    onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setExaminationForm({ ...examinationForm, missing_teeth: e.target.value })}
                    placeholder={tI18n('dental.dental_panel_exam_placeholder_missing')}
                    className="w-full px-3 py-2 border var(--mac-border) rounded-md  var(--mac-accent) " />

                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium var(--mac-text-primary) mb-2">{tI18n('dental.dental_panel_exam_label_plaque')}</label>
                    <select
                    value={examinationForm.dental_plaque}
                    onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setExaminationForm({ ...examinationForm, dental_plaque: e.target.value })}
                    className="w-full px-3 py-2 border var(--mac-border) rounded-md  var(--mac-accent) ">

                      <option value="">{tI18n('dental.dental_panel_option_select')}</option>
                      <option value="none">{tI18n('dental.dental_panel_plaque_none')}</option>
                      <option value="minimal">{tI18n('dental.dental_panel_plaque_minimal')}</option>
                      <option value="moderate">{tI18n('dental.dental_panel_plaque_moderate')}</option>
                      <option value="heavy">{tI18n('dental.dental_panel_plaque_heavy')}</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium var(--mac-text-primary) mb-2">{tI18n('dental.dental_panel_exam_label_bleeding')}</label>
                    <select
                    value={examinationForm.gingival_bleeding}
                    onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setExaminationForm({ ...examinationForm, gingival_bleeding: e.target.value })}
                    className="w-full px-3 py-2 border var(--mac-border) rounded-md  var(--mac-accent) ">

                      <option value="">{tI18n('dental.dental_panel_option_select')}</option>
                      <option value="none">{tI18n('dental.dental_panel_bleeding_none')}</option>
                      <option value="mild">{tI18n('dental.dental_panel_bleeding_mild')}</option>
                      <option value="moderate">{tI18n('dental.dental_panel_bleeding_moderate')}</option>
                      <option value="severe">{tI18n('dental.dental_panel_bleeding_severe')}</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium var(--mac-text-primary) mb-2">{tI18n('dental.dental_panel_exam_label_diagnosis')}</label>
                  <textarea
                  aria-label={tI18n('dental.dental_panel_exam_aria_diagnosis')}
                  value={examinationForm.diagnosis}
                  onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setExaminationForm({ ...examinationForm, diagnosis: e.target.value })}
                  placeholder={tI18n('dental.dental_panel_exam_placeholder_diagnosis')}
                  rows={3}
                  className="w-full px-3 py-2 border var(--mac-border) rounded-md  var(--mac-accent) " />

                </div>

                <div>
                  <label className="block text-sm font-medium var(--mac-text-primary) mb-2">{tI18n('dental.dental_panel_exam_label_recommendations')}</label>
                  <textarea
                  aria-label={tI18n('dental.dental_panel_exam_aria_recommendations')}
                  value={examinationForm.recommendations}
                  onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setExaminationForm({ ...examinationForm, recommendations: e.target.value })}
                  placeholder={tI18n('dental.dental_panel_exam_placeholder_recommendations')}
                  rows={3}
                  className="w-full px-3 py-2 border var(--mac-border) rounded-md  var(--mac-accent) " />

                </div>

                <div className="flex gap-2">
                  <Button type="submit" className="flex items-center gap-2">
                    <Save className="h-4 w-4" />
                    {tI18n('dental.dental_panel_exam_btn_save')}
                  </Button>
                  <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowExaminationForm(false)}>

                    {tI18n('dental.dental_panel_exam_btn_cancel')}
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
      {confirmDialog as unknown as React.ReactNode}

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
