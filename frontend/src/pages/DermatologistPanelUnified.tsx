import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import type { CSSProperties } from 'react';
import { useLocation } from 'react-router-dom';
// P-009 fix: shared doctor panel state hook
import { useDoctorPanelState } from '../hooks/useDoctorPanelState';
import { useLabDirtyGuard } from '../components/laboratory/LabDirtyGuardContext';
import { DERMATOLOGY_PANEL_TABS, getDermatologyTabAliases } from './dermatologyTabAliases';
// S-M-2 (история, ОТМЕНЕНО Track 3-2): macos-Icon обёртка → lucide refs (§3.3)
import { Button, Card, Badge, AppEmpty } from '../components/ui/macos';

import { useTheme } from '../contexts/ThemeContext';
import { adaptTimeFields } from '../utils/registrarAggregation';
import './dermatology.css';
import AppointmentSummaryBar from '../components/doctor/AppointmentSummaryBar';
import AIAssistant from '../components/ai/AIAssistant';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import SessionWarningModal from '../components/common/SessionWarningModal';
import EditPatientModal from '../components/common/EditPatientModal';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import QueueIntegration from '../components/QueueIntegration';
import { EMRContainerV2 } from '../components/emr-v2/EMRContainerV2';
import DermaPatientsTab from '../components/dermatology/DermaPatientsTab';
import DermaVisitGallery from '../components/dermatology/DermaVisitGallery';
import { useDermatologyPatientHistory } from './useDermatologyPatientHistory';
import PrescriptionSystem from '../components/PrescriptionSystem';
import VisitTimeline from '../components/VisitTimeline';
import { printPanelTicket } from '../services/panelPrint';
import { queueService } from '../services/queue';
import { printService } from '../services/print';
import { getApiBaseUrl } from '../api/runtime';
import { api } from '../api/client';  // PR-53: replace raw fetch with axios
import type { AxiosResponse } from 'axios';
import { resolveCanonicalVisitId } from '../utils/canonicalVisit';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
import notify from '../services/notify';
// STRAT#33: useTranslation adapter for confirm/notify i18n.
import { useTranslation } from '../i18n/useTranslation';
import i18n from '../i18n';
const i18nT = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;
import { useConfirm } from '../components/common/ConfirmDialog';
import { useSessionTimeoutWarning } from '../hooks/useSessionTimeoutWarning';
import { useDermaHotkeys } from '../hooks/useDermaHotkeys';
import {
  countAppointmentsByStatuses,
  getAllPatientServices,
  makeEnsureCanonicalVisitId,
  normalizeNumericId,
  SPECIALTY_KEYS,
} from '../utils/doctorPanelShared';
import { useVisitLifecycle } from '../hooks/useVisitLifecycle';
import { subscribe as subscribeAuth } from '../stores/auth';
import { useDermaQueueVisit } from './useDermaQueueVisit';
import {
  canCompleteDermatologyVisit,
  isSameDermatologyVisit,
  postDermatologyPrescription,
  toPrescriptionSystemRecord,
  toPrescriptionCreatePayload,
  type DermatologyVisitContext,
} from './dermatologyVisitActions';
import { Calendar, CheckCircle2, FileText, RotateCw, Stethoscope } from 'lucide-react';

const API_V1_BASE = getApiBaseUrl();
const DERMATOLOGY_REQUEST_COOLDOWN_MS = 5000;
const DERMATOLOGY_WAITING_STATUSES = ['waiting', 'confirmed', 'pending'];
const DERMATOLOGY_CALLED_STATUSES = ['called', 'in_progress'];
const DERMATOLOGY_COMPLETED_STATUSES = ['completed', 'done'];
const dermatologyAppointmentsHeaderStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  gap: 'var(--mac-spacing-4)',
  marginBottom: 'var(--mac-spacing-5)',
  flexWrap: 'wrap'
};
const dermatologyAppointmentsTitleStyle: CSSProperties = {
  fontSize: 'var(--mac-font-size-lg)',
  fontWeight: 'var(--mac-font-weight-semibold)',
  color: 'var(--mac-text-primary)',
  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
  display: 'flex',
  alignItems: 'center',
  margin: 0,
  minWidth: 'min(100%, 260px)'
};
// DERMACACHE-FE-001 (audit 3892): the module-scope queue/services cache is
// scoped to the authenticated principal. A principal change (staff logout
// + login without a hard document reload) must never reuse the previous
// principal's cached rows or in-flight promise — they carry PHI the new
// principal may not be entitled to see.
type DermatologyCacheEntry = {
  ownerKey: string | null;
  promise: Promise<unknown> | null;
  data: unknown;
  lastAttemptAt: number;
};
const dermatologyRequestCache: {
  appointments: DermatologyCacheEntry & { data: unknown[] | null };
  services: DermatologyCacheEntry & { data: Record<string, unknown> | null };
} = {
  appointments: { ownerKey: null, promise: null, data: null, lastAttemptAt: 0 },
  services: { ownerKey: null, promise: null, data: null, lastAttemptAt: 0 },
};

function dermatologyCacheOwnerKey(): string | null {
  const token = tokenManager.getAccessToken();
  return typeof token === 'string' && token ? token : null;
}

function resetDermatologyRequestCache(): void {
  dermatologyRequestCache.appointments = { ownerKey: null, promise: null, data: null, lastAttemptAt: 0 };
  dermatologyRequestCache.services = { ownerKey: null, promise: null, data: null, lastAttemptAt: 0 };
}

/**
 * DERMACACHE-FE-001: returns true when the cache entry still belongs to
 * the CURRENT principal; otherwise the entry is reset (promise + data
 * dropped) so the caller treats it as a miss and issues its own request.
 */
function ensureDermatologyCacheOwner(entry: DermatologyCacheEntry): boolean {
  const ownerKey = dermatologyCacheOwnerKey();
  if (ownerKey !== null && entry.ownerKey === ownerKey) {
    return true;
  }
  entry.ownerKey = ownerKey;
  entry.promise = null;
  entry.data = null;
  entry.lastAttemptAt = 0;
  return false;
}

interface DermatologyPatient {
  id?: number | string | null;
  patient_id?: number | string | null;
  appointment_id?: number | string | null;
  visit_id?: string | number | null;
  patient_name?: string;
  patient_fio?: string;
  name?: string;
  last_name?: string;
  first_name?: string;
  middle_name?: string;
  phone?: string;
  patient_phone?: string;
  birth_date?: string;
  patient_birth_year?: string | number;
  address?: string;
  specialty?: string;
  source?: string;
  status?: string | null;
  number?: number | string;
  doctor_queue_entry_id?: number | string | null;
  queue_entry_id?: number | string | null;
  patient?: { id?: number | string | null; [key: string]: unknown } | null;
  [key: string]: unknown;
}

interface DermatologyAppointment {
  id?: number | string;
  appointment_id?: number | string | null;
  patient_id?: number | string;
  patient_fio?: string;
  patient_name?: string;
  name?: string;
  last_name?: string;
  first_name?: string;
  middle_name?: string;
  phone?: string;
  patient_phone?: string;
  patient_birth_year?: string | number;
  address?: string;
  visit_type?: string;
  discount_mode?: string;
  services?: unknown[];
  service_codes?: unknown[];
  payment_type?: string | null;
  payment_status?: string | null;
  available_actions?: unknown[];
  can_mark_paid?: boolean;
  can_start_visit?: boolean;
  can_print_ticket?: boolean;
  can_complete?: boolean;
  can_cancel?: boolean;
  queue_entry_id?: number | string | null;
  doctor_queue_entry_id?: number | string | null;
  canonical_record_id?: number | string;
  record_kind?: string;
  source_kind?: string;
  canonical_status?: string | null;
  queue_status?: string | null;
  queue_position?: number;
  doctor?: string;
  specialty?: string;
  status?: string | null;
  cost?: number;
  visit_id?: number | string | null;
  all_patient_services?: unknown[];
  all_patient_service_codes?: unknown[];
  [key: string]: unknown;
}

