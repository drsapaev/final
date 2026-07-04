/**
 * Shared helpers for doctor specialty panels (cardiology / dermatology / dentistry).
 *
 * These utilities are NOT contract-bound: the SSOT contract in
 * `pages/__tests__/DoctorPanels.contract.test.jsx` only requires
 * `function resolveDoctorQueueEntryId(row)` to live inside each panel file
 * (because its body asserts specific identifier-resolution logic).
 *
 * Anything else that is mechanically identical across panels is collected
 * here so that future bug fixes land in one place.
 *
 * @module utils/doctorPanelShared
 */

/**
 * Canonical specialty keys used to call the doctor queue service.
 *
 * The backend (backend/app/api/v1/endpoints/doctor_integration.py) accepts
 * a wide variety of aliases — `cardio`/`cardiology`, `derma`/`dermatology`,
 * `dental`/`dentistry`/`stomatology` — and normalises them through
 * `DOCTOR_QUEUE_SPECIALTY_VARIANTS`. That tolerant mapping kept the system
 * running even when the frontend mixed short and long forms across panels,
 * but it made the call sites ambiguous.
 *
 * This constant is the single source of truth on the frontend: panels MUST
 * call `queueService.callNextWaiting(SPECIALTY_KEYS.CARDIOLOGY)` rather than
 * passing the literal `'cardiology'` or `'cardio'`. The value matches the
 * long form because that is what the backend seeds
 * (`backend/app/scripts/dev_seed.py: "specialty": "cardiology"`) and what
 * `registrar_integration.py` returns in the specialist catalogue.
 *
 * @readonly
 * @enum {string}
 */
export const SPECIALTY_KEYS = Object.freeze({
  CARDIOLOGY: 'cardiology',
  DERMATOLOGY: 'dermatology',
  DENTISTRY: 'dentistry',
  LAB: 'lab',
  GENERAL: 'general',
});

/**
 * Set of all known aliases for each canonical specialty. Used by
 * `matchesSpecialty()` to keep the tolerant comparisons that were
 * previously hard-coded as `apt.specialty === 'cardio' || apt.specialty === 'cardiology'`.
 *
 * Aligned with backend `DOCTOR_QUEUE_SPECIALTY_VARIANTS`.
 */
export const SPECIALTY_ALIASES = Object.freeze({
  [SPECIALTY_KEYS.CARDIOLOGY]: ['cardiology', 'cardio', 'Cardiologist', 'Cardio'],
  [SPECIALTY_KEYS.DERMATOLOGY]: ['derma', 'dermatology', 'Dermatologist'],
  [SPECIALTY_KEYS.DENTISTRY]: ['dentist', 'dental', 'dentistry', 'Dentist', 'stomatology'],
  [SPECIALTY_KEYS.LAB]: ['lab', 'laboratory', 'Laboratory'],
  [SPECIALTY_KEYS.GENERAL]: ['general', 'therapy', 'therapist', 'general_practice'],
});

/**
 * Check whether a given specialty string matches the canonical key,
 * tolerating any of the known aliases.
 *
 * @param {string} candidate - The specialty string from the appointment/entry.
 * @param {string} canonicalKey - One of SPECIALTY_KEYS.*.
 * @returns {boolean}
 */
export function matchesSpecialty(candidate, canonicalKey) {
  if (!candidate || !canonicalKey) return false;
  if (candidate === canonicalKey) return true;
  const aliases = SPECIALTY_ALIASES[canonicalKey];
  return Array.isArray(aliases) && aliases.includes(candidate);
}

/**
 * Count appointments whose status matches any of the given statuses.
 *
 * Uses a Set for O(1) membership checks — previously each panel used
 * `statuses.includes(appointment.status)` which is O(n*m). For typical
 * clinic volumes (≤200 appointments/day × 3 statuses) the difference is
 * negligible, but the Set version is idiomatic and faster for larger lists.
 *
 * @param {Array<{status?: string}>} appointments
 * @param {string[]} statuses
 * @returns {number}
 */
