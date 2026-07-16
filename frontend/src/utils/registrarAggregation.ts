// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { parseRegistrarTimestamp } from './dateUtils';

export const normalizeRegistrationMode = (value) => {
  const normalized = String(value || 'none').toLowerCase();
  return ['none', 'repeat', 'benefit', 'all_free'].includes(normalized) ? normalized : 'none';
};

export const normalizePaymentStatus = (value) => String(value || 'pending').toLowerCase() === 'paid' ? 'paid' : 'pending';

export const getRecordAmount = (appointment) => {
  const amount = Number(appointment?.cost ?? 0);
  return Number.isFinite(amount) ? amount : 0;
};

/**
 * PR-11: Unified time-field adaptation for registrar/doctor/specialty panels.
 *
 * Extracts the 6 time-related fields that EnhancedAppointmentsTable's
 * getRegistrarTimestampDisplay() needs to render "Очередь" / "Создано" +
 * "Изменено" indicator correctly.
 *
 * Before PR-11, only RegistrarPanel.adaptEntry passed these through.
 * Cardio/Derma/Dental panels dropped them, causing:
 *   - "Очередь" label never showed (fell back to "Создано")
 *   - "Изменено" indicator never rendered after services added
 *
 * Usage:
 *   import { adaptTimeFields } from '../utils/registrarAggregation';
 *   const row = { ...otherFields, ...adaptTimeFields(entry, data) };
 *
 * @param {Object} entry - backend queue entry (from /registrar/queues/today)
 * @param {Object} [data] - top-level response (for timezone fallback)
 * @returns {Object} { created_at, queue_time, updated_at, last_changed_at, display_time_kind, timezone }
 */
export const adaptTimeFields = (entry, data) => {
  const fullEntry = entry?.data || entry || {};
  const sourceEntry = entry || {};

  const createdAt = fullEntry.created_at || sourceEntry.created_at || null;
  const hasQueueTime = Boolean(fullEntry.queue_time || sourceEntry.queue_time);
  const queueTime = fullEntry.queue_time || sourceEntry.queue_time || createdAt;

  return {
    created_at: createdAt,
    queue_time: queueTime,
    updated_at: fullEntry.updated_at || fullEntry.last_changed_at || sourceEntry.updated_at || sourceEntry.last_changed_at || null,
    last_changed_at: fullEntry.last_changed_at || fullEntry.updated_at || sourceEntry.last_changed_at || sourceEntry.updated_at || null,
    display_time_kind: fullEntry.display_time_kind || sourceEntry.display_time_kind || (hasQueueTime ? 'queue_time' : 'created_at'),
    timezone: fullEntry.timezone || sourceEntry.timezone || data?.timezone || 'Asia/Tashkent',
  };
};

export const getRegistrarPresentationSortTime = (record) => {
  const value = record?.queue_time || record?.created_at || null;
  if (!value) return 0;
  const date = parseRegistrarTimestamp(value);
  return !date || Number.isNaN(date.getTime()) ? 0 : date.getTime();
};

export const compareRegistrarPresentationOrder = (a, b) => {
  const aTime = getRegistrarPresentationSortTime(a);
  const bTime = getRegistrarPresentationSortTime(b);
  if (aTime === bTime) {
    return Number(a?.id || 0) - Number(b?.id || 0);
  }
  return aTime - bTime;
};

export const sortRegistrarRowsForPresentation = (records = []) => (
  [...records].sort(compareRegistrarPresentationOrder)
);

const normalizeRecordKind = (appointment) => String(
  appointment?.record_kind ?? appointment?.source_kind ?? appointment?.record_type ?? appointment?.type ?? ''
).trim().toLowerCase();

const pickCanonicalVisitId = (appointment) => appointment?.visit_id ?? appointment?.visitId ?? null;

const pickCanonicalAppointmentId = (appointment) => appointment?.appointment_id ?? null;

const hasQueueIdentityValue = (value) => value !== null && value !== undefined && value !== '';