// Queue entry shape returned by /registrar/queues/today, used by
// loadDermatologyAppointments to build DermatologyAppointment rows.
interface DermatologyQueueEntryItem {
  id?: number | string;
  appointment_id?: number | string | null;
  patient_id?: number | string;
  patient_name?: string;
  patient?: { first_name?: string; last_name?: string; [k: string]: unknown };
  phone?: string;
  patient_birth_year?: string | number;
  address?: string;
  discount_mode?: string;
  services?: unknown[];
  service_codes?: unknown[];
  payment_type?: string | null;
  payment_status?: string | null;
  available_actions?: unknown[];
  can_mark_paid?: boolean;
  can_start_visit?: boolean;
  can_print_ticket?: boolean;
  can_complete?: boolean;
  can_cancel?: boolean;
  queue_entry_id?: number | string | null;
  canonical_record_id?: number | string;
  record_kind?: string;
  source_kind?: string;
  canonical_status?: string | null;
  queue_status?: string | null;
  queue_position?: number;
  doctor_name?: string;
  status?: string | null;
  cost?: number;
  visit_id?: number | string | null;
  [key: string]: unknown;
}

// countAppointmentsByStatuses is imported from utils/doctorPanelShared
// (unified implementation shared with Cardiology and Dentistry panels).

function resolveDoctorQueueEntryId(row: Record<string, unknown>): number | string | null {
  const explicitQueueEntryId = row?.doctor_queue_entry_id ?? row?.queue_entry_id ?? null;
  if (explicitQueueEntryId !== null && explicitQueueEntryId !== undefined) {
    return explicitQueueEntryId as number | string;
  }

  return null;
}

function safeErrorMetadata(error: unknown): { errorType: string; statusCode?: number } {
  const value = error !== null && typeof error === 'object'
    ? error as { response?: { status?: unknown } }
    : null;
  const status = value?.response?.status;
  return {
    errorType: error instanceof Error ? error.name : typeof error,
    ...(typeof status === 'number' ? { statusCode: status } : {}),
  };
}

function getRecentDermatologyCache<T>(cacheEntry: { lastAttemptAt: number; data: T | null }, fallbackValue: T): T | null {
  if (cacheEntry.lastAttemptAt && Date.now() - cacheEntry.lastAttemptAt < DERMATOLOGY_REQUEST_COOLDOWN_MS) {
    return cacheEntry.data ?? fallbackValue;
  }
  return null;
}

// normalizeNumericId is imported from utils/doctorPanelShared
// (unified implementation shared with Cardiology and Dentistry panels).

function splitFullName(fullName: unknown) {
  const nameParts = String(fullName || '').trim().split(/\s+/).filter(Boolean);
  return {
    last_name: nameParts[0] || '',
    first_name: nameParts[1] || '',
    middle_name: nameParts[2] || ''
  };
}

function buildDermatologyPatientFromAppointment(appointment: Record<string, unknown> | null | undefined): DermatologyPatient | null {
  if (!appointment) {
    return null;
  }

  const patientId = (appointment.patient_id as number | string | null) || (appointment.id as number | string | null) || null;
  if (!patientId) {
    return null;
  }

  const patientName =
    (appointment.patient_fio as string) || (appointment.patient_name as string) || (appointment.name as string) || i18nT('derma.derma_panel_patient_default');
  const nameParts = splitFullName(patientName);

  return {
    id: patientId,
    patient_id: patientId,
    appointment_id: (appointment.appointment_id as number | string | null) || null,
    visit_id: normalizeNumericId(appointment.visit_id),
    patient_name: patientName,
    patient_fio: patientName,
    name: patientName,
    last_name: (appointment.last_name as string) || nameParts.last_name,
    first_name: (appointment.first_name as string) || nameParts.first_name,
    middle_name: (appointment.middle_name as string) || nameParts.middle_name,
    phone: (appointment.patient_phone as string) || (appointment.phone as string) || '',
    birth_date: (appointment.birth_date as string) || '',
    patient_birth_year: appointment.patient_birth_year as string | number | undefined,
    address: (appointment.address as string) || '',
    specialty: (appointment.specialty as string) || 'dermatology',
    source: (appointment.source as string) || 'appointments'
  };
}

/**
 * Унифицированная панель дерматолога
 * Объединяет: очередь + фото до/после + косметология + AI
 */
