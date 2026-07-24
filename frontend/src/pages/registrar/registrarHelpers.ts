/**
 * Registrar Panel — pure helper functions (no React, no state).
 *
 * Decomposition step: extracted from RegistrarPanel.jsx (lines 27-363).
 * These functions are pure: given input, return output, no side effects.
 * Safe to extract because they don't depend on React hooks or component state.
 *
 * Related: audit §5.12 Scalability, §8 Strategic Changes Direction 1 (Decomposition).
 */

import { getApiOrigin } from '../../api/runtime';

/**
 * Backend API base URL. Used by all fetch calls in registrar panel.
 */
export const API_BASE = getApiOrigin();

/**
 * Map of department tab IDs to i18n keys for tab labels.
 * Used by ModernTabs to render localized tab names.
 */
export const REGISTRAR_TAB_LABEL_KEYS = {
  appointments: 'tabs_appointments',
  cardio: 'tabs_cardio',
  echokg: 'tabs_echokg',
  derma: 'tabs_derma',
  dental: 'tabs_dental',
  lab: 'tabs_lab',
  procedures: 'tabs_procedures',
};

/**
 * Map of status filter values to i18n keys for status labels.
 * Used by status filter dropdown and context menu.
 */
export const REGISTRAR_STATUS_LABEL_KEYS = {
  scheduled: 'status_scheduled',
  confirmed: 'status_confirmed',
  queued: 'status_queued',
  in_cabinet: 'status_in_cabinet',
  done: 'status_done',
  cancelled: 'status_cancelled',
  no_show: 'status_no_show',
  paid_pending: 'status_paid_pending',
  paid: 'status_paid',
};

/**
 * Set of valid registrar record kinds.
 * Used to filter out invalid record refs from grouped_records.
 */
export const REGISTRAR_RECORD_KINDS = new Set(['visit', 'online_queue', 'appointment']);

/**
 * Workflow header styles (shared between welcome and worklist views).
 * Using macOS design system tokens (canonical).
 */
// Phase 3: registrarWorkflowHeaderStyle, registrarWorkflowTitleStyle,
// registrarWorkflowMetaStyle constants removed — replaced by
// .registrar-workflow-header, .registrar-workflow-title, .registrar-workflow-meta
// CSS classes in registrar.css.

// Phase 3: registrarWorkflowActionsStyle removed — replaced by
// .registrar-workflow-actions CSS class in registrar.css.

// ───────────────────────────────────────────────────────────
// Contract normalization helpers
// ───────────────────────────────────────────────────────────

export const normalizeRegistrarContractValue = (value: unknown) => {
  if (value === null || value === undefined) return '';
  return String(value).trim().toLowerCase();
};

export const getRegistrarRecordKind = (record) => normalizeRegistrarContractValue(
  record?.record_kind ?? record?.source_kind ?? record?.record_type ?? record?.type
);

export const getRegistrarRecordId = (record, recordKind = getRegistrarRecordKind(record)) => {
  if (!record) return null;
  if (record.canonical_record_id !== undefined && record.canonical_record_id !== null) {
    return record.canonical_record_id;
  }
  if (recordKind === 'visit' && record.visit_id !== undefined && record.visit_id !== null) {
    return record.visit_id;
  }
  if (recordKind === 'online_queue' && record.queue_entry_id !== undefined && record.queue_entry_id !== null) {
    return record.queue_entry_id;
  }
  if (recordKind === 'appointment' && record.appointment_id !== undefined && record.appointment_id !== null) {
    return record.appointment_id;
  }
  return record.id ?? null;
};

export const getRegistrarRecordRefs = (record) => {
  if (!record) return [];

  const candidates = [];
  if (Array.isArray(record.grouped_record_refs)) {
    candidates.push(...record.grouped_record_refs);
  }
  if (Array.isArray(record.grouped_records)) {
    record.grouped_records.forEach((groupedRecord) => {
      if (groupedRecord?.record_ref) {
        candidates.push(groupedRecord.record_ref);
      }
    });
  }

  const recordKind = getRegistrarRecordKind(record);
  const recordId = getRegistrarRecordId(record, recordKind);
  if (recordKind && recordId !== null && recordId !== undefined) {
    candidates.push({ record_kind: recordKind, record_id: recordId });
  }

  const seen = new Set();
  return candidates.reduce((refs, candidate) => {
    const kind = getRegistrarRecordKind(candidate);
    const id = candidate?.record_id ?? candidate?.recordId ?? getRegistrarRecordId(candidate, kind);
    const numericId = Number(id);
    if (!REGISTRAR_RECORD_KINDS.has(kind) || !Number.isFinite(numericId) || numericId <= 0) {
      return refs;
    }
    const key = `${kind}:${numericId}`;
    if (seen.has(key)) {
      return refs;
    }
    seen.add(key);
    refs.push({ record_kind: kind, record_id: numericId });
    return refs;
  }, []);
};