const pickQueueNumberEntryId = (queueNumber) => {
  if (!queueNumber || typeof queueNumber !== 'object') return null;

  const explicitQueueEntryId = queueNumber.original_queue_id ??
    queueNumber.queue_entry_id ??
    queueNumber.doctor_queue_entry_id ??
    null;
  if (hasQueueIdentityValue(explicitQueueEntryId)) {
    return explicitQueueEntryId;
  }

  if (hasQueueIdentityValue(queueNumber.queue_id)) {
    return null;
  }

  return hasQueueIdentityValue(queueNumber.id) ? queueNumber.id : null;
};

const pickCanonicalQueueEntryId = (appointment) => {
  const explicitQueueEntryId = appointment?.queue_entry_id ??
    appointment?.original_queue_id ??
    appointment?.doctor_queue_entry_id ??
    null;
  if (hasQueueIdentityValue(explicitQueueEntryId)) {
    return explicitQueueEntryId;
  }

  return pickQueueNumberEntryId(appointment?.queue_numbers?.[0]);
};

const pickOnlineQueueRecordId = (appointment) => {
  const queueEntryId = pickCanonicalQueueEntryId(appointment);
  if (hasQueueIdentityValue(queueEntryId)) {
    return queueEntryId;
  }
  if (
    hasQueueIdentityValue(appointment?.queue_id) ||
    hasQueueIdentityValue(appointment?.queue_numbers?.[0]?.queue_id)
  ) {
    return null;
  }
  return appointment?.id;
};

const buildRecordRef = (appointment) => {
  const recordKind = normalizeRecordKind(appointment);
  const recordId = appointment?.canonical_record_id
    ?? (recordKind === 'visit' ? appointment?.visit_id : null)
    ?? (recordKind === 'online_queue' ? pickOnlineQueueRecordId(appointment) : null)
    ?? (recordKind === 'appointment' ? appointment?.appointment_id : null)
    ?? (recordKind === 'online_queue' ? null : appointment?.id);

  if (!['visit', 'online_queue', 'appointment'].includes(recordKind)) return null;
  const numericId = Number(recordId);
  if (!Number.isFinite(numericId) || numericId <= 0) return null;
  return { record_kind: recordKind, record_id: numericId };
};

const buildPatientGroupKey = (appointment, index = 0) => {
  const patientId = appointment?.patient_id;
  if (patientId !== null && patientId !== undefined && String(patientId).trim() !== '') {
    return `patient:${patientId}`;
  }

  const fio = String(appointment?.patient_fio || '').trim().toLowerCase();
  const phone = String(appointment?.patient_phone || appointment?.phone || '').replace(/\D/g, '');
  const birth = String(
    appointment?.patient_birth_date ||
    appointment?.birth_date ||
    appointment?.patient_birth_year ||
    ''
  ).trim();
  if (fio || phone || birth) {
    return `identity:${fio}|${phone}|${birth}`;
  }

  const recordRef = buildRecordRef(appointment);
  if (recordRef) {
    return `record:${recordRef.record_kind}:${recordRef.record_id}`;
  }

  return `row:${appointment?.id ?? index}`;
};

const pickPatientGender = (appointment) => (
  appointment?.patient_gender ??
  appointment?.patient_sex ??
  appointment?.gender ??
  appointment?.sex ??
  null
);