const DermatologistPanelUnified = () => {
  // Всегда вызываем хуки первыми
  const { isDark, getColor, getSpacing, getFontSize } = useTheme();
  // QW-5 (UX audit): confirm hook for visit completion
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw;
  // STRAT#33: useTranslation adapter for confirm/notify i18n.
  const { t: tI18n } = useTranslation();
  const t = tI18n as unknown as (key: string, options?: Record<string, unknown>) => string;
  const { guardTransition, hasPendingOperations } = useLabDirtyGuard();
  // QW-6 (UX audit): session timeout warning
  const [sessionWarning, setSessionWarning] = useState<{ active: boolean } | null>(null);

  useSessionTimeoutWarning({
    onWarning: () => setSessionWarning({ active: true }),
    onExpired: () => {
      setSessionWarning(null);
      notify.error(t('derma.session_expired'));
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    },
  });

  // DERMACACHE-FE-001 (audit 3892): reset the module-scope queue cache
  // whenever the authenticated principal changes (logout / login / 401
  // session sweep) so a new principal never reuses the previous one's
  // cached rows or in-flight promise.
  useEffect(() => {
    const reset = () => {
      resetDermatologyRequestCache();
      // Self-review (audit 3892 wave 2): the same-mounted component's
      // per-entry load promise must not be handed to the NEXT principal
      // before the module cache is consulted — drop it on auth change.
      appointmentsLoadPromiseRef.current = null;
    };
    const unsubscribe = subscribeAuth(reset);
    window.addEventListener('authStateChanged', reset);
    return () => {
      unsubscribe();
      window.removeEventListener('authStateChanged', reset);
    };
  }, []);

  // Deferred #2: keyboard shortcuts for tab switching, refresh, clear selection.
  useDermaHotkeys({
    handleTabChange: (tab: string) => {},
    refreshData: () => loadDermatologyAppointments(true),
    clearSelection: () => {
      if (hasPendingOperations) {
        notify.info(t('workbench.saving'));
        return;
      }

      // Escape is an in-panel state transition: use the shared dirty-source
      // registry without the route-history sentinel. Scope Discard to the
      // captured visit so a new EMR mounted while the dialog is open cannot
      // inherit the older visit's discard decision.
      const dialogVisitContext = currentVisitContextRef.current;
      const visitId = dialogVisitContext.visitId;
      const sourceIds = visitId === null || visitId === undefined || visitId === ''
        ? []
        : ['emr-visit-' + visitId];
      guardTransition(() => {
        if (!isSameDermatologyVisit(dialogVisitContext, currentVisitContextRef.current)) {
          return;
        }
        setSelectedPatient(null);
        setCurrentAppointment(null);
      }, { sourceIds, intentPolicy: 'leave' });
    },
  });
  const location = useLocation();
  // P-009: navigate removed — useDoctorPanelState handles tab URL sync
  const dermatologyTabAliases = useMemo(
    () => getDermatologyTabAliases(location.search),
    [location.search]
  );

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
    // Phase 4+: the sidebar has three destinations — queue / visit / patients.
    defaultTab: 'queue',
    visitDeepLinkTab: 'visit',
    patientDeepLinkTab: 'patients',
    validTabs: [...DERMATOLOGY_PANEL_TABS],
    tabAliases: dermatologyTabAliases,
  }) as {
    activeTab: string;
    setActiveTab: (tab: string) => void;
    handleTabChange: (tab: string) => void;
    patientIdFromUrl: number | null;
    visitIdFromUrl: number | null;
    selectedPatient: DermatologyPatient | null;
    setSelectedPatient: (patient: DermatologyPatient | null) => void;
  };
  const [visitData, setVisitData] = useState({
    complaint: '',
    diagnosis: '',
    icd10: '',
    notes: ''
  });
  const [loading, setLoading] = useState(false);
  const [scheduleNextModal, setScheduleNextModal] = useState<{ open: boolean; patient: DermatologyPatient | null }>({ open: false, patient: null });
  const [editPatientModal, setEditPatientModal] = useState<{ open: boolean; patient: Record<string, unknown> | null; loading: boolean }>({ open: false, patient: null, loading: false });

  // Состояния для таблицы записей
  const [appointments, setAppointments] = useState<DermatologyAppointment[]>([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [services, setServices] = useState<Record<string, unknown>>({});
  const appointmentsLoadPromiseRef = useRef<Promise<DermatologyAppointment[]> | null>(null);
  const urlResolutionRef = useRef({ search: '', refreshAttempted: false, refreshSettled: false, notified: false, appliedPair: null as { patientId: number | string | null; visitId: number | string | null } | null });
  // DERMAURL-FE-002 (audit 3892): monotonic generation for the deep-link
  // resolution — invalidates in-flight resolutions on unmount/re-run.
  const urlResolutionGenerationRef = useRef(0);


  // Дополнительные состояния из старого файла
  const [currentAppointment, setCurrentAppointment] = useState<DermatologyPatient | null>(null);
  const [emr, setEmr] = useState<Record<string, unknown> | null>(null);
  const [prescription, setPrescription] = useState<Record<string, unknown> | null>(null);
  const [canCreatePrescription, setCanCreatePrescription] = useState(false);
  const [appointmentCompletionStatus, setAppointmentCompletionStatus] = useState<{
    appointmentId: string;
    visitId: string | null;
    canComplete: boolean;
  } | null>(null);
  const statusRequestIdRef = useRef(0);

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
  useVisitLifecycle(lifecycleVisitId as unknown as string | number, lifecyclePatientId as unknown as string | number, {
    invalidateCacheOnChange: true,
    onCleanup: () => {
      // Reset local EMR + prescription state so stale data does not bleed
      // into the next visit's view. loadEMR / prescription endpoints will
      // be re-invoked by the existing useEffect when selectedPatient /
      // currentAppointment changes.
      setEmr(null);
      setPrescription(null);
      setAppointmentCompletionStatus(null);
    },
  });

  // Загрузка услуг для правильного отображения в tooltips
  const loadServices = useCallback(async (force = false) => {
    ensureDermatologyCacheOwner(dermatologyRequestCache.services);
    // Self-review (audit 3892 wave 2): capture the principal at launch — a
    // continuation that resolves after an auth change must not write the
    // previous principal's services into the new principal's state/cache.
    const ownerKeyAtLaunch = dermatologyCacheOwnerKey();
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

    const loadPromise = (async (): Promise<Record<string, unknown>> => {
      dermatologyRequestCache.services.lastAttemptAt = Date.now();
      try {
        const token = tokenManager.getAccessToken();
        if (!token) return {};
        const response = (await api.get('/registrar/services')) as AxiosResponse<Record<string, unknown>>;
        // Self-review (audit 3892 wave 2): stale continuation guard —
        // another principal owns the cache now; ignore this response.
        if (dermatologyCacheOwnerKey() !== ownerKeyAtLaunch) {
          return (dermatologyRequestCache.services.data as Record<string, unknown>) || {};
        }
        if (response.status < 400) {
          const data = response.data as Record<string, unknown>;
          const servicesData = (data.services_by_group as Record<string, unknown>) || {};
          setServices(servicesData);
          dermatologyRequestCache.services.data = servicesData as Record<string, unknown>;
          logger.info('[Dermatology] Услуги загружены:', Object.keys(servicesData).length, 'групп');
          return servicesData;
        }
        return (dermatologyRequestCache.services.data as Record<string, unknown>) || {};
      } catch (error: unknown) {
        logger.error('[Dermatology] Service list request failed', safeErrorMetadata(error));
        return (dermatologyRequestCache.services.data as Record<string, unknown>) || {};
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
  const getAllPatientServicesCb = useCallback((patientId: number | string | null | undefined, allAppointments: DermatologyAppointment[]) => {
    return getAllPatientServices(patientId, allAppointments as unknown as Array<Record<string, unknown>>);
  }, []);

  // Загрузка записей дерматолога
  const loadDermatologyAppointments = useCallback(async (force = false) => {
    ensureDermatologyCacheOwner(dermatologyRequestCache.appointments);
    // Self-review (audit 3892 wave 2): capture the principal at launch —
    // an in-flight queue response that resolves after an auth change must
    // never write the previous principal's rows into the next principal's
    // state or into the freshly reset module cache object.
    const ownerKeyAtLaunch = dermatologyCacheOwnerKey();
    if (!force) {
      if (appointmentsLoadPromiseRef.current) {
        return appointmentsLoadPromiseRef.current;
      }

      if (dermatologyRequestCache.appointments.promise) {
        return dermatologyRequestCache.appointments.promise;
      }

      const cachedAppointments = getRecentDermatologyCache(dermatologyRequestCache.appointments, [] as DermatologyAppointment[]);
      if (cachedAppointments) {
        const cached = cachedAppointments as DermatologyAppointment[];
        setAppointments(cached);
        return cached;
      }
    }

    const loadPromise = (async (): Promise<DermatologyAppointment[]> => {
      dermatologyRequestCache.appointments.lastAttemptAt = Date.now();
      setAppointmentsLoading(true);
      try {
        const token = tokenManager.getAccessToken();
        if (!token) {
          return [];
        }

        // Используем комбинированный подход: получаем данные из queues для услуг и из БД для payment_status
        // PR-47: removed unused `today` variable
        // 1. Получаем очереди для информации об услугах
        const queuesResponse = (await api.get('/registrar/queues/today')) as AxiosResponse<Record<string, unknown>>;

        // Self-review (audit 3892 wave 2): stale continuation guard — the
        // principal changed while this response was in flight; do not let
        // the OLD principal's queue rows reach the new principal's state
        // or cache (fail closed to an empty snapshot).
        if (dermatologyCacheOwnerKey() !== ownerKeyAtLaunch) {
          return [];
        }

        const allAppointments: DermatologyAppointment[] = [];
        if (queuesResponse.status < 400) {
          const queuesData = queuesResponse.data;

          // Собираем записи из очередей
          if (queuesData && queuesData.queues && Array.isArray(queuesData.queues)) {
            queuesData.queues.forEach((queue) => {
              if (queue.entries) {
                (queue.entries as unknown as DermatologyQueueEntryItem[]).forEach((entry) => {
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
                      entry.discount_mode === 'repeat' ? t('derma.derma_panel_visit_type_repeat') :
                      entry.discount_mode === 'benefit' ? t('derma.derma_panel_visit_type_benefit') :
                      entry.discount_mode === 'all_free' ? t('derma.derma_panel_visit_type_free') :
                      t('derma.derma_panel_visit_type_paid'),
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
                    doctor: entry.doctor_name || t('derma.derma_panel_doctor_default'),
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
        const appointmentsData = allAppointments.filter((apt: DermatologyAppointment) =>
        apt.specialty === 'derma' || apt.specialty === 'dermatology'
        );

        // Добавляем информацию о всех услугах пациента
        const enrichedAppointmentsData = appointmentsData.map((apt: DermatologyAppointment) => {
          const allPatientServices = getAllPatientServicesCb(apt.patient_id, allAppointments);
          return {
            ...apt,
            all_patient_services: allPatientServices.services,
            all_patient_service_codes: allPatientServices.service_codes
          };
        });

        setAppointments(enrichedAppointmentsData);
        dermatologyRequestCache.appointments.data = enrichedAppointmentsData;
        logger.info('[Dermatology] Загружено записей:', enrichedAppointmentsData.length);
        return enrichedAppointmentsData;
      } catch (error: unknown) {
        logger.error('[Dermatology] Appointment list request failed', safeErrorMetadata(error));
        return [];
      } finally {
        // Self-review (audit 3892 wave 2): a stale continuation must not
        // clear the NEXT principal's loading flag while its own request
        // is still in flight.
        if (dermatologyCacheOwnerKey() === ownerKeyAtLaunch) {
          setAppointmentsLoading(false);
        }
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
    if (activeTab === 'appointments') {
      loadDermatologyAppointments();
      loadServices();
    }

    // Слушаем глобальные события обновления очереди
    const handleQueueUpdate = () => {
      if (activeTab === 'appointments') {
        loadDermatologyAppointments();
      }
    };
    window.addEventListener('queueUpdated', handleQueueUpdate);

    return () => {
      window.removeEventListener('queueUpdated', handleQueueUpdate);
    };
  }, [activeTab, loadDermatologyAppointments, loadServices]);

  const ensureCanonicalVisitId = useCallback(
    (row: Record<string, unknown>) => makeEnsureCanonicalVisitId(setAppointments as unknown as React.Dispatch<React.SetStateAction<any[]>>, resolveCanonicalVisitId)(row),
    []
  );

  // Функция для создания частичного объекта пациента из данных row (для QR-пациентов)
  const createPartialPatientFromRow = useCallback((row: DermatologyAppointment) => {
    const nameParts = (row.patient_fio || '').split(' ').filter(Boolean);
    return {
      firstName: nameParts[1] || '',
      lastName: nameParts[0] || '',
      middleName: nameParts[2] || '',
      phone: row.patient_phone || '',
      address: row.address || '',
      birthDate: (row as DermatologyAppointment & { birth_date?: string }).birth_date || ''
    };
  }, []);

  // Обработчик редактирования пациента
  const handleEditPatient = useCallback(async (row: DermatologyAppointment) => {
    // Если нет patient_id (QR-пациент), используем частичные данные из row
    if (!row.patient_id) {
      const partialPatient = createPartialPatientFromRow(row);
      setEditPatientModal({ open: true, patient: partialPatient, loading: false });
      return;
    }

    const patientForEdit =
      buildDermatologyPatientFromAppointment(row) ||
      createPartialPatientFromRow(row);

    setEditPatientModal({ open: true, patient: patientForEdit, loading: false });
  }, [createPartialPatientFromRow]);

  // Обработчики для таблицы записей
  const handleAppointmentRowClick = async (row: DermatologyAppointment) => {
    // Можно открыть детали записи или переключиться на прием
    if (row.patient_fio) {
      const visitId = await ensureCanonicalVisitId(row);
      if (!visitId) {
        logger.warn('[Dermatology] Could not resolve the canonical visit for the selected row');
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

  const handleAppointmentActionClick = async (action: string, row: DermatologyAppointment, event?: unknown) => {
    if (event) {
      (event as React.MouseEvent).stopPropagation();
    }

    switch (action) {
      case 'view':
        await handleAppointmentRowClick(row);
        break;
      case 'call':
        // Вызвать пациента
        try {
          const queueEntryId = resolveDoctorQueueEntryId(row);
          if (queueEntryId === null) {
            logger.warn('[Dermatology] Cannot start visit without a queue entry ID');
            notify.error(t('derma.no_queue_id_for_visit'));
            break;
          }
          const token = tokenManager.getAccessToken();
          const response = (await api.post(`/doctor/queue/${queueEntryId}/start-visit`)) as AxiosResponse<Record<string, unknown>>;

          if (response.status < 400) {
            await loadDermatologyAppointments();
          }
        } catch (error: unknown) {
          logger.error('[Dermatology] Could not start the selected visit', safeErrorMetadata(error));
        }
        break;
      case 'payment':
        logger.info('[Dermatology] Payment action is unavailable in doctor view');
        break;
      case 'print':
        try {
          const printResult = await printPanelTicket(row, {
            specialtyName: t('derma.derma_panel_specialty_name')
          });
          notify.success(printResult?.message || t('derma.derma_panel_ticket_printed', { name: row.patient_fio }));
        } catch (error: unknown) {
          logger.error('[Dermatology] Queue ticket print failed', safeErrorMetadata(error));
          notify.error(t('derma.derma_panel_ticket_print_failed'));
        }
        break;
      case 'complete':
        // Завершить приём
        try {
          const visitId = await ensureCanonicalVisitId(row);
          if (!visitId) {
            logger.warn('[Dermatology] Cannot open completion flow without a canonical visit');
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
          setSelectedPatient(patient);
          setCurrentAppointment(patient);
          handleTabChange('visit');
        } catch (error: unknown) {
          logger.error('[Dermatology] Could not open visit completion flow', safeErrorMetadata(error));
        }
        break;
      case 'edit':
        // Загружаем полные данные пациента перед открытием модального окна
        await handleEditPatient(row);
        break;
      case 'cancel':
        // Логика отмены записи
        break;
      default:
        break;
    }
  };

  const getSelectedPatientId = useCallback(() => (
    selectedPatient?.patient?.id ||
    selectedPatient?.patient_id ||
    currentAppointment?.patient_id ||
    null
  ), [currentAppointment?.patient_id, selectedPatient]);

  const patientHistory = useDermatologyPatientHistory(getSelectedPatientId());
  const {
    appointments: patientAppointmentsHistory,
    skinExaminations,
    cosmeticProcedures,
    skinExaminationsTotal,
    cosmeticProceduresTotal,
    hasMoreExaminations,
    hasMoreProcedures,
    loadingMoreExaminations,
    loadingMoreProcedures,
    loadMoreExaminations,
    loadMoreProcedures,
    loading: patientHistoryLoading,
    ready: patientHistoryReady,
    error: patientHistoryError,
  } = patientHistory;

  // D-5 (UX audit): auto-promote selectedPatient to currentAppointment
  // so the first visit branch (with EMRContainerV2) renders correctly.
  useEffect(() => {
    if (selectedPatient && !currentAppointment && activeTab === 'visit') {
      setCurrentAppointment(selectedPatient);
    }
  }, [selectedPatient, currentAppointment, activeTab]);

  // ✅ Автоматическая загрузка пациента из URL параметра patientId / visitId
  useEffect(() => {
    // DERMAURL-FE-002 (audit 3892): generation token — every effect run
    // gets a unique generation; a stale continuation (deep-link resolution
    // that awaited a queue refresh while the URL or the selection moved on)
    // bails instead of overriding the newer context.
    const generation = ++urlResolutionGenerationRef.current;
    const loadPatientFromUrl = async () => {
      // P-009: patientIdFromUrl / visitIdFromUrl come from useDoctorPanelState
      const searchKey = location.search;

      if (!patientIdFromUrl && !visitIdFromUrl) {
        urlResolutionRef.current = {
          search: searchKey,
          refreshAttempted: false,
          refreshSettled: false,
          notified: false,
          appliedPair: null,
        };
        return;
      }

      if (urlResolutionRef.current.search !== searchKey) {
        urlResolutionRef.current = {
          search: searchKey,
          refreshAttempted: false,
          refreshSettled: false,
          notified: false,
          // DERMAURL-FE-002: appliedPair survives a pure `tab` param change —
          // only a change of the patient/visit pair itself invalidates it.
          appliedPair: urlResolutionRef.current.appliedPair,
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

      // DERMAURL-FE-002 (audit 3892): a manual/other selection that
      // contradicts the URL pair must survive — once THIS deep-link pair
      // was applied (and the URL pair itself has not changed since), the
      // resolution must not clobber the clinician's later choice back to
      // the stale deep-link target on every state change.
      const urlPairKey = `${patientIdFromUrl ?? ''}|${visitIdFromUrl ?? ''}`;
      const appliedPairKey = urlResolutionRef.current.appliedPair
        ? `${urlResolutionRef.current.appliedPair.patientId ?? ''}|${urlResolutionRef.current.appliedPair.visitId ?? ''}`
        : '';
      const selectionContradictsUrl =
        (patientIdFromUrl !== null && currentPatientId !== null && String(currentPatientId) !== String(patientIdFromUrl)) ||
        (visitIdFromUrl !== null && currentVisitId !== null && String(currentVisitId) !== String(visitIdFromUrl));
      if (selectionContradictsUrl && appliedPairKey === urlPairKey) {
        return;
      }

      // DERMAURL-FE-001 (audit 3892): when BOTH ids are supplied, the
      // matched row must satisfy both — an OR match would combine the
      // URL's visit with another visit's patient row into an unverified
      // patient/visit context for the EMR editor.
      const matchesUrlPair = (appointment: DermatologyAppointment): boolean => {
        const rowVisitId = normalizeNumericId(appointment.visit_id);
        if (patientIdFromUrl && visitIdFromUrl) {
          return (
            String(appointment.patient_id) === String(patientIdFromUrl) &&
            rowVisitId !== null &&
            String(rowVisitId) === String(visitIdFromUrl)
          );
        }
        if (visitIdFromUrl) {
          // Self-review (audit 3892 wave 2): a visit-only match must carry a
          // canonical patient_id. A queue-only row (online/QR, patient_id:
          // null) would otherwise fabricate the patient identity from its
          // queue-entry id through buildDermatologyPatientFromAppointment's
          // `patient_id || id` fallback — refuse to open the editor instead.
          return (
            rowVisitId !== null &&
            String(rowVisitId) === String(visitIdFromUrl) &&
            appointment.patient_id !== null &&
            appointment.patient_id !== undefined &&
            appointment.patient_id !== ''
          );
        }
        if (patientIdFromUrl) {
          return String(appointment.patient_id) === String(patientIdFromUrl);
        }
        return false;
      };

      try {
        const matchingAppointment = appointments.find(matchesUrlPair);

        const applyAppointmentSelection = (appointment: DermatologyAppointment) => {
          const patientObj = buildDermatologyPatientFromAppointment(appointment as Record<string, unknown>);
          if (!patientObj) {
            return false;
          }

          // DERMAURL-FE-001: trust the authoritative row's own visit — the
          // URL visit id must never be stamped onto a row it does not
          // belong to (the row matched the full URL pair when both ids
          // were supplied).
          const nextPatient: DermatologyPatient = {
            ...patientObj,
            visit_id: normalizeNumericId(patientObj.visit_id) || null,
          };
          setSelectedPatient(nextPatient);
          setCurrentAppointment(nextPatient);
          setActiveTab(visitIdFromUrl ? 'visit' : 'queue');
          urlResolutionRef.current.notified = false;
          urlResolutionRef.current.appliedPair = {
            patientId: nextPatient.patient_id ?? null,
            visitId: nextPatient.visit_id ?? null,
          };
          notify.info(t('derma.derma_panel_patient_loaded', { name: patientObj.patient_name }));
          return true;
        };

        if (matchingAppointment && applyAppointmentSelection(matchingAppointment)) {
          return;
        }

        if (!urlResolutionRef.current.refreshAttempted) {
          urlResolutionRef.current.refreshAttempted = true;
          const refreshedAppointments = await loadDermatologyAppointments() as DermatologyAppointment[] | null | undefined;
          // The queue snapshot this resolution depends on has settled — a
          // re-run that arrives while the request is in flight must not
          // conclude "not found" from a temporarily empty list.
          urlResolutionRef.current.refreshSettled = true;
          // DERMAURL-FE-002: the awaited refresh raced with a newer URL
          // or selection — drop this continuation entirely (the re-run that
          // observes the loaded `appointments` owns the resolution now).
          if (urlResolutionGenerationRef.current !== generation || location.search !== searchKey) {
            return;
          }
          const refreshedMatch = (refreshedAppointments || []).find(matchesUrlPair);

          if (refreshedMatch && applyAppointmentSelection(refreshedMatch)) {
            return;
          }
        }

        // DERMAURL-FE-001: the fallback may only ever establish a
        // patient-only context (no canonical visit). Fabricating a
        // patient/visit pair from two independent URL ids would open the
        // EMR editor at a visit whose patient was never verified.
        if (patientIdFromUrl && !visitIdFromUrl) {
          const fallbackPatientId = normalizeNumericId(patientIdFromUrl);
          const fallbackLabel = t('derma.derma_panel_patient_hash', { id: fallbackPatientId });
          const fallbackPatient: DermatologyPatient = {
            id: fallbackPatientId,
            appointment_id: null,
            visit_id: null,
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
          setActiveTab('queue');
          urlResolutionRef.current.notified = false;
          urlResolutionRef.current.appliedPair = { patientId: fallbackPatientId, visitId: null };
          return;
        }

        if (!urlResolutionRef.current.notified) {
          if (!urlResolutionRef.current.refreshSettled) {
            // DERMAURL-FE-001: the refresh is still in flight (or its rows
            // have not been reflected yet) — deciding "not found" now would
            // clear a context the in-flight resolution is about to apply.
            return;
          }
          urlResolutionRef.current.notified = true;
          urlResolutionRef.current.appliedPair = null;
          setSelectedPatient(null);
          setCurrentAppointment(null);
          handleTabChange('patients');
          notify.info(
            visitIdFromUrl
              ? t('derma.derma_panel_visit_not_found')
              : t('derma.derma_panel_patient_not_found')
          );
        }
      } catch (error: unknown) {
        logger.error('[Dermatology] URL patient selection failed', safeErrorMetadata(error));
        notify.error(t('derma.patient_load_failed'));
      }
    };

    loadPatientFromUrl();
    // DERMAURL-FE-002 (audit 3892): a re-run/unmount invalidates the
    // previous resolution's pending continuation.
    return () => {
      urlResolutionGenerationRef.current += 1;
    };
  }, [location.search, patientIdFromUrl, visitIdFromUrl, selectedPatient?.patient_id, selectedPatient?.visit_id, currentAppointment?.visit_id, appointments, loadDermatologyAppointments, setActiveTab, setSelectedPatient]);

  const currentVisitContext = useMemo<DermatologyVisitContext>(() => ({
    appointmentId: currentAppointment?.appointment_id ?? selectedPatient?.appointment_id ?? null,
    patientId: currentAppointment?.patient_id ?? selectedPatient?.patient_id ?? null,
    visitId: currentAppointment?.visit_id ?? selectedPatient?.visit_id ?? null,
    queueEntryId: currentAppointment?.doctor_queue_entry_id ?? currentAppointment?.queue_entry_id ??
      selectedPatient?.doctor_queue_entry_id ?? selectedPatient?.queue_entry_id ?? null,
  }), [
    currentAppointment?.appointment_id,
    currentAppointment?.patient_id,
    currentAppointment?.visit_id,
    currentAppointment?.doctor_queue_entry_id,
    currentAppointment?.queue_entry_id,
    selectedPatient?.appointment_id,
    selectedPatient?.patient_id,
    selectedPatient?.visit_id,
    selectedPatient?.doctor_queue_entry_id,
    selectedPatient?.queue_entry_id,
  ]);
  const currentVisitContextRef = useRef(currentVisitContext);
  currentVisitContextRef.current = currentVisitContext;
  const selectedPatientRef = useRef(selectedPatient);
  selectedPatientRef.current = selectedPatient;

  const updateSelectedPatient = useCallback((update: (patient: DermatologyPatient | null) => DermatologyPatient | null) => {
    const previous = selectedPatientRef.current;
    const next = update(previous);
    if (next !== previous) {
      selectedPatientRef.current = next;
      setSelectedPatient(next);
    }
  }, [setSelectedPatient]);

  const refreshCanonicalStatus = useCallback(async (
    expectedContext: DermatologyVisitContext,
    refreshQueue: boolean,
  ) => {
    if (!isSameDermatologyVisit(expectedContext, currentVisitContextRef.current)) return;

    const requestId = ++statusRequestIdRef.current;
    const expectedAppointmentId = expectedContext.appointmentId === null || expectedContext.appointmentId === undefined
      ? null
      : String(expectedContext.appointmentId);
    const expectedQueueEntryId = expectedContext.queueEntryId === null || expectedContext.queueEntryId === undefined
      ? null
      : String(expectedContext.queueEntryId);

    if (expectedAppointmentId) {
      setAppointmentCompletionStatus({
        appointmentId: expectedAppointmentId,
        visitId: expectedContext.visitId === null || expectedContext.visitId === undefined
          ? null
          : String(expectedContext.visitId),
        canComplete: false,
      });
    } else {
      setAppointmentCompletionStatus(null);
      setPrescription(null);
      setCanCreatePrescription(false);
    }

    if (refreshQueue && expectedQueueEntryId) {
      setCurrentAppointment((previous) => previous ? { ...previous, can_complete: false } : previous);
      updateSelectedPatient((previous) => previous ? { ...previous, can_complete: false } : previous);
    }

    const statusRequest = expectedAppointmentId
      ? api.get(`/appointments/${expectedAppointmentId}/status`)
      : expectedContext.visitId !== null && expectedContext.visitId !== undefined
        ? api.get(`/v2/emr/${expectedContext.visitId}`)
        : Promise.resolve(null);
    const queueRequest = refreshQueue && expectedQueueEntryId
      ? api.get('/doctor/dermatology/queue/today')
      : Promise.resolve(null);

    const [statusResult, queueResult] = await Promise.allSettled([statusRequest, queueRequest]);
    if (
      statusRequestIdRef.current !== requestId ||
      !isSameDermatologyVisit(expectedContext, currentVisitContextRef.current)
    ) return;

    if (statusResult.status === 'fulfilled' && statusResult.value && statusResult.value.status < 400) {
      const statusData = statusResult.value.data as Record<string, unknown>;
      if (expectedAppointmentId) {
        const statusVisitId = normalizeNumericId(statusData.visit_id as string | number | null | undefined);
        if (expectedContext.visitId !== null && expectedContext.visitId !== undefined &&
          String(statusVisitId) !== String(expectedContext.visitId)) {
          return;
        }

        setEmr((statusData.emr as Record<string, unknown>) || null);
        setPrescription(toPrescriptionSystemRecord(statusData.prescription));
        setCanCreatePrescription(statusData.can_create_prescription === true);
        setAppointmentCompletionStatus({
          appointmentId: expectedAppointmentId,
          visitId: statusVisitId === null ? null : String(statusVisitId),
          canComplete: statusData.can_complete === true,
        });

        const appointmentData = statusData.appointment as { status?: string } | undefined;
        setCurrentAppointment((previous) => previous &&
          String(previous.appointment_id) === expectedAppointmentId
          ? {
              ...previous,
              ...(statusVisitId !== null ? { visit_id: statusVisitId } : {}),
              ...(appointmentData?.status ? { status: appointmentData.status } : {}),
            }
          : previous);
        updateSelectedPatient((previous) => previous &&
          String(previous.appointment_id) === expectedAppointmentId
          ? {
              ...previous,
              ...(statusVisitId !== null ? { visit_id: statusVisitId } : {}),
              ...(appointmentData?.status ? { status: appointmentData.status } : {}),
            }
          : previous);
      } else {
        const returnedVisitId = normalizeNumericId(
          (statusData.visit_id ?? statusData.visitId) as string | number | null | undefined,
        );
        if (expectedContext.visitId !== null && expectedContext.visitId !== undefined &&
          returnedVisitId !== null && String(returnedVisitId) !== String(expectedContext.visitId)) {
          return;
        }
        // DERMAURL-FE-001 (audit 3892, defense in depth): the EMR payload
        // carries the canonical patient — if it contradicts the context
        // the panel selected, fail closed instead of rendering the visit
        // under the wrong patient's header.
        const returnedPatientId = normalizeNumericId(
          statusData.patient_id as string | number | null | undefined,
        );
        if (expectedContext.patientId !== null && expectedContext.patientId !== undefined &&
          returnedPatientId !== null && String(returnedPatientId) !== String(expectedContext.patientId)) {
          logger.warn('[Dermatology] EMR patient identity contradicts the selected context — fail closed');
          return;
        }
        const isDraft = statusData.is_draft ?? statusData.isDraft ?? statusData.status === 'draft';
        setEmr({ ...statusData, is_draft: isDraft === true });
        setPrescription(null);
        setCanCreatePrescription(false);
        setAppointmentCompletionStatus(null);
      }
    } else if (statusResult.status === 'rejected') {
      logger.warn('[Dermatology] Canonical visit status refresh failed', safeErrorMetadata(statusResult.reason));
    }

    if (refreshQueue && expectedQueueEntryId) {
      let queueCanComplete = false;
      if (queueResult.status === 'fulfilled' && queueResult.value && queueResult.value.status < 400) {
        const queueData = queueResult.value.data as { entries?: unknown };
        const entries = Array.isArray(queueData.entries)
          ? queueData.entries as Array<Record<string, unknown>>
          : [];
        const matchingEntry = entries.find((entry) => String(entry.id) === expectedQueueEntryId);
        const sameVisit = matchingEntry && (
          expectedContext.visitId === null || expectedContext.visitId === undefined ||
          String(matchingEntry.visit_id) === String(expectedContext.visitId)
        );
        const samePatient = matchingEntry && (
          expectedContext.patientId === null || expectedContext.patientId === undefined ||
          String(matchingEntry.patient_id) === String(expectedContext.patientId)
        );
        queueCanComplete = Boolean(sameVisit && samePatient && matchingEntry?.can_complete === true);
      } else if (queueResult.status === 'rejected') {
        logger.warn('[Dermatology] Doctor queue status refresh failed', safeErrorMetadata(queueResult.reason));
      }

      const updateQueueEntry = (previous: DermatologyPatient | null): DermatologyPatient | null => {
        if (!previous || String(resolveDoctorQueueEntryId(previous as unknown as Record<string, unknown>)) !== expectedQueueEntryId) {
          return previous;
        }
        if (expectedContext.visitId !== null && expectedContext.visitId !== undefined &&
          String(previous.visit_id) !== String(expectedContext.visitId)) return previous;
        if (expectedContext.patientId !== null && expectedContext.patientId !== undefined &&
          String(previous.patient_id) !== String(expectedContext.patientId)) return previous;
        return { ...previous, can_complete: queueCanComplete };
      };
      setCurrentAppointment(updateQueueEntry);
      updateSelectedPatient(updateQueueEntry);
    }
  }, [updateSelectedPatient]);

  useEffect(() => {
    setEmr(null);
    setPrescription(null);
    setCanCreatePrescription(false);
    if (currentVisitContext.appointmentId !== null && currentVisitContext.appointmentId !== undefined) {
      setAppointmentCompletionStatus({
        appointmentId: String(currentVisitContext.appointmentId),
        visitId: currentVisitContext.visitId === null || currentVisitContext.visitId === undefined
          ? null
          : String(currentVisitContext.visitId),
        canComplete: false,
      });
    } else {
      setAppointmentCompletionStatus(null);
    }

    if (
      (currentVisitContext.appointmentId === null || currentVisitContext.appointmentId === undefined) &&
      (currentVisitContext.visitId === null || currentVisitContext.visitId === undefined)
    ) return;

    void refreshCanonicalStatus(currentVisitContext, false);
    return () => {
      statusRequestIdRef.current += 1;
    };
  }, [currentVisitContext, refreshCanonicalStatus]);


  const savePrescription = async (prescriptionData: unknown) => {
    // DERMARX-FE-004 (audit 3892): capture the visit context that owns
    // this save — a late response must never populate a different visit's
    // prescription state (nor toast as the current visit's success).
    const saveContext = currentVisitContext;
    let prescriptionPayload: ReturnType<typeof toPrescriptionCreatePayload>;
    try {
      prescriptionPayload = toPrescriptionCreatePayload(prescriptionData, {
        appointmentId: saveContext.appointmentId,
        visitId: saveContext.visitId,
        emrId: emr?.id,
      });
    } catch {
      notify.error(t('derma.no_entry_for_prescription'));
      throw new Error('Prescription requires an appointment');
    }

    try {
      const savedPrescription = await postDermatologyPrescription(
        prescriptionPayload,
        (appointmentId, payload) => api.post(`/appointments/${appointmentId}/prescription`, payload) as Promise<AxiosResponse<unknown>>,
      );
      if (!isSameDermatologyVisit(saveContext, currentVisitContextRef.current)) {
        // DERMARX-FE-004: the clinician switched visits while the POST was
        // in flight — the write belongs to the OLD visit; do not render it
        // into the new context.
        logger.warn('[Dermatology] Late prescription save response ignored for a changed visit context');
        return;
      }
      setPrescription(savedPrescription);
      notify.success(t('derma.prescription_saved'));
    } catch (error: unknown) {
      const statusCode = safeErrorMetadata(error).statusCode;
      notify.error(statusCode === 422
        ? t('derma.derma_panel_prescription_save_failed_short')
        : t('derma.prescription_save_failed'));
      throw new Error('Prescription save failed');
    }
  };

  const printPrescription = async (prescriptionData: unknown) => {
    const patientFullName =
      selectedPatient?.patient_name ||
      currentAppointment?.patient_fio ||
      currentAppointment?.patient_name ||
      selectedPatient?.name ||
      i18nT('derma.derma_panel_patient_default');

    const prescriptionRecord = prescriptionData as Record<string, unknown>;
    const payload = {
      prescription: {
        ...prescriptionRecord,
        recommendations: (prescriptionRecord.instructions as string) || ''
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
      const result = await printService.printPrescription(payload) as { success?: boolean; error?: string; data?: { message?: string; printer?: string; job_id?: string } };

      if (!result.success) {
        throw new Error(result.error || t('derma.derma_panel_prescription_print_failed'));
      }

      notify.success(result.data?.message || t('derma.derma_panel_prescription_printed'));
    } catch (error: unknown) {
      logger.error('[Dermatology] Prescription print failed', safeErrorMetadata(error));
      notify.error(t('derma.derma_panel_prescription_print_failed'));
      throw error;
    }
  };

  // УДАЛЕНО: старая функция completeVisit заменена на унифицированную handleSaveVisit

  // Обработка AI предложений
  const handleAISuggestion = (type: string, suggestion: unknown) => {
    if (type === 'icd10') {
      setVisitData({ ...visitData, icd10: String(suggestion ?? '') });
        notify.success(t('derma.icd_added_from_ai'));
    } else if (type === 'diagnosis') {
      setVisitData({ ...visitData, diagnosis: String(suggestion ?? '') });
        notify.success(t('derma.diagnosis_added_from_ai'));
    }
  };

  const selectQueueVisitPatient = useCallback((patient: Record<string, unknown>) => {
    setSelectedPatient(patient as DermatologyPatient);
    setCurrentAppointment(patient as DermatologyPatient);
    handleTabChange('visit');
  }, [handleTabChange, setSelectedPatient]);

  // DERMAQUEUE-FE-001 (audit 3892): the dermatologist's live queue gets
  // the same Start Visit handoff dentistry wires — backend start-visit
  // ack resolves the canonical patient/visit, fail-closed otherwise.
  // Self-review (audit 3892 wave 2): the deferred ack guard — a start-visit
  // acknowledgement that arrives after a newer selection/navigation must
  // not pull the panel back into the stale queue row.
  const shouldApplyStartVisitAck = useCallback((queueEntryId: string | number): boolean => {
    const current = selectedPatientRef.current;
    if (current === null || current === undefined) {
      // No active selection — nothing for the ack to override.
      return true;
    }
    const currentEntry =
      (current as { doctor_queue_entry_id?: unknown; queue_entry_id?: unknown }).doctor_queue_entry_id ??
      (current as { queue_entry_id?: unknown }).queue_entry_id ?? null;
    if (currentEntry === null || currentEntry === undefined) {
      // The active selection has no queue identity (e.g. patients-tab) —
      // an explicit user action owns it, not this ack.
      return false;
    }
    return String(currentEntry) === String(queueEntryId);
  }, []);
  const handleStartQueueVisit = useDermaQueueVisit({
    selectPatient: selectQueueVisitPatient,
    shouldApplyAck: shouldApplyStartVisitAck,
    onDeferredAck: (queueEntryId) => {
      logger.warn('[Dermatology] Deferred start-visit ack not applied — a newer selection is active', { queueEntryId });
    },
  });

  const currentVisitAppointmentId = currentVisitContext.appointmentId === null || currentVisitContext.appointmentId === undefined
    ? null
    : String(currentVisitContext.appointmentId);
  const currentVisitStatusId = currentVisitContext.visitId === null || currentVisitContext.visitId === undefined
    ? null
    : String(currentVisitContext.visitId);
  const appointmentStatusMatches = Boolean(
    appointmentCompletionStatus &&
    appointmentCompletionStatus.appointmentId === currentVisitAppointmentId &&
    appointmentCompletionStatus.visitId === currentVisitStatusId &&
    appointmentCompletionStatus.canComplete,
  );
  const canCompleteCurrentVisit = canCompleteDermatologyVisit(
    currentAppointment?.can_complete === true &&
      currentVisitContext.queueEntryId !== null && currentVisitContext.queueEntryId !== undefined,
    currentVisitContext.appointmentId,
    appointmentStatusMatches,
  );
  const canCompleteCurrentVisitRef = useRef(canCompleteCurrentVisit);
  canCompleteCurrentVisitRef.current = canCompleteCurrentVisit;

  // Унифицированная обработка сохранения визита
  const handleSaveVisit = async () => {
    if (!canCompleteCurrentVisitRef.current) return;
    const completionContext = currentVisitContext;
    const entryId =
      resolveDoctorQueueEntryId(currentAppointment as unknown as Record<string, unknown>) ??
      resolveDoctorQueueEntryId(selectedPatient as unknown as Record<string, unknown>);
    if (!entryId || String(entryId) !== String(completionContext.queueEntryId)) {
      notify.error(t('derma.no_patient_for_complete'));
      return;
    }

    // QW-5 (UX audit): confirm before completing the visit
    const ok = await confirm({
      title: t('derma.complete_visit_title'),
      message: t('derma.complete_visit_message'),
      description: t('derma.derma_panel_complete_description'),
      confirmLabel: t('derma.complete_visit_confirm'),
      cancelLabel: t('derma.cancel'),
      intent: 'primary',
    });
    if (!ok) {
      return;
    }
    if (
      !isSameDermatologyVisit(completionContext, currentVisitContextRef.current) ||
      !canCompleteCurrentVisitRef.current
    ) return;

    try {
      setLoading(true);
      // DOCFLOW-FE-001 (audit 3886): only a confirmed `success: true` DTO
      // completes the visit in the UI. An ambiguous (unreadable 2xx) or
      // rejected response keeps the clinical state intact; the ambiguous
      // branch additionally reconciles the visible queue with the canonical
      // server snapshot instead of blindly retrying.
      const completionAck = await queueService.completeVisit(entryId, {});
      if (completionAck?.success !== true) {
        const ackMessage = (completionAck as { message?: unknown } | undefined)?.message;
        notify.error(
          (typeof ackMessage === 'string' && ackMessage) || t('derma.derma_panel_complete_failed')
        );
        logger.error('[Dermatology] Visit completion NOT confirmed by the server');
        if ((completionAck as { unknown?: unknown } | undefined)?.unknown === true) {
          // Ambiguous outcome — refresh the visible queue from the server.
          void loadDermatologyAppointments(true);
        }
        return;
      }

      // DERMACOMPLETE-FE-002 (audit 3892): the POST was in flight while
      // the clinician could switch to another visit (row click, deep link,
      // Escape). The completion belongs to the CAPTURED visit: a stale
      // ack is suppressed entirely — no unqualified success toast over
      // the newer context, no reset of the newly selected visit's state,
      // no schedule-next modal over it, and no auto-call for the stale
      // context.
      if (!isSameDermatologyVisit(completionContext, currentVisitContextRef.current)) {
        logger.warn('[Dermatology] Stale completion response ignored for a changed visit context');
        return;
      }
      notify.success(t('derma.visit_completed'));

      // D-004 fix: offer to schedule next visit (was dead code — setScheduleNextModal was never called)
      if (selectedPatient) {
        setScheduleNextModal({ open: true, patient: selectedPatient });
      }

      // Очищаем форму и состояние
      setSelectedPatient(null);
      setCurrentAppointment(null);
      setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
      setEmr(null);
      setPrescription(null);
      handleTabChange('queue');

      // Автоматически вызвать следующего пациента по дерматологии
      try {
        const next = await queueService.callNextWaiting(SPECIALTY_KEYS.DERMATOLOGY);
        logger.info('[Dermatology] Next dermatology queue entry requested', { succeeded: next?.success === true });
        if (next?.success) {
            notify.success(t('derma.derma_panel_next_patient_called', { number: (next as { entry?: { number?: string | number } }).entry?.number ?? '' }));
        }
      } catch (error: unknown) {
        logger.warn('[Dermatology] Next dermatology queue entry request failed', safeErrorMetadata(error));
      }

    } catch (error: unknown) {
      logger.error('[Dermatology] Visit completion failed', safeErrorMetadata(error));
      notify.error(t('derma.derma_panel_complete_failed'));
    } finally {
      setLoading(false);
    }
  };

  const appointmentSummaryItems = [
    {
      key: 'total',
      label: t('derma.derma_panel_summary_total'),
      value: appointments.length,
      variant: 'info'
    },
    {
      key: 'waiting',
      label: t('derma.derma_panel_summary_waiting'),
      value: countAppointmentsByStatuses(appointments, DERMATOLOGY_WAITING_STATUSES),
      variant: 'warning'
    },
    {
      key: 'called',
      label: t('derma.derma_panel_summary_called'),
      value: countAppointmentsByStatuses(appointments, DERMATOLOGY_CALLED_STATUSES),
      variant: 'primary'
    },
    {
      key: 'completed',
      label: t('derma.derma_panel_summary_completed'),
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
              <Card className="derma-card-w-full">
                <div style={dermatologyAppointmentsHeaderStyle}>
                  <h3 style={dermatologyAppointmentsTitleStyle}>
                    <Calendar size={20} className="derma-icon-mr-green" aria-hidden="true" />
                    {t('derma.derma_panel_appointments_title')}
                  </h3>
                  <AppointmentSummaryBar
                    ariaLabel={t('derma.derma_panel_appointments_summary_aria')}
                    items={appointmentSummaryItems}
                    onRefresh={loadDermatologyAppointments}
                    refreshDisabled={appointmentsLoading}
                    buttonProps={{ variant: 'outline' }}
                  />
                </div>

                <EnhancedAppointmentsTable
                data={appointments as unknown as never[]}
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

              </Card>
            </div>
          }

          {(activeTab === 'patients' || activeTab === 'history') && (
            <DermaPatientsTab
              selectedPatient={selectedPatient}
              onSelectPatient={(patient) => {
                setSelectedPatient(patient as DermatologyPatient | null);
                setCurrentAppointment(null);
              }}
              appointments={patientAppointmentsHistory}
              skinExaminations={skinExaminations}
              cosmeticProcedures={cosmeticProcedures}
              skinExaminationsTotal={skinExaminationsTotal}
              cosmeticProceduresTotal={cosmeticProceduresTotal}
              hasMoreExaminations={hasMoreExaminations}
              hasMoreProcedures={hasMoreProcedures}
              loadingMoreExaminations={loadingMoreExaminations}
              loadingMoreProcedures={loadingMoreProcedures}
              onLoadMoreExaminations={loadMoreExaminations}
              onLoadMoreProcedures={loadMoreProcedures}
              historyLoading={patientHistoryLoading}
              historyReady={patientHistoryReady}
              historyError={patientHistoryError}
            />
          )}

          {/* Прием пациента - EMR система */}
          {activeTab === 'queue' &&
          <QueueIntegration specialty="dermatology" onStartVisit={handleStartQueueVisit} />
          }

          {activeTab === 'visit' && currentAppointment &&
          <div className="derma-flex-col-24">
              <Card className="derma-p-8">
                <div className="derma-flex-center">
                  <h3 className="derma-flex-center">
                    <Stethoscope size={20} className="derma-icon-mr-orange" aria-hidden="true" />
                    {t('derma.derma_panel_visit_title', { name: currentAppointment.patient_name || t('derma.derma_panel_visit_name_unspecified') })}
                  </h3>
                  <Badge variant="info">
                    {t('derma.derma_panel_status_inline', { status: currentAppointment.status })}
                  </Badge>
                </div>

                {/* Временная шкала приема */}
                <VisitTimeline
                appointment={currentAppointment as unknown as never}
                emr={emr}
                prescription={prescription} />


                {/* EMR система */}
                <div className="derma-mt-24">
                  <h4 className="derma-flex-center">
                    <FileText size={20} className="derma-icon-mr-blue" aria-hidden="true" />
                    {t('derma.derma_panel_emr_title')}
                  </h4>
                  <EMRContainerV2
                  key={(currentAppointment?.visit_id ?? 'no-visit') as string | number}
                  visitId={(currentAppointment?.visit_id ?? undefined) as string | number}
                  patientId={(currentAppointment?.patient_id ?? undefined) as string | number | null | undefined}
                  specialty="dermatology"
                  onPersisted={() => refreshCanonicalStatus(currentVisitContext, true)} />

                </div>

                {currentAppointment.patient_id && currentAppointment.visit_id && (
                  <div className="derma-mt-24">
                    <DermaVisitGallery
                      patientId={currentAppointment.patient_id}
                      visitId={currentAppointment.visit_id} />
                  </div>
                )}

                {/* Система рецептов */}
                {emr && !emr.is_draft &&
              <div className="derma-mt-24">
                    <h4 className="derma-flex-center">
                      <FileText size={20} className="derma-icon-mr-green" aria-hidden="true" />
                      {t('derma.derma_panel_prescription_title')}
                    </h4>
                    <PrescriptionSystem
                  key={`rx-${String(currentVisitContext.appointmentId ?? currentVisitContext.visitId ?? 'none')}`}
                  appointment={currentAppointment as unknown as never}
                  emr={emr}
                  prescription={prescription}
                  canCreatePrescription={Boolean(currentVisitContext.appointmentId && canCreatePrescription)}
                  onSave={savePrescription}
                  onPrint={printPrescription} />

                  </div>
              }

                {/* Кнопка завершения приема */}
                {emr && !emr.is_draft &&
              <div className="derma-mt-24 derma-text-center">
                    <Button
                  onClick={handleSaveVisit}
                  disabled={loading || !canCompleteCurrentVisit}
                  className="derma-flex-center">

                      {loading ?
                  <RotateCw size={20} className="animate-spin" aria-hidden="true" /> :

                  <CheckCircle2 size={20} aria-hidden="true" />
                  }
                      {loading ? t('derma.derma_panel_completing') : t('derma.derma_panel_complete_button')}
                    </Button>
                  </div>
              }
              </Card>
            </div>
          }

          {/* Прием пациента - простая версия */}
          {/* D-5 (UX audit): removed duplicate visit branch (157 lines).
              The first visit branch (currentAppointment) handles all rendering via EMRContainerV2.
              If selectedPatient exists without currentAppointment, a useEffect auto-promotes it. */}

          {activeTab === 'visit' && !currentAppointment && !selectedPatient &&
          <Card className="derma-p-48">
              <AppEmpty
              icon="calendar"
              title={t('derma.derma_panel_select_visit_title')}
              description={t('derma.derma_panel_select_visit_desc')}
              action={
              <Button variant="outline" onClick={() => handleTabChange('patients')} className="derma-p-4 derma-mt-16">
                    {t('derma.derma_panel_go_to_appointments')}
                  </Button>
              } />
            </Card>
          }

          {activeTab === 'ai' &&
          <AIAssistant
            specialty="dermatology"
            onSuggestionSelect={handleAISuggestion} />

          }

        </div>{/* End of tab content wrapper */}

        {/* Модальное окно Schedule Next */}
        {scheduleNextModal.open &&
        <ScheduleNextModal
          isOpen={scheduleNextModal.open}
          onClose={() => setScheduleNextModal({ open: false, patient: null })}
          patient={scheduleNextModal.patient ?? undefined}
          theme={{ isDark, getColor, getSpacing, getFontSize }}
          specialtyFilter="dermatology" />

        }

        {/* Модальное окно редактирования пациента */}
        {editPatientModal.open &&
        <EditPatientModal
          isOpen={editPatientModal.open}
          onClose={() => setEditPatientModal({ open: false, patient: null, loading: false })}
          patient={editPatientModal.patient ?? undefined}
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
          onExtend={() => notify.info(t('derma.session_extending'))}
        />
      )}

      {/* X-13: AIChatWidget removed — AiTab in sidebar provides the same functionality */}

      </div>
    </div>);

};

export default DermatologistPanelUnified;