export function countAppointmentsByStatuses(appointments, statuses) {
  if (!Array.isArray(appointments) || !Array.isArray(statuses) || statuses.length === 0) {
    return 0;
  }
  const statusSet = new Set(statuses);
  let count = 0;
  for (let i = 0; i < appointments.length; i++) {
    if (statusSet.has(appointments[i]?.status)) {
      count++;
    }
  }
  return count;
}

/**
 * Parse a possibly-string numeric id into a finite integer, or null.
 *
 * Used for visit_id / patient_id coercion across panels. Returns null for
 * empty strings, non-numeric strings, NaN, Infinity, and non-finite values.
 *
 * @param {*} value
 * @returns {number|null}
 */
export function normalizeNumericId(value) {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const parsed = parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * Collect all unique services + service_codes for a given patient across
 * all their appointments.
 *
 * Previously duplicated verbatim in CardiologistPanelUnified,
 * DermatologistPanelUnified, and DentistPanelUnified (~20 lines each).
 * Now exported from here so future bug fixes land in one place.
 *
 * @param {number|string} patientId - The patient id to filter by.
 * @param {Array<{patient_id: *, services?: Array, service_codes?: Array}>} allAppointments
 * @returns {{services: Array, service_codes: Array}} Deduplicated arrays.
 */
export function getAllPatientServices(patientId, allAppointments) {
  const patientServices = new Set();
  const patientServiceCodes = new Set();

  if (Array.isArray(allAppointments)) {
    allAppointments.forEach((appointment) => {
      if (appointment && appointment.patient_id === patientId) {
        if (Array.isArray(appointment.services)) {
          appointment.services.forEach((service) => patientServices.add(service));
        }
        if (Array.isArray(appointment.service_codes)) {
          appointment.service_codes.forEach((code) => patientServiceCodes.add(code));
        }
      }
    });
  }

  return {
    services: Array.from(patientServices),
    service_codes: Array.from(patientServiceCodes),
  };
}

/**
 * Factory that creates an `ensureCanonicalVisitId` callback bound to a
 * specific appointments setter.
 *
 * The three doctor specialty panels each had an identical copy of this
 * function, differing only in which setter they call:
 *   - CardiologistPanelUnified: setAppointments
 *   - DermatologistPanelUnified: setAppointments
 *   - DentistPanelUnified:       setAppointmentsTableData
 *
 * The function body resolves the canonical visit_id for a row (either
 * from the row itself, or by calling resolveCanonicalVisitId with the
 * appointment_id), and writes it back into the appointments state so
 * subsequent lookups skip the API call.
 *
 * Usage in a panel:
 *   const ensureCanonicalVisitId = useCallback(
 *     makeEnsureCanonicalVisitId(setAppointments, resolveCanonicalVisitId),
 *     [resolveCanonicalVisitId]
 *   );
 *
 * @param {(updater: (prev: Array) => Array) => void} setAppointments - The
 *   panel-specific appointments setter (from useState).
 * @param {(appointmentId: number|string) => Promise<number|null>} resolveCanonicalVisitId -
 *   Imported from utils/canonicalVisit. Resolves an appointment_id to a
 *   canonical visit_id via backend API.
 * @returns {(row: {appointment_id?: *, visit_id?: *, id: *}) => Promise<number|null>}
 */
export function makeEnsureCanonicalVisitId(setAppointments, resolveCanonicalVisitId) {
  return async function ensureCanonicalVisitId(row) {
    const appointmentId = row?.appointment_id || null;
    const visitId = row?.visit_id || (appointmentId && typeof resolveCanonicalVisitId === 'function' ? await resolveCanonicalVisitId(appointmentId) : null);

    if (visitId && typeof setAppointments === 'function') {
      setAppointments((prev) => (Array.isArray(prev) ? prev.map((appointment) =>
        appointment && appointment.id === row.id ? { ...appointment, visit_id: visitId } : appointment
      ) : prev));
    }

    return visitId;
  };
}

const doctorPanelShared = {
  SPECIALTY_KEYS,
  SPECIALTY_ALIASES,
  matchesSpecialty,
  countAppointmentsByStatuses,
  normalizeNumericId,
  getAllPatientServices,
  makeEnsureCanonicalVisitId,
};

export default doctorPanelShared;
