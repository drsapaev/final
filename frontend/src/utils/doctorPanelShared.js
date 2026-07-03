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

const doctorPanelShared = {
  countAppointmentsByStatuses,
  normalizeNumericId,
};

export default doctorPanelShared;