export const getRegistrarSelectionKey = (record) => {
  const refs = getRegistrarRecordRefs(record);
  if (refs.length > 0) {
    return refs.map((ref) => `${ref.record_kind}:${ref.record_id}`).join('|');
  }
  return record?.id !== undefined && record?.id !== null ? `legacy:${record.id}` : null;
};

export const findRegistrarRecordBySelectionKey = (records, selectionKey) => {
  if (!selectionKey) return null;
  return (records || []).find((record) => getRegistrarSelectionKey(record) === selectionKey) || null;
};

// ───────────────────────────────────────────────────────────
// Backend action availability helpers
// ───────────────────────────────────────────────────────────

const hasOwn = (object, key) => Object.prototype.hasOwnProperty.call(object || {}, key);

export const hasBackendAction = (record, action) => {
  if (!record) return false;
  const normalizedAction = String(action || '').trim();
  const equivalentActions = new Set([
    normalizedAction,
    normalizedAction.replace('_', '-'),
    normalizedAction.replace('-', '_'),
  ]);
  if (Array.isArray(record.grouped_records) && record.grouped_records.length > 0) {
    return record.grouped_records.every((groupedRecord) =>
      hasBackendAction(groupedRecord, normalizedAction)
    );
  }
  if (Array.isArray(record.available_actions)) {
    return record.available_actions.some((availableAction) =>
      equivalentActions.has(String(availableAction || '').trim())
    );
  }

  const actionFlagByName = {
    mark_paid: 'can_mark_paid',
    start_visit: 'can_start_visit',
    print_ticket: 'can_print_ticket',
    complete: 'can_complete',
    cancel: 'can_cancel',
  };
  const flagName = actionFlagByName[normalizedAction.replace('-', '_')];
  if (flagName && record[flagName] !== undefined) {
    return Boolean(record[flagName]);
  }

  return false;
};

export const getRegistrarActionForStatus = (status) => {
  const normalizedStatus = normalizeRegistrarContractValue(status).replace('-', '_');
  if (normalizedStatus === 'complete' || normalizedStatus === 'done') return 'complete';
  if (normalizedStatus === 'paid' || normalizedStatus === 'mark_paid') return 'mark_paid';
  if (normalizedStatus === 'in_cabinet') return 'start_visit';
  if (normalizedStatus === 'cancelled' || normalizedStatus === 'canceled' || normalizedStatus === 'no_show') return 'cancel';
  return null;
};

// ───────────────────────────────────────────────────────────
// Patient display contract helpers
// ───────────────────────────────────────────────────────────

export const hasBackendPatientDisplayContract = (record) => {
  if (!record) return false;
  const hasName = Boolean(record.patient_fio || record.patient_name);
  const hasPhone = hasOwn(record, 'patient_phone') || hasOwn(record, 'phone');
  const hasBirthYear = hasOwn(record, 'patient_birth_year') || hasOwn(record, 'birth_year');
  const hasAddress = hasOwn(record, 'address');
  return hasName && hasPhone && hasBirthYear && hasAddress;
};

export const normalizePatientGender = (record) => (
  record?.patient_gender ??
  record?.patient_sex ??
  record?.gender ??
  record?.sex ??
  null
);

export const hasBackendPatientGenderContract = (record) => {
  const gender = normalizePatientGender(record);
  return gender !== null && gender !== undefined && String(gender).trim() !== '';
};

// ───────────────────────────────────────────────────────────
// Preview formatting
// ───────────────────────────────────────────────────────────

export const formatPreviewList = (value: unknown) => {
  if (Array.isArray(value)) {
    return value.map((item: Record<string, unknown>) => {
      if (typeof item === 'string') return item;
      return item?.name || item?.service_name || item?.code || item?.queue_name || item?.queue_tag || '';
    }).filter(Boolean).join(', ');
  }
  return value || '';
};

// ───────────────────────────────────────────────────────────
// Wizard queue assignment normalization
// ───────────────────────────────────────────────────────────

const hasQueueIdentityValue = (value: unknown) => value !== null && value !== undefined && value !== '';

export const resolveWizardQueueEntryId = (assignment) => {
  if (!assignment || typeof assignment !== 'object') return null;
  const explicitQueueEntryId = assignment.queue_entry_id ??
    assignment.original_queue_id ??
    assignment.doctor_queue_entry_id ??
    null;
  if (hasQueueIdentityValue(explicitQueueEntryId)) return explicitQueueEntryId;

  if (hasQueueIdentityValue(assignment.queue_id)) return null;

  return hasQueueIdentityValue(assignment.id) ? assignment.id : null;
};

