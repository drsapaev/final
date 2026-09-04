/**
 * Registrar worklist — backend queue entry → worklist row adapter (pure).
 *
 * PR-UI-13-1: extracted verbatim from RegistrarPanel.tsx loadAppointments
 * (Decomp step: the SSOT field-adaptation layer becomes an independently
 * unit-testable pure function).
 *
 * Contract (pinned by RegistrarPanel.contract.test.tsx):
 * - Each backend queue entry maps to exactly ONE frontend row (no dedup,
 *   no aggregation — SSOT: backend owns queue facts).
 * - Entries without an ID are skipped (null).
 * - Patient display fields pass through backend contract first
 *   (fullEntry.* ?? entry.* fallbacks), gender triple-normalized via
 *   normalizePatientGender.
 *
 * @param entry   one queue entry (may wrap payload in entry.data)
 * @param queue   the owning queue object (queue_tag/specialty/specialist_name)
 * @param data    the full GET /registrar/queues/today response
 * @param dateParam target_date requested for this load
 * @param fallbackPatientLabel localized "unknown patient" label
 */
import { adaptTimeFields } from '../../utils/registrarAggregation';
import { normalizePatientGender } from './registrarHelpers';

export const adaptQueueEntry = (
  entry: Record<string, unknown>,
  queue: Record<string, unknown>,
  data: Record<string, unknown>,
  dateParam: string,
  fallbackPatientLabel: string,
): Record<string, unknown> | null => {
  const fullEntry = (entry.data ?? entry) as Record<string, unknown>;
  const entryId = fullEntry?.id;
  if (!entryId) return null; // Skip entries without ID

  const queueNum = fullEntry.queue_position ?? fullEntry.number ?? 0;
  const queueTag = fullEntry.queue_tag ?? queue.queue_tag ?? queue.specialty ?? null;
  const queueName = fullEntry.queue_name ?? queue.specialist_name ?? queue.specialty ?? null;
  const queueTime = entry.queue_time || fullEntry.queue_time || fullEntry.created_at || null;
  const canonicalStatus = fullEntry.canonical_status ?? fullEntry.queue_status ?? fullEntry.status ?? null;

  return {
    // SSOT passthrough
    id: entryId,
    canonical_record_id: fullEntry.canonical_record_id ?? entry.canonical_record_id ?? entryId,
    record_kind: fullEntry.record_kind ?? entry.record_kind ?? null,
    source_kind: fullEntry.source_kind ?? entry.source_kind ?? null,
    visit_id: fullEntry.visit_id || entry.visit_id || null,
    appointment_id: fullEntry.appointment_id || entry.appointment_id || null,
    queue_entry_id: fullEntry.queue_entry_id || entry.queue_entry_id || null,
    patient_id: fullEntry.patient_id || entry.patient_id,
    patient_fio: fullEntry.patient_fio ?? fullEntry.patient_name ?? entry.patient_fio ?? entry.patient_name ?? fallbackPatientLabel,
    patient_birth_year: fullEntry.patient_birth_year ?? fullEntry.birth_year ?? entry.patient_birth_year ?? entry.birth_year ?? null,
    patient_phone: fullEntry.patient_phone ?? fullEntry.phone ?? entry.patient_phone ?? entry.phone ?? '',
    patient_gender: normalizePatientGender(fullEntry as Record<string, unknown>) ?? normalizePatientGender(entry as Record<string, unknown>),
    gender: normalizePatientGender(fullEntry as Record<string, unknown>) ?? normalizePatientGender(entry as Record<string, unknown>),
    sex: normalizePatientGender(fullEntry as Record<string, unknown>) ?? normalizePatientGender(entry as Record<string, unknown>),
    address: fullEntry.address ?? entry.address ?? '',
    services: Array.isArray(fullEntry.services) ? fullEntry.services : [],
    service_codes: Array.isArray(fullEntry.service_codes) ? fullEntry.service_codes : [],
    service_details: Array.isArray(fullEntry.service_details) ? fullEntry.service_details : [],
    cost: fullEntry.cost || 0,
    payment_status: fullEntry.payment_status ?? null,
    source: fullEntry.source || entry.source || 'desk',
    status: canonicalStatus,
    canonical_status: fullEntry.canonical_status ?? canonicalStatus,
    queue_status: fullEntry.queue_status ?? canonicalStatus,
    record_type: fullEntry.record_type ?? fullEntry.type ?? entry.record_type ?? entry.type ?? null,
    ...adaptTimeFields(entry, data),
    // Keep queueTime (computed above) as queue_time fallback for backward compat
    queue_time: queueTime,
    discount_mode: fullEntry.discount_mode ?? null,
    approval_status: fullEntry.approval_status || null,
    available_actions: Array.isArray(fullEntry.available_actions) ? fullEntry.available_actions : [],
    can_mark_paid: Boolean(fullEntry.can_mark_paid),
    can_start_visit: Boolean(fullEntry.can_start_visit),
    can_cancel: Boolean(fullEntry.can_cancel),
    can_print_ticket: Boolean(fullEntry.can_print_ticket),
    can_complete: Boolean(fullEntry.can_complete),

    // Queue info
    queue_number: queueNum,
    queue_numbers: [{
      number: queueNum,
      queue_tag: queueTag,
      queue_name: queueName,
      specialty: queueTag,
      status: canonicalStatus,
      queue_time: queueTime,
      updated_at: fullEntry.updated_at || fullEntry.last_changed_at || null,
      last_changed_at: fullEntry.last_changed_at || fullEntry.updated_at || null,
      timezone: fullEntry.timezone || data.timezone || 'Asia/Tashkent'
    }],
    specialty: queueTag,
    queue_tag: queueTag,
    queue_name: queueName,
    department: fullEntry.department ?? queueTag,
    department_key: fullEntry.department_key || null,

    // Derived fields (minimal)
    visit_type: fullEntry.visit_type ?? fullEntry.discount_mode ?? null,
    payment_type: fullEntry.payment_type ?? null,
    date: fullEntry.date ?? data.date ?? dateParam,
    appointment_date: fullEntry.appointment_date ?? data.date ?? dateParam,

    // ⭐ SSOT: session_id for visual grouping (presentation only)
    // DO NOT parse this value - it's an opaque string from backend
    session_id: fullEntry.session_id || null,

    // P1 fix: pass through lab report summary so registrar can see
    // if lab results are ready for this patient's visit.
    latest_lab_report: fullEntry.latest_lab_report ?? null,
  };
};

export default adaptQueueEntry;