export const aggregatePatientsForAllDepartments = (appointments = []) => {
  const patientGroups = {};

  const toTime = (value) => {
    if (!value) return null;
    const date = parseRegistrarTimestamp(value);
    return !date || Number.isNaN(date.getTime()) ? null : date.getTime();
  };

  const pickEarlierTimestamp = (currentValue, nextValue) => {
    if (!currentValue) return nextValue || currentValue;
    if (!nextValue) return currentValue;

    const currentTime = toTime(currentValue);
    const nextTime = toTime(nextValue);

    if (currentTime === null) return nextValue;
    if (nextTime === null) return currentValue;

    return nextTime < currentTime ? nextValue : currentValue;
  };

  const pickLaterTimestamp = (currentValue, nextValue) => {
    if (!currentValue) return nextValue || currentValue;
    if (!nextValue) return currentValue;

    const currentTime = toTime(currentValue);
    const nextTime = toTime(nextValue);

    if (currentTime === null) return nextValue;
    if (nextTime === null) return currentValue;

    return nextTime > currentTime ? nextValue : currentValue;
  };

  appointments.forEach((appointment, index) => {
    const patientKey = buildPatientGroupKey(appointment, index);
    const normalizedDiscountMode = normalizeRegistrationMode(appointment.discount_mode);
    const normalizedPayment = normalizePaymentStatus(appointment.payment_status);
    const appointmentCost = getRecordAmount(appointment);
    const recordRef = buildRecordRef(appointment);
    const patientGender = pickPatientGender(appointment);

    if (!patientGroups[patientKey]) {
      const initialVisitId = pickCanonicalVisitId(appointment);
      const initialAppointmentId = pickCanonicalAppointmentId(appointment);
      const initialQueueEntryId = pickCanonicalQueueEntryId(appointment);

      patientGroups[patientKey] = {
        id: appointment.id,
        visit_id: initialVisitId,
        appointment_id: initialAppointmentId,
        queue_entry_id: initialQueueEntryId,
        visit_ids: initialVisitId !== null && initialVisitId !== undefined ? [initialVisitId] : [],
        appointment_ids: initialAppointmentId !== null && initialAppointmentId !== undefined ? [initialAppointmentId] : [],
        queue_entry_ids: initialQueueEntryId !== null && initialQueueEntryId !== undefined ? [initialQueueEntryId] : [],
        patient_id: appointment.patient_id,
        patient_fio: appointment.patient_fio,
        patient_birth_year: appointment.patient_birth_year,
        patient_gender: patientGender,
        gender: patientGender,
        sex: patientGender,
        patient_phone: appointment.patient_phone,
        address: appointment.address,
        visit_type: appointment.visit_type ?? null,
        payment_type: appointment.payment_type ?? null,
        payment_status: normalizedPayment,
        cost: 0,
        status: appointment.status,
        date: appointment.date,
        appointment_date: appointment.appointment_date,
        created_at: appointment.created_at,
        queue_time: appointment.queue_time,
        updated_at: appointment.updated_at || appointment.last_changed_at || appointment.created_at,
        last_changed_at: appointment.last_changed_at || appointment.updated_at || appointment.created_at,
        display_time_kind: appointment.display_time_kind || (appointment.queue_time ? 'queue_time' : 'created_at'),
        timezone: appointment.timezone || 'Asia/Tashkent',
        services: [],
        service_details: Array.isArray(appointment.service_details) ? [...appointment.service_details] : [],
        departments: new Set(),
        doctors: new Set(),
        department: appointment.department,
        doctor_specialty: appointment.doctor_specialty,
        queue_numbers: Array.isArray(appointment.queue_numbers) ? [...appointment.queue_numbers] : [],
        confirmation_status: appointment.confirmation_status,
        confirmed_at: appointment.confirmed_at,
        confirmed_by: appointment.confirmed_by,
        record_type: appointment.record_type,
        source: appointment.source,
        discount_mode: normalizedDiscountMode,
        approval_status: appointment.approval_status,
        grouped_discount_modes: [],
        grouped_payment_statuses: [],
        grouped_payment_types: [],
        grouped_records: [],
        grouped_record_refs: [],
        aggregated_ids: appointment.aggregated_ids ? [...appointment.aggregated_ids] : [appointment.id],
      };
    } else {
      const newIds = appointment.aggregated_ids || [appointment.id];
      patientGroups[patientKey].aggregated_ids.push(...newIds);
      patientGroups[patientKey].aggregated_ids = [...new Set(patientGroups[patientKey].aggregated_ids)];

      const nextVisitId = pickCanonicalVisitId(appointment);
      const nextAppointmentId = pickCanonicalAppointmentId(appointment);
      const nextQueueEntryId = pickCanonicalQueueEntryId(appointment);

      if (nextVisitId !== null && nextVisitId !== undefined) {
        patientGroups[patientKey].visit_ids.push(nextVisitId);
        patientGroups[patientKey].visit_ids = [...new Set(patientGroups[patientKey].visit_ids)];
        if (!patientGroups[patientKey].visit_id) {
          patientGroups[patientKey].visit_id = nextVisitId;
        }
      }

      if (nextAppointmentId !== null && nextAppointmentId !== undefined) {
        patientGroups[patientKey].appointment_ids.push(nextAppointmentId);
        patientGroups[patientKey].appointment_ids = [...new Set(patientGroups[patientKey].appointment_ids)];
        if (!patientGroups[patientKey].appointment_id) {
          patientGroups[patientKey].appointment_id = nextAppointmentId;
        }
      }

      if (nextQueueEntryId !== null && nextQueueEntryId !== undefined) {
        patientGroups[patientKey].queue_entry_ids.push(nextQueueEntryId);
        patientGroups[patientKey].queue_entry_ids = [...new Set(patientGroups[patientKey].queue_entry_ids)];
        if (!patientGroups[patientKey].queue_entry_id) {
          patientGroups[patientKey].queue_entry_id = nextQueueEntryId;
        }
      }

      if (!patientGroups[patientKey].patient_gender && patientGender) {
        patientGroups[patientKey].patient_gender = patientGender;
        patientGroups[patientKey].gender = patientGender;
        patientGroups[patientKey].sex = patientGender;
      }

      patientGroups[patientKey].queue_time = pickEarlierTimestamp(
        patientGroups[patientKey].queue_time,
        appointment.queue_time,
      );
      patientGroups[patientKey].updated_at = pickLaterTimestamp(
        patientGroups[patientKey].updated_at,
        appointment.updated_at || appointment.last_changed_at,
      );
      patientGroups[patientKey].last_changed_at = pickLaterTimestamp(
        patientGroups[patientKey].last_changed_at,
        appointment.last_changed_at || appointment.updated_at,
      );

      if (Array.isArray(appointment.queue_numbers)) {
        const existingQueueIds = new Set(
          (patientGroups[patientKey].queue_numbers || []).map((qn) => qn.id?.toString() || `${qn.queue_tag}_${qn.service_id}`),
        );

        appointment.queue_numbers.forEach((qn) => {
          const queueId = qn.id?.toString() || `${qn.queue_tag}_${qn.service_id}`;
          if (!existingQueueIds.has(queueId)) {
            patientGroups[patientKey].queue_numbers.push(qn);
            existingQueueIds.add(queueId);
          }
        });
      }

      const isQRSource = (src) => src === 'online';
      const currentIsQR = isQRSource(appointment.source);
      const aggregatedIsQR = isQRSource(patientGroups[patientKey].source);

      if (currentIsQR && !aggregatedIsQR) {
        patientGroups[patientKey].source = appointment.source;
        patientGroups[patientKey].record_type = appointment.record_type || patientGroups[patientKey].record_type;
      }
    }

    patientGroups[patientKey].cost += appointmentCost;
    patientGroups[patientKey].grouped_discount_modes.push(normalizedDiscountMode);
    patientGroups[patientKey].grouped_payment_statuses.push(normalizedPayment);
    if (appointment.payment_type) {
      patientGroups[patientKey].grouped_payment_types.push(appointment.payment_type);
    }
    if (recordRef) {
      const refKey = `${recordRef.record_kind}:${recordRef.record_id}`;
      const existingRefKeys = new Set(
        patientGroups[patientKey].grouped_record_refs.map((ref) => `${ref.record_kind}:${ref.record_id}`),
      );
      if (!existingRefKeys.has(refKey)) {
        patientGroups[patientKey].grouped_record_refs.push(recordRef);
      }
    }
    patientGroups[patientKey].grouped_records.push({
      record_ref: recordRef,
      available_actions: Array.isArray(appointment.available_actions) ? [...appointment.available_actions] : [],
      can_mark_paid: Boolean(appointment.can_mark_paid),
      can_start_visit: Boolean(appointment.can_start_visit),
      can_cancel: Boolean(appointment.can_cancel),
      can_print_ticket: Boolean(appointment.can_print_ticket),
      can_complete: Boolean(appointment.can_complete),
      discount_mode: normalizedDiscountMode,
      approval_status: appointment.approval_status,
      payment_status: normalizedPayment,
      payment_type: appointment.payment_type || null,
      cost: appointmentCost,
    });

    if (Array.isArray(appointment.services)) {
      appointment.services.forEach((service) => {
        if (!patientGroups[patientKey].services.includes(service)) {
          patientGroups[patientKey].services.push(service);
        }
      });
    }

    if (Array.isArray(appointment.service_codes)) {
      if (!patientGroups[patientKey].service_codes) {
        patientGroups[patientKey].service_codes = [];
      }
      appointment.service_codes.forEach((code) => {
        if (!patientGroups[patientKey].service_codes.includes(code)) {
          patientGroups[patientKey].service_codes.push(code);
        }
      });
    }

    if (Array.isArray(appointment.service_details)) {
      if (!patientGroups[patientKey].service_details) {
        patientGroups[patientKey].service_details = [];
      }
      const existingServiceDetailKeys = new Set(
        patientGroups[patientKey].service_details.map((serviceDetail) => (
          serviceDetail?.service_id ??
          serviceDetail?.id ??
          serviceDetail?.service_code ??
          serviceDetail?.code ??
          serviceDetail?.service_name ??
          serviceDetail?.name
        )).filter((value) => value !== null && value !== undefined).map(String),
      );

      appointment.service_details.forEach((serviceDetail) => {
        if (!serviceDetail) return;
        const serviceDetailKey = serviceDetail.service_id ??
          serviceDetail.id ??
          serviceDetail.service_code ??
          serviceDetail.code ??
          serviceDetail.service_name ??
          serviceDetail.name ??
          null;
        if (serviceDetailKey === null || serviceDetailKey === undefined || existingServiceDetailKeys.has(String(serviceDetailKey))) {
          return;
        }
        patientGroups[patientKey].service_details.push(serviceDetail);
        existingServiceDetailKeys.add(String(serviceDetailKey));
      });
    }

    if (appointment.department) {
      patientGroups[patientKey].departments.add(appointment.department);
    }

    if (appointment.doctor_specialty) {
      patientGroups[patientKey].doctors.add(appointment.doctor_specialty);
    }
  });

  return Object.values(patientGroups).map((group) => {
    const records = group.grouped_records || [];
    const uniqueRegistrationModes = [...new Set((group.grouped_discount_modes || []).filter(Boolean))];
    const uniquePaymentStatuses = [...new Set((group.grouped_payment_statuses || []).filter(Boolean))];
    const uniquePaymentTypes = [...new Set((group.grouped_payment_types || []).filter(Boolean))];

    const allApprovedZeroCostRegistrations = records.length > 0 && records.every((record) => (
      record.cost <= 0 &&
      (
        record.discount_mode === 'repeat' ||
        record.discount_mode === 'benefit' ||
        (record.discount_mode === 'all_free' && record.approval_status === 'approved')
      )
    ));

    const allPendingAllFree = records.length > 0 && records.every(
      (record) => record.discount_mode === 'all_free' && record.approval_status !== 'approved',
    );
    const allPaid = records.length > 0 && records.every((record) => record.payment_status === 'paid');
    const allUnpaidMonetary = records.length > 0 && records.every((record) => (
      record.cost > 0 &&
      record.payment_status !== 'paid' &&
      record.discount_mode !== 'all_free'
    ));
    const hasMixedPaymentState = uniquePaymentStatuses.length > 1;
    const hasMixedPaymentMethod = uniquePaymentTypes.length > 1;

    let aggregatePaymentType = null;
    if (allPendingAllFree) {
      aggregatePaymentType = 'approval_pending';
    } else if (allApprovedZeroCostRegistrations && Number(group.cost) <= 0) {
      aggregatePaymentType = 'free';
    } else if (hasMixedPaymentState || hasMixedPaymentMethod) {
      aggregatePaymentType = 'mixed_payment';
    } else if (allPaid && uniquePaymentTypes.length === 1) {
      aggregatePaymentType = uniquePaymentTypes[0];
    } else if (allPaid) {
      aggregatePaymentType = 'unknown_payment';
    } else if (allUnpaidMonetary) {
      aggregatePaymentType = 'pending_payment';
    } else {
      aggregatePaymentType = 'mixed_payment';
    }

    return {
      ...group,
      visit_type: uniqueRegistrationModes.length === 1 ? group.visit_type : 'mixed',
      discount_mode: uniqueRegistrationModes.length === 1 ? uniqueRegistrationModes[0] : 'mixed',
      payment_type: aggregatePaymentType,
      payment_status: uniquePaymentStatuses.length === 1 ? uniquePaymentStatuses[0] : 'mixed',
      cost: Number(group.cost || 0),
      cost_display: Number(group.cost || 0) <= 0 ? 'free' : null,
    };
  });
};
