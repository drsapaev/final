// PR-UI-15-3: module-level dental contracts infra extracted verbatim from
// pages/DentistPanelUnified.tsx (registrar/cashier decomposition precedent).
// Pure/shared plumbing: types, status constants, module-level caches with
// the BS-42 PHI-leak invalidation helper, queue-id resolution, patient
// derivation, and localStorage documents bootstrap.
//
// Dead definition-only members NOT ported (verified ref-count = 1 at
// extraction time): API_V1_BASE const, authHeader callback,
// loadTreatmentPlans / loadProsthetics no-op stubs (endpoints pending
// backend per PR-43/Medium-24 — the pr43 contract test accepts removal).

import type { Appointment } from '../../types/domain/clinic';
import { normalizeNumericId } from '../../utils/doctorPanelShared';
import {
  DENTIST_DOCUMENTS_STORAGE_KEY,
  getDefaultDentistDocuments,
} from '../../utils/dentistryDocuments';

/**
 * Loose shape for the doctor-panel `selectedPatient` state object.
 * The shared `useDoctorPanelState` hook keeps `selectedPatient` typed as
 * `null` (its useState is declared without an explicit generic, and the
 * runtime payload is built ad-hoc from API/queue rows). Until the hook
 * ships a proper type, the panel casts its return through this alias.
 */
export type SelectedPatient = {
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

export type DoctorPanelState = {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  handleTabChange: (tab: string) => void;
  patientIdFromUrl: number | null;
  visitIdFromUrl: number | null;
  selectedPatient: SelectedPatient | null;
  setSelectedPatient: React.Dispatch<React.SetStateAction<SelectedPatient | null>>;
};

export const DENTISTRY_WAITING_STATUSES = ['waiting', 'confirmed', 'pending'];
export const DENTISTRY_CALLED_STATUSES = ['called', 'in_progress'];
export const DENTISTRY_COMPLETED_STATUSES = ['completed', 'done'];

// PR-UI-15-3: module-level caches moved verbatim (BS-42 audit trail).
let dentistAppointmentsCache: Appointment[] | null = null;
let dentistAppointmentsLoadPromise: Promise<Appointment[]> | null = null;
let dentistServicesCache: Record<string, unknown> | null = null;
let dentistServicesLoadPromise: Promise<Record<string, unknown> | null> | null = null;
const dentistVisitProtocolsCache = new Map<string, Record<string, unknown>[]>();
const dentistVisitProtocolsLoadPromises = new Map<string, Promise<Record<string, unknown>[]>>();
const dentistFallbackLoggedKeys = new Set<string>();

// DENTCACHE-FE-001 (audit 3892): ownership epoch for the module-level
// worklist cache. Every invalidation advances the epoch, revoking the
// ownership of any still-in-flight worklist load — a slow older response
// can then never repopulate the cache or the panel state after a context
// switch, unmount or principal change.
let dentistAppointmentsEpoch = 0;

// audit/phase-1, BS-42: invalidation helper for the 7 module-level caches.
// Previously these caches were never invalidated on patient switch, so on
// rapid visit-to-visit navigation the panel showed the previous patient's
// appointments / services (PHI leak between patients on a shared workstation).
// `useVisitLifecycle` already aborts in-flight requests and clears the
// cacheService layer; this helper additionally clears the panel-local
// module-level singletons so the next render refetches from the backend.
export function invalidateDentistPanelCaches() {
  dentistAppointmentsCache = null;
  dentistAppointmentsLoadPromise = null;
  dentistServicesCache = null;
  dentistServicesLoadPromise = null;
  dentistVisitProtocolsCache.clear();
  dentistVisitProtocolsLoadPromises.clear();
  // DENTCACHE-FE-001 (audit 3892): revoke the in-flight worklist loader's
  // cache/state ownership, not just its promise reference.
  dentistAppointmentsEpoch += 1;
  // DENTPHI-FE-001 (audit 3892): defensively purge the legacy protocol
  // storage key too — no code path may keep identifiable clinical data in
  // shared-origin localStorage.
  purgeLegacyDentistDocumentsStorage();
  // Note: dentistFallbackLoggedKeys intentionally retained — it only guards
  // against duplicate log noise, holds no PHI, and clearing it would resurface
  // log spam on the next visit to the same patient.
}

// PR-UI-15-3: internal cache accessors for the extracted data hooks. The
// caches stay module-level (verbatim semantics: shared across mounts,
// invalidated by invalidateDentistPanelCaches via useVisitLifecycle).
export const dentistCache = {
  get appointments(): Appointment[] | null {
    return dentistAppointmentsCache;
  },
  set appointments(value: Appointment[] | null) {
    dentistAppointmentsCache = value;
  },
  get appointmentsLoadPromise(): Promise<Appointment[]> | null {
    return dentistAppointmentsLoadPromise;
  },
  set appointmentsLoadPromise(value: Promise<Appointment[]> | null) {
    dentistAppointmentsLoadPromise = value;
  },
  // DENTCACHE-FE-001 (audit 3892): the current ownership epoch of the
  // worklist cache. A loader may only commit when its captured epoch still
  // matches this value.
  get appointmentsEpoch(): number {
    return dentistAppointmentsEpoch;
  },
  get services(): Record<string, unknown> | null {
    return dentistServicesCache;
  },
  set services(value: Record<string, unknown> | null) {
    dentistServicesCache = value;
  },
  get servicesLoadPromise(): Promise<Record<string, unknown> | null> | null {
    return dentistServicesLoadPromise;
  },
  set servicesLoadPromise(value: Promise<Record<string, unknown> | null> | null) {
    dentistServicesLoadPromise = value;
  },
  get visitProtocolsCache(): Map<string, Record<string, unknown>[]> {
    return dentistVisitProtocolsCache;
  },
  get visitProtocolsLoadPromises(): Map<string, Promise<Record<string, unknown>[]>> {
    return dentistVisitProtocolsLoadPromises;
  },
  get fallbackLoggedKeys(): Set<string> {
    return dentistFallbackLoggedKeys;
  },
};

// countAppointmentsByStatuses and normalizeNumericId are imported from
// utils/doctorPanelShared (unified across Cardiology / Dermatology / Dentistry).

export function resolveDoctorQueueEntryId(row: Record<string, unknown> | null | undefined): string | number | null {
  const explicitQueueEntryId = row?.doctor_queue_entry_id ?? row?.queue_entry_id ?? null;
  if (explicitQueueEntryId !== null && explicitQueueEntryId !== undefined) {
    return explicitQueueEntryId as string | number;
  }

  return null;
}

export function buildPatientsFromAppointments(
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

export function loadStoredDentistDocuments() {
  // DENTPHI-FE-001 (audit 3892): visit protocols carry identifiable clinical
  // data (patient ids, names, full visit payloads). They must not persist in
  // unscoped, plaintext, shared-origin localStorage across sessions. The
  // legacy key is purged instead of read; the in-session list lives in
  // memory and the EMR remains the source of truth.
  purgeLegacyDentistDocumentsStorage();
  return getDefaultDentistDocuments();
}

// DENTPHI-FE-001 (audit 3892): removes the legacy dentist documents key from
// the shared browser storage. Exported for the invalidation helper and for
// any future bootstrap that wants to guarantee the at-rest purge.
export function purgeLegacyDentistDocumentsStorage() {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.removeItem(DENTIST_DOCUMENTS_STORAGE_KEY);
  } catch {
    // Storage may be unavailable (private mode / permissions) — nothing to do.
  }
}