export const normalizeWizardQueueAssignment = (assignment, visitId = null) => {
  if (!assignment || typeof assignment !== 'object') return null;
  const queueEntryId = resolveWizardQueueEntryId(assignment);
  const queueNumber = assignment.queue_number ??
    assignment.number ??
    assignment.ticket_number ??
    assignment.queue_position ??
    assignment.queue_no ??
    null;

  return {
    ...assignment,
    id: assignment.queue_id ?? queueEntryId ?? assignment.id ?? null,
    queue_entry_id: queueEntryId,
    visit_id: assignment.visit_id ?? (visitId !== null && visitId !== undefined && visitId !== '' ? Number(visitId) : null),
    queue_number: queueNumber,
    number: queueNumber,
  };
};

export const flattenWizardQueueNumbers = (queueNumbers) => {
  if (!queueNumbers) return [];

  if (Array.isArray(queueNumbers)) {
    return queueNumbers
      .map((assignment) => normalizeWizardQueueAssignment(assignment, assignment?.visit_id))
      .filter(Boolean);
  }

  if (typeof queueNumbers !== 'object') return [];

  return Object.entries(queueNumbers).flatMap(([visitId, assignments]) => {
    const assignmentList = Array.isArray(assignments) ? assignments : [assignments];
    return assignmentList
      .map((assignment) => normalizeWizardQueueAssignment(assignment, visitId))
      .filter(Boolean);
  });
};

// ───────────────────────────────────────────────────────────
// Post-wizard payment row builder
// ───────────────────────────────────────────────────────────

export const buildPostWizardPaymentRow = (wizardResult) => {
  if (!wizardResult?.success) return null;

  const visitIds = Array.isArray(wizardResult.visit_ids) ? wizardResult.visit_ids.filter(Boolean) : [];
  if (visitIds.length === 0) return null;

  const createdVisits = Array.isArray(wizardResult.created_visits) ? wizardResult.created_visits : [];
  const firstVisit = createdVisits[0] || {};
  const services = createdVisits.flatMap((visit) =>
    (Array.isArray(visit.services) ? visit.services : [])
      .map((service) => service?.name || service?.code)
      .filter(Boolean)
  );
  const queueNumbers = flattenWizardQueueNumbers(wizardResult.queue_numbers);
  const firstQueueNumber = queueNumbers.find((queueItem) => (
    queueItem?.queue_number !== null &&
    queueItem?.queue_number !== undefined &&
    queueItem?.queue_number !== ''
  ));
  const printTickets = (Array.isArray(wizardResult.print_tickets) ? wizardResult.print_tickets : [])
    .map((ticket, index) => {
      if (!ticket || typeof ticket !== 'object') return null;
      const queueNumber = ticket.queue_number ??
        ticket.number ??
        ticket.ticket_number ??
        queueNumbers[index]?.queue_number ??
        queueNumbers[index]?.number ??
        null;
      if (queueNumber === null || queueNumber === undefined || queueNumber === '') return null;
      return {
        ...ticket,
        queue_number: queueNumber,
      };
    })
    .filter(Boolean);
  const totalAmount = Number(wizardResult.total_amount ?? 0);

  return {
    id: visitIds[0],
    canonical_record_id: visitIds[0],
    record_kind: 'visit',
    visit_id: visitIds[0],
    visit_ids: visitIds,
    grouped_record_refs: visitIds.map((visitId) => ({ record_kind: 'visit', record_id: Number(visitId) })),
    available_actions: ['mark_paid', 'print_ticket'],
    can_mark_paid: totalAmount > 0,
    can_print_ticket: true,
    invoice_id: wizardResult.invoice_id ?? null,
    patient_fio: firstVisit.patient_name || 'Пациент',
    services,
    queue_number: firstQueueNumber?.queue_number ?? null,
    number: firstQueueNumber?.queue_number ?? null,
    cost: totalAmount,
    payment_amount: totalAmount,
    payment_status: totalAmount > 0 ? 'pending' : 'paid',
    payment_type: null,
    queue_numbers: queueNumbers,
    print_tickets: printTickets,
    created_visits: createdVisits,
  };
};

// ───────────────────────────────────────────────────────────
// Multi-record aggregate row helpers
// ───────────────────────────────────────────────────────────

const hasMultipleRecordRefs = (value: unknown) => Array.isArray(value) && value.filter(Boolean).length > 1;

export const isMultiRecordAggregateRow = (row: Record<string, unknown>) => (
  hasMultipleRecordRefs(row?.grouped_record_refs) ||
  hasMultipleRecordRefs(row?.grouped_records) ||
  hasMultipleRecordRefs(row?.aggregated_ids)
);
